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
# Full history: docs/CHANGELOG.md and Git history.

"""Convert calibrated hand observations into stable gamepad states for supported gesture profiles."""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace

from .model import AXIS_MAX, Calibration, ControllerState, HandObservation


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
    ) -> None:
        if profile not in SUPPORTED_PROFILES:
            raise ValueError(f"unknown profile: {profile}")
        self.profile = profile
        self.config = config or GestureConfig()
        self.calibration_frames = calibration_frames
        self.calibration: Calibration | None = None
        self._samples: deque[HandObservation] = deque(maxlen=calibration_frames)
        self._calibrating = True
        self._sequence = 0
        self._last_seen = 0.0
        self._last_state: ControllerState | None = None
        self._push_was_active = False
        self._pull_was_active = False
        self._program_toggle = False
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
                "roll_left",
                "roll_right",
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
                for name in ("thumb", "index", "middle")}

    def push_feedback(self, observation: HandObservation) -> dict:
        """Expose continuous depth state so Learn cannot miss a one-frame push event."""
        ready = self.calibrated and observation.detected
        depth = observation.palm_scale / self.calibration.palm_scale - 1 if ready else 0.0
        return {"active": bool(ready and self._push_was_active),
                "depth": depth, "threshold": self.config.push_on}

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
            self._start_gesture.update(False, observation.timestamp)
            self._select_gesture.update(False, observation.timestamp)
            for switch in self._switches.values():
                switch.active = False
            self._last_state = ControllerState.released(
                self._sequence, observation.timestamp, self.profile, self.calibrated
            )
            return self._last_state
        if not observation.detected:
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
            "left": self._switches["left"].negative(dx, cfg.move_on, cfg.move_off),
            "right": self._switches["right"].positive(dx, cfg.move_on, cfg.move_off),
            "up": self._switches["up"].negative(dy, cfg.move_on, cfg.move_off),
            "down": self._switches["down"].positive(dy, cfg.move_on, cfg.move_off),
        }
        thumb = self._switches["thumb"].positive(
            observation.thumb_curl, cfg.curl_on, cfg.curl_off
        )
        index = self._switches["index"].positive(
            observation.index_curl, cfg.curl_on, cfg.curl_off
        )
        middle = self._switches["middle"].positive(
            observation.middle_curl, cfg.curl_on, cfg.curl_off
        )
        roll_left = self._switches["roll_left"].negative(
            roll, cfg.roll_on, cfg.roll_off
        )
        roll_right = self._switches["roll_right"].positive(
            roll, cfg.roll_on, cfg.roll_off
        )

        events: list[str] = []
        pushing = depth >= (cfg.push_off if self._push_was_active else cfg.push_on)
        if pushing and not self._push_was_active:
            events.append("glove_zap")
        self._push_was_active = pushing

        # Deliberate, held menu poses avoid needing an electronic glove.
        # V sign = Start; thumbs-up with the four fingers closed = Select.
        start_pose = (
            observation.index_curl < 0.28
            and observation.middle_curl < 0.28
            and observation.ring_curl > 0.42
            and observation.pinky_curl > 0.42
        )
        select_pose = (
            observation.thumb_curl < 0.32
            and observation.index_curl > 0.42
            and observation.middle_curl > 0.42
            and observation.ring_curl > 0.42
            and observation.pinky_curl > 0.42
        )
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

        if profile == "program_a":
            # Pinball: index/right flipper, thumb/left flipper, roll/tilt.
            dpad = {name: False for name in dpad}
            pulling = depth <= -(self.config.push_off if self._pull_was_active else self.config.push_on)
            if pulling and not self._pull_was_active:
                self._program_toggle = not self._program_toggle
            self._pull_was_active = pulling
            combined = self._program_toggle and (index or thumb)
            a = index or combined
            dpad["up"] = thumb or combined
            b = abs(roll) >= self.config.roll_on
        elif profile == "program_b":
            # Joust: lateral steering and pulsed finger flap.
            dpad["up"] = dpad["down"] = False
            a = (index or middle) and pulse_on
            b = thumb
        elif profile == "program_c":
            # Gyruss: wrist rotation, straight index fires, pull back bombs.
            dpad = {name: False for name in dpad}
            dpad["left"] = roll <= -self.config.roll_on
            dpad["right"] = roll >= self.config.roll_on
            a = observation.index_curl < self.config.curl_off
            b = depth <= -self.config.push_on
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
            b = abs(roll) >= self.config.roll_on
            if observation.ring_curl >= self.config.curl_on:
                dpad["left"] = int(observation.timestamp * 12) % 2 == 0
                dpad["right"] = not dpad["left"]
        elif profile == "program_f":
            # Sesame Street: moving an open hand = Yes, closed hand = No.
            moving = abs(dx) >= self.config.move_on or abs(dy) >= self.config.move_on
            closed = all(value >= self.config.curl_on for value in observation.fingers.values())
            dpad = {name: False for name in dpad}
            a = moving and not closed
            b = closed
        elif profile == "program_g":
            # Gun.Smoke: position moves; index fires; thumb+ring is a menu guard.
            guarded = thumb and observation.ring_curl >= self.config.curl_on
            if abs(roll) >= self.config.roll_on:
                dpad["left"] = roll < 0
                dpad["right"] = roll > 0
            a = index and not guarded
            b = depth >= self.config.push_on and not guarded
            if guarded:
                dpad = {name: False for name in dpad}
        elif profile == "program_h":
            # General play/training: conventional motion and pulsed buttons.
            a = index and pulse_on
            b = thumb and pulse_on
        elif profile == "program_i":
            # Knight Rider/driving: wrist steering, finger throttle, hand brake.
            dpad = {name: False for name in dpad}
            dpad["left"] = roll <= -self.config.roll_on
            dpad["right"] = roll >= self.config.roll_on
            dpad["down"] = dy >= self.config.move_on
            turbo = depth >= self.config.push_on
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
