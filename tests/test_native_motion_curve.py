# Project: VirtualGlove
# File: tests/test_native_motion_curve.py
# Purpose: Verify deterministic four-lane native movement-curve comparison.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Added bounded speed-curve replay coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise replay selection without a camera, game, or controller output."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "native_motion_curve", ROOT / "scripts/benchmark-native-motion-curve.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def replay_document():
    """Create labeled stationary, slow, medium, fast, and reversal samples."""
    samples = []
    frame = 0

    def add(start, points):
        nonlocal frame
        for offset, (x, y) in enumerate(points):
            frame += 1
            samples.append({"frame": frame, "elapsed": start + offset / 30,
                            "detected": True, "confidence": .95,
                            "x": x, "y": y, "scale": .2})

    add(0, [(0.5 + (i % 3 - 1) * .0005, .5) for i in range(15)])
    add(1, [(0.5 + i * .006, .5) for i in range(12)])
    add(2, [(0.5, .5), (.52, .5), (.52, .5), (.54, .5), (.54, .5)])
    add(3, [(.5, .5), (.58, .5), (.66, .5), (.58, .5), (.50, .5)])
    add(4, [(.5, .5), (.5005, .5), (.4995, .5), (.5, .5)])
    cues = [
        {"label": "neutral_near", "start": 0, "end": .5},
        {"label": "slow_xy", "start": 1, "end": 1.5},
        {"label": "short_directions", "start": 2, "end": 2.5},
        {"label": "fast_xy", "start": 3, "end": 3.5},
        {"label": "neutral_finish", "start": 4, "end": 4.5},
    ]
    return {"version": 2, "clip": "/tmp/example.avi", "cues": cues,
            "lanes": [{"observation_samples": samples,
                       "detection_continuity_percent": 100.0}]}


class NativeMotionCurveTests(unittest.TestCase):
    def test_four_lanes_are_reported_and_speed_curve_never_overshoots(self):
        report = MODULE.compare(replay_document())
        self.assertEqual(set(report["lanes"]), {
            "deployed_overshoot_reference", "error_curve_capped",
            "speed_curve", "latest_coordinate",
        })
        self.assertEqual(report["lanes"]["speed_curve"]["overshoot_count"], 0)
        self.assertEqual(report["lanes"]["speed_curve"]["reversal_misses"], 0)
        self.assertEqual(report["lanes"]["speed_curve"]["stop_misses"], 0)
        self.assertEqual(len(report["candidate_sweep"]), 27)

    def test_tracking_recovery_reseeds_from_the_first_fresh_coordinate(self):
        document = replay_document()
        samples = document["lanes"][0]["observation_samples"]
        samples.insert(15, {"frame": 99, "elapsed": .75, "detected": False,
                            "confidence": 0, "x": None, "y": None, "scale": None})
        document["lanes"][0]["motion_samples"] = samples
        report = MODULE.compare(document)
        speed = report["lanes"]["speed_curve"]
        self.assertEqual(speed["tracking_recoveries"], 1)
        self.assertEqual(speed["recovery_misses"], 0)

    def test_settling_measurement_stops_cleanly_at_tracking_loss(self):
        document = replay_document()
        samples = document["lanes"][0]["observation_samples"]
        samples.insert(30, {"frame": 100, "elapsed": 2.2, "detected": False,
                            "confidence": 0, "x": None, "y": None, "scale": None})
        document["lanes"][0]["motion_samples"] = samples
        report = MODULE.compare(document)
        self.assertEqual(report["lanes"]["speed_curve"]["overshoot_count"], 0)

    def test_old_replay_format_is_rejected(self):
        document = replay_document()
        del document["lanes"][0]["observation_samples"][0]["elapsed"]
        with self.assertRaisesRegex(ValueError, "version 2"):
            MODULE.compare(document)


if __name__ == "__main__":
    unittest.main()
