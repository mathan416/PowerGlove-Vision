#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/benchmark-vision-replay.py
# Purpose: Compare repeatable tracker configurations using one local camera clip.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Reported capture-time tracking loss and recovery timing.
#   2026-09-08 - Added fused-colour and fixed search-region comparison lanes.
#   2026-09-07 - Retained temporary palm-anchor candidates for aggregate comparison.
#   2026-09-05 - Kept aggregate means compatible with Python 3.7.
#   2026-09-05 - Added repeatable MediaPipe backend, thread, size, and preview comparisons.
# Full history: docs/CHANGELOG.md and Git history.

"""Replay one local clip through proven and experimental vision configurations."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
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


def parse_roi_shift(value: str) -> tuple[float, float]:
    """Parse one bounded replay-only X,Y next-frame ROI shift."""
    try:
        parts = value.split(",")
        if len(parts) != 2:
            raise ValueError
        shift = (float(parts[0]), float(parts[1]))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("ROI shift must be X,Y") from exc
    if any(not math.isfinite(item) or not -.25 <= item <= .25 for item in shift):
        raise argparse.ArgumentTypeError(
            "ROI shift values must be finite and between -0.25 and 0.25"
        )
    return shift


def roi_shift_lane_label(shift_x: float, shift_y: float) -> str:
    """Make the production baseline unmistakable from fixed-shift research."""
    if shift_x == 0.0 and shift_y == 0.0:
        return "production-zero-shift"
    return f"replay-research-fixed-shift-x{shift_x:+.2f}-y{shift_y:+.2f}"


def tracking_path_summary(samples: list[dict]) -> dict:
    """Summarize detector cost and consecutive missing results per replay lane."""
    counts = Counter(sample["path"] for sample in samples)
    timing = {}
    for path in sorted(counts):
        values = [sample["ms"] for sample in samples if sample["path"] == path]
        timing[path] = {
            "count": len(values),
            "p50": percentile(values, .50),
            "p95": percentile(values, .95),
        }
    missing_runs = []
    missing_run_details = []
    current_run = 0
    current_detail = None
    for index, sample in enumerate(samples, start=1):
        if not sample["detected"]:
            current_run += 1
            if current_detail is None:
                current_detail = {
                    "start_frame": sample.get("frame", index),
                    "end_frame": sample.get("frame", index),
                    "start_elapsed": sample.get("elapsed"),
                    "end_elapsed": sample.get("elapsed"),
                    "cues": [],
                }
            current_detail["end_frame"] = sample.get("frame", index)
            current_detail["end_elapsed"] = sample.get("elapsed")
            cue = sample.get("cue")
            if cue is not None and cue not in current_detail["cues"]:
                current_detail["cues"].append(cue)
        elif current_run:
            missing_runs.append(current_run)
            current_detail["frames"] = current_run
            missing_run_details.append(current_detail)
            current_run = 0
            current_detail = None
    if current_run:
        missing_runs.append(current_run)
        current_detail["frames"] = current_run
        missing_run_details.append(current_detail)
    recovery_gaps = [sample["recovery_gap_ms"] for sample in samples
                     if sample.get("recovery_gap_ms") is not None]
    recovery_missing_spans = [sample["recovery_missing_span_ms"] for sample in samples
                              if sample.get("recovery_missing_span_ms") is not None]
    recovery_inference = [sample["recovery_inference_ms"] for sample in samples
                          if sample.get("recovery_inference_ms") is not None]
    return {
        "paths": timing,
        "missing_runs": missing_runs,
        "missing_run_details": missing_run_details,
        "short_missing_runs": [length for length in missing_runs if length <= 3],
        "long_missing_runs": [length for length in missing_runs if length > 3],
        "recovery_gap_ms": {
            "count": len(recovery_gaps),
            "p50": percentile(recovery_gaps, .50),
            "p95": percentile(recovery_gaps, .95),
        },
        "recovery_missing_span_ms": {
            "count": len(recovery_missing_spans),
            "p50": percentile(recovery_missing_spans, .50),
            "p95": percentile(recovery_missing_spans, .95),
        },
        "recovery_inference_ms": {
            "count": len(recovery_inference),
            "p50": percentile(recovery_inference, .50),
            "p95": percentile(recovery_inference, .95),
        },
    }


def run_lane(clip: Path, backend: str, threads: int, size: tuple[int, int],
             preview: bool, model: Path | None, cues: list[dict],
             tracking_confidence: float = .55,
             tracking_roi_scale: float = 2.0,
             tracking_roi_shift: tuple[float, float] = (0.0, 0.0),
             palm_detection_mode: str = "tracked",
             detection_confidence: float = .55,
             model_complexity: int = 0,
             fused_preprocessing: bool = True,
             palm_inference_threads: int | None = None,
             tracking_roi_scale_x: float | None = None,
             tracking_roi_scale_y: float | None = None,
             frame_times: list[float] | None = None,
             effective_fps: float | None = None,
             directional_search: bool = False,
             directional_search_gain: float = .275,
             directional_search_min_speed: float = .5,
             directional_search_max_offset: float = .04) -> dict:
    """Replay one clip through a single tracker configuration and summarize it."""
    import cv2
    tracker = MediaPipeTracker(
        backend=backend, inference_threads=threads, model_path=model, mirror=True,
        tracking_confidence=tracking_confidence,
        tracking_roi_scale=tracking_roi_scale,
        tracking_roi_shift_x=tracking_roi_shift[0],
        tracking_roi_shift_y=tracking_roi_shift[1],
        use_previous_landmarks=palm_detection_mode == "tracked",
        detection_confidence=detection_confidence,
        model_complexity=model_complexity,
        fused_preprocessing=fused_preprocessing,
        palm_inference_threads=palm_inference_threads,
        tracking_roi_scale_x=tracking_roi_scale_x,
        tracking_roi_scale_y=tracking_roi_scale_y,
        directional_search=directional_search,
        directional_search_gain=directional_search_gain,
        directional_search_min_speed=directional_search_min_speed,
        directional_search_max_offset=directional_search_max_offset,
        tracking_evidence=True,
    )
    tracker.preview_enabled = preview
    tracker.diagnostics_enabled = preview
    capture = cv2.VideoCapture(str(clip))
    source_fps = effective_fps or capture.get(cv2.CAP_PROP_FPS) or 30.0
    inference = []
    detected = []
    observations = []
    motion_samples = []
    tracking_paths = []
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
            cue = next(
                (item for item in cues if item["start"] <= elapsed < item["end"]),
                None,
            )
            frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
            started = time.monotonic()
            result = tracker.process(frame, elapsed)
            finished = time.monotonic()
            inference.append((finished - started) * 1000)
            detected.append(result.observation.detected)
            tracking_paths.append({
                "path": result.diagnostics.get("tracking_path", "unavailable"),
                "frame": frame_index,
                "elapsed": elapsed,
                "cue": None if cue is None else cue["label"],
                "ms": (finished - started) * 1000,
                "detected": result.observation.detected,
                "recovery_gap_ms": result.diagnostics.get("recovery_gap_ms"),
                "recovery_missing_span_ms": (
                    result.diagnostics.get("recovery_missing_span_ms")
                ),
                "recovery_inference_ms": (
                    result.diagnostics.get("last_recovery_inference_ms")
                    if result.diagnostics.get("tracking_recovered") else None
                ),
            })
            state = engine.update(result.observation)
            item = result.observation
            motion_samples.append({
                "frame": frame_index, "elapsed": elapsed,
                "detected": item.detected, "confidence": item.confidence,
                "confidence_source": item.confidence_source,
                "x": item.palm_x if item.detected else None,
                "y": item.palm_y if item.detected else None,
                "scale": item.palm_scale if item.detected else None,
                "palm_anchors": result.palm_anchors if item.detected else {},
                "directional_search_active": bool(
                    result.diagnostics.get("directional_search_active", False)
                ),
                "directional_search_offset": result.diagnostics.get(
                    "directional_search_offset", (0.0, 0.0)
                ),
            })
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
                    "confidence_source": item.confidence_source,
                    "x": item.palm_x, "y": item.palm_y,
                    "scale": item.palm_scale, "roll": item.roll,
                    "thumb": item.thumb_curl, "index": item.index_curl,
                    "middle": item.middle_curl, "ring": item.ring_curl,
                    "pinky": item.pinky_curl,
                    "palm_anchors": result.palm_anchors,
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
        "backend": backend, "threads": threads,
        "palm_inference_threads": palm_inference_threads or threads,
        "tracking_confidence": tracking_confidence, "resize": list(size),
        "tracking_roi_scale": tracking_roi_scale,
        "tracking_roi_scale_x": tracking_roi_scale_x or tracking_roi_scale,
        "tracking_roi_scale_y": tracking_roi_scale_y or tracking_roi_scale,
        "tracking_roi_shift": {"x": tracking_roi_shift[0], "y": tracking_roi_shift[1]},
        "tracking_roi_lane": roi_shift_lane_label(*tracking_roi_shift),
        "tracking_roi_shift_research_only": tracking_roi_shift != (0.0, 0.0),
        "palm_detection_mode": palm_detection_mode,
        "detection_confidence": detection_confidence,
        "model_complexity": model_complexity,
        "frame_preparation": "fused" if fused_preprocessing else "current",
        "directional_search": directional_search,
        "directional_search_gain": directional_search_gain,
        "directional_search_min_speed": directional_search_min_speed,
        "directional_search_max_offset": directional_search_max_offset,
        "preview": "open" if preview else "closed", "frames": frame_index,
        "inference_ms": {"p50": percentile(inference, .50),
                         "p95": percentile(inference, .95),
                         "mean": round(sum(inference) / len(inference), 2) if inference else None},
        "preview_encode_ms": {"p50": percentile(encoded_ms, .50),
                              "p95": percentile(encoded_ms, .95)},
        "detection_continuity_percent": round(sum(detected) / len(detected) * 100, 2) if detected else 0,
        "tracking_path_summary": tracking_path_summary(tracking_paths),
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
    result.add_argument("--threads", nargs="+", type=int, choices=(1, 2, 4))
    result.add_argument(
        "--palm-threads", nargs="+", type=int, choices=(1, 2, 4),
        help="replay research only: palm-detector threads; landmark threads remain --threads",
    )
    result.add_argument("--tracking-confidences", nargs="+", type=float,
                        choices=(.10, .20, .25, .30, .35, .40, .45, .50, .55, .60))
    result.add_argument("--tracking-roi-scales", nargs="+", type=float,
                        choices=(2.0, 2.1, 2.15, 2.2, 2.25, 2.3, 2.35,
                                 2.4, 2.6, 2.8, 3.0))
    result.add_argument(
        "--tracking-roi-x-scales", nargs="+", type=float,
        choices=(2.0, 2.1, 2.15, 2.2, 2.25, 2.3, 2.35, 2.4, 2.45,
                 2.5, 2.6, 2.8, 3.0),
        help="replay research only: override horizontal next-frame ROI scale",
    )
    result.add_argument(
        "--tracking-roi-shift", action="append", type=parse_roi_shift,
        help=("replay research only: add one fixed ROI-local X,Y shift to the "
              "next-frame landmark region; repeat this option for multiple lanes"),
    )
    result.add_argument("--palm-detection-modes", nargs="+",
                        choices=("tracked", "every-frame"))
    result.add_argument("--detection-confidences", nargs="+", type=float,
                        choices=(.30, .35, .40, .45, .50, .55, .60))
    result.add_argument("--model-complexities", nargs="+", type=int,
                        choices=(0, 1))
    result.add_argument("--preview", choices=("closed", "open", "both"))
    result.add_argument(
        "--frame-preparations", nargs="+", choices=("current", "fused"),
        help="compare the current two-step transform with fused full-colour preparation",
    )
    result.add_argument(
        "--directional-search-modes", nargs="+", choices=("off", "on"),
        help="replay research only: compare conditional direction-aware input search",
    )
    result.add_argument("--directional-search-gains", nargs="+", type=float)
    result.add_argument("--directional-search-min-speeds", nargs="+", type=float)
    result.add_argument("--directional-search-max-offsets", nargs="+", type=float)
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
    focused = bool(args.threads or args.palm_threads or args.tracking_confidences
                   or args.tracking_roi_scales or args.tracking_roi_x_scales
                   or args.tracking_roi_shift
                   or args.palm_detection_modes
                   or args.detection_confidences or args.model_complexities
                   or args.frame_preparations or args.directional_search_modes
                   or args.directional_search_gains
                   or args.directional_search_min_speeds
                   or args.directional_search_max_offsets or args.preview)
    sizes = ((640, 480),) if args.quick or focused else ((640, 480), (512, 384))
    previews = ((False,) if args.preview in (None, "closed") else
                (True,) if args.preview == "open" else (False, True))
    if not args.quick and not focused:
        previews = (False, True)
    threads_to_test = tuple(args.threads or ((2,) if args.quick or focused else (1, 2, 4)))
    palm_threads_to_test = tuple(args.palm_threads or (None,))
    confidences = tuple(args.tracking_confidences or (.55,))
    roi_scales = tuple(args.tracking_roi_scales or (2.0,))
    roi_x_scales = tuple(args.tracking_roi_x_scales or (None,))
    roi_shifts = tuple(args.tracking_roi_shift or ((0.0, 0.0),))
    palm_modes = tuple(args.palm_detection_modes or ("tracked",))
    detection_confidences = tuple(args.detection_confidences or (.55,))
    model_complexities = tuple(args.model_complexities or (0,))
    frame_preparations = tuple(args.frame_preparations or ("fused",))
    directional_modes = tuple(args.directional_search_modes or ("off",))
    directional_gains = tuple(args.directional_search_gains or (.275,))
    directional_min_speeds = tuple(args.directional_search_min_speeds or (.5,))
    directional_max_offsets = tuple(args.directional_search_max_offsets or (.04,))
    for size in sizes:
        for preview in previews:
            for threads in threads_to_test:
                for palm_threads in palm_threads_to_test:
                    for confidence in confidences:
                        for roi_scale in roi_scales:
                            for roi_x_scale in roi_x_scales:
                                for roi_shift in roi_shifts:
                                    for palm_mode in palm_modes:
                                        for detection_confidence in detection_confidences:
                                            for model_complexity in model_complexities:
                                                for preparation in frame_preparations:
                                                    for directional_mode in directional_modes:
                                                        for directional_gain in directional_gains:
                                                            for directional_speed in directional_min_speeds:
                                                                for directional_offset in directional_max_offsets:
                                                                    lanes.append(run_lane(
                                                                        args.clip, "legacy", threads, size, preview,
                                                                        None, cues, confidence, roi_scale, roi_shift,
                                                                        palm_mode, detection_confidence, model_complexity,
                                                                        preparation == "fused", palm_threads,
                                                                        roi_x_scale, None,
                                                                        frame_times, effective_fps,
                                                                        directional_mode == "on", directional_gain,
                                                                        directional_speed, directional_offset,
                                                                    ))
            if args.model is not None and not args.quick:
                lanes.append(run_lane(
                    args.clip, "tasks-video", 1, size, preview, args.model, cues,
                    .55, 2.0, (0.0, 0.0), "tracked", .55, 0, True, None,
                    None, None,
                    frame_times, effective_fps,
                ))
    result = {
        "version": 2, "clip": str(args.clip), "full_frame_resize_only": True,
        "fixed_roi_shift_scope": "replay research only; production remains zero shift",
        "directional_search_scope": "replay research only; production remains disabled",
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
