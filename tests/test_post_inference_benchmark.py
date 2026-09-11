# Project: VirtualGlove
# File: tests/test_post_inference_benchmark.py
# Purpose: Verify the camera-free post-inference load benchmark.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Added synthetic UDP and Dashboard-lane coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify the production-shaped post-inference benchmark without network I/O."""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark-post-inference.py"
SPEC = importlib.util.spec_from_file_location("benchmark_post_inference", SCRIPT)
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class PostInferenceBenchmarkTests(unittest.TestCase):
    def test_lane_sends_every_state_and_throttles_dashboard(self):
        lane = BENCHMARK.run_lane(200, statistics=True, slow_publish_ms=1)
        self.assertEqual(lane["iterations"], 200)
        self.assertEqual(lane["udp_datagrams"], 210)
        self.assertGreater(lane["dashboard_submitted"], 0)
        self.assertLess(lane["dashboard_submitted"], lane["udp_datagrams"])
        self.assertLessEqual(lane["dashboard_published"], lane["dashboard_submitted"])
        self.assertEqual(lane["udp_send_ms"]["samples"], 200)
        self.assertEqual(lane["full_iteration_ms"]["samples"], 200)


if __name__ == "__main__":
    unittest.main()
