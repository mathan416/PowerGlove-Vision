# Project: PowerGlove Vision
# File: src/powerglove_vision/transport.py
# Purpose: Encode bounded controller packets and send them to RetroPie without blocking vision recovery.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
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
    if data.get("protocol") != "powerglove-vision/1":
        raise ValueError("unsupported controller protocol")
    return data


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
        now = time.monotonic()
        if now < self._retry_at:
            return False
        try:
            self.socket.sendto(
                encode_state(state, self.token, self.session), self.destination
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
