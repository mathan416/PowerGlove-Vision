# Project: PowerGlove Vision
# File: tests/test_gesture.py
# Purpose: Verify calibration, hysteresis, safety release, menu poses, and supported gesture profiles.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Verified Program I throttle, brake, steering, turbo, and weapons.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify calibration, hysteresis, safety release, menu poses, and supported gesture profiles."""

import unittest

from powerglove_vision.gesture import GestureConfig, GestureEngine
from powerglove_vision.model import HandObservation


def hand(t: float, **changes) -> HandObservation:
    values = dict(
        timestamp=t,
        detected=True,
        confidence=0.95,
        palm_x=0.5,
        palm_y=0.5,
        palm_scale=0.2,
        roll=0.0,
    )
    values.update(changes)
    return HandObservation(**values)


def calibrated_engine(profile="bad_street_brawler") -> GestureEngine:
    engine = GestureEngine(profile, GestureConfig(loss_release_ms=100), calibration_frames=3)
    for t in (0.00, 0.03, 0.06):
        engine.update(hand(t))
    assert engine.calibrated
    return engine


class GestureTests(unittest.TestCase):
    def test_calibration_suppresses_output(self):
        engine = GestureEngine("bad_street_brawler", calibration_frames=3)
        state = engine.update(hand(0.0, palm_x=0.8))
        self.assertFalse(state.calibrated)
        self.assertFalse(any(state.dpad.values()))

    def test_direction_uses_hysteresis(self):
        engine = calibrated_engine()
        self.assertTrue(engine.update(hand(0.1, palm_x=0.60)).dpad["right"])
        self.assertTrue(engine.update(hand(0.2, palm_x=0.56)).dpad["right"])
        self.assertFalse(engine.update(hand(0.3, palm_x=0.53)).dpad["right"])

    def test_middle_finger_is_a_plus_b(self):
        state = calibrated_engine().update(hand(0.1, middle_curl=0.9))
        self.assertTrue(state.buttons["a"])
        self.assertTrue(state.buttons["b"])

    def test_push_is_edge_triggered(self):
        engine = calibrated_engine()
        first = engine.update(hand(0.1, palm_scale=0.28))
        held = engine.update(hand(0.2, palm_scale=0.28))
        self.assertEqual(first.events, ["glove_zap"])
        self.assertEqual(held.events, [])
        self.assertTrue(engine.push_feedback(hand(.2, palm_scale=.28))["active"])
        self.assertFalse(engine.push_feedback(HandObservation(.3, False))["active"])
        engine.begin_calibration()
        self.assertFalse(engine.push_feedback(hand(.4, palm_scale=.28))["active"])

    def test_tracking_loss_releases_controls(self):
        engine = calibrated_engine()
        engine.update(hand(0.1, palm_x=0.62))
        state = engine.update(HandObservation(timestamp=0.25, detected=False))
        self.assertFalse(any(state.dpad.values()))
        self.assertFalse(state.detected)

    def test_brief_tracking_dropout_does_not_chatter(self):
        engine = calibrated_engine()
        engine.update(hand(0.10, palm_x=0.62))
        state = engine.update(HandObservation(timestamp=0.15, detected=False))
        self.assertTrue(state.dpad["right"])
        self.assertFalse(state.detected)

    def test_super_glove_preserves_analogue_and_fingers(self):
        engine = calibrated_engine("super_glove_ball")
        state = engine.update(hand(0.1, palm_x=0.58, ring_curl=0.8))
        self.assertGreater(state.axes["x"], 0)
        self.assertEqual(state.fingers["ring"], 2)

    def test_all_cartridge_free_programs_are_available(self):
        for letter in "abcdefghi":
            with self.subTest(program=letter):
                engine = calibrated_engine(f"program_{letter}")
                state = engine.update(hand(0.1, palm_x=0.62, index_curl=0.9))
                self.assertEqual(state.profile, f"program_{letter}")

    def test_program_d_reverses_directions(self):
        state = calibrated_engine("program_d").update(hand(0.1, palm_x=0.62))
        self.assertTrue(state.dpad["left"])
        self.assertFalse(state.dpad["right"])

    def test_program_b_pulses_joust_flap(self):
        state = calibrated_engine("program_b").update(hand(0.15, index_curl=0.9))
        self.assertTrue(state.buttons["a"])

    def test_program_i_maps_driving_controls_to_the_nes_pad(self):
        engine = calibrated_engine("program_i")
        throttle = engine.update(hand(0.10, index_curl=0.9))
        self.assertTrue(throttle.dpad["up"])
        self.assertFalse(throttle.buttons["a"])

        turbo = engine.update(hand(0.20, palm_scale=0.30))
        self.assertTrue(turbo.dpad["up"])
        self.assertTrue(turbo.buttons["a"])

        weapons = engine.update(hand(0.30, thumb_curl=0.9))
        self.assertTrue(weapons.buttons["b"])

        brake = engine.update(hand(0.40, palm_y=0.62))
        self.assertTrue(brake.dpad["down"])

        steering = engine.update(hand(0.50, roll=-1.2))
        self.assertTrue(steering.dpad["left"])

    def test_held_v_sign_pulses_start_without_attacking(self):
        engine = calibrated_engine()
        pose = dict(index_curl=0.1, middle_curl=0.1, ring_curl=0.9, pinky_curl=0.9)
        forming = engine.update(hand(0.10, **pose))
        pulse = engine.update(hand(0.85, **pose))
        held = engine.update(hand(1.10, **pose))
        self.assertFalse(forming.buttons["start"])
        self.assertTrue(pulse.buttons["start"])
        self.assertFalse(pulse.buttons["a"])
        self.assertFalse(held.buttons["start"])
        self.assertEqual(engine.menu_feedback()["pose"], "start")
        self.assertTrue(engine.menu_feedback()["recognized"])
        engine.update(hand(1.5))
        self.assertIsNone(engine.menu_feedback()["pose"])

    def test_held_thumbs_up_pulses_select_without_attacking(self):
        engine = calibrated_engine()
        pose = dict(thumb_curl=0.1, index_curl=0.9, middle_curl=0.9, ring_curl=0.9, pinky_curl=0.9)
        engine.update(hand(0.10, **pose))
        pulse = engine.update(hand(0.85, **pose))
        self.assertTrue(pulse.buttons["select"])
        self.assertFalse(pulse.buttons["a"])
        self.assertFalse(pulse.buttons["b"])
        engine.update(hand(1.10, **pose))
        self.assertEqual(engine.menu_feedback()["pose"], "select")
        self.assertTrue(engine.menu_feedback()["recognized"])


if __name__ == "__main__":
    unittest.main()
