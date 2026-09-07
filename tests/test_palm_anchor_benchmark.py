# Project: PowerGlove Vision
# File: tests/test_palm_anchor_benchmark.py
# Purpose: Verify deterministic palm-anchor benchmark selection gates.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Added deterministic palm-anchor selection coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify the aggregate pose-stability and retained-travel selection gate."""

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_palm_anchors", ROOT / "scripts" / "benchmark-palm-anchors.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PalmAnchorBenchmarkTests(unittest.TestCase):
    def test_candidate_requires_pose_stability_and_retained_travel(self):
        cues = [
            {"label": "neutral_near", "start": 0, "end": 1},
            {"label": "closed_hand", "start": 1, "end": 2},
            {"label": "slow_xy", "start": 2, "end": 4},
        ]
        rows = []
        for elapsed, base_x, stable_x in (
            (.1, .50, .50), (.5, .51, .505),
            (1.1, .54, .51), (1.5, .55, .515),
            (2.1, .30, .30), (3.1, .70, .70),
        ):
            rows.append({
                "elapsed": elapsed,
                "detected": True,
                "palm_anchors": {
                    "five_point_average": [base_x, .5],
                    "palm_polygon": [stable_x, .5],
                },
            })
        report = MODULE.compare({"clip": "temporary", "cues": cues,
                                 "lanes": [{"motion_samples": rows}]})
        self.assertEqual(report["selected_candidate"], "palm_polygon")
        self.assertEqual(report["detection_continuity_percent"], 100)
        self.assertEqual(report["reacquisition_count"], 0)

    def test_missing_candidate_data_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.compare({"cues": [], "lanes": [{"motion_samples": []}]})


if __name__ == "__main__":
    unittest.main()
