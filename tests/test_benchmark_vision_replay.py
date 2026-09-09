# Project: PowerGlove Vision
# File: tests/test_benchmark_vision_replay.py
# Purpose: Verify repeatable MediaPipe search-region and frame-preparation experiments.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Covered zero/one-frame directional reacquisition comparison.
#   2026-09-09 - Verified selected conditional search replay reporting.
# Full history: docs/CHANGELOG.md and Git history.

"""Keep fixed search-region shifts bounded and visibly research-only."""

import argparse
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "benchmark-vision-replay.py"
SPEC = importlib.util.spec_from_file_location("benchmark_vision_replay", SCRIPT)
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class FixedRoiShiftReplayTests(unittest.TestCase):
    def test_tracking_path_summary_separates_short_and_long_losses(self):
        samples = [
            {"path": "landmark_continuation", "ms": 10, "detected": True},
            {
                "path": "hand_missing_path_unobservable", "ms": 20,
                "detected": False, "frame": 2, "elapsed": .04, "cue": "fast_xy",
            },
            {
                "path": "palm_reacquisition", "ms": 30, "detected": True,
                "recovery_gap_ms": 66.7, "recovery_missing_span_ms": 33.3,
                "recovery_inference_ms": 30,
            },
            {"path": "palm_detection_no_valid_hand", "ms": 40, "detected": False},
            {"path": "palm_detection_no_valid_hand", "ms": 50, "detected": False},
            {"path": "palm_detection_no_valid_hand", "ms": 60, "detected": False},
            {"path": "palm_detection_no_valid_hand", "ms": 70, "detected": False},
        ]
        summary = BENCHMARK.tracking_path_summary(samples)
        self.assertEqual(summary["short_missing_runs"], [1])
        self.assertEqual(summary["long_missing_runs"], [4])
        self.assertEqual(summary["missing_run_details"][0], {
            "start_frame": 2, "end_frame": 2,
            "start_elapsed": .04, "end_elapsed": .04,
            "cues": ["fast_xy"], "frames": 1,
        })
        self.assertEqual(summary["paths"]["palm_detection_no_valid_hand"]["p95"], 70)
        self.assertEqual(summary["recovery_gap_ms"]["p50"], 66.7)
        self.assertEqual(summary["recovery_missing_span_ms"]["p50"], 33.3)
        self.assertEqual(summary["recovery_inference_ms"]["p50"], 30)

    def test_shift_parser_accepts_research_candidates(self):
        self.assertEqual(BENCHMARK.parse_roi_shift("0.05,-0.10"), (.05, -.10))
        self.assertEqual(BENCHMARK.parse_roi_shift("0,0"), (0.0, 0.0))

    def test_shift_parser_rejects_malformed_nonfinite_and_unsafe_values(self):
        for value in ("0.1", "x,0", "nan,0", "0,inf", ".251,0", "0,-.251"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                BENCHMARK.parse_roi_shift(value)

    def test_lane_labels_distinguish_production_from_replay_research(self):
        self.assertEqual(
            BENCHMARK.roi_shift_lane_label(0.0, 0.0),
            "production-zero-shift",
        )
        self.assertEqual(
            BENCHMARK.roi_shift_lane_label(.05, -.1),
            "replay-research-fixed-shift-x+0.05-y-0.10",
        )

    def test_cli_keeps_zero_shift_implicit_and_research_explicit(self):
        baseline = BENCHMARK.parser().parse_args(["clip.mov", "--output", "out.json"])
        research = BENCHMARK.parser().parse_args([
            "clip.mov", "--output", "out.json",
            "--tracking-roi-shift", ".05,0",
            "--tracking-roi-shift=-.05,0",
        ])
        self.assertIsNone(baseline.tracking_roi_shift)
        self.assertEqual(research.tracking_roi_shift, [(.05, 0.0), (-.05, 0.0)])

    def test_cli_accepts_repeatable_current_and_fused_preparation_lanes(self):
        parsed = BENCHMARK.parser().parse_args([
            "clip.avi", "--output", "report.json",
            "--frame-preparations", "current", "fused",
        ])
        self.assertEqual(parsed.frame_preparations, ["current", "fused"])

    def test_cli_accepts_separate_palm_detector_thread_lanes(self):
        parsed = BENCHMARK.parser().parse_args([
            "clip.avi", "--output", "report.json",
            "--threads", "4", "--palm-threads", "1", "2", "4",
        ])
        self.assertEqual(parsed.threads, [4])
        self.assertEqual(parsed.palm_threads, [1, 2, 4])

    def test_cli_accepts_low_tracking_confidence_research_lanes(self):
        parsed = BENCHMARK.parser().parse_args([
            "clip.avi", "--output", "report.json",
            "--tracking-confidences", ".10", ".20", ".25", ".35",
        ])
        self.assertEqual(parsed.tracking_confidences, [.10, .20, .25, .35])

    def test_cli_accepts_horizontal_roi_research_lanes(self):
        parsed = BENCHMARK.parser().parse_args([
            "clip.avi", "--output", "report.json",
            "--tracking-roi-x-scales", "2.25", "2.45", "2.6",
        ])
        self.assertEqual(parsed.tracking_roi_x_scales, [2.25, 2.45, 2.6])

    def test_cli_accepts_conditional_directional_search_lanes(self):
        parsed = BENCHMARK.parser().parse_args([
            "clip.avi", "--output", "report.json",
            "--directional-search-modes", "off", "on",
            "--directional-search-gains", ".35", ".5",
            "--directional-search-min-speeds", ".4", ".6",
            "--directional-search-max-offsets", ".04", ".08",
            "--directional-search-recovery-frames", "0", "1",
        ])
        self.assertEqual(parsed.directional_search_modes, ["off", "on"])
        self.assertEqual(parsed.directional_search_gains, [.35, .5])
        self.assertEqual(parsed.directional_search_min_speeds, [.4, .6])
        self.assertEqual(parsed.directional_search_max_offsets, [.04, .08])
        self.assertEqual(parsed.directional_search_recovery_frames, [0, 1])


if __name__ == "__main__":
    unittest.main()
