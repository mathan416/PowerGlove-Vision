#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/benchmark-frame-preprocessing.py
# Purpose: Measure allocation-free camera preprocessing before changing tracker semantics.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Added an output-paused mirror and buffer-reuse benchmark.
# Full history: docs/CHANGELOG.md and Git history.

"""Compare current preprocessing with reusable buffers on a local camera clip.

The no-mirror lane is a cost ceiling only. It is deliberately ineligible for
promotion until an end-to-end tracker experiment proves identical handedness,
roll, preview mirroring, anchors, and gestures.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path


def percentile(values: list[float], fraction: float) -> float | None:
    """Return one nearest-rank percentile from a numeric sequence."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)]


def summary(values: list[float]) -> dict:
    """Summarize preprocessing duration without retaining frame content."""
    return {
        "count": len(values),
        "p50_ms": round(statistics.median(values), 4) if values else None,
        "p95_ms": round(percentile(values, .95), 4) if values else None,
    }


def run(path: Path, maximum: int) -> dict:
    """Compare allocation patterns over at most the requested frame count."""
    import cv2
    import numpy as np

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"could not open clip: {path}")
    frames = []
    while len(frames) < maximum:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    if not frames:
        raise RuntimeError("clip contains no readable frames")

    current, reused, no_mirror = [], [], []
    mirror_buffer = np.empty_like(frames[0])
    rgb_buffer = np.empty_like(frames[0])
    bit_exact = True
    for frame in frames:
        started = time.perf_counter_ns()
        expected = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
        current.append((time.perf_counter_ns() - started) / 1e6)

        started = time.perf_counter_ns()
        cv2.flip(frame, 1, dst=mirror_buffer)
        cv2.cvtColor(mirror_buffer, cv2.COLOR_BGR2RGB, dst=rgb_buffer)
        reused.append((time.perf_counter_ns() - started) / 1e6)
        bit_exact = bit_exact and bool(np.array_equal(expected, rgb_buffer))

        started = time.perf_counter_ns()
        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB, dst=rgb_buffer)
        no_mirror.append((time.perf_counter_ns() - started) / 1e6)

    current_summary, reused_summary = summary(current), summary(reused)
    gain = 0.0
    if current_summary["p95_ms"]:
        gain = 100 * (current_summary["p95_ms"] - reused_summary["p95_ms"]) \
            / current_summary["p95_ms"]
    return {
        "format": "powerglove-frame-preprocessing-benchmark-v1",
        "source": str(path),
        "frames": len(frames),
        "controller_output": False,
        "current_flip_and_convert": current_summary,
        "reused_flip_and_convert": reused_summary,
        "reused_output_bit_exact": bit_exact,
        "reused_p95_improvement_percent": round(gain, 2),
        "no_mirror_cost_ceiling": summary(no_mirror),
        "promotion_eligible": bit_exact and gain > 0,
        "no_mirror_promotion_eligible": False,
        "limitations": [
            "This isolates preprocessing cost and does not measure MediaPipe latency.",
            "The no-mirror lane is informational until end-to-end output equivalence is proven.",
            "A live repeated run is required before changing production buffer handling.",
        ],
    }


def main() -> int:
    """Read one local clip and optionally create an aggregate report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("clip", type=Path)
    parser.add_argument("--frames", type=int, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run(args.clip, max(1, args.frames))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
