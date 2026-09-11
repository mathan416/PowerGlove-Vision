#!/usr/bin/env python3
# Project: VirtualGlove
# File: scripts/benchmark-palm-anchors.py
# Purpose: Compare pose stability and deliberate travel of MediaPipe palm anchors.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Added pose-stability and retained-travel anchor selection.
# Full history: docs/CHANGELOG.md and Git history.

"""Select a pose-stable palm anchor from a labeled vision replay report."""

import argparse
import json
import math
import statistics
from pathlib import Path


BASELINE = "five_point_average"
POSE_CUES = {
    "a", "b", "roll_left", "roll_right", "closed_hand",
    "start", "select", "menu_guard", "push", "pull",
}
MOVEMENT_CUES = {"slow_xy", "fast_xy", "short_directions"}


def percentile(values, fraction):
    """Return one nearest-rank percentile from a numeric sequence."""
    values = sorted(values)
    if not values:
        return None
    return values[min(len(values) - 1, math.ceil(len(values) * fraction) - 1)]


def cue_at(elapsed, cues):
    """Resolve the labeled recording cue active at an elapsed time."""
    return next((cue["label"] for cue in cues
                 if cue["start"] <= elapsed < cue["end"]), None)


def span(points, axis):
    """Measure one axis of a collection of X/Y points."""
    values = [point[axis] for point in points]
    return max(values) - min(values) if values else 0.0


def compare(document, lane_index=0):
    """Compare every retained anchor against the existing calibration anchor."""
    lanes = document.get("lanes", [])
    if not 0 <= lane_index < len(lanes):
        raise ValueError("Replay report does not contain the requested lane")
    samples = lanes[lane_index].get("motion_samples", [])
    cues = document.get("cues", [])
    names = sorted({name for row in samples for name in row.get("palm_anchors", {})})
    if BASELINE not in names:
        raise ValueError("Replay report does not contain palm-anchor candidates")
    results = {}
    for name in names:
        tagged = [(row, row["palm_anchors"][name], cue_at(row["elapsed"], cues))
                  for row in samples if name in row.get("palm_anchors", {})]
        neutral = [point for _row, point, cue in tagged if cue and cue.startswith("neutral")]
        if not neutral:
            raise ValueError("Replay needs detected neutral cue samples")
        centre = (statistics.median(point[0] for point in neutral),
                  statistics.median(point[1] for point in neutral))
        pose_shifts = []
        for label in POSE_CUES:
            points = [point for _row, point, cue in tagged if cue == label]
            if points:
                pose_centre = (statistics.median(point[0] for point in points),
                               statistics.median(point[1] for point in points))
                pose_shifts.append(math.hypot(pose_centre[0] - centre[0],
                                              pose_centre[1] - centre[1]))
        movement = [point for _row, point, cue in tagged if cue in MOVEMENT_CUES]
        results[name] = {
            "samples": len(tagged),
            "neutral_span": {"x": span(neutral, 0), "y": span(neutral, 1)},
            "pose_shift_p95": percentile(pose_shifts, .95),
            "movement_span": {"x": span(movement, 0), "y": span(movement, 1)},
        }
    baseline = results[BASELINE]
    detection = [bool(row.get("detected", bool(row.get("palm_anchors"))))
                 for row in samples]
    reacquisitions = sum(
        not previous and current for previous, current in zip(detection, detection[1:])
    )
    accepted = []
    for name, result in results.items():
        if name == BASELINE or baseline["pose_shift_p95"] in (None, 0):
            continue
        retained = {
            axis: (result["movement_span"][axis] / baseline["movement_span"][axis]
                   if baseline["movement_span"][axis] else None)
            for axis in ("x", "y")
        }
        result["movement_retained"] = retained
        if (result["pose_shift_p95"] <= baseline["pose_shift_p95"] * .75
                and all(value is None or value >= .99 for value in retained.values())):
            accepted.append(name)
    accepted.sort(key=lambda name: (
        results[name]["pose_shift_p95"],
        results[name]["neutral_span"]["x"] + results[name]["neutral_span"]["y"],
        name,
    ))
    return {
        "version": 1,
        "source_replay": document.get("clip"),
        "source_lane": lane_index,
        "baseline": BASELINE,
        "detection_continuity_percent": (
            sum(detection) / len(detection) * 100 if detection else 0
        ),
        "reacquisition_count": reacquisitions,
        "results": results,
        "selected_candidate": accepted[0] if accepted else None,
        "selection_rule": "At least 25% less pose shift and at least 99% retained X/Y travel",
        "limitation": "Pose cues must be recorded without intentional palm translation.",
    }


def main():
    """Read a replay report and exclusively create an aggregate comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    parser.add_argument("--lane", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(json.loads(args.replay.read_text()), args.lane)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(args.output),
                      "selected_candidate": report["selected_candidate"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
