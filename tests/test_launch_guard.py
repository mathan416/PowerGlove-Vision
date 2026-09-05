# Project: PowerGlove Vision
# File: tests/test_launch_guard.py
# Purpose: Verify the bounded pre-emulator controller-delivery guard.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added startup guard and low-latency camera-default coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify the bounded pre-emulator controller-delivery guard."""

import unittest

from powerglove_vision.vision_app import _launch_guard_active, build_parser


class LaunchGuardTests(unittest.TestCase):
    def test_default_guard_covers_runcommand_startup(self):
        args = build_parser().parse_args(["--receiver", "console", "--token", "x" * 16])
        self.assertEqual(args.launch_guard_ms, 6000)

    def test_default_camera_path_prefers_low_latency(self):
        args = build_parser().parse_args(["--receiver", "console", "--token", "x" * 16])
        self.assertEqual(args.fps, 60)
        self.assertEqual(args.inference_threads, 4)
        self.assertEqual(args.preview_fps, 5.0)

    def test_guard_expires_at_deadline(self):
        self.assertTrue(_launch_guard_active(16.0, now=15.999))
        self.assertFalse(_launch_guard_active(16.0, now=16.0))
        self.assertFalse(_launch_guard_active(16.0, now=17.0))


if __name__ == "__main__":
    unittest.main()
