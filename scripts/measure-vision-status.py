#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/measure-vision-status.py
# Purpose: Collect a read-only, aggregate baseline from fresh vision status samples.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Added bounded status sampling before camera-to-game latency tuning.
# Full history: docs/CHANGELOG.md and Git history.

"""Measure observed vision stages without opening the camera or changing controls."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


TIMINGS = (
    "capture_age_ms", "capture_interval_ms", "inference_ms",
    "inference_interval_ms", "send_ms", "sample_age_ms",
)
CONDITIONS = (
    "active_profile", "vision_profile", "practice_mode", "controller_enabled",
    "controller_context_active", "tracker_backend", "camera_width", "camera_height",
    "camera_format", "camera_fps", "preview_clients", "version",
)
LIMITATIONS = [
    "Status polling observes a subset of inference results, not every camera frame.",
    "Public status is cached by the supervisor; poll round trips are not gameplay latency.",
    "Camera timestamps begin after OpenCV read, excluding exposure and driver buffering.",
    "Inference includes tracking and gesture processing; send is the local send attempt.",
    "UDP send success does not confirm network reception or native-state publication.",
    "Network reception, receiver validation/publication, core pickup, and display are unmeasured.",
    "Do not subtract monotonic timestamps from different machines or add stage percentiles.",
    "Neutral axis variation includes physical hand motion; it is not isolated tracker noise.",
]


def finite(value) -> bool:
    """Accept finite numbers but reject booleans and nonnumeric status fields."""
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def summarize(values: list[float]) -> dict:
    """Summarize this observation window, never averaging rolling percentiles."""
    if not values:
        return {"samples": 0}
    ordered = sorted(values)
    return {
        "samples": len(values),
        "p50": round(ordered[math.ceil(len(values) * .50) - 1], 3),
        "p95": round(ordered[math.ceil(len(values) * .95) - 1], 3),
        "max": round(ordered[-1], 3),
    }


class StatusWindow:
    """Deduplicate inference observations and separate changing run conditions."""

    def __init__(self, phase: str) -> None:
        self.phase = phase
        self.polls = self.duplicates = self.inactive = self.invalid = self.errors = 0
        self.round_trips = []
        self.seen = set()
        self.segments = []
        self.current = None
        self.last_identity = None

    def observe(self, status: dict, round_trip_ms: float) -> None:
        """Retain allowlisted aggregates only; ignore cached, idle, or malformed samples."""
        self.polls += 1
        self.round_trips.append(round_trip_ms)
        if not isinstance(status, dict):
            self.invalid += 1
            return
        if status.get("vision_state") != "active":
            self.inactive += 1
            self.current = None
            return
        timestamp, sequence = status.get("timestamp"), status.get("capture_sequence")
        if not finite(timestamp) or timestamp < 0 or type(sequence) is not int or sequence < 1:
            self.invalid += 1
            return
        # Timestamp disambiguates capture restarts and profile sequence resets.
        identity = (timestamp, sequence)
        if identity in self.seen:
            self.duplicates += 1
            return
        self.seen.add(identity)
        if self.last_identity is not None and (
                timestamp <= self.last_identity[0] or sequence <= self.last_identity[1]):
            self.current = None
        self.last_identity = identity
        conditions = {key: status.get(key) for key in CONDITIONS
                      if type(status.get(key)) in (str, bool)
                      or finite(status.get(key))}
        if self.current is None or self.current["conditions"] != conditions:
            self.current = {"conditions": conditions, "observed_samples": 0,
                            "detected_samples": 0, "calibrated_samples": 0,
                            "local_send_success_samples": 0,
                            "timings": {key: [] for key in TIMINGS},
                            "detected_inference_ms": [], "missing_hand_inference_ms": [],
                            "capture_skips": [],
                            "sent_sample_age_ms": [], "axes": {"x": [], "y": []}}
            self.segments.append(self.current)
        segment = self.current
        segment["observed_samples"] += 1
        for field in ("detected", "calibrated"):
            segment[field + "_samples"] += int(status.get(field) is True)
        sent = status.get("receiver_available") is True
        segment["local_send_success_samples"] += int(sent)
        for key in TIMINGS:
            value = status.get(key)
            if finite(value) and value >= 0:
                segment["timings"][key].append(value)
        age = status.get("sample_age_ms")
        inference = status.get("inference_ms")
        if finite(inference) and inference >= 0:
            key = "detected_inference_ms" if status.get("detected") is True else "missing_hand_inference_ms"
            segment[key].append(inference)
        skipped = status.get("capture_skipped_total")
        if type(skipped) is int and skipped >= 0:
            segment["capture_skips"].append(skipped)
        if sent and finite(age) and age >= 0:
            segment["sent_sample_age_ms"].append(age)
        if self.phase == "neutral" and status.get("detected") is True and status.get("calibrated") is True:
            axes = status.get("axes", {})
            if isinstance(axes, dict):
                for key in ("x", "y"):
                    value = axes.get(key)
                    if finite(value) and -32767 <= value <= 32767:
                        segment["axes"][key].append(value)

    def report(self, elapsed: float) -> dict:
        """Export aggregate timings with explicit missing-stage and sampling boundaries."""
        segments = []
        for segment in self.segments:
            result = {key: value for key, value in segment.items()
                      if key not in ("timings", "sent_sample_age_ms", "axes", "capture_skips",
                                     "detected_inference_ms", "missing_hand_inference_ms")}
            result["timings_ms"] = {key: summarize(values) for key, values in segment["timings"].items()}
            for key in ("detected_inference_ms", "missing_hand_inference_ms"):
                result[key] = summarize(segment[key])
            skips = segment["capture_skips"]
            result["capture_skipped_delta"] = skips[-1] - skips[0] if len(skips) >= 2 else None
            result["sent_sample_age_ms"] = summarize(segment["sent_sample_age_ms"])
            if self.phase == "neutral":
                result["neutral_axis_variation"] = {
                    key: {"samples": len(values), "span": max(values) - min(values),
                          "standard_deviation": round(statistics.pstdev(values), 3)}
                    for key, values in segment["axes"].items() if values
                }
            segments.append(result)
        return {
            "format": 1, "phase": self.phase,
            "elapsed_seconds": round(elapsed, 3),
            "polls": self.polls, "request_errors": self.errors,
            "duplicate_polls": self.duplicates, "inactive_polls": self.inactive,
            "invalid_polls": self.invalid, "observed_samples": len(self.seen),
            "status_round_trip_ms": summarize(self.round_trips),
            "segments": segments, "limitations": LIMITATIONS,
        }


def status_url(value: str) -> str:
    """Require a credential-free explicit HTTP(S) status endpoint."""
    url = urlsplit(value)
    if (url.scheme not in ("http", "https") or not url.hostname
            or url.username or url.password or url.query or url.fragment
            or url.path != "/status"):
        raise argparse.ArgumentTypeError("Use http(s)://HOST:PORT/status without credentials or query parameters")
    return value


def collect(url: str, duration: float, interval: float, phase: str) -> dict:
    """Poll with bounded reads and deadlines without invoking any mutation endpoint."""
    window = StatusWindow(phase)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.monotonic()
    deadline = started + duration
    while time.monotonic() < deadline:
        before = time.monotonic()
        try:
            with opener.open(url, timeout=min(2, max(.01, deadline - before))) as response:
                body = response.read(262145)
            if len(body) > 262144:
                raise ValueError("Status exceeds limit")
            status = json.loads(body)
            window.observe(status, (time.monotonic() - before) * 1000)
        except (OSError, ValueError, RecursionError):
            window.errors += 1
        time.sleep(max(0, min(interval - (time.monotonic() - before), deadline - time.monotonic())))
    return window.report(time.monotonic() - started)


def main() -> int:
    """Collect a bounded baseline and refuse to overwrite an existing report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-url", type=status_url, required=True)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--interval", type=float, default=.1)
    parser.add_argument("--phase", choices=("neutral", "movement", "idle"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600 or not .05 <= args.interval <= 5:
        parser.error("Use 1-600 seconds and a 0.05-5 second polling interval")
    if args.output.exists():
        parser.error("Choose a new output path; existing reports are preserved")
    report = collect(args.status_url, args.seconds, args.interval, args.phase)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print("Observed %d fresh samples; %d request errors. Report: %s" % (
        report["observed_samples"], report["request_errors"], args.output))
    return 0 if report["observed_samples"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
