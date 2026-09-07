# Project: PowerGlove Vision
# File: tests/test_motion.py
# Purpose: Verify asynchronous motion correction, freshness, and native control release.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Cover experimental palm flow with synthetic images and blocked inference.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise real optical flow where available and controller safety everywhere."""

from dataclasses import replace
import threading
import unittest

from powerglove_vision.gesture import GestureEngine
from powerglove_vision.model import Calibration, HandObservation
from powerglove_vision.tracker import TrackingResult
from powerglove_vision.vision_app import build_parser

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = np = None


class NativeMotionTests(unittest.TestCase):
    def setUp(self):
        self.engine = GestureEngine('super_glove_ball', calibration=Calibration(.5, .5, .2, 0))
        self.pose = HandObservation(10, True, .95, .5, .5, .2)

    def test_opt_in(self):
        args = ['--receiver', 'test', '--token', 'x' * 16]
        self.assertFalse(build_parser().parse_args(args).motion_tracking)
        self.assertTrue(build_parser().parse_args(args + ['--motion-tracking']).motion_tracking)

    def test_medium_step_override_passes_through_but_small_step_is_smoothed(self):
        for distance, immediate in ((.05, True), (.005, False), (-.05, True)):
            with self.subTest(distance=distance):
                self.setUp()
                self.engine.config = replace(self.engine.config, motion_coordinate_boost=8.)
                self.engine.update_native_motion(self.pose, self.pose)
                pose = replace(self.pose, timestamp=10+1/60, palm_x=.5+distance)
                self.engine.update_native_motion(pose, pose)
                filtered = self.engine._filtered_palm_x
                if immediate:
                    self.assertAlmostEqual(filtered, pose.palm_x)
                else:
                    self.assertGreater(filtered, .5)
                    self.assertLess(filtered, pose.palm_x)

    def test_motion_boost_override_does_not_change_synchronous_path(self):
        other = GestureEngine('super_glove_ball', calibration=self.engine.calibration)
        other.config = replace(other.config, motion_coordinate_boost=8.)
        for i, x in enumerate((.5, .55, .54, .45)):
            pose = replace(self.pose, timestamp=10+i/60, palm_x=x)
            self.assertEqual(self.engine.update(pose).axes, other.update(pose).axes)

    def test_experimental_motion_max_can_extrapolate_above_target(self):
        self.engine.config = replace(self.engine.config, motion_coordinate_boost=14.,
                                     motion_coordinate_max=1.15)
        self.engine.update_native_motion(self.pose, self.pose)
        target = replace(self.pose, timestamp=10 + 1/60, palm_x=.55)
        self.engine.update_native_motion(target, target)
        self.assertGreater(self.engine._filtered_palm_x, target.palm_x)
        self.assertLessEqual(self.engine._filtered_palm_x, .5 + 1.15 * .05)

    def test_supervisor_passes_only_explicit_boolean_opt_in(self):
        import runpy
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        worker_command = runpy.run_path(str(root / 'python/main.py'))['worker_command']
        for value in (False, True, 'true', None):
            command = worker_command({'motion_tracking': value}, Path('/tmp/model'))
            self.assertEqual('--motion-tracking' in command, value is True)

    def test_fast_position_does_not_replay_gesture_or_depth_samples(self):
        fist = replace(self.pose, thumb_curl=1, index_curl=1, middle_curl=1, ring_curl=1, pinky_curl=1)
        first = self.engine.update_native_motion(replace(fist, timestamp=10.1), fist)
        history = list(self.engine._depth_history)
        for i in range(1, 6):
            state = self.engine.update_native_motion(replace(fist, timestamp=10.1+i*.016, palm_x=.6))
            self.assertGreater(state.sequence, first.sequence)
            self.assertTrue(state.buttons['closed_hand'])
            self.assertEqual(state.events, [])
        self.assertGreater(state.axes['x'], first.axes['x'])
        self.assertEqual(list(self.engine._depth_history), history)
        self.assertEqual(self.engine._last_seen, fist.timestamp)

    def test_loss_immediately_releases_and_requires_new_gesture(self):
        self.engine.update_native_motion(self.pose, self.pose)
        lost = self.engine.update_native_motion(HandObservation(10.01, False))
        self.assertFalse(lost.detected)
        self.assertFalse(any(lost.buttons.values()))
        self.assertFalse(any(lost.axes.values()))
        self.assertFalse(self.engine.update_native_motion(replace(self.pose, timestamp=10.02)).detected)
        recovered = replace(self.pose, timestamp=10.03)
        self.assertTrue(self.engine.update_native_motion(recovered, recovered).detected)

    def test_delayed_recognition_does_not_rewind_xy_filter(self):
        self.engine.update_native_motion(self.pose, self.pose)
        moved = self.engine.update_native_motion(replace(self.pose, timestamp=10.1, palm_x=.7))
        correction = self.engine.update_native_motion(
            replace(self.pose, timestamp=10.12, palm_x=.7), replace(self.pose, timestamp=10.02))
        self.assertGreaterEqual(correction.axes['x'], moved.axes['x'])

    def test_repeated_motion_cannot_complete_menu_hold(self):
        v_sign = replace(self.pose, thumb_curl=1, ring_curl=1, pinky_curl=1)
        self.engine.update_native_motion(v_sign, v_sign)
        started = self.engine._start_gesture.started_at
        self.assertIsNotNone(started)
        for i in range(10):
            state = self.engine.update_native_motion(replace(v_sign, timestamp=10.1+i*.01))
            self.assertFalse(state.buttons['start'])
        self.assertEqual(self.engine._start_gesture.started_at, started)

    def test_wrong_profile_or_uncalibrated_is_rejected(self):
        for engine in (GestureEngine('super_glove_ball'), GestureEngine('bad_street_brawler')):
            with self.assertRaises(ValueError):
                engine.update_native_motion(self.pose, self.pose)


