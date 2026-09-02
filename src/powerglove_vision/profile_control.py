# Copyright (c) 2026 Iain Bennett
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import queue
import socket
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .gesture import SUPPORTED_PROFILES


PROTOCOL = "powerglove-profile/1"
MAX_PACKET_BYTES = 4096


def _canonical(data: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in data.items() if key != "signature"}
    return json.dumps(unsigned, separators=(",", ":"), sort_keys=True).encode()


def sign_message(data: dict[str, Any], token: str) -> dict[str, Any]:
    result = dict(data)
    result["signature"] = hmac.new(token.encode(), _canonical(result), hashlib.sha256).hexdigest()
    return result


def verify_message(data: dict[str, Any], token: str) -> bool:
    supplied = data.get("signature")
    if not isinstance(supplied, str):
        return False
    expected = hmac.new(token.encode(), _canonical(data), hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def read_token(token: str | None, token_file: Path | None) -> str:
    value = token if token is not None else token_file.read_text().strip() if token_file else ""
    if len(value) < 16:
        raise ValueError("profile token must contain at least 16 characters")
    return value


@dataclass(frozen=True)
class ProfileRequest:
    request_id: str
    profile: str | None
    system: str
    rom: str
    peer: tuple[str, int]


class ProfileCommandServer:
    """Authenticated Pi-to-UNO-Q profile requests with explicit acknowledgements."""

    def __init__(self, host: str, port: int, token: str) -> None:
        self.token = token
        self.requests: queue.SimpleQueue[ProfileRequest] = queue.SimpleQueue()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind((host, port))
        except Exception:
            self.socket.close()
            raise
        self.socket.settimeout(0.25)
        self._closed = threading.Event()
        self._seen: set[str] = set()
        self._acks: dict[str, bytes] = {}
        self._thread = threading.Thread(target=self._run, name="profile-control", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._closed.is_set():
            try:
                payload, peer = self.socket.recvfrom(MAX_PACKET_BYTES + 1)
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                if len(payload) > MAX_PACKET_BYTES:
                    raise ValueError("packet too large")
                data = json.loads(payload)
                if (data.get("protocol") != PROTOCOL or data.get("kind") != "set_profile"
                        or not verify_message(data, self.token)):
                    raise ValueError("invalid request")
                request_id = str(data["request_id"])
                if request_id in self._seen:
                    ack = self._acks.get(request_id)
                    if ack is not None:
                        self.socket.sendto(ack, peer)
                    continue
                profile = data.get("profile")
                if profile is not None and profile not in SUPPORTED_PROFILES:
                    raise ValueError("unknown profile")
                self._seen.add(request_id)
                if len(self._seen) > 256:
                    self._seen.clear()
                    self._acks.clear()
                self.requests.put(ProfileRequest(
                    request_id=request_id,
                    profile=profile,
                    system=str(data.get("system", ""))[:64],
                    rom=Path(str(data.get("rom", ""))).name[:255],
                    peer=peer,
                ))
            except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue

    def take(self) -> ProfileRequest | None:
        try:
            return self.requests.get_nowait()
        except queue.Empty:
            return None

    def acknowledge(self, request: ProfileRequest, accepted: bool, profile: str | None) -> None:
        data = sign_message({
            "protocol": PROTOCOL,
            "kind": "ack",
            "request_id": request.request_id,
            "accepted": accepted,
            "profile": profile,
        }, self.token)
        payload = json.dumps(data, separators=(",", ":")).encode()
        self._acks[request.request_id] = payload
        self.socket.sendto(payload, request.peer)

    def close(self) -> None:
        self._closed.set()
        self.socket.close()
        self._thread.join(timeout=1)


def load_registry(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text())
    games = data.get("games")
    if not isinstance(games, dict):
        raise ValueError("profile registry must contain a games object")
    result: dict[str, str] = {}
    for filename, profile in games.items():
        if profile not in SUPPORTED_PROFILES:
            raise ValueError(f"unknown profile {profile!r} for {filename!r}")
        result[Path(filename).name.casefold()] = profile
    return result


def select_profile(registry: dict[str, str], system: str, rom: str) -> str | None:
    if system.casefold() not in {"nes", "famicom"}:
        return None
    return registry.get(Path(rom).name.casefold())


def send_request(host: str, port: int, token: str, profile: str | None,
                 system: str, rom: str, timeout: float) -> dict[str, Any]:
    request_id = uuid.uuid4().hex
    message = sign_message({
        "protocol": PROTOCOL,
        "kind": "set_profile",
        "request_id": request_id,
        "profile": profile,
        "system": system,
        "rom": Path(rom).name,
    }, token)
    payload = json.dumps(message, separators=(",", ":")).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        for _attempt in range(3):
            sock.sendto(payload, (host, port))
            try:
                response, _peer = sock.recvfrom(MAX_PACKET_BYTES + 1)
                ack = json.loads(response)
                if (ack.get("protocol") == PROTOCOL and ack.get("kind") == "ack"
                        and ack.get("request_id") == request_id and verify_message(ack, token)):
                    return ack
            except socket.timeout:
                continue
    raise TimeoutError("UNO Q did not acknowledge the profile change")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Select the UNO Q gesture profile for a launched ROM")
    parser.add_argument("--uno-q", required=True, help="UNO Q hostname or address")
    parser.add_argument("--port", type=int, default=55356)
    tokens = parser.add_mutually_exclusive_group(required=True)
    tokens.add_argument("--token")
    tokens.add_argument("--token-file", type=Path)
    parser.add_argument("--registry", type=Path, default=Path("/etc/powerglove/games.json"))
    parser.add_argument("--system", default="nes")
    parser.add_argument("--rom", default="Manual selection")
    parser.add_argument("--profile", choices=(*SUPPORTED_PROFILES, "off"),
                        help="manual override; otherwise select from the ROM registry")
    parser.add_argument("--timeout", type=float, default=0.4)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    token = read_token(args.token, args.token_file)
    profile = (None if args.profile == "off" else args.profile) if args.profile else select_profile(
        load_registry(args.registry), args.system, args.rom
    )
    try:
        ack = send_request(args.uno_q, args.port, token, profile, args.system, args.rom, args.timeout)
    except TimeoutError as exc:
        print(str(exc))
        return 2
    label = profile or "off"
    print(f"PowerGlove profile: {label} ({'accepted' if ack.get('accepted') else 'rejected'})")
    return 0 if ack.get("accepted") else 3


if __name__ == "__main__":
    raise SystemExit(main())
