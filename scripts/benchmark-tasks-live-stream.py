#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/benchmark-tasks-live-stream.py
# Purpose: Probe CPU/GPU MediaPipe Tasks live-stream performance without controller output.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Added isolated paced CPU/GPU Tasks live-stream probes.
# Full history: docs/CHANGELOG.md and Git history.

"""Run paced, output-paused MediaPipe Tasks live-stream acceleration probes."""

import argparse
import json
import math
import threading
import time
from pathlib import Path


def percentile(values, fraction):
    """Return one nearest-rank percentile from a numeric sequence."""
    values = sorted(values)
    return values[min(len(values) - 1, math.ceil(len(values) * fraction) - 1)] if values else None


def run_lane(clip, model, delegate_name, maximum_frames):
    """Run one output-paused Tasks live-stream delegate lane."""
    import cv2
    import mediapipe as mp

    lock = threading.Lock()
    submitted_at = {}
    callbacks = []

    def receive(result, _image, timestamp_ms):
        """Retain aggregate delivery timing for one asynchronous result."""
        finished = time.monotonic()
        with lock:
            started = submitted_at.get(timestamp_ms)
            callbacks.append({
                "timestamp_ms": timestamp_ms,
                "detected": bool(result.hand_landmarks),
                "latency_ms": (finished - started) * 1000 if started is not None else None,
            })

    delegate = (mp.tasks.BaseOptions.Delegate.GPU if delegate_name == "gpu"
                else mp.tasks.BaseOptions.Delegate.CPU)
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model), delegate=delegate),
        running_mode=mp.tasks.vision.RunningMode.LIVE_STREAM,
        num_hands=1,
        min_hand_detection_confidence=.55,
        min_hand_presence_confidence=.55,
        min_tracking_confidence=.55,
        result_callback=receive,
    )
    capture = cv2.VideoCapture(str(clip))
    source_fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    submitted = 0
    started = time.monotonic()
    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as tracker:
            while submitted < maximum_frames:
                ok, frame = capture.read()
                if not ok:
                    break
                target = started + submitted / source_fps
                delay = target - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                timestamp_ms = round(submitted * 1000 / source_fps) + 1
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                with lock:
                    submitted_at[timestamp_ms] = time.monotonic()
                tracker.detect_async(image, timestamp_ms)
                submitted += 1
            time.sleep(1.0)
    finally:
        capture.release()
    with lock:
        rows = list(callbacks)
    latencies = [row["latency_ms"] for row in rows if row["latency_ms"] is not None]
    ordered = all(a["timestamp_ms"] < b["timestamp_ms"] for a, b in zip(rows, rows[1:]))
    elapsed = max(.001, time.monotonic() - started - 1.0)
    return {
        "delegate": delegate_name,
        "submitted": submitted,
        "callbacks": len(rows),
        "callback_hz": len(rows) / elapsed,
        "delivered_percent": len(rows) / submitted * 100 if submitted else 0,
        "detection_percent": (sum(row["detected"] for row in rows) / len(rows) * 100
                              if rows else 0),
        "ordered": ordered,
        "latency_ms": {"p50": percentile(latencies, .50),
                       "p95": percentile(latencies, .95)},
    }


def main():
    """Probe requested delegates and record unsupported runtimes safely."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clip", type=Path)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delegate", choices=("cpu", "gpu", "both"), default="both")
    parser.add_argument("--frames", type=int, default=300,
                        help="Bound each hardware probe; full recognition uses legacy replay")
    args = parser.parse_args()
    if not args.clip.is_file() or not args.model.is_file():
        parser.error("The clip and model must already exist locally")
    delegates = ("cpu", "gpu") if args.delegate == "both" else (args.delegate,)
    lanes = []
    for delegate in delegates:
        try:
            lanes.append(run_lane(args.clip, args.model, delegate, max(1, args.frames)))
        except Exception as exc:
            lanes.append({"delegate": delegate, "supported": False,
                          "error": type(exc).__name__ + ": " + str(exc)})
    report = {"version": 1, "controller_output": False, "lanes": lanes}
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "lanes": len(lanes)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