@unittest.skipIf(cv2 is None, 'optional vision dependencies unavailable')
class OpticalMotionTests(unittest.TestCase):
    def setUp(self):
        from powerglove_vision.motion import MotionTracker, PalmFlow
        self.Flow, self.Tracker = PalmFlow, MotionTracker
        self.gray = np.zeros((240, 320), dtype=np.uint8)
        self.gray[75:160, 115:205] = np.random.default_rng(10).integers(40, 240, (85, 90), dtype=np.uint8)
        self.pose = HandObservation(10, True, .95, .5, .5, .25)
        self.points = [(.36, .32), (.63, .32), (.65, .5), (.63, .66), (.36, .66)]

    def shifted(self, x, y=0):
        return cv2.warpAffine(self.gray, np.float32([[1, 0, x], [0, 1, y]]), (320, 240))

    def test_translation_reversal_and_occlusion(self):
        flow = self.Flow(cv2)
        self.assertTrue(flow.seed(self.gray, self.pose, self.points))
        for x, y in [(4, 3), (8, 6), (4, 3), (0, 0), (-4, -3)]:
            position = flow.advance(self.shifted(x, y))
            self.assertIsNotNone(position)
            self.assertAlmostEqual(position[0], .5 + x/320, delta=.002)
            self.assertAlmostEqual(position[1], .5 + y/240, delta=.002)
        self.assertIsNone(flow.advance(np.zeros_like(self.gray)))

    def test_textureless_palm_is_rejected(self):
        flow = self.Flow(cv2)
        self.assertFalse(flow.seed(np.zeros_like(self.gray), self.pose, self.points))

    def make_tracker(self, mirror=False):
        owner = self
        class SlowTracker:
            backend = 'legacy'
            backend_label = 'test'
            def __init__(self):
                self.cv2, self.mirror = cv2, mirror
                self.entered, self.release = threading.Event(), threading.Event()
                self.closed = False
            def process(self, frame, timestamp=None):
                self.entered.set()
                if not self.release.wait(2):
                    raise RuntimeError('test worker timed out')
                return TrackingResult(replace(owner.pose, timestamp=timestamp), frame,
                                      palm_points=owner.points)
            def close(self):
                self.closed = True
        slow = SlowTracker()
        clock = [10.0]
        tracker = self.Tracker(slow, clock=lambda: clock[0])
        self.addCleanup(tracker.close)
        self.addCleanup(slow.release.set)
        return tracker, slow, clock

    def test_inference_never_blocks_frames_and_correction_uses_source_image(self):
        tracker, slow, clock = self.make_tracker()
        original = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        first = tracker.process(original, timestamp=10, fast=True)
        self.assertFalse(first.observation.detected)
        self.assertTrue(slow.entered.wait(1))
        original[:] = 0  # The worker and correction history must own their pixels.
        clock[0] = 10.04
        result = tracker.process(cv2.cvtColor(self.shifted(4), cv2.COLOR_GRAY2BGR), 10.04, fast=True)
        self.assertFalse(result.observation.detected)
        slow.release.set()
        tracker.pending.result(timeout=2)
        clock[0] = 10.08
        result = tracker.process(cv2.cvtColor(self.shifted(8), cv2.COLOR_GRAY2BGR), 10.08, fast=True)
        self.assertTrue(result.observation.detected)
        self.assertEqual(result.gesture_observation.timestamp, 10)
        self.assertAlmostEqual(result.observation.palm_x, .5+8/320, delta=.002)
        self.assertEqual(result.observation.timestamp, 10.08)
        self.assertEqual(result.diagnostics['motion_correction_steps'], 1,
                         'Correction cost must not grow with intervening frames')

    def test_mirror_tracks_in_screen_coordinates(self):
        tracker, slow, clock = self.make_tracker(mirror=True)
        tracker.process(cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR), 10, fast=True)
        slow.release.set()
        tracker.pending.result(timeout=2)
        clock[0] = 10.08
        result = tracker.process(cv2.cvtColor(self.shifted(8), cv2.COLOR_GRAY2BGR), 10.08, fast=True)
        self.assertTrue(result.observation.detected)
        self.assertAlmostEqual(result.observation.palm_x, .5-8/320, delta=.002)

    def test_next_recognition_starts_before_correction_and_flow_is_downscaled(self):
        tracker, slow, clock = self.make_tracker()
        frame = cv2.resize(cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR), (640, 480))
        tracker.process(frame, 10, fast=True)
        slow.release.set()
        tracker.pending.result(timeout=2)
        slow.release.clear()
        slow.entered.clear()
        seed = tracker.flow.seed
        def checked_seed(gray, observation, points):
            self.assertTrue(slow.entered.wait(1), 'Recognition must overlap correction')
            self.assertEqual(gray.shape, (240, 320))
            return seed(gray, observation, points)
        tracker.flow.seed = checked_seed
        clock[0] = 10.08
        result = tracker.process(frame, 10.08, fast=True)
        self.assertTrue(result.observation.detected)
        self.assertEqual(result.diagnostics['motion_correction_steps'], 1)

    def test_correction_budget_uses_recognition_without_renewing_source_age(self):
        tracker, slow, clock = self.make_tracker()
        frame = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        tracker.process(frame, 10, fast=True)
        clock[0] = 10.02
        tracker.process(frame, 10.02, fast=True)
        slow.release.set()
        tracker.pending.result(timeout=2)
        slow.release.clear()
        advance = tracker.flow.advance
        def expensive(gray):
            clock[0] += .030
            return advance(gray)
        tracker.flow.advance = expensive
        clock[0] = 10.08
        result = tracker.process(frame, 10.08, fast=True)
        self.assertTrue(result.observation.detected)
        self.assertEqual(result.gesture_observation.timestamp, 10)
        self.assertEqual(result.observation.palm_x, .5)
        self.assertIsNone(tracker.flow.points)
        self.assertIsNone(result.diagnostics['motion_failure'])
        self.assertEqual(result.diagnostics['motion_fallback_reason'], 'correction_budget')
        self.assertEqual(result.diagnostics['motion_correction_steps'], 1)

    def test_failed_correction_jumps_to_recognition_then_flow_recovers(self):
        tracker, slow, clock = self.make_tracker()
        frame = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        tracker.process(frame, 10, fast=True)
        slow.release.set()
        tracker.pending.result(timeout=2)
        slow.release.clear()
        tracker.flow.advance = lambda gray: None
        clock[0] = 10.08
        result = tracker.process(frame, 10.08, fast=True)
        self.assertTrue(result.observation.detected)
        self.assertEqual(result.observation.palm_x, .5)
        self.assertEqual(result.diagnostics['motion_fallback_reason'], 'correction_flow_lost')
        self.assertIsNone(tracker.flow.points)
        self.assertEqual(result.motion_trace['recognized_capture_ns'], 10_000_000_000)
        self.assertEqual(result.motion_trace['selected_xy'], [.5, .5])
        self.assertIsNone(result.motion_trace['flow_xy'])
        self.assertFalse(result.motion_trace['flow_accepted'])
        # Next recognition can jump a large distance without inventing a path.
        self.pose = replace(self.pose, palm_x=.8)
        slow.release.set()
        tracker.pending.result(timeout=2)
        slow.release.clear()
        clock[0] = 10.12
        result = tracker.process(frame, 10.12, fast=True)
        self.assertTrue(result.observation.detected)
        self.assertAlmostEqual(result.observation.palm_x, .8, delta=.002)
        self.assertIsNone(result.diagnostics['motion_fallback_reason'])
        clock[0] = 10.14
        shifted = cv2.cvtColor(self.shifted(4), cv2.COLOR_GRAY2BGR)
        result = tracker.process(shifted, 10.14, fast=True)
        self.assertAlmostEqual(result.observation.palm_x, .8 + 4/320, delta=.002)
        self.assertTrue(result.motion_trace['flow_accepted'])
        self.assertFalse(result.motion_trace['recognition_completed'])
        self.assertIsNone(result.motion_trace['recognized_xy'])
        self.assertEqual(result.motion_trace['anchor_capture_ns'], 10_080_000_000)

    def test_fallback_expires_and_rejects_invalid_recognition(self):
        for replacement in (None, replace(self.pose, detected=False),
                            replace(self.pose, confidence=.69)):
            with self.subTest(replacement=replacement):
                tracker, slow, clock = self.make_tracker()
                frame = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
                tracker.process(frame, 10, fast=True)
                slow.release.set()
                tracker.pending.result(timeout=2)
                slow.release.clear()
                tracker.flow.advance = lambda gray: None
                clock[0] = 10.08
                self.assertTrue(tracker.process(frame, 10.08, fast=True).observation.detected)
                if replacement is not None:
                    self.pose = replacement
                    slow.release.set()
                    tracker.pending.result(timeout=2)
                    slow.release.clear()
                    clock[0] = 10.12
                else:
                    clock[0] = 10.251
                result = tracker.process(frame, clock[0], fast=True)
                self.assertFalse(result.observation.detected)
                self.assertIsNone(result.gesture_observation)
                self.pose = replace(self.pose, detected=True, confidence=.95)
                slow.release.set()
                tracker.close()

    def test_correction_cannot_publish_source_that_expires_during_work(self):
        tracker, slow, clock = self.make_tracker()
        frame = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        tracker.process(frame, 10, fast=True)
        slow.release.set()
        tracker.pending.result(timeout=2)
        slow.release.clear()
        def expensive(gray):
            clock[0] += .030
            return None
        tracker.flow.advance = expensive
        clock[0] = 10.24
        result = tracker.process(frame, 10.24, fast=True)
        self.assertFalse(result.observation.detected)
        self.assertIsNone(result.gesture_observation)
        self.assertEqual(result.diagnostics['motion_failure'], 'gesture_stale')
        self.assertIsNone(result.motion_trace['selected_xy'])
        self.assertIsNone(result.motion_trace['anchor_capture_ns'])

    def test_invalid_recognition_cannot_be_used_as_textureless_fallback(self):
        tracker, slow, clock = self.make_tracker()
        self.pose = replace(self.pose, detected=False)
        frame = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        tracker.process(frame, 10, fast=True)
        slow.release.set()
        tracker.pending.result(timeout=2)
        clock[0] = 10.08
        result = tracker.process(frame, 10.08, fast=True)
        self.assertFalse(result.observation.detected)
        self.assertEqual(result.diagnostics['motion_failure'], 'recognition_invalid')

    def test_active_flow_expires_while_next_inference_is_blocked(self):
        tracker, slow, clock = self.make_tracker()
        frame = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        tracker.process(frame, 10, fast=True)
        slow.release.set()
        tracker.pending.result(timeout=2)
        slow.release.clear()
        clock[0] = 10.08
        self.assertTrue(tracker.process(frame, 10.08, fast=True).observation.detected)
        clock[0] = 10.24
        self.assertTrue(tracker.process(frame, 10.24, fast=True).observation.detected)
        clock[0] = 10.251
        result = tracker.process(frame, 10.251, fast=True)
        self.assertFalse(result.observation.detected)
        self.assertIsNone(result.gesture_observation)

    def test_stale_gesture_releases_despite_fresh_camera(self):
        tracker, slow, clock = self.make_tracker()
        frame = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        tracker.process(frame, 10, fast=True)
        slow.release.set()
        tracker.pending.result(timeout=2)
        clock[0] = 10.30
        result = tracker.process(frame, 10.30, fast=True)
        self.assertFalse(result.observation.detected)
        self.assertIsNone(result.gesture_observation)

    def test_worker_exception_returns_neutral_and_can_recover(self):
        tracker, slow, clock = self.make_tracker()
        def broken(*args, **kwargs):
            raise ValueError('failed inference')
        slow.process = broken
        frame = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        tracker.process(frame, 10, fast=True)
        with self.assertRaises(ValueError):
            tracker.pending.result(timeout=2)
        clock[0] = 10.04
        result = tracker.process(frame, 10.04, fast=True)
        self.assertFalse(result.observation.detected)
        self.assertEqual(result.diagnostics['recognition_error'], 'ValueError')

    def test_mode_exit_and_close_finish_worker_before_tracker_close(self):
        tracker, slow, clock = self.make_tracker()
        frame = cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR)
        tracker.process(frame, 10, fast=True)
        slow.release.set()
        result = tracker.process(frame, 10.1, fast=False)
        self.assertFalse(result.motion_only)
        self.assertFalse(tracker.history)
        tracker.close()
        self.assertTrue(slow.closed)
