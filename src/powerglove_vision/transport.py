# Project: PowerGlove Vision
# File: src/powerglove_vision/transport.py
# Purpose: Encode bounded controller packets and send them to RetroPie without blocking vision recovery.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Support an unconfigured first-run receiver without blocking local practice.
# Full history: docs/CHANGELOG.md and Git history.

"""Encode bounded controller packets and send them to RetroPie without blocking vision recovery."""

from __future__ import annotations

import json
import socket
import time
import uuid

from .model import ControllerState


MAX_PACKET_BYTES = 4096


def encode_state(
    state: ControllerState, token: str | None = None, session: str | None = None
) -> bytes:
    """Serialize one controller state into a size-bounded protocol packet."""
    data = state.to_dict(token)
    if session:
        data["session"] = session
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    if len(payload) > MAX_PACKET_BYTES:
        raise ValueError("controller packet is unexpectedly large")
    return payload


def decode_state(payload: bytes) -> dict:
    """Parse and validate one size-bounded controller protocol packet."""
    if len(payload) > MAX_PACKET_BYTES:
        raise ValueError("controller packet exceeds size limit")
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict) or data.get("protocol") != "powerglove-vision/1":
        raise ValueError("unsupported controller protocol")
    sequence = data.get("sequence")
    if type(sequence) is not int or not 0 <= sequence <= 2_147_483_647:
        raise ValueError("invalid controller sequence")
    for name in ("session", "token"):
        value = data.get(name)
        if value is not None and (not isinstance(value, str) or not value.isascii()
                                  or not 1 <= len(value) <= (128 if name == "session" else 256)):
            raise ValueError("invalid controller " + name)
    for name, keys, maximum in (
        ("axes", {"x", "y", "z", "roll"}, 32767),
        ("dpad", {"up", "down", "left", "right"}, None),
        ("buttons", {"a", "b", "start", "select", "glove_zap", "menu_guard"}, None),
        ("fingers", {"thumb", "index", "middle", "ring", "pinky"}, 3),
    ):
        values = data.get(name, {})
        if not isinstance(values, dict) or set(values) - keys:
            raise ValueError("invalid controller " + name)
        for value in values.values():
            if maximum is None:
                valid = type(value) is bool
            else:
                valid = type(value) is int and (-maximum if name == "axes" else 0) <= value <= maximum
            if not valid:
                raise ValueError("invalid controller " + name)
    for name in ("timestamp", "confidence"):
        if name in data:
            value = data[name]
            if (type(value) not in (int, float)
                    or not 0 <= value <= (1 if name == "confidence" else 1e15)):
                raise ValueError("invalid controller " + name)
    for name in ("detected", "calibrated"):
        if name in data and type(data[name]) is not bool:
            raise ValueError("invalid controller " + name)
    return data


from .resolver import resolve_ipv4


class UdpSender:
    """Send controller states in recoverable sessions over connectionless UDP."""
    def __init__(self, host: str, port: int, token: str | None) -> None:
        self.destination = (host, port)
        self.token = token
        self.session = uuid.uuid4().hex
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.last_error: str | None = None
        self._retry_at = 0.0

    def send(self, state: ControllerState) -> bool:
        """Send a controller state without letting network loss stop vision.

        UDP has no persistent connection, and hostname resolution can briefly
        fail while Wi-Fi, mDNS, or the RetroPie console is starting. Throttle
        retries after an error so tracking and the dashboard remain responsive.
        """
        if not self.destination[0].strip():
            self.last_error = "Configure your RetroPie destination in Connection before starting controls."
            return False
        now = time.monotonic()
        if now < self._retry_at:
            return False
        try:
            self.socket.sendto(
                encode_state(state, self.token, self.session),
                (resolve_ipv4(self.destination[0]), self.destination[1])
            )
        except OSError as exc:
            self.last_error = str(exc)
            self._retry_at = now + 2.0
            return False
        self.last_error = None
        self._retry_at = 0.0
        return True

    def new_session(self) -> None:
        """Allow sequence numbers to restart after an atomic profile change."""
        self.session = uuid.uuid4().hex

    def close(self) -> None:
        """Close the sender socket."""
        self.socket.close()
