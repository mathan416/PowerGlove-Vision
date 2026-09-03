# Copyright (c) 2026 Iain Bennett
from __future__ import annotations

import argparse
import hmac
import socket
from pathlib import Path

from .transport import MAX_PACKET_BYTES, decode_state


class DryRunDevice:
    def write_state(self, state: dict) -> None:
        print(
            f"seq={state.get('sequence')} detected={state.get('detected')} "
            f"dpad={state.get('dpad')} buttons={state.get('buttons')} axes={state.get('axes')}",
            flush=True,
        )

    def release(self) -> None:
        print("released", flush=True)

    def close(self) -> None:
        pass


class UInputDevice:
    def __init__(self) -> None:
        try:
            from evdev import AbsInfo, UInput, ecodes
        except ImportError as exc:
            raise RuntimeError("install receiver dependencies with: pip install -e '.[receiver]'") from exc
        self.ecodes = ecodes
        absolute = AbsInfo(value=0, min=-32767, max=32767, fuzz=256, flat=2048, resolution=0)
        capabilities = {
            ecodes.EV_KEY: [
                ecodes.BTN_SOUTH, ecodes.BTN_EAST, ecodes.BTN_START,
                ecodes.BTN_SELECT, ecodes.BTN_TR2,
                ecodes.BTN_DPAD_UP, ecodes.BTN_DPAD_DOWN,
                ecodes.BTN_DPAD_LEFT, ecodes.BTN_DPAD_RIGHT,
            ],
            ecodes.EV_ABS: [
                (ecodes.ABS_X, absolute), (ecodes.ABS_Y, absolute),
                (ecodes.ABS_RX, absolute), (ecodes.ABS_RY, absolute),
            ],
        }
        self.device = UInput(capabilities, name="PowerGlove Vision", version=0x0100)

    def write_state(self, state: dict) -> None:
        e = self.ecodes
        dpad = state.get("dpad", {})
        buttons = state.get("buttons", {})
        axes = state.get("axes", {})
        for code, value in (
            (e.BTN_DPAD_UP, dpad.get("up", False)),
            (e.BTN_DPAD_DOWN, dpad.get("down", False)),
            (e.BTN_DPAD_LEFT, dpad.get("left", False)),
            (e.BTN_DPAD_RIGHT, dpad.get("right", False)),
            (e.BTN_SOUTH, buttons.get("a", False)),
            (e.BTN_EAST, buttons.get("b", False)),
            (e.BTN_START, buttons.get("start", False)),
            (e.BTN_SELECT, buttons.get("select", False)),
            (e.BTN_TR2, buttons.get("glove_zap", False)),
        ):
            self.device.write(e.EV_KEY, code, int(bool(value)))
        for code, name in ((e.ABS_X, "x"), (e.ABS_Y, "y"), (e.ABS_RX, "roll"), (e.ABS_RY, "z")):
            self.device.write(e.EV_ABS, code, int(axes.get(name, 0)))
        self.device.syn()

    def release(self) -> None:
        self.write_state({"dpad": {}, "buttons": {}, "axes": {}})

    def close(self) -> None:
        self.device.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Receive PowerGlove Vision as a Linux gamepad")
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55355)
    tokens = parser.add_mutually_exclusive_group(required=True)
    tokens.add_argument("--token")
    tokens.add_argument("--token-file", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=250)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    token = args.token if args.token is not None else args.token_file.read_text().strip()
    if len(token) < 16:
        raise ValueError("receiver token must contain at least 16 characters")
    # Keep an idle virtual controller out of frontend startup. Create the real
    # uinput device only after an authenticated controller packet arrives.
    device = DryRunDevice() if args.dry_run else None
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.listen, args.port))
    sock.settimeout(args.timeout_ms / 1000)
    released = True
    last_sequence = -1
    last_session: str | None = None
    try:
        while True:
            try:
                payload, _peer = sock.recvfrom(MAX_PACKET_BYTES + 1)
                try:
                    state = decode_state(payload)
                except (ValueError, UnicodeError):
                    continue
                supplied_token = state.get("token")
                if not isinstance(supplied_token, str) or not hmac.compare_digest(supplied_token, token):
                    continue
                session = state.get("session")
                if isinstance(session, str) and session != last_session:
                    last_session = session
                    last_sequence = -1
                sequence = int(state.get("sequence", -1))
                if last_sequence >= 0 and sequence <= last_sequence:
                    continue
                last_sequence = sequence
                if device is None:
                    device = UInputDevice()
                device.write_state(state)
                released = False
            except socket.timeout:
                if device is not None and not released:
                    device.release()
                    released = True
    except KeyboardInterrupt:
        return 0
    finally:
        if device is not None:
            device.release()
            device.close()
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
