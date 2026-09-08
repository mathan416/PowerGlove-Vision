# Project: PowerGlove Vision
# File: tests/test_motion.py
# Purpose: Verify asynchronous motion correction, freshness, and native control release.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Cover MediaPipe cadence smoothing and saturated jitter fallback.
#   2026-09-07 - Cover MediaPipe-first native routing and preview scaling.
#   2026-09-06 - Cover experimental palm flow with synthetic images and blocked inference.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise real optical flow where available and controller safety everywhere."""

from dataclasses import replace
import threading
import unittest
from unittest import mock

from powerglove_vision.gesture import GestureEngine
from powerglove_vision.model import Calibration, HandObservation
from powerglove_vision.tracker import TrackingResult
from powerglove_vision.vision_app import (
    _native_trace_fields, _native_xy_active, _native_xy_source,
    _update_controller_state, build_parser,
)

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
        self.assertEqual(build_parser().parse_args(args).native_xy_mode, 'latest')
        self.assertEqual(
            build_parser().parse_args(args + ['--native-xy-mode', 'latest']).native_xy_mode,
            'latest',
        )

    def test_mediapipe_native_route_defaults_to_latest_coordinate(self):
        first = TrackingResult(self.pose, object())
        state, source = _update_controller_state(self.engine, first, True)
        self.assertEqual(source, 'mediapipe')
        self.assertTrue(state.detected)
        target = replace(self.pose, timestamp=10 + 1/60, palm_x=.505)
        state, source = _update_controller_state(
            self.engine, TrackingResult(target, object()), True
        )
        self.assertEqual(source, 'mediapipe')
        self.assertEqual(self.engine._filtered_palm_x, target.palm_x)

    def test_mediapipe_cadence_keeps_slow_motion_smoothed(self):
        self.engine.update_native_motion(self.pose, self.pose)
        target = replace(self.pose, timestamp=10.1, palm_x=.51)
        self.engine.update_native_motion(target, target)
        self.assertGreater(self.engine._filtered_palm_x, self.pose.palm_x)
        self.assertLess(self.engine._filtered_palm_x, target.palm_x)

    def test_saturated_calibration_jitter_uses_safe_floor(self):
        calibration = Calibration(.5, .5, .06, 0, noise_x=1.0, noise_y=1.0)
        engine = GestureEngine('super_glove_ball', calibration=calibration)
        engine.update_native_motion(self.pose, self.pose)
        target = replace(self.pose, timestamp=10.1, palm_x=.51)
        engine.update_native_motion(target, target)
        self.assertGreater(engine._filtered_palm_x, self.pose.palm_x)
        self.assertLess(engine._filtered_palm_x, target.palm_x)

    def test_native_source_and_activation_are_explicit(self):
        self.assertTrue(_native_xy_active(self.engine, False, False, False))
        self.assertFalse(_native_xy_active(self.engine, True, False, False))
        self.assertFalse(_native_xy_active(self.engine, False, True, False))
        self.assertFalse(_native_xy_active(self.engine, False, False, True))
        self.assertEqual(_native_xy_source(True), 'mediapipe')
        self.assertEqual(_native_xy_source(False), 'inactive')

    def test_latest_coordinate_lane_is_unsmoothed(self):
        self.engine.update_native_motion(self.pose, self.pose, bounded=False)
        target = replace(self.pose, timestamp=10.1, palm_x=.507, palm_y=.492)
        state, source = _update_controller_state(
            self.engine, TrackingResult(target, object()), True, 'latest'
        )
        self.assertEqual(source, 'mediapipe')
        self.assertEqual(self.engine._filtered_palm_x, target.palm_x)
        self.assertEqual(self.engine._filtered_palm_y, target.palm_y)
        self.assertNotEqual(state.axes['x'], 0)
        self.assertNotEqual(state.axes['y'], 0)

    def test_native_trace_distinguishes_observation_from_recovery_hold(self):
        result = TrackingResult(self.pose, object())
        fields = _native_trace_fields(self.engine, result, True)
        self.assertTrue(fields['observation_detected'])
        self.assertEqual(fields['observed_xy'], [.5, .5])
        self.assertTrue(fields['native_xy_active'])
        self.engine._latest_confirmation_pending = True
        fields = _native_trace_fields(self.engine, result, True)
        self.assertTrue(fields['latest_confirmation_pending'])
        missing = _native_trace_fields(
            self.engine, TrackingResult(HandObservation(10.1, False), object()), True
        )
        self.assertFalse(missing['observation_detected'])
        self.assertIsNone(missing['observed_xy'])

    def test_latest_holds_one_backward_reacquisition_after_consistent_motion(self):
        for timestamp, x in ((10.0, .50), (10.1, .55), (10.2, .60)):
            pose = replace(self.pose, timestamp=timestamp, palm_x=x)
            self.engine.update_native_motion(pose, pose, bounded=False)
        held = self.engine.update_native_motion(
            HandObservation(10.25, False), bounded=False
        )
        self.assertTrue(held.detected)
        recovered = replace(self.pose, timestamp=10.30, palm_x=.57)
        bridged = self.engine.update_native_motion(
            recovered, recovered, bounded=False
        )
        self.assertEqual(self.engine._filtered_palm_x, .60)
        self.assertEqual(bridged.axes['x'], held.axes['x'])

    def test_latest_accepts_second_recovery_result_as_authoritative_reversal(self):
        for timestamp, x in ((10.0, .50), (10.1, .55), (10.2, .60)):
            pose = replace(self.pose, timestamp=timestamp, palm_x=x)
            self.engine.update_native_motion(pose, pose, bounded=False)
        self.engine.update_native_motion(HandObservation(10.25, False), bounded=False)
        first = replace(self.pose, timestamp=10.30, palm_x=.57)
        self.engine.update_native_motion(first, first, bounded=False)
        reversal = replace(self.pose, timestamp=10.40, palm_x=.54)
        state = self.engine.update_native_motion(reversal, reversal, bounded=False)
        self.assertEqual(self.engine._filtered_palm_x, reversal.palm_x)
        expected = GestureEngine(
            'super_glove_ball', calibration=self.engine.calibration
        ).update_native_motion(reversal, reversal, bounded=False)
        self.assertEqual(state.axes['x'], expected.axes['x'])

    def test_latest_does_not_predict_without_established_direction(self):
        self.engine.update_native_motion(self.pose, self.pose, bounded=False)
        self.engine.update_native_motion(HandObservation(10.05, False), bounded=False)
        recovered = replace(self.pose, timestamp=10.10, palm_x=.45)
        self.engine.update_native_motion(recovered, recovered, bounded=False)
        self.assertEqual(self.engine._filtered_palm_x, recovered.palm_x)

    def test_latest_recovery_hold_cannot_overshoot_reach_edge(self):
        reference = Calibration(.5, .5, .2, 0, reach_left=.2, reach_right=.1,
                                reach_up=.2, reach_down=.2)
        engine = GestureEngine('super_glove_ball', calibration=reference)
        for timestamp, x in ((10.0, .55), (10.1, .58), (10.2, .60)):
            pose = replace(self.pose, timestamp=timestamp, palm_x=x)
            engine.update_native_motion(pose, pose, bounded=False)
        engine.update_native_motion(HandObservation(10.25, False), bounded=False)
        recovered = replace(self.pose, timestamp=10.30, palm_x=.57)
        state = engine.update_native_motion(recovered, recovered, bounded=False)
        self.assertEqual(engine._filtered_palm_x, .60)
        self.assertEqual(state.axes['x'], 32767)

    def test_latest_accepts_large_direction_aligned_reacquisition(self):
        for timestamp, x in ((10.0, .40), (10.1, .45), (10.2, .50)):
            pose = replace(self.pose, timestamp=timestamp, palm_x=x)
            self.engine.update_native_motion(pose, pose, bounded=False)
        held = self.engine.update_native_motion(
            HandObservation(10.25, False), bounded=False
        )
        jumped = replace(self.pose, timestamp=10.30, palm_x=.72)
        first = self.engine.update_native_motion(jumped, jumped, bounded=False)
        self.assertEqual(self.engine._filtered_palm_x, jumped.palm_x)
        self.assertGreater(first.axes['x'], held.axes['x'])

    def test_latest_holds_large_sideways_reacquisition_once(self):
        for timestamp, x in ((10.0, .40), (10.1, .45), (10.2, .50)):
            pose = replace(self.pose, timestamp=timestamp, palm_x=x)
            self.engine.update_native_motion(pose, pose, bounded=False)
        held = self.engine.update_native_motion(
            HandObservation(10.25, False), bounded=False
        )
        sideways = replace(self.pose, timestamp=10.30, palm_x=.52, palm_y=.70)
        first = self.engine.update_native_motion(sideways, sideways, bounded=False)
        self.assertEqual(first.axes['x'], held.axes['x'])
        self.assertEqual(first.axes['y'], held.axes['y'])
        confirmed = replace(sideways, timestamp=10.40, palm_x=.53, palm_y=.69)
        second = self.engine.update_native_motion(confirmed, confirmed, bounded=False)
        self.assertEqual(self.engine._filtered_palm_x, confirmed.palm_x)
        self.assertEqual(self.engine._filtered_palm_y, confirmed.palm_y)
        self.assertNotEqual(second.axes['y'], held.axes['y'])

    def test_latest_accepts_plausible_forward_recovery_immediately(self):
        for timestamp, x in ((10.0, .50), (10.1, .52), (10.2, .54)):
            pose = replace(self.pose, timestamp=timestamp, palm_x=x)
            self.engine.update_native_motion(pose, pose, bounded=False)
        self.engine.update_native_motion(HandObservation(10.25, False), bounded=False)
        recovered = replace(self.pose, timestamp=10.30, palm_x=.56)
        state = self.engine.update_native_motion(recovered, recovered, bounded=False)
        self.assertEqual(self.engine._filtered_palm_x, recovered.palm_x)
        self.assertGreater(state.axes['x'], 0)

    def test_latest_coordinate_clamps_before_retaining_filter_state(self):
        calibration = Calibration(.5, .5, .2, 0, reach_left=.2, reach_right=.1,
                                  reach_up=.2, reach_down=.2)
        engine = GestureEngine('super_glove_ball', calibration=calibration)
        outside = replace(self.pose, palm_x=.9)
        state = engine.update_native_motion(outside, outside, bounded=False)
        self.assertEqual(state.axes['x'], 32767)
        self.assertAlmostEqual(engine._filtered_palm_x, .6)
        inside = replace(outside, timestamp=10.1, palm_x=.59)
        state = engine.update_native_motion(inside, inside, bounded=False)
        self.assertLess(state.axes['x'], 32767)
        self.assertAlmostEqual(engine._filtered_palm_x, .59)

    def test_stale_motion_history_recovers_at_first_fresh_coordinate(self):
        self.engine.config = replace(
            self.engine.config, motion_noise_floor=.0001,
            motion_slow_follow=.2, motion_full_speed=20,
        )
        self.engine.update_native_motion(self.pose, self.pose)
        moving = replace(self.pose, timestamp=10.1, palm_x=.55)
        self.engine.update_native_motion(moving, moving)
        self.assertLess(self.engine._filtered_palm_x, moving.palm_x)
        recovered = replace(moving, timestamp=10.5, palm_x=.6)
        self.engine.update_native_motion(recovered, recovered)
        self.assertEqual(self.engine._filtered_palm_x, recovered.palm_x)

    def test_bounded_diagonal_uses_one_follow_weight(self):
        self.engine.config = replace(
            self.engine.config, motion_noise_floor=.0001,
            motion_slow_follow=.2, motion_full_speed=20,
        )
        self.engine.update_native_motion(self.pose, self.pose)
        target = replace(self.pose, timestamp=10.1, palm_x=.51, palm_y=.52)
        self.engine.update_native_motion(target, target)
        x_fraction = (self.engine._filtered_palm_x - .5) / .01
        y_fraction = (self.engine._filtered_palm_y - .5) / .02
        self.assertAlmostEqual(x_fraction, y_fraction)

    def test_both_native_modes_use_the_same_calibrated_reach(self):
        calibration = Calibration(.5, .5, .2, 0, reach_left=.2, reach_right=.1,
                                  reach_up=.25, reach_down=.15)
        for bounded in (True, False):
            with self.subTest(bounded=bounded):
                engine = GestureEngine('super_glove_ball', calibration=calibration)
                engine.update_native_motion(self.pose, self.pose, bounded=bounded)
                edge = replace(self.pose, timestamp=10.1, palm_x=.6, palm_y=.65)
                state = engine.update_native_motion(edge, edge, bounded=bounded)
                self.assertEqual(state.axes['x'], 32767)
                self.assertEqual(state.axes['y'], 32767)

    def test_non_native_route_keeps_standard_update(self):
        engine = GestureEngine('program_a', calibration=self.engine.calibration)
        with mock.patch.object(
            engine, 'update_native_motion', wraps=engine.update_native_motion
        ) as native:
            state, source = _update_controller_state(
                engine, TrackingResult(self.pose, object()), False
            )
        self.assertTrue(state.detected)
        self.assertEqual(source, 'inactive')
        native.assert_not_called()

    def test_medium_speed_is_direct_but_small_step_is_smoothed(self):
        for distance, immediate in ((.05, True), (.005, False), (-.05, True)):
            with self.subTest(distance=distance):
                self.setUp()
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

    def test_legacy_motion_overrides_do_not_change_bounded_native_curve(self):
        other = GestureEngine('super_glove_ball', calibration=self.engine.calibration)
        other.config = replace(other.config, motion_coordinate_boost=15.,
                               motion_coordinate_max=1.30)
        for i, x in enumerate((.5, .505, .55, .55, .52)):
            pose = replace(self.pose, timestamp=10+i/60, palm_x=x)
            expected = self.engine.update_native_motion(pose, pose)
            actual = other.update_native_motion(pose, pose)
            self.assertEqual(expected.axes, actual.axes)

    def test_legacy_experimental_motion_max_cannot_overshoot_target(self):
        self.engine.config = replace(self.engine.config, motion_coordinate_boost=14.,
                                     motion_coordinate_max=1.15)
        self.engine.update_native_motion(self.pose, self.pose)
        target = replace(self.pose, timestamp=10 + 1/60, palm_x=.55)
        self.engine.update_native_motion(target, target)
        self.assertLessEqual(self.engine._filtered_palm_x, target.palm_x)
        self.assertGreaterEqual(self.engine._filtered_palm_x, self.pose.palm_x)

    def test_stationary_noise_holds_until_cumulative_exit(self):
        self.engine.config = replace(
            self.engine.config, motion_noise_floor=.003, motion_noise_exit_ratio=1.5
        )
        self.engine.update_native_motion(self.pose, self.pose)
        for index, x in enumerate((.501, .499, .502, .498), 1):
            pose = replace(self.pose, timestamp=10 + index / 60, palm_x=x)
            self.engine.update_native_motion(pose, pose)
            self.assertEqual(self.engine._filtered_palm_x, .5)
        moved = replace(self.pose, timestamp=10 + 5 / 60, palm_x=.505)
        self.engine.update_native_motion(moved, moved)
        self.assertGreater(self.engine._filtered_palm_x, .5)

    def test_slow_deliberate_motion_is_not_permanently_suppressed(self):
        self.engine.config = replace(
            self.engine.config, motion_noise_floor=.002, motion_noise_exit_ratio=1.5,
            motion_slow_follow=.7, motion_full_speed=2.0,
        )
        self.engine.update_native_motion(self.pose, self.pose)
        for index in range(1, 9):
            pose = replace(self.pose, timestamp=10 + index / 60, palm_x=.5 + index * .001)
            self.engine.update_native_motion(pose, pose)
        self.assertGreaterEqual(self.engine._filtered_palm_x, .505)
        self.assertLessEqual(self.engine._filtered_palm_x, pose.palm_x)

    def test_large_motion_uses_latest_coordinate_immediately(self):
        self.engine.update_native_motion(self.pose, self.pose)
        target = replace(self.pose, timestamp=10 + 1 / 60, palm_x=.62, palm_y=.38)
        self.engine.update_native_motion(target, target)
        self.assertEqual(self.engine._filtered_palm_x, target.palm_x)
        self.assertEqual(self.engine._filtered_palm_y, target.palm_y)

    def test_stop_and_reversal_have_no_catch_up_tail(self):
        self.engine.config = replace(
            self.engine.config, motion_noise_floor=.001, motion_slow_follow=.4,
            motion_full_speed=20.0,
        )
        self.engine.update_native_motion(self.pose, self.pose)
        moving = replace(self.pose, timestamp=10.1, palm_x=.54)
        self.engine.update_native_motion(moving, moving)
        self.assertLess(self.engine._filtered_palm_x, moving.palm_x)
        stopped = replace(moving, timestamp=10.2)
        self.engine.update_native_motion(stopped, stopped)
        self.assertLessEqual(abs(self.engine._filtered_palm_x - stopped.palm_x), .001000001)
        settled = replace(stopped, timestamp=10.3)
        self.engine.update_native_motion(settled, settled)
        self.assertEqual(self.engine._filtered_palm_x, stopped.palm_x)
        forward = replace(stopped, timestamp=10.4, palm_x=.58)
        self.engine.update_native_motion(forward, forward)
        reverse = replace(forward, timestamp=10.5, palm_x=.55)
        self.engine.update_native_motion(reverse, reverse)
        self.assertEqual(self.engine._filtered_palm_x, reverse.palm_x)

    def test_asymmetric_reach_normalizes_velocity_by_direction(self):
        calibration = Calibration(.5, .5, .2, 0, reach_left=.1, reach_right=.4,
                                  reach_up=.2, reach_down=.2)
        left = GestureEngine('super_glove_ball', calibration=calibration)
        right = GestureEngine('super_glove_ball', calibration=calibration)
        config = replace(left.config, motion_noise_floor=.001, motion_slow_follow=.2,
                         motion_full_speed=8.0)
        left.config = right.config = config
        left.update_native_motion(self.pose, self.pose)
        right.update_native_motion(self.pose, self.pose)
        left_target = replace(self.pose, timestamp=10.1, palm_x=.48)
        right_target = replace(self.pose, timestamp=10.1, palm_x=.52)
        left.update_native_motion(left_target, left_target)
        right.update_native_motion(right_target, right_target)
        self.assertGreater(.5 - left._filtered_palm_x,
                           right._filtered_palm_x - .5)

    def test_irregular_timestamp_is_bounded_and_finite(self):
        import math
        self.engine.update_native_motion(self.pose, self.pose)
        for timestamp, x in ((10.0, .51), (9.0, .52), (20.0, .53)):
            pose = replace(self.pose, timestamp=timestamp, palm_x=x)
            self.engine.update_native_motion(pose, pose)
            self.assertTrue(math.isfinite(self.engine._filtered_palm_x))
            self.assertLessEqual(self.engine._filtered_palm_x, max(.5, x))

    def test_equivalent_velocity_is_stable_across_frame_rates(self):
        def run(hz):
            engine = GestureEngine('super_glove_ball', calibration=self.engine.calibration)
            engine.config = replace(engine.config, motion_noise_floor=.0001,
                                    motion_slow_follow=.55, motion_full_speed=10.0)
            for index in range(int(.2 * hz) + 1):
                elapsed = index / hz
                pose = replace(self.pose, timestamp=10 + elapsed,
                               palm_x=.5 + elapsed * .2)
                engine.update_native_motion(pose, pose)
            return engine._filtered_palm_x

        self.assertAlmostEqual(run(30), run(60), delta=.0015)

    def test_supervisor_passes_only_supported_native_xy_modes(self):
        import runpy
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        worker_command = runpy.run_path(str(root / 'python/main.py'))['worker_command']
        for value, expected in ((None, 'latest'), ('bounded', 'bounded'),
                                ('latest', 'latest'), ('invalid', 'latest')):
            command = worker_command({'native_xy_mode': value}, Path('/tmp/model'))
            index = command.index('--native-xy-mode')
            self.assertEqual(command[index + 1], expected)
            self.assertNotIn('--motion-tracking', command)
            thread_index = command.index('--inference-threads')
            self.assertEqual(command[thread_index + 1], '4')

    def test_supervisor_validates_inference_thread_setting(self):
        import runpy
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        worker_command = runpy.run_path(str(root / 'python/main.py'))['worker_command']
        for value, expected in ((1, '1'), (2, '2'), (4, '4'), (3, '4'), ('4', '4')):
            command = worker_command({'inference_threads': value}, Path('/tmp/model'))
            index = command.index('--inference-threads')
            self.assertEqual(command[index + 1], expected)

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

    def test_brief_loss_holds_xy_but_releases_actions_then_neutralizes(self):
        fist = replace(
            self.pose, palm_x=.6, thumb_curl=1, index_curl=1,
            middle_curl=1, ring_curl=1, pinky_curl=1,
        )
        active = self.engine.update_native_motion(fist, fist, bounded=False)
        self.assertTrue(active.buttons['closed_hand'])
        lost = self.engine.update_native_motion(HandObservation(10.05, False))
        self.assertTrue(lost.detected)
        self.assertEqual(lost.axes['x'], active.axes['x'])
        self.assertEqual(lost.axes['y'], active.axes['y'])
        self.assertEqual(lost.axes['z'], 0)
        self.assertEqual(lost.axes['roll'], 0)
        self.assertFalse(any(lost.dpad.values()))
        self.assertFalse(any(lost.buttons.values()))
        expired = self.engine.update_native_motion(HandObservation(10.13, False))
        self.assertFalse(expired.detected)
        self.assertFalse(any(expired.buttons.values()))
        self.assertFalse(any(expired.axes.values()))
        recovered = replace(self.pose, timestamp=10.14)
        self.assertTrue(self.engine.update_native_motion(recovered, recovered).detected)

    def test_brief_loss_recovery_resumes_from_fresh_latest_coordinate(self):
        for bounded in (False, True):
            with self.subTest(bounded=bounded):
                engine = GestureEngine(
                    'super_glove_ball', calibration=Calibration(.5, .5, .2, 0)
                )
                engine.update_native_motion(self.pose, self.pose, bounded=bounded)
                lost = engine.update_native_motion(
                    HandObservation(10.05, False), bounded=bounded
                )
                self.assertTrue(lost.detected)
                recovered = replace(self.pose, timestamp=10.10, palm_x=.58, palm_y=.46)
                state = engine.update_native_motion(recovered, recovered, bounded=bounded)
                self.assertEqual(engine._filtered_palm_x, recovered.palm_x)
                self.assertEqual(engine._filtered_palm_y, recovered.palm_y)
                self.assertEqual(
                    state.axes['x'],
                    engine.update_native_motion(recovered, recovered, bounded=bounded).axes['x'],
                )

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

    def test_preview_circle_uses_full_display_coordinates(self):
        tracker, slow, clock = self.make_tracker()
        frame = cv2.resize(cv2.cvtColor(self.gray, cv2.COLOR_GRAY2BGR), (640, 480))
        tracker.process(frame, 10, fast=True)
        slow.release.set()
        tracker.pending.result(timeout=2)
        clock[0] = 10.08
        result = tracker.process(frame, 10.08, fast=True)
        self.assertEqual(result.frame.shape[:2], (480, 640))
        # The outlined marker is centred near the 640x480 palm coordinate, not
        # the 320x240 optical-flow work image's corresponding pixel.
        expected = result.frame[234:247, 314:327]
        wrong_scale = result.frame[114:127, 154:167]
        green = lambda image: ((image[:, :, 1] > 240) & (image[:, :, 0] < 40)).any()
        self.assertTrue(green(expected))
        self.assertFalse(green(wrong_scale))

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
