#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/compare-motion-matrix.py
# Purpose: Compare controlled native-motion trace configurations.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Kept trace-name parsing compatible with RetroPie Python 3.7.
#   2026-09-06 - Added controlled smoothing-matrix comparison.
# Full history: docs/CHANGELOG.md and Git history.

"""Compare a directory of motion traces using the shared trace analyzer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("motion_trace", ROOT / "scripts/analyze-motion-trace.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def compare(directory):
    """Return aggregate rows for conventionally named trace files."""
    rows = []
    for path in sorted(Path(directory).glob("min*.trace.json")):
        result = MODULE.analyze(path)
        name = path.name[:-len(".trace.json")]
        try:
            minimum, boost = name.split("-boost")
            minimum = float(minimum[len("min"):])
            boost = int(boost)
        except ValueError:
            minimum = boost = None
        rows.append({"configuration": name, "minimum_smoothing": minimum,
                     "motion_boost": boost, "vision_events": result["vision_events"],
                     "valid_percent": result["valid_percent"],
                     "tracking_losses": result["tracking_losses"],
                     "trace_dropped": result["trace_dropped"],
                     "recognition_age_ms": result["recognition_source_age_ms"],
                     "error_x": result["selected_filtered_error_x"],
                     "error_y": result["selected_filtered_error_y"],
                     "movement_classes": result["movement_classes"],
                     "fallback_reasons": result["fallback_reasons"]})
    return {"rows": rows,
            "interpretation": [
                "Rows are comparable only when the same movement sequence and camera conditions were used.",
                "Validity, tracking losses, and recognition age are confounders for settling metrics.",
                "A trace-only matrix cannot measure physical hand-to-screen latency.",
                "The 250 ms freshness limit, 320 px flow width, and 25 ms correction budget are not varied."]}


def main():
    """Create a JSON comparison and print its compact table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.directory)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print("configuration valid_percent losses age_p95_ms medium_settle_p95_ms")
    for row in result["rows"]:
        medium = row["movement_classes"]["medium"]["settling_ms"]["p95"]
        age = row["recognition_age_ms"]["p95"]
        print("%s %.2f %d %s %s" % (row["configuration"], row["valid_percent"],
                                     row["tracking_losses"], age, medium))


if __name__ == "__main__":
    main()
