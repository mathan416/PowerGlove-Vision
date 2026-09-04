# Project: PowerGlove Vision
# File: src/powerglove_vision/gesture.py
# Purpose: Convert calibrated hand observations into stable gamepad states for supported gesture profiles.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Corrected Program I throttle and turbo output for Knight Rider.
#   2026-09-03 - Persist and restore neutral-hand calibration.
# Full history: docs/CHANGELOG.md and Git history.

"""Convert calibrated hand observations into stable gamepad states for supported gesture profiles."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from collections import deque
from dataclasses import asdict, dataclass, field, replace

from .model import AXIS_MAX, Calibration, ControllerState, HandObservation


def load_calibration(path: Path) -> Calibration | None:
    """Read a finite, versioned neutral reference; reject missing or corrupt data."""
    try:
        data = json.loads(path.read_text())
        if data["version"] != 1:
            return None
        value = Calibration(**data["neutral"])
        if not all(type(v) in (int, float) and math.isfinite(v) for v in asdict(value).values()):
            return None
        if value.palm_scale <= 0:
            return None
        return value
    except (OSError, ValueError, TypeError, KeyError):
        return None


def save_calibration(path: Path, calibration: Calibration) -> None:
    """Atomically persist a completed reference without truncating the previous one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
            name = handle.name
            json.dump({"version": 1, "neutral": asdict(calibration)}, handle, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


PROGRAM_PROFILES = tuple(f"program_{letter}" for letter in "abcdefghi")
GAME_PROFILES = ("bad_street_brawler", "super_glove_ball")
SUPPORTED_PROFILES = PROGRAM_PROFILES + GAME_PROFILES


@dataclass(frozen=True)
class GestureConfig:
    """Hold movement, curl, roll, depth, pulse, and tracking-loss thresholds."""
    move_on: float = 0.38
    move_off: float = 0.24
    curl_on: float = 0.50
    curl_off: float = 0.35
    roll_on: float = 0.58
    roll_off: float = 0.40
    push_on: float = 0.34
    push_off: float = 0.18
    pulse_hz: float = 7.0
    loss_release_ms: int = 120
    thresholds: dict = field(default_factory=dict)

    def pair(self, channel: str) -> tuple[float, float]:
        """Resolve independent personal thresholds over existing profile defaults."""
        if channel in self.thresholds:
            value = self.thresholds[channel]
            return value["on"], value["off"]
        prefix = ("move" if channel in ("left", "right", "up", "down") else
                  "roll" if channel.startswith("roll_") else
                  "push" if channel in ("push", "pull") else "curl")
        return getattr(self, prefix + "_on"), getattr(self, prefix + "_off")

    def menu_limit(self, finger: str, closed: bool, default: float) -> float:
        """Keep legacy menu cutoffs until this finger has a personal adjustment."""
        return self.pair(finger)[0 if closed else 1] if finger in self.thresholds else default


MENU_FINGERS = {
    "start": {"index": False, "middle": False, "ring": True, "pinky": True},
    "select": {"thumb": False, "index": True, "middle": True, "ring": True, "pinky": True},
}


def finger_pose_feedback(config, gesture, requirements, values):
    """Use the same finger boundaries for menu recognition and tuning feedback."""
    feedback = {}
    for finger, closed in requirements.items():
        if finger not in ("thumb", "index", "middle", "ring", "pinky"):
            continue
        value = values.get(finger)
        if gesture in MENU_FINGERS:
            limit = config.menu_limit(finger, closed, .42 if closed else .32 if finger == "thumb" else .28)
            matches = value is not None and (value > limit if closed else value < limit)
        else:
            limit = config.pair(finger)[0 if closed else 1]
            matches = value is not None and (value >= limit if closed else value < limit)
        feedback[finger] = {"expected": "curled" if closed else "extended",
                            "matches": bool(matches), "value": value, "threshold": limit}
    return feedback


def _clamp(value: float, low: float, high: float) -> float:
    """Limit a floating-point value to an inclusive range."""
    return max(low, min(high, value))


def _axis(value: float) -> int:
    """Convert a normalized signed value to the virtual gamepad axis range."""
    return round(_clamp(value, -1.0, 1.0) * AXIS_MAX)


def _circular_delta(value: float, origin: float) -> float:
    """Return the shortest signed angular difference in radians."""
    return math.atan2(math.sin(value - origin), math.cos(value - origin))


class Hysteresis:
    """Track one threshold with separate activation and release points."""
    def __init__(self) -> None:
        self.active = False

    def positive(self, value: float, on: float, off: float) -> bool:
        """Update and return the positive-direction threshold state."""
        self.active = value >= (off if self.active else on)
        return self.active

    def negative(self, value: float, on: float, off: float) -> bool:
        """Update and return the negative-direction threshold state."""
        self.active = value <= -(off if self.active else on)
        return self.active


class HeldGesture:
    """Turns a deliberately held pose into one short button pulse."""

    def __init__(self, hold_seconds: float = 0.7, pulse_seconds: float = 0.18) -> None:
        self.hold_seconds = hold_seconds
        self.pulse_seconds = pulse_seconds
        self.started_at: float | None = None
        self.pulse_until = 0.0
        self.fired = False

    def update(self, matches: bool, now: float) -> bool:
        """Return a short pulse after a pose remains stable for the configured hold time."""
        if not matches:
            self.started_at = None
            self.fired = False
            return now < self.pulse_until
        if self.started_at is None:
            self.started_at = now
        if not self.fired and now - self.started_at >= self.hold_seconds:
            self.fired = True
            self.pulse_until = now + self.pulse_seconds
        return now < self.pulse_until


class GestureEngine:
    """Turns continuous landmark measurements into stable controller state."""

    def __init__(
        self,
        profile: str,
        config: GestureConfig | None = None,
        calibration_frames: int = 24,
        calibration: Calibration | None = None,
    ) -> None:
        if profile not in SUPPORTED_PROFILES:
            raise ValueError(f"unknown profile: {profile}")
        self.profile = profile
        self.config = config or GestureConfig()
        self.calibration_frames = calibration_frames
        self.calibration = calibration
        self._samples: deque[HandObservation] = deque(maxlen=calibration_frames)
        self._calibrating = calibration is None
        self._sequence = 0
        self._last_seen = 0.0
        self._last_state: ControllerState | None = None
        self._push_was_active = False
        self._pull_was_active = False
        self._program_toggle = False
        self._zap_until = 0.0
        self._start_gesture = HeldGesture()
        self._select_gesture = HeldGesture()
        self._switches = {
            name: Hysteresis()
            for name in (
                "left",
                "right",
                "up",
                "down",
                "thumb",
                "index",
                "middle",
                "ring",
                "pinky",
                "roll_left",
                "roll_right",
                "pull",
            )
        }

    @property
    def calibrated(self) -> bool:
        """Return whether a complete neutral-hand calibration is active."""
        return self.calibration is not None and not self._calibrating

    def begin_calibration(self) -> None:
        """Clear prior samples and begin a fresh neutral-hand calibration."""
        self._samples.clear()
        for switch in self._switches.values():
            switch.active = False
        self._calibrating = True
        self._push_was_active = False
        self._pull_was_active = False
        self._program_toggle = False
        self._zap_until = 0.0

    def _collect_calibration(self, observation: HandObservation) -> None:
        """Accumulate valid frames and derive a stable neutral-hand reference."""
        if observation.detected and observation.palm_scale > 0.01:
            self._samples.append(observation)
        if len(self._samples) < self.calibration_frames:
            return
        count = len(self._samples)
        sin_roll = sum(math.sin(item.roll) for item in self._samples)
        cos_roll = sum(math.cos(item.roll) for item in self._samples)
        self.calibration = Calibration(
            palm_x=sum(item.palm_x for item in self._samples) / count,
            palm_y=sum(item.palm_y for item in self._samples) / count,
            palm_scale=max(0.01, sum(item.palm_scale for item in self._samples) / count),
            roll=math.atan2(sin_roll, cos_roll),
        )
        self._calibrating = False

    def curl_feedback(self, observation: HandObservation) -> dict:
        """Expose held finger switches to Learn, independent of game button pulses."""
        ready = self.calibrated and observation.detected
        return {name: bool(ready and self._switches[name].active)
                for name in ("thumb", "index", "middle", "ring", "pinky")}

    def push_feedback(self, observation: HandObservation) -> dict:
        """Expose continuous depth state so Learn cannot miss a one-frame push event."""
        ready = self.calibrated and observation.detected
        depth = observation.palm_scale / self.calibration.palm_scale - 1 if ready else 0.0
        return {"active": bool(ready and self._push_was_active),
                "depth": depth, "threshold": self.config.pair("push")[0]}

    def pull_feedback(self, observation: HandObservation) -> dict:
        """Expose continuous pull recognition in Learn, independent of game mappings."""
        ready = self.calibrated and observation.detected
        depth = 1.0 - observation.palm_scale / self.calibration.palm_scale if ready else 0.0
        return {"active": bool(ready and self._switches["pull"].active),
                "depth": depth, "threshold": self.config.pair("pull")[0]}

    def menu_feedback(self) -> dict:
        """Expose held menu recognition to Learn independently of short button pulses."""
        state = self._last_state
        if not self.calibrated or state is None or not state.detected:
            return {"pose": None, "recognized": False, "held_seconds": 0.0}
        for name, gesture in (("start", self._start_gesture), ("select", self._select_gesture)):
            if gesture.started_at is not None:
                return {"pose": name, "recognized": gesture.fired,
                        "held_seconds": max(0.0, state.timestamp - gesture.started_at)}
        return {"pose": None, "recognized": False, "held_seconds": 0.0}

    def update(self, observation: HandObservation) -> ControllerState:
        """Map one observation to a debounced controller state with safe tracking-loss release."""
        self._sequence += 1
        if self._calibrating:
            self._collect_calibration(observation)
            return ControllerState.released(
                self._sequence, observation.timestamp, self.profile, self.calibrated
            )

        if observation.detected:
            self._last_seen = observation.timestamp
        lost_for = observation.timestamp - self._last_seen
        if not observation.detected and lost_for * 1000 >= self.config.loss_release_ms:
            self._push_was_active = False
            self._zap_until = 0.0
            self._pull_was_active = False
            self._start_gesture.update(False, observation.timestamp)
            self._select_gesture.update(False, observation.timestamp)
            for switch in self._switches.values():
                switch.active = False
            self._last_state = ControllerState.released(
                self._sequence, observation.timestamp, self.profile, self.calibrated
            )
            return self._last_state
        if not observation.detected:
            self._zap_until = 0.0
            if (self.profile == "bad_street_brawler" and self._last_state is not None
                    and self._last_state.dpad.get("left") and self._last_state.dpad.get("right")):
                self._last_state = replace(self._last_state, dpad=dict.fromkeys(self._last_state.dpad, False))
            if self._last_state is not None:
                return replace(
                    self._last_state,
                    sequence=self._sequence,
                    timestamp=observation.timestamp,
                    detected=False,
                    confidence=0.0,
                    events=[],
                )
            return ControllerState.released(
                self._sequence, observation.timestamp, self.profile, self.calibrated
            )

        assert self.calibration is not None
        reference = self.calibration
        # Normalize screen displacement by hand size so the thresholds feel
        # similar at different distances from the camera.
        dx = (observation.palm_x - reference.palm_x) / reference.palm_scale
        dy = (observation.palm_y - reference.palm_y) / reference.palm_scale
        depth = observation.palm_scale / reference.palm_scale - 1.0
        roll = _circular_delta(observation.roll, reference.roll) / (math.pi / 2)

        cfg = self.config
        dpad = {
            "left": self._switches["left"].negative(dx, *cfg.pair("left")),
            "right": self._switches["right"].positive(dx, *cfg.pair("right")),
            "up": self._switches["up"].negative(dy, *cfg.pair("up")),
            "down": self._switches["down"].positive(dy, *cfg.pair("down")),
        }
        thumb = self._switches["thumb"].positive(
            observation.thumb_curl, *cfg.pair("thumb")
        )
        index = self._switches["index"].positive(
            observation.index_curl, *cfg.pair("index")
        )
        middle = self._switches["middle"].positive(
            observation.middle_curl, *cfg.pair("middle")
        )
        for finger in ("ring", "pinky"):
            self._switches[finger].positive(observation.fingers[finger], *cfg.pair(finger))
        roll_left = self._switches["roll_left"].negative(
            roll, *cfg.pair("roll_left")
        )
        roll_right = self._switches["roll_right"].positive(
            roll, *cfg.pair("roll_right")
        )

        events: list[str] = []
        self._switches["pull"].negative(depth, *cfg.pair("pull"))
        pushing = depth >= cfg.pair("push")[1 if self._push_was_active else 0]
        if pushing and not self._push_was_active:
            events.append("glove_zap")
        self._push_was_active = pushing

        # Deliberate, held menu poses avoid needing an electronic glove.
        # V sign = Start; thumbs-up with the four fingers closed = Select.
        start_pose = all(item["matches"] for item in finger_pose_feedback(
            cfg, "start", MENU_FINGERS["start"], observation.fingers).values())
        select_pose = all(item["matches"] for item in finger_pose_feedback(
            cfg, "select", MENU_FINGERS["select"], observation.fingers).values())
        start = self._start_gesture.update(start_pose, observation.timestamp)
        select = self._select_gesture.update(select_pose, observation.timestamp)
        menu_pose = start_pose or select_pose or start or select
        if menu_pose:
            dpad = {name: False for name in dpad}

        pulse_on = int(observation.timestamp * cfg.pulse_hz * 2) % 2 == 0
        if self.profile == "bad_street_brawler":
            buttons = {
                "a": (middle or roll_left or roll_right) and not menu_pose,
                "b": (middle or (thumb and pulse_on)) and not menu_pose,
                "start": start,
                "select": select,
                "glove_zap": pushing,
            }
            if roll_left:
                dpad["left"] = True
            if roll_right:
                dpad["right"] = True
            # The cartridge recognizes its Glove Zap as simultaneous Left+Right.
            # Emit one 180 ms pulse per push edge; never leak it into menu poses.
            if menu_pose:
                self._zap_until = 0.0
            elif "glove_zap" in events:
                self._zap_until = observation.timestamp + 0.18
            if observation.timestamp < self._zap_until:
                dpad = {"left": True, "right": True, "up": False, "down": False}
                buttons["a"] = buttons["b"] = False
        elif self.profile == "super_glove_ball":
            buttons = {
                "a": index and not menu_pose,
                "b": thumb and not menu_pose,
                "start": start,
                "select": select,
                "glove_zap": False,
            }
        else:
            dpad, buttons = self._program_mapping(
                observation, dx, dy, depth, roll, dpad,
                thumb, index, middle, pulse_on, menu_pose, start, select,
            )

        fingers = {
            name: round(_clamp(value, 0.0, 1.0) * 3)
            for name, value in observation.fingers.items()
        }
        self._last_state = ControllerState(
            sequence=self._sequence,
            timestamp=observation.timestamp,
            profile=self.profile,
            detected=True,
            confidence=observation.confidence,
            calibrated=True,
            axes={
                "x": _axis(dx / 1.25),
                "y": _axis(dy / 1.25),
                "z": _axis(depth / 0.75),
                "roll": _axis(roll),
            },
            dpad=dpad,
            buttons=buttons,
            fingers=fingers,
            events=events,
        )
        return self._last_state

    def _program_mapping(
        self,
        observation: HandObservation,
        dx: float,
        dy: float,
        depth: float,
        roll: float,
        dpad: dict[str, bool],
        thumb: bool,
        index: bool,
        middle: bool,
        pulse_on: bool,
        menu_pose: bool,
        start: bool,
        select: bool,
    ) -> tuple[dict[str, bool], dict[str, bool]]:
        """Implement the useful behaviour of the cartridge's Programs A-I.

        These mappings deliberately emit ordinary NES controls, so the target
        game needs no Power Glove support and Bad Street Brawler is not needed
        as a loader.
        """
        profile = self.profile
        a = b = False
        # Consume the recognition states already updated for this frame. These
        # retain activation until release, just like Learn's movement feedback.
        roll_left = self._switches["roll_left"].active
        roll_right = self._switches["roll_right"].active
        pushing = self._push_was_active
        pulling = self._switches["pull"].active

        if profile == "program_a":
            # Pinball: index/right flipper, thumb/left flipper, roll/tilt.
            dpad = {name: False for name in dpad}
            if pulling and not self._pull_was_active:
                self._program_toggle = not self._program_toggle
            self._pull_was_active = pulling
            combined = self._program_toggle and (index or thumb)
            a = index or combined
            dpad["up"] = thumb or combined
            b = (roll_left or roll_right)
        elif profile == "program_b":
            # Joust: lateral steering and pulsed finger flap.
            dpad["up"] = dpad["down"] = False
            a = (index or middle) and pulse_on
            b = thumb
        elif profile == "program_c":
            # Gyruss: wrist rotation, straight index fires, pull back bombs.
            dpad = {name: False for name in dpad}
            dpad["left"] = roll_left
            dpad["right"] = roll_right
            a = observation.index_curl < self.config.pair("index")[1]
            b = pulling
        elif profile == "program_d":
            # Reverse all four directions.
            dpad = {
                "up": dpad["down"], "down": dpad["up"],
                "left": dpad["right"], "right": dpad["left"],
            }
            a, b = thumb, index
        elif profile == "program_e":
            # Defender II: hand position, thumb fire, wrist smart bomb.
            a = thumb
            b = (roll_left or roll_right)
            if observation.ring_curl >= self.config.pair("ring")[0]:
                dpad["left"] = int(observation.timestamp * 12) % 2 == 0
                dpad["right"] = not dpad["left"]
        elif profile == "program_f":
            # Sesame Street: moving an open hand = Yes, closed hand = No.
            moving = any(self._switches[name].active for name in ("left", "right", "up", "down"))
            closed = all(value >= self.config.pair(name)[0] for name, value in observation.fingers.items())
            dpad = {name: False for name in dpad}
            a = moving and not closed
            b = closed
        elif profile == "program_g":
            # Gun.Smoke: position moves; index fires; thumb+ring is a menu guard.
            guarded = thumb and observation.ring_curl >= self.config.pair("ring")[0]
            if (roll_left or roll_right):
                dpad["left"] = roll_left
                dpad["right"] = roll_right
            a = index and not guarded
            b = pushing and not guarded
            if guarded:
                dpad = {name: False for name in dpad}
        elif profile == "program_h":
            # General play/training: conventional motion and pulsed buttons.
            a = index and pulse_on
            b = thumb and pulse_on
        elif profile == "program_i":
            # Knight Rider/driving: wrist steering, finger throttle, hand brake.
            dpad = {name: False for name in dpad}
            dpad["left"] = roll_left
            dpad["right"] = roll_right
            dpad["down"] = self._switches["down"].active
            turbo = pushing
            dpad["up"] = index or turbo
            a = turbo
            b = thumb

        if menu_pose:
            a = b = False
        return dpad, {
            "a": a,
            "b": b,
            "start": start,
            "select": select,
            "glove_zap": False,
        }
