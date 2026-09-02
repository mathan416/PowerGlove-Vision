# Copyright (c) 2026 Iain Bennett
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


AXIS_MIN = -32767
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
        return {
            "thumb": self.thumb_curl,
            "index": self.index_curl,
            "middle": self.middle_curl,
            "ring": self.ring_curl,
            "pinky": self.pinky_curl,
        }


@dataclass
class Calibration:
    palm_x: float
    palm_y: float
    palm_scale: float
    roll: float


@dataclass
class ControllerState:
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
        result = asdict(self)
        result["protocol"] = "powerglove-vision/1"
        if token:
            result["token"] = token
        return result

    @classmethod
    def released(
        cls, sequence: int, timestamp: float, profile: str, calibrated: bool = False
    ) -> "ControllerState":
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
