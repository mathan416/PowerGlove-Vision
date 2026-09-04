# Project: PowerGlove Vision
# File: src/powerglove_vision/model.py
# Purpose: Define the hand-observation, calibration, and virtual-controller data models.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Define the hand-observation, calibration, and virtual-controller data models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


AXIS_MAX = 32767


@dataclass
class HandObservation:
    """Normalized measurements from one video frame."""

    timestamp: float
    detected: bool
    confidence: float = 0.0
    palm_x: float = 0.5
    palm_y: float = 0.5
    palm_scale: float = 0.0
    roll: float = 0.0
    thumb_curl: float = 0.0
    index_curl: float = 0.0
    middle_curl: float = 0.0
    ring_curl: float = 0.0
    pinky_curl: float = 0.0

    @property
    def fingers(self) -> dict[str, float]:
        """Return curl measurements keyed by common finger name."""
        return {
            "thumb": self.thumb_curl,
            "index": self.index_curl,
            "middle": self.middle_curl,
            "ring": self.ring_curl,
            "pinky": self.pinky_curl,
        }


@dataclass
class Calibration:
    """Store the neutral palm position, apparent size, and wrist roll."""
    palm_x: float
    palm_y: float
    palm_scale: float
    roll: float


@dataclass
class ControllerState:
    """Represent one complete, sequenced virtual-gamepad update."""
    sequence: int
    timestamp: float
    profile: str
    detected: bool
    confidence: float
    calibrated: bool
    axes: dict[str, int] = field(
        default_factory=lambda: {"x": 0, "y": 0, "z": 0, "roll": 0}
    )
    dpad: dict[str, bool] = field(
        default_factory=lambda: {
            "up": False,
            "down": False,
            "left": False,
            "right": False,
        }
    )
    buttons: dict[str, bool] = field(default_factory=dict)
    fingers: dict[str, int] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)

    def to_dict(self, token: str | None = None) -> dict[str, Any]:
        """Serialize the state with protocol metadata and an optional transport token."""
        result = asdict(self)
        result["protocol"] = "powerglove-vision/1"
        if token:
            result["token"] = token
        return result

    @classmethod
    def released(
        cls, sequence: int, timestamp: float, profile: str, calibrated: bool = False
    ) -> "ControllerState":
        """Create a neutral state that explicitly releases every supported control."""
        return cls(
            sequence=sequence,
            timestamp=timestamp,
            profile=profile,
            detected=False,
            confidence=0.0,
            calibrated=calibrated,
            buttons={"a": False, "b": False, "start": False, "select": False},
            fingers={name: 0 for name in ("thumb", "index", "middle", "ring", "pinky")},
        )
