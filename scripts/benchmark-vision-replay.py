#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/benchmark-vision-replay.py
# Purpose: Compare repeatable tracker configurations using one local camera clip.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-05 - Kept aggregate means compatible with Python 3.7.
#   2026-09-05 - Added repeatable MediaPipe backend, thread, size, and preview comparisons.
# Full history: docs/CHANGELOG.md and Git history.

"""Replay one local clip through proven and experimental vision configurations."""

from __future__ import annotations

import argparse
import json
import sys
import time
from math import ceil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from powerglove_vision.tracker import MediaPipeTracker  # noqa: E402
from powerglove_vision.gesture import GestureEngine  # noqa: E402


def percentile(values: list[float], fraction: float) -> float | None:
    """Return a nearest-rank percentile rounded for the aggregate report."""
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, ceil(len(ordered) * fraction) - 1)], 2)


def run_lane(clip: Path, backend: str, threads: int, size: tuple[int, int],
             preview: bool, model: Path | None, cues: list[dict],
             frame_times: list[float] | None = None,
             effective_fps: float | None = None) -> dict:
    """Replay one clip through a single tracker configuration and summarize it."""
    import cv2
    tracker = MediaPipeTracker(
        backend=backend, inference_threads=threads, model_path=model, mirror=True,
    )
    tracker.preview_enabled = preview
    tracker.diagnostics_enabled = preview
    capture = cv2.VideoCapture(str(clip))
    source_fps = effective_fps or capture.get(cv2.CAP_PROP_FPS) or 30.0
    inference = []
    detected = []
    observations = []
    motion_samples = []
    encoded_ms = []
    frame_index = 0
    engine = GestureEngine("practice")
    cue_stats = {
        cue["label"]: {"frames": 0, "detected": 0, "recognized": 0, "first_ms": None}
        for cue in cues
    }
    neutral_false_frames = 0
    neutral_axes = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_index += 1
            elapsed = (
                frame_times[frame_index - 1]
                if frame_times is not None and frame_index <= len(frame_times)
                else frame_index / source_fps
            )
            frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
            started = time.monotonic()
            result = tracker.process(frame, elapsed)
            finished = time.monotonic()
            inference.append((finished - started) * 1000)
            detected.append(result.observation.detected)
            state = engine.update(result.observation)
            item = result.observation
            motion_samples.append({
                "frame": frame_index, "elapsed": elapsed,
                "detected": item.detected, "confidence": item.confidence,
                "x": item.palm_x if item.detected else None,
                "y": item.palm_y if item.detected else None,
                "scale": item.palm_scale if item.detected else None,
            })
            cue = next((item for item in cues if item["start"] <= elapsed < item["end"]), None)
            feedback = engine.recognition_feedback()
            curls = engine.curl_feedback(result.observation)
            push = engine.push_feedback(result.observation)["active"]
            pull = engine.pull_feedback(result.observation)["active"]
            recognized = {
                "short_directions": any(state.dpad.values()),
                "a": curls["index"], "b": curls["thumb"],
                "roll_left": feedback["roll_left"],
                "roll_right": feedback["roll_right"],
                "closed_hand": feedback["closed_hand"],
                "push": push, "pull": pull,
                "a_b_far": curls["index"] or curls["thumb"],
            }
            any_action = (
                any(state.dpad.values()) or any(curls.values()) or push or pull
                or feedback["roll_left"] or feedback["roll_right"]
                or feedback["closed_hand"] or feedback["menu_guard"]
            )
            if cue is not None:
                stat = cue_stats[cue["label"]]
                stat["frames"] += 1
                stat["detected"] += int(result.observation.detected)
                active = recognized.get(cue["label"], False)
                stat["recognized"] += int(active)
                if active and stat["first_ms"] is None:
                    stat["first_ms"] = round((elapsed - cue["start"]) * 1000)
                if cue["label"] in ("neutral_near", "neutral_far", "neutral_finish"):
                    neutral_false_frames += int(any_action)
                    if state.calibrated and state.detected:
                        neutral_axes.append((state.axes["x"], state.axes["y"]))
            if result.observation.detected:
                item = result.observation
                observations.append({
                    "frame": frame_index, "elapsed": elapsed,
                    "confidence": item.confidence,
                    "x": item.palm_x, "y": item.palm_y,
                    "scale": item.palm_scale, "roll": item.roll,
                    "thumb": item.thumb_curl, "index": item.index_curl,
                    "middle": item.middle_curl, "ring": item.ring_curl,
                    "pinky": item.pinky_curl,
                })
            if preview and frame_index % max(1, round(source_fps / 5)) == 0:
                encode_started = time.monotonic()
                cv2.imencode(".jpg", result.frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                encoded_ms.append((time.monotonic() - encode_started) * 1000)
    finally:
        capture.release()
        tracker.close()
    for stat in cue_stats.values():
        stat["detection_percent"] = round(
            stat["detected"] / stat["frames"] * 100, 2
        ) if stat["frames"] else 0
        stat["recognition_percent"] = round(
            stat["recognized"] / stat["frames"] * 100, 2
        ) if stat["frames"] else 0
    jitter_span = {
        axis: (max(values) - min(values) if values else None)
        for axis, values in (
            ("x", [value[0] for value in neutral_axes]),
            ("y", [value[1] for value in neutral_axes]),
        )
    }
    return {
        "backend": backend, "threads": threads, "resize": list(size),
        "preview": "open" if preview else "closed", "frames": frame_index,
        "inference_ms": {"p50": percentile(inference, .50),
                         "p95": percentile(inference, .95),
                         "mean": round(sum(inference) / len(inference), 2) if inference else None},
        "preview_encode_ms": {"p50": percentile(encoded_ms, .50),
                              "p95": percentile(encoded_ms, .95)},
        "detection_continuity_percent": round(sum(detected) / len(detected) * 100, 2) if detected else 0,
        "cue_results": cue_stats,
        "neutral_false_activation_frames": neutral_false_frames,
        "neutral_coordinate_jitter_span": jitter_span,
        "observation_samples": observations,
        "motion_samples": motion_samples,
    }


def parser() -> argparse.ArgumentParser:
    """Build the repeatable replay benchmark command-line interface."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("clip", type=Path)
    result.add_argument("--model", type=Path)
    result.add_argument("--output", type=Path, required=True)
    result.add_argument(
        "--quick", action="store_true",
        help="Run only the proven 640x480, two-thread lane for clip validation",
    )
    return result


def main() -> int:
    """Run every requested comparison lane and write one aggregate JSON report."""
    args = parser().parse_args()
    if not args.clip.is_file():
        raise FileNotFoundError(args.clip)
    sidecar = args.clip.with_suffix(args.clip.suffix + ".json")
    if not sidecar.is_file():
        raise FileNotFoundError(f"Benchmark cue sidecar is missing: {sidecar}")
    cue_document = json.loads(sidecar.read_text())
    cues = cue_document["cues"]
    frame_times = cue_document.get("frame_times_seconds")
    effective_fps = cue_document.get("effective_fps")
    lanes = []
    sizes = ((640, 480),) if args.quick else ((640, 480), (512, 384))
    previews = (False,) if args.quick else (False, True)
    threads_to_test = (2,) if args.quick else (1, 2, 4)
    for size in sizes:
        for preview in previews:
            for threads in threads_to_test:
                lanes.append(run_lane(
                    args.clip, "legacy", threads, size, preview, None, cues,
                    frame_times, effective_fps,
                ))
            if args.model is not None and not args.quick:
                lanes.append(run_lane(
                    args.clip, "tasks-video", 1, size, preview, args.model, cues,
                    frame_times, effective_fps,
                ))
    result = {
        "version": 2, "clip": str(args.clip), "full_frame_resize_only": True,
        "cues": cues,
        "lanes": lanes,
        "note": ("Observation samples support cue-by-cue recognition review. Live Dashboard "
                 "telemetry remains authoritative for latest-frame age and camera-to-send latency."),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "lanes": len(lanes)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
