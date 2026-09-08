# Project: PowerGlove Vision
# File: tests/test_full_vision_exposure_soak.py
# Purpose: Verify the full-pipeline exposure soak remains isolated and finite.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-08 - Added isolation checks for the full vision exposure soak.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify the full vision exposure soak cannot enable controller output."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


spec = importlib.util.spec_from_file_location(
    "full_vision_exposure_soak",
    Path(__file__).resolve().parents[1] / "scripts" / "soak-full-vision-exposure.py",
)
soak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(soak)


class FullVisionExposureSoakTests(unittest.TestCase):
    def test_worker_is_direct_v4l2_manual_and_never_enables_controller(self):
        args = SimpleNamespace(
            device="/dev/video2", web_port=8189, profile_port=55456,
            model=Path("/model.task"), exposure=78, gain=96, transition_profile=None,
        )
        command = soak.worker_command(args)
        self.assertIn("direct-v4l2", command)
        self.assertIn("--camera-manual-exposure-test", command)
        self.assertIn("--camera-manual-gain-test", command)
        self.assertNotIn("--controller-enabled", command)

    def test_status_endpoint_is_private(self):
        args = SimpleNamespace(
            device="/dev/video2", web_port=8189, profile_port=55456,
            model=Path("/model.task"), exposure=78, gain=96, transition_profile=None,
        )
        command = soak.worker_command(args)
        self.assertEqual(command[command.index("--web-host") + 1], "127.0.0.1")
        self.assertEqual(command[command.index("--profile-listen") + 1], "127.0.0.1")

    def test_transition_lane_starts_off_and_still_never_enables_output(self):
        args = SimpleNamespace(
            device="/dev/video2", web_port=8189, profile_port=55456,
            model=Path("/model.task"), exposure=78, gain=96,
            transition_profile="super_glove_ball",
        )
        command = soak.worker_command(args)
        self.assertEqual(command[command.index("--profile") + 1], "off")
        self.assertNotIn("--controller-enabled", command)


if __name__ == "__main__":
    unittest.main()
