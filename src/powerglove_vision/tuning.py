# Project: PowerGlove Vision
# File: src/powerglove_vision/tuning.py
# Purpose: Record gesture measurements and manage expiring global threshold previews.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added guided gesture sampling and persistent personal thresholds.
# Full history: docs/CHANGELOG.md and Git history.

"""Personal threshold overlays; samples and previews never become camera recordings."""
from __future__ import annotations

import copy
import json
import math
import threading
import time
from dataclasses import replace
from pathlib import Path

CHANNELS = ("left", "right", "up", "down", "thumb", "index", "middle", "ring", "pinky",
            "roll_left", "roll_right", "push", "pull")
FINGERS = ("thumb", "index", "middle", "ring", "pinky")
GESTURES = {key: {key: True} for key in CHANNELS}
GESTURES.update(start={"index": False, "middle": False, "ring": True, "pinky": True},
                select={"thumb": False, "index": True, "middle": True, "ring": True, "pinky": True},
                closed_hand={key: True for key in FINGERS}, menu_guard={"thumb": True, "ring": True})
LABELS = {key: key.replace("_", " ").capitalize() for key in GESTURES}
LABELS.update({key: "Curl " + key + " finger" for key in FINGERS})
LABELS["thumb"] = "Curl thumb"
LABELS.update(start="Start — V sign", select="Select — thumbs-up", closed_hand="Closed hand",
              menu_guard="Menu guard — thumb and ring", push="Push toward camera", pull="Pull away from camera",
              roll_left="Roll wrist left", roll_right="Roll wrist right")


def validate_overrides(values: dict) -> dict:
    """Require bounded activation/release pairs for known independent channels."""
    if not isinstance(values, dict) or set(values) - set(CHANNELS):
        raise ValueError("Unknown gesture threshold.")
    for channel, pair in values.items():
        if not isinstance(pair, dict) or set(pair) != {"on", "off"}:
            raise ValueError("Each gesture needs activation and release values.")
        maximum = 1.0 if channel in FINGERS or channel == "pull" else 2.0 if channel.startswith("roll") else 4.0
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in pair.values()):
            raise ValueError("Thresholds must be finite numbers.")
        if not 0 <= pair["off"] < pair["on"] <= maximum:
            raise ValueError("Release must be below activation; values must be between zero and " + str(maximum))
    return copy.deepcopy(values)


def measurements(observation, calibration):
    """Expose the same unclipped normalized signals used by gameplay recognition."""
    if calibration is None or not observation.detected:
        return {}
    dx = (observation.palm_x - calibration.palm_x) / calibration.palm_scale
    dy = (observation.palm_y - calibration.palm_y) / calibration.palm_scale
    depth = observation.palm_scale / calibration.palm_scale - 1
    angle = observation.roll - calibration.roll
    roll = math.atan2(math.sin(angle), math.cos(angle)) / (math.pi / 2)
    return dict(observation.fingers, left=-dx, right=dx, up=-dy, down=dy,
                roll_left=-roll, roll_right=roll, push=depth, pull=-depth)


