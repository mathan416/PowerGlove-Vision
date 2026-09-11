# Project: VirtualGlove
# File: tests/test_measure_vision_status.py
# Purpose: Verify latency baselines reject cached samples and retain only aggregates.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Added fresh-sample, condition, and missing-stage regression coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise the read-only baseline collector without camera or network access."""

import argparse
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "measure_vision_status", Path(__file__).resolve().parents[1] / "scripts/measure-vision-status.py")
measure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure)


def sample(timestamp=1, **values):
    result = dict(vision_state="active", timestamp=timestamp, capture_sequence=int(timestamp),
                  active_profile="super_glove_ball", detected=True, calibrated=True,
                  controller_enabled=True, receiver_available=True,
                  inference_ms=90, sample_age_ms=110, send_ms=.1,
                  axes={"x": 100, "y": 200})
    result.update(values)
    return result


class StatusMeasurementTests(unittest.TestCase):
    def test_cached_samples_do_not_bias_timing_or_jitter(self):
        window = measure.StatusWindow("neutral")
        for _ in range(10):
            window.observe(sample(), 2)
        window.observe(sample(2, inference_ms=100, axes={"x": 120, "y": 220}), 3)
        report = window.report(1)
        self.assertEqual(report["observed_samples"], 2)
        self.assertEqual(report["duplicate_polls"], 9)
        segment = report["segments"][0]
        self.assertEqual(segment["timings_ms"]["inference_ms"],
                         {"samples": 2, "p50": 90, "p95": 100, "max": 100})
        self.assertEqual(segment["neutral_axis_variation"]["x"]["span"], 20)

    def test_idle_and_failed_requests_cannot_look_like_good_gameplay(self):
        window = measure.StatusWindow("idle")
        window.observe(sample(vision_state="idle"), 2)
        window.errors += 1
        self.assertEqual(window.report(1)["segments"], [])
        window.observe(sample(receiver_available=False), 2)
        segment = window.report(1)["segments"][0]
        self.assertEqual(segment["sent_sample_age_ms"], {"samples": 0})
        self.assertEqual(segment["local_send_success_samples"], 0)

    def test_changed_conditions_are_not_pooled(self):
        window = measure.StatusWindow("movement")
        window.observe(sample(), 1)
        window.observe(sample(2, practice_mode=True), 1)
        window.observe(sample(3, vision_state="idle"), 1)
        window.observe(sample(4, practice_mode=True), 1)
        report = window.report(2)
        self.assertEqual(len(report["segments"]), 3)
        self.assertNotIn("neutral_axis_variation", report["segments"][0])

    def test_capture_restart_does_not_hide_a_new_sample(self):
        window = measure.StatusWindow("neutral")
        window.observe(sample(), 1)
        window.observe(sample(10, capture_sequence=1), 1)
        self.assertEqual(window.report(1)["observed_samples"], 2)
        self.assertEqual(len(window.report(1)["segments"]), 2)

    def test_tracking_loss_timings_and_capture_skips_remain_distinct(self):
        window = measure.StatusWindow("movement")
        window.observe(sample(inference_ms=80, capture_skipped_total=10), 1)
        window.observe(sample(2, detected=False, inference_ms=200, capture_skipped_total=14), 1)
        segment = window.report(1)["segments"][0]
        self.assertEqual(segment["detected_inference_ms"]["p95"], 80)
        self.assertEqual(segment["missing_hand_inference_ms"]["p95"], 200)
        self.assertEqual(segment["capture_skipped_delta"], 4)

    def test_report_excludes_private_data_and_invalid_measurements(self):
        window = measure.StatusWindow("neutral")
        window.observe(sample(token="private-token", hand_landmarks=[[.5, .5]],
                              inference_ms=float("nan"), send_ms=-1,
                              axes={"x": float("inf"), "y": True}), 1)
        invalid = sample()
        invalid["timestamp"] = []
        window.observe(invalid, 1)
        report = window.report(1)
        encoded = json.dumps(report, allow_nan=False)
        self.assertNotIn("private-token", encoded)
        self.assertNotIn("hand_landmarks", encoded)
        self.assertEqual(report["invalid_polls"], 1)
        segment = report["segments"][0]
        self.assertEqual(segment["timings_ms"]["inference_ms"], {"samples": 0})
        self.assertEqual(segment["neutral_axis_variation"], {})

    def test_endpoint_requires_explicit_status_path_without_credentials(self):
        for value in ("file:///etc/passwd", "http://host/api/profile", "http://user:secret@host/status",
                      "http://host/status?token=secret"):
            with self.assertRaises(argparse.ArgumentTypeError):
                measure.status_url(value)
        self.assertEqual(measure.status_url("http://localhost:8089/status"),
                         "http://localhost:8089/status")

    def test_collection_uses_bounded_read_only_requests(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self, maximum):
                self.maximum = maximum
                return json.dumps(sample()).encode()

        response = Response()
        with patch.object(measure.urllib.request, "build_opener") as build, \
                patch.object(measure.time, "monotonic", side_effect=[0, 0, 0, .1, .1, .1, 1, 1]), \
                patch.object(measure.time, "sleep"):
            build.return_value.open.return_value = response
            report = measure.collect("http://localhost:8089/status", 1, .1, "movement")
        self.assertEqual(report["observed_samples"], 1)
        self.assertEqual(response.maximum, 262145)
        build.return_value.open.assert_called_once_with("http://localhost:8089/status", timeout=1)


if __name__ == "__main__":
    unittest.main()
