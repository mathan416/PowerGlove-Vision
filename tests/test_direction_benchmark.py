# Project: PowerGlove Vision
# File: tests/test_direction_benchmark.py
# Purpose: Verify deterministic direction-response benchmark helpers and coverage.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "direction_benchmark", ROOT / "scripts/benchmark-direction-response.py"
)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class DirectionBenchmarkTests(unittest.TestCase):
    def test_first_divergence_is_one_based_and_none_when_equal(self):
        self.assertEqual(benchmark.first_divergence([1, 2, 3], [1, 9, 3]), 2)
        self.assertIsNone(benchmark.first_divergence([1, 2], [1, 2]))

    def test_frame_result_reports_a_60_hz_visible_latency(self):
        class FakeSession:
            def __init__(self):
                self.branch_frame = 0

            def load(self, _saved):
                self.branch_frame = 0

            def run(self, mask):
                self.branch_frame += 1
                return (mask if self.branch_frame >= 2 else 0), True

        result = benchmark.matched_branches(FakeSession(), b"state", 0, 1, 3)
        self.assertEqual(result["first_video_divergence_frame"], 2)
        self.assertEqual(result["first_video_divergence_ms_at_60hz"], 33.3)
        self.assertTrue(result["libretro_input_polled_on_frame_1"])

    def test_shared_recognition_activates_short_moves_and_releases_near_center(self):
        result = benchmark.recognition_results()
        self.assertEqual(set(result), {"left", "right", "up", "down"})
        for direction in result.values():
            self.assertTrue(direction["activated"])
            self.assertTrue(direction["released"])
            self.assertEqual(direction["activation_displacement"], .29)
            self.assertEqual(direction["release_displacement"], .13)

    def test_fceumm_build_is_pinned_and_benchmark_covers_both_paths(self):
        build = (ROOT / "scripts/build-fceumm-benchmark.sh").read_text()
        runner = (ROOT / "scripts/benchmark-direction-response.py").read_text()
        self.assertIn("236ccdfc911e84c60fea6b9d0699c2d440a8de14", build)
        self.assertIn("native_super_glove_ball", runner)
        self.assertIn("fceumm_super_glove_ball", runner)
        self.assertIn("fceumm_gun_smoke", runner)
        self.assertIn("standard_libretro_joypad", runner)
        self.assertIn("first_video_divergence_frame", runner)
        self.assertIn("retro_serialize", runner)


if __name__ == "__main__":
    unittest.main()
