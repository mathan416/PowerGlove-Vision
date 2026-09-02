# Copyright (c) 2026 Iain Bennett
from __future__ import annotations

import json
import socket
import uuid

from .model import ControllerState


MAX_PACKET_BYTES = 4096


def encode_state(
    state: ControllerState, token: str | None = None, session: str | None = None
) -> bytes:
    data = state.to_dict(token)
    if session:
        data["session"] = session
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    if len(payload) > MAX_PACKET_BYTES:
        raise ValueError("controller packet is unexpectedly large")
    return payload


def decode_state(payload: bytes) -> dict:
    if len(payload) > MAX_PACKET_BYTES:
        raise ValueError("controller packet exceeds size limit")
    data = json.loads(payload.decode("utf-8"))
    if data.get("protocol") != "powerglove-vision/1":
        raise ValueError("unsupported controller protocol")
    return data


class UdpSender:
    def __init__(self, host: str, port: int, token: str | None) -> None:
        self.destination = (host, port)
        self.token = token
        self.session = uuid.uuid4().hex
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, state: ControllerState) -> None:
        self.socket.sendto(
            encode_state(state, self.token, self.session), self.destination
        )

    def new_session(self) -> None:
        """Allow sequence numbers to restart after an atomic profile change."""
        self.session = uuid.uuid4().hex

    def close(self) -> None:
        self.socket.close()
