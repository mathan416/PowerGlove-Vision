# Project: PowerGlove Vision
# File: tests/test_motion_trace.py
# Purpose: Verify native-motion trace classification and summary calculations.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Added per-frame motion-trace analysis coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify native-motion trace classification and summary calculations."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("motion_trace", ROOT / "scripts/analyze-motion-trace.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MotionTraceTests(unittest.TestCase):
    def test_classifies_changes_and_calculates_age_and_error(self):
        events = []
        for i, x in enumerate((.5, .505, .54, .70, .70, .70)):
            t = 1_000_000_000 + i * 16_000_000
            events.append({"event": "vision", "capture_ns": t, "detected": True,
                           "filtered_xy": [x - (.005 if i == 1 else 0), .5],
                           "motion": {"selected_xy": [x, .5], "recognized_capture_ns": t - 8_000_000,
                                      "fallback_reason": None}})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.json"
            path.write_text(json.dumps({"events": events, "dropped": 0}))
            result = MODULE.analyze(path)
        self.assertEqual(result["vision_events"], 6)
        self.assertEqual(result["movement_classes"]["small"]["changes"], 1)
        self.assertEqual(result["movement_classes"]["medium"]["changes"], 1)
        self.assertEqual(result["movement_classes"]["large"]["changes"], 1)
        self.assertEqual(result["recognition_source_age_ms"]["median"], 8.0)
        self.assertEqual(result["selected_filtered_error_x"]["max"], .005)

    def test_excludes_invalid_and_reports_losses(self):
        events = [{"event": "vision", "capture_ns": 1, "detected": True,
                   "filtered_xy": [.5, .5], "motion": {"selected_xy": [.5, .5]}},
                  {"event": "vision", "capture_ns": 2, "detected": False,
                   "filtered_xy": None, "motion": {"selected_xy": None}}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.json"; path.write_text(json.dumps({"events": events}))
            result = MODULE.analyze(path)
        self.assertEqual(result["valid_events"], 1)
        self.assertEqual(result["tracking_losses"], 1)

    def test_analyzes_mediapipe_latest_and_counts_recovery_hold(self):
        events = [
            {"event": "vision", "capture_ns": 1, "detected": True,
             "observation_detected": True, "observed_xy": [.50, .50],
             "filtered_xy": [.50, .50]},
            {"event": "vision", "capture_ns": 2, "detected": True,
             "observation_detected": False, "observed_xy": None,
             "filtered_xy": [.50, .50], "latest_recovery_pending": True},
            {"event": "vision", "capture_ns": 3, "detected": True,
             "observation_detected": True, "observed_xy": [.70, .50],
             "filtered_xy": [.50, .50], "latest_confirmation_pending": True},
            {"event": "vision", "capture_ns": 4, "detected": True,
             "observation_detected": True, "observed_xy": [.68, .50],
             "filtered_xy": [.68, .50]},
        ]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.json"
            path.write_text(json.dumps({"events": events, "dropped": 0}))
            result = MODULE.analyze(path)
        self.assertEqual(result["valid_events"], 3)
        self.assertEqual(result["observation_losses"], 1)
        self.assertEqual(result["latest_recovery_holds"], 1)
        self.assertEqual(result["selected_filtered_error_x"]["max"], .2)


if __name__ == "__main__":
    unittest.main()
