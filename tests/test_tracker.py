# Project: PowerGlove Vision
# File: tests/test_tracker.py
# Purpose: Verify depth-aware curl geometry and MediaPipe coordinate selection.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Covered folded fingers, rotation, API variants, and menu recognition.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify camera curl geometry without requiring MediaPipe or a camera."""

import math
import unittest
from types import SimpleNamespace

from powerglove_vision.tracker import _Point, _curl, _finger_curls, _camera_curl_points
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
                engine.update(HandObservation(t, True, palm_x=.5, palm_y=.5, palm_scale=.2))
            curls = _finger_curls(pose_points(closed))
            for t in (.1, .85):
                state = engine.update(HandObservation(t, True, palm_x=.8, palm_y=.2, palm_scale=.2, **curls))
                self.assertFalse(any(state.dpad.values()))
            self.assertTrue(state.buttons[button])
            state = engine.update(HandObservation(1.2, True, palm_x=.8, palm_y=.2, palm_scale=.2, **curls))
            self.assertFalse(state.buttons[button])
            self.assertTrue(engine.menu_feedback()['recognized'])
