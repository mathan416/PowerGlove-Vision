# Project: PowerGlove Vision
# File: tests/test_motion_matrix.py
# Purpose: Verify controlled motion-trace matrix aggregation and caveats.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Added smoothing-matrix comparison coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify controlled motion-trace matrix aggregation and caveats."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("motion_matrix", ROOT / "scripts/compare-motion-matrix.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MotionMatrixTests(unittest.TestCase):
    def test_compares_named_trace_files_and_preserves_confounds(self):
        event = {"event": "vision", "capture_ns": 1_000_000_000, "detected": True,
                 "filtered_xy": [.5, .5], "motion": {"selected_xy": [.5, .5]}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "min0.70-boost8.trace.json"
            path.write_text(json.dumps({"events": [event], "dropped": 0}))
            result = MODULE.compare(folder)
        self.assertEqual(result["rows"][0]["minimum_smoothing"], .7)
        self.assertEqual(result["rows"][0]["motion_boost"], 8)
        self.assertIn("same movement", result["interpretation"][0])


if __name__ == "__main__":
    unittest.main()