def percentile(values, fraction):
    """Return a deterministic nearest-rank statistic without another dependency."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def suggest(gesture: str, phases: list) -> dict:
    """Separate rest noise from three consistent performed-and-released gestures."""
    if len(phases) != 7 or any(len(phase) < 12 for phase in phases):
        raise ValueError("Record the baseline and all three gesture-and-release repetitions.")
    suggestion = {}
    for channel, positive in GESTURES[gesture].items():
        # Extended fingers in a menu pose often also remain extended at rest.
        # Keep their current thresholds rather than inventing an unsupported adjustment.
        rest = [sample[channel] for i in (0, 2, 4, 6) for sample in phases[i]]
        active = [[sample[channel] for sample in phases[i]] for i in (1, 3, 5)]
        if not positive:
            continue
        low = max(0.0, percentile(rest, .95))
        high = min(percentile(repetition, .10) for repetition in active)
        gap = high - low
        if gap < .08:
            raise ValueError("The resting and performed measurements overlap for " + channel + ". Try a clearer movement and fully release it.")
        suggestion[channel] = {"on": round(low + gap * .65, 4), "off": round(low + gap * .30, 4)}
    return validate_overrides(suggestion)


class TuningManager:
    """Own one leased tuning session and commit only explicitly saved overlays."""
    def __init__(self, path, clock=time.monotonic):
        self.path, self.clock = Path(path), clock
        self.lock = threading.RLock()
        self.saved = {}
        self.error = None
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text())
                if data.get("version") != 1:
                    raise ValueError("Unsupported tuning version")
                self.saved = validate_overrides(data["thresholds"])
        except (OSError, ValueError, KeyError, TypeError):
            self.error = "Saved tuning could not be loaded; using supplied defaults. Restore defaults to replace the invalid file."
        self.session = None
        self.expires = 0
        self.gesture = "index"
        self.preview = None
        self.phases = []
        self.recording = None
        self.latest = {}
        self.last_observed = -100.0
        self.ready = False
        self.effective = {}
        self.revision = 0
        self.last_frame = None
        self.calibration = None

    def _expire(self):
        """Discard temporary state when the browser lease ends."""
        if self.session and self.clock() >= self.expires:
            self.session = None
            self.preview = None
            self.phases = []
            self.recording = None
            self.revision += 1
        if self.recording and self.clock() - self.recording[0] >= 3:
            samples = self.recording[1]
            self.recording = None
            if len(samples) >= 12:
                self.phases.append(samples)
                self.error = None
            else:
                self.error = "Not enough clear hand measurements. Keep your palm visible and retry this step."

    def active(self) -> bool:
        """Return whether an unexpired tuning owner exists."""
        with self.lock:
            self._expire()
            return self.session is not None

    def configuration(self, config):
        """Overlay personal or preview thresholds without altering shipped defaults."""
        with self.lock:
            self._expire()
            values = dict(self.saved)
            values.update(self.preview or {})
            return replace(config, thresholds=copy.deepcopy(values))

    def snapshot(self) -> dict:
        """Return browser-safe progress and measurements without recording images."""
        with self.lock:
            self._expire()
            return {"active": bool(self.session), "gesture": self.gesture,
                    "gestures": LABELS, "components": list(GESTURES[self.gesture]),
                    "saved": copy.deepcopy(self.saved), "effective": copy.deepcopy(self.effective),
                    "preview": copy.deepcopy(self.preview), "measurements": dict(self.latest),
                    "recording": self.recording is not None, "completed_phases": len(self.phases),
                    "samples": len(self.recording[1]) if self.recording else 0,
                    "ready": self.ready and self.clock() - self.last_observed < 2,
                    "error": self.error, "revision": self.revision}

    def invalidate(self):
        """Invalidate measurement sessions after an explicit neutral calibration."""
        with self.lock:
            self.phases, self.recording, self.preview = [], None, None
            self.revision += 1
            self.error = "Neutral calibration changed. Record a new baseline."

    def observe(self, observation, calibration, config, calibrated):
        """Sample each worker frame once, accepting only calibrated high-confidence hands."""
        with self.lock:
            self._expire()
            self.last_observed = self.clock()
            self.ready = calibrated and observation.detected and observation.confidence >= .7
            self.latest = measurements(observation, calibration)
            self.effective = {key: dict(zip(("on", "off"), config.pair(key))) for key in CHANNELS}
            if self.calibration is not None and calibration != self.calibration and self.session:
                self.invalidate()
            self.calibration = calibration
            if not self.recording:
                return
            started, samples = self.recording
            if (calibrated and observation.detected and observation.confidence >= .7
                    and observation.timestamp != self.last_frame and len(samples) < 180
                    and all(math.isfinite(v) for v in self.latest.values())):
                samples.append(dict(self.latest))
            self.last_frame = observation.timestamp
            if self.clock() - started >= 3:
                self.recording = None
                if len(samples) < 12:
                    self.error = "Not enough clear hand measurements. Keep your palm visible and retry this step."
                else:
                    self.phases.append(samples)
                    self.error = None

    def command(self, data: dict) -> dict:
        """Validate ownership, stage recordings, preview changes, and atomically save."""
        from .game_registry import atomic_write
        with self.lock:
            self._expire()
            action, session = data.get("action"), data.get("session")
            if not isinstance(session, str) or not 8 <= len(session) <= 128 or not all(c.isalnum() or c in "-_" for c in session):
                raise ValueError("A valid tuning session is required.")
            if action == "begin":
                if self.session and self.session != session:
                    raise ValueError("Another Learn tab is tuning. Close it or wait for its session to expire.")
                self.session, self.expires = session, self.clock() + 6
            elif self.session != session:
                raise ValueError("Tuning session expired. Switch to Tune again.")
            else:
                self.expires = self.clock() + 6
            if action in ("begin", "heartbeat"):
                return self.snapshot()
            if action == "end":
                self.expires = 0
                self._expire()
            elif action == "select":
                gesture = data.get("gesture")
                if gesture not in GESTURES:
                    raise ValueError("Choose a supported gesture.")
                self.gesture, self.phases, self.recording, self.preview = gesture, [], None, None
                self.error = None
                self.revision += 1
            elif action == "record":
                if self.recording or len(self.phases) >= 7:
                    raise ValueError("Finish or restart this recording first.")
                self.error = None
                self.recording = (self.clock(), [])
            elif action == "suggest":
                self.preview = suggest(self.gesture, self.phases)
                self.revision += 1
            elif action in ("preview", "save"):
                values = validate_overrides(data.get("thresholds"))
                if not values or set(values) - set(GESTURES[self.gesture]):
                    raise ValueError("Adjust only the selected gesture's components.")
                if action == "save":
                    merged = dict(self.saved, **values)
                    atomic_write(self.path, json.dumps({"version": 1, "thresholds": merged}, indent=2) + "\n")
                    self.saved, self.preview = merged, None
                else:
                    self.preview = values
                self.error = None
                self.revision += 1
            elif action == "reset":
                merged = {k: v for k, v in self.saved.items() if k not in GESTURES[self.gesture]}
                atomic_write(self.path, json.dumps({"version": 1, "thresholds": merged}, indent=2) + "\n")
                self.saved, self.preview, self.error = merged, None, None
                self.revision += 1
            elif action == "discard":
                self.phases, self.recording, self.preview, self.error = [], None, None, None
                self.revision += 1
            else:
                raise ValueError("Unknown tuning operation.")
            return self.snapshot()
