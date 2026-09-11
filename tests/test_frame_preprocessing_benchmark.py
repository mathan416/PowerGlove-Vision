# Project: VirtualGlove
# File: tests/test_frame_preprocessing_benchmark.py
# Purpose: Verify privacy-safe frame-preparation benchmark reporting.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-08 - Added focused coverage for fused and control-only lanes.
# Full history: docs/CHANGELOG.md and Git history.

"""Tests for the output-paused frame-preparation benchmark."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script():
    """Load the hyphenated benchmark script without optional vision packages."""
    path = ROOT / "scripts" / "benchmark-frame-preprocessing.py"
    spec = importlib.util.spec_from_file_location("frame_preprocessing_benchmark", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Frame:
    """Record the multidimensional slice requested by the fused candidate."""

    def __init__(self) -> None:
        self.key = None

    def __getitem__(self, key):
        self.key = key
        return "negative-stride-view"


class _Numpy:
    """Record that the fused candidate makes MediaPipe-safe contiguous output."""

    value = None

    @classmethod
    def ascontiguousarray(cls, value):
        cls.value = value
        return "contiguous-rgb"


class FramePreprocessingBenchmarkTests(unittest.TestCase):
    """Keep experimental conclusions explicit and reports free of frame data."""

    def test_fused_candidate_mirrors_width_and_reverses_channels(self) -> None:
        """The one-copy candidate must perform exactly the two production transforms."""
        benchmark = load_script()
        frame = _Frame()
        result = benchmark.fused_mirror_channel_swap(frame, _Numpy)
        self.assertEqual(result, "contiguous-rgb")
        self.assertEqual(_Numpy.value, "negative-stride-view")
        self.assertEqual(len(frame.key), 3)
        self.assertEqual(frame.key[0], slice(None))
        self.assertEqual(frame.key[1].step, -1)
        self.assertEqual(frame.key[2].step, -1)

    def test_report_promotes_only_a_faster_bit_exact_fused_lane(self) -> None:
        """Control lanes cannot become production candidates from timing alone."""
        benchmark = load_script()
        lanes = {
            "current_flip_and_convert": [3.0, 4.0],
            "reused_flip_and_convert": [4.0, 5.0],
            "fused_numpy_mirror_channel_swap": [1.0, 2.0],
            "no_mirror_convert_only": [.5, .75],
            "grayscale_transform_expand_control": [.4, .6],
            "synthetic_jpeg_color_decode_prepare": [5.0, 6.0],
            "synthetic_jpeg_grayscale_decode_expand": [2.0, 3.0],
        }
        report = benchmark.build_report(
            lanes, frames=2, equivalence={"reused": True, "fused": True}
        )
        self.assertTrue(report["promotion_eligible"])
        self.assertFalse(report["reused_promotion_eligible"])
        self.assertTrue(report["fused_promotion_eligible"])
        self.assertFalse(report["grayscale_promotion_eligible"])
        self.assertFalse(report["no_mirror_promotion_eligible"])
        self.assertFalse(report["controller_output"])
        self.assertFalse(report["mediapipe_inference_run"])
        self.assertFalse(report["frame_content_retained"])
        self.assertNotIn("samples", report)
        self.assertEqual(report["lanes"]["current_flip_and_convert"]["count"], 2)

        report = benchmark.build_report(
            lanes, frames=2, equivalence={"reused": True, "fused": False}
        )
        self.assertFalse(report["promotion_eligible"])

    def test_slower_fused_lane_is_not_promoted(self) -> None:
        """Pixel equivalence alone is insufficient when the candidate costs more."""
        benchmark = load_script()
        lanes = {
            "current_flip_and_convert": [1.0, 1.0],
            "reused_flip_and_convert": [1.0, 1.0],
            "fused_numpy_mirror_channel_swap": [2.0, 2.0],
            "no_mirror_convert_only": [.5, .5],
            "grayscale_transform_expand_control": [.5, .5],
        }
        report = benchmark.build_report(
            lanes, frames=2, equivalence={"reused": True, "fused": True}
        )
        self.assertFalse(report["promotion_eligible"])
        self.assertFalse(report["fused_promotion_eligible"])
        self.assertLess(report["fused_p95_improvement_percent"], 0)


if __name__ == "__main__":
    unittest.main()
