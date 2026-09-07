# Project: PowerGlove Vision
# File: tests/test_tracker.py
# Purpose: Verify depth-aware curl geometry and MediaPipe coordinate selection.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Covered landmark validity, palm anchors, and confidence semantics.
#   2026-09-05 - Covered stable backend identifiers and display names.
#   2026-09-03 - Covered folded fingers, rotation, API variants, and menu recognition.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify camera curl geometry without requiring MediaPipe or a camera."""

import math
import unittest
from types import SimpleNamespace

from powerglove_vision.tracker import (
    TRACKER_BACKEND_LABELS,
    _Point, _camera_curl_points, _curl, _finger_bends,
    _finger_curls, _finger_curls_from_bends, _landmarks_valid,
    _palm_anchor_candidates, _polygon_centroid,
)
from powerglove_vision.gesture import GestureEngine
from powerglove_vision.model import HandObservation


def pose_points(closed):
    """Build straight or depth-folded fingers with two right-angle bends."""
    points = [_Point(0, 0, 0)]
    for name in ('thumb', 'index', 'middle', 'ring', 'pinky'):
        finger = [(0, 0, 0), (0, 1, 0), (0, 1, -1), (0, 0, -1)] if name in closed else [(0, i, 0) for i in range(4)]
        points.extend(_Point(*p) for p in finger)
    return points


class TrackerGeometryTests(unittest.TestCase):
    def test_handedness_certainty_is_not_position_confidence(self):
        self.assertFalse(HandObservation(1.0, True, confidence=.69).usable)
        self.assertTrue(HandObservation(
            1.0, True, confidence=.01, confidence_source="handedness"
        ).usable)
        self.assertFalse(HandObservation(
            1.0, False, confidence=1.0, confidence_source="handedness"
        ).usable)

    def test_palm_anchor_candidates_translate_without_distortion(self):
        points = [_Point(index / 100, (index % 5) / 20, 0) for index in range(21)]
        original = _palm_anchor_candidates(points)
        moved = _palm_anchor_candidates([
            _Point(point.x + .2, point.y - .1, point.z) for point in points
        ])
        self.assertEqual(set(original), set(moved))
        for name in original:
            self.assertAlmostEqual(moved[name][0] - original[name][0], .2)
            self.assertAlmostEqual(moved[name][1] - original[name][1], -.1)

    def test_polygon_centroid_falls_back_for_degenerate_palm(self):
        self.assertEqual(_polygon_centroid([(0, 0), (1, 0), (2, 0)]), (1, 0))

    def test_landmark_validation_rejects_missing_and_nonfinite_values(self):
        valid = [_Point(.2 + index * .01, .3 + (index % 4) * .01, 0)
                 for index in range(21)]
        self.assertTrue(_landmarks_valid(valid))
        self.assertFalse(_landmarks_valid(valid[:-1]))
        self.assertFalse(_landmarks_valid([_Point(.5, .5, 0) for _ in range(21)]))
        valid[3].x = float("nan")
        self.assertFalse(_landmarks_valid(valid))

    def test_backend_identifiers_have_clear_display_names(self):
        self.assertEqual(TRACKER_BACKEND_LABELS, {
            "legacy": "MediaPipe Hands",
            "tasks-video": "MediaPipe Tasks Video (experimental)",
        })

    def test_precomputed_bends_produce_identical_curls(self):
        points = pose_points({'thumb', 'middle', 'pinky'})
        self.assertEqual(
            _finger_curls_from_bends(_finger_bends(points)),
            _finger_curls(points),
        )

    def test_base_knuckle_bend_is_detected_with_straight_outer_joints(self):
        points = pose_points(set())
        points[0] = _Point(0, -1, 0)
        points[5:9] = [_Point(0, 0, -i) for i in range(4)]
        self.assertAlmostEqual(_finger_curls(points)['index_curl'], .75)

    def test_single_joint_bend_is_not_diluted(self):
        points = pose_points(set())
        points[5:9] = [_Point(0, 0, 0), _Point(0, 1, 0),
                       _Point(0, 1, -1), _Point(0, 1, -2)]
        self.assertAlmostEqual(_finger_curls(points)['index_curl'], .75)

    def test_depth_fold_is_not_mistaken_for_straight(self):
        points = pose_points({'ring', 'pinky'})
        self.assertEqual(_curl(*points[13:16]), 0.0)
        curls = _finger_curls(points)
        self.assertAlmostEqual(curls['ring_curl'], 0.75)
        self.assertAlmostEqual(curls['pinky_curl'], 0.75)
        self.assertEqual(curls['index_curl'], 0.0)

    def test_curl_is_invariant_to_rotation_scale_and_translation(self):
        points = pose_points({'ring', 'pinky'})
        expected = _finger_curls(points)
        for angle in (0.4, 1.3, 2.8):
            rotated = [_Point(2+p.x*3, 4+3*(p.y*math.cos(angle)-p.z*math.sin(angle)),
                              -5+3*(p.y*math.sin(angle)+p.z*math.cos(angle))) for p in points]
            for name, value in _finger_curls(rotated).items():
                self.assertAlmostEqual(value, expected[name])

    def test_world_points_are_used_for_both_mediapipe_apis(self):
        points = pose_points({'ring'})
        for tasks, result in [(True, SimpleNamespace(hand_world_landmarks=[points])),
                              (False, SimpleNamespace(multi_hand_world_landmarks=[SimpleNamespace(landmark=points)]))]:
            self.assertIs(_camera_curl_points(result, [], tasks, 640, 480), points)

    def test_fallback_corrects_aspect_ratio_without_rescaling_depth(self):
        points = _camera_curl_points(SimpleNamespace(), [_Point(.2, .4, -.3)], True, 640, 480)
        self.assertAlmostEqual(points[0].y, .3)
        self.assertEqual(points[0].z, -.3)

    def test_collapsed_joint_stays_neutral(self):
        point = _Point(0, 0, 0)
        self.assertEqual(_curl(point, point, point, True), 0.0)

    def test_folded_menu_poses_suppress_directions_and_fire_once(self):
        for button, closed in [('start', {'ring', 'pinky'}),
                               ('select', {'index', 'middle', 'ring', 'pinky'})]:
            engine = GestureEngine('program_h', calibration_frames=3)
            for t in (0, .03, .06):
                engine.update(HandObservation(t, True, confidence=.95,
                                              palm_x=.5, palm_y=.5, palm_scale=.2))
            curls = _finger_curls(pose_points(closed))
            for t in (.1, .85):
                state = engine.update(HandObservation(t, True, palm_x=.8, palm_y=.2, palm_scale=.2, **curls))
                self.assertFalse(any(state.dpad.values()))
            self.assertTrue(state.buttons[button])
            state = engine.update(HandObservation(1.2, True, palm_x=.8, palm_y=.2, palm_scale=.2, **curls))
            self.assertFalse(state.buttons[button])
            self.assertTrue(engine.menu_feedback()['recognized'])
