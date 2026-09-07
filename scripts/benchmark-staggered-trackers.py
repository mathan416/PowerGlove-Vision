#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/benchmark-staggered-trackers.py
# Purpose: Evaluate two staggered MediaPipe Hands graphs without controller output.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Added isolated dual-graph newest-sequence measurements.
# Full history: docs/CHANGELOG.md and Git history.

"""Measure newest-sequence arbitration for two isolated single-thread trackers."""

import argparse
import json
import math
import queue
import threading
import time
from pathlib import Path


def percentile(values, fraction):
    """Return one nearest-rank percentile from a numeric sequence."""
    values = sorted(values)
    return values[min(len(values) - 1, math.ceil(len(values) * fraction) - 1)] if values else None


class Worker:
    """Own one independent single-thread MediaPipe tracker and one pending job."""
    def __init__(self, tracker_class, results):
        self.tracker = tracker_class(inference_threads=1)
        self.tracker.preview_enabled = self.tracker.diagnostics_enabled = False
        self.results = results
        self.jobs = queue.Queue(maxsize=1)
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def submit(self, job):
        """Submit one frame without queuing behind an existing frame."""
        try:
            self.jobs.put_nowait(job)
            return True
        except queue.Full:
            return False

    def run(self):
        """Process submitted frames until the explicit sentinel arrives."""
        while True:
            job = self.jobs.get()
            if job is None:
                return
            sequence, captured_at, frame, submitted_at = job
            result = self.tracker.process(frame, captured_at)
            self.results.put((time.monotonic(), sequence, submitted_at,
                              result.observation.detected))

    def close(self):
        """Drain the pending frame and release this tracker."""
        self.jobs.put(None)
        self.thread.join()
        self.tracker.close()


def run(clip):
    """Pace a clip through two trackers and arbitrate by newest sequence."""
    import cv2
    from powerglove_vision.tracker import MediaPipeTracker

    capture = cv2.VideoCapture(str(clip))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    results = queue.Queue()
    workers = [Worker(MediaPipeTracker, results), Worker(MediaPipeTracker, results)]
    submitted = dropped_busy = 0
    started = time.monotonic()
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            target = started + submitted / fps
            delay = target - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            submitted_at = time.monotonic()
            if not workers[submitted % 2].submit(
                    (submitted + 1, target, frame, submitted_at)):
                dropped_busy += 1
            submitted += 1
    finally:
        capture.release()
        for worker in workers:
            worker.close()
    rows = []
    while not results.empty():
        rows.append(results.get())
    rows.sort()
    newest = 0
    accepted = []
    stale = 0
    for finished, sequence, submitted_at, detected in rows:
        if sequence <= newest:
            stale += 1
            continue
        newest = sequence
        accepted.append((finished, sequence, submitted_at, detected))
    latencies = [(finished - submitted_at) * 1000
                 for finished, _sequence, submitted_at, _detected in accepted]
    intervals = [(second[0] - first[0]) * 1000
                 for first, second in zip(accepted, accepted[1:])]
    elapsed = max(.001, rows[-1][0] - started) if rows else .001
    return {
        "version": 1,
        "controller_output": False,
        "submitted": submitted,
        "busy_drops": dropped_busy,
        "completed": len(rows),
        "accepted": len(accepted),
        "stale_results": stale,
        "accepted_hz": len(accepted) / elapsed,
        "detection_percent": (sum(row[3] for row in accepted) / len(accepted) * 100
                              if accepted else 0),
        "latency_ms": {"p50": percentile(latencies, .50),
                       "p95": percentile(latencies, .95)},
        "accepted_interval_ms": {"p50": percentile(intervals, .50),
                                 "p95": percentile(intervals, .95)},
    }


def main():
    """Validate local inputs and exclusively write the isolated report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clip", type=Path)
    parser.add_argument("--source-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.clip.is_file():
        parser.error("The clip must already exist locally")
    import sys
    sys.path.insert(0, str(args.source_root / "src"))
    report = run(args.clip)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"output": str(args.output),
                      "accepted_hz": report["accepted_hz"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
