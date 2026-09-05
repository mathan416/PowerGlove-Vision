# Project: PowerGlove Vision
# File: src/powerglove_vision/receiver.py
# Purpose: Validate controller datagrams and publish them as a Linux virtual gamepad through uinput.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Validate controller datagrams and publish them as a Linux virtual gamepad through uinput."""

from __future__ import annotations

import argparse
import hmac
import socket
import time
from pathlib import Path

from .native_state import DEFAULT_PATH as DEFAULT_NATIVE_STATE_PATH, NativeStateWriter
from .transport import MAX_PACKET_BYTES, decode_state


class DryRunDevice:
    """Print received state changes without creating a kernel input device."""
    def write_state(self, state: dict) -> None:
        """Print the meaningful controls in one accepted packet."""
        print(
            f"seq={state.get('sequence')} detected={state.get('detected')} "
            f"dpad={state.get('dpad')} buttons={state.get('buttons')} axes={state.get('axes')}",
            flush=True,
        )

    def release(self) -> None:
        """Report a timeout-driven neutral-controller release."""
        print("released", flush=True)

    def close(self) -> None:
        """Complete the no-resource dry-run device interface."""
        pass


class UInputDevice:
    """Expose authenticated PowerGlove state as a standard Linux gamepad."""
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
        """Write all buttons and axes, then synchronize the uinput frame."""
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
        """Emit a neutral frame so no control remains held after loss or shutdown."""
        self.write_state({"dpad": {}, "buttons": {}, "axes": {}})

    def close(self) -> None:
        """Close and remove the virtual input device."""
        self.device.close()


def build_parser() -> argparse.ArgumentParser:
    """Create the virtual-controller receiver command-line parser."""
    parser = argparse.ArgumentParser(description="Receive PowerGlove Vision as a Linux gamepad")
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=55355)
    tokens = parser.add_mutually_exclusive_group(required=True)
    tokens.add_argument("--token")
    tokens.add_argument("--token-file", type=Path)
    parser.add_argument("--timeout-ms", type=int, default=250)
    parser.add_argument("--native-state", type=Path, default=DEFAULT_NATIVE_STATE_PATH,
                        help="latest validated sample for the custom Nestopia core")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    """Authenticate sequenced datagrams, drive uinput, and release controls on timeout."""
    args = build_parser().parse_args()
    token = args.token if args.token is not None else args.token_file.read_text().strip()
    if len(token) < 16:
        raise ValueError("receiver token must contain at least 16 characters")
    # Keep an idle virtual controller out of frontend startup. Create the real
    # uinput device only after an authenticated controller packet arrives.
    device = DryRunDevice() if args.dry_run else None
    native = None
    try:
        native = NativeStateWriter(args.native_state)
    except OSError as exc:
        # The standard uinput path remains usable on systems without the optional core.
        print(f"Native Power Glove state unavailable: {exc}", flush=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.listen, args.port))
    if args.timeout_ms <= 0:
        sock.close()
        raise ValueError("receiver timeout must be positive")
    timeout = args.timeout_ms / 1000
    sock.settimeout(timeout)
    last_valid_at = None
    released = True
    last_sequence = -1
    last_session: str | None = None
    try:
        while True:
            now = time.monotonic()
            if last_valid_at is not None and not released and now - last_valid_at >= timeout:
                device.release()
                if native is not None:
                    native.release(last_sequence + 1)
                released = True
            remaining = timeout if released or last_valid_at is None else timeout - (now - last_valid_at)
            sock.settimeout(max(0.001, remaining))
            try:
                payload, _peer = sock.recvfrom(MAX_PACKET_BYTES + 1)
                try:
                    state = decode_state(payload)
                except (ValueError, UnicodeError, RecursionError):
                    continue
                supplied_token = state.get("token")
                if not isinstance(supplied_token, str) or not hmac.compare_digest(supplied_token, token):
                    continue
                session = state.get("session")
                if isinstance(session, str) and session != last_session:
                    last_session = session
                    last_sequence = -1
                sequence = state["sequence"]
                if last_sequence >= 0 and sequence <= last_sequence:
                    continue
                last_sequence = sequence
                if device is None:
                    device = UInputDevice()
                device.write_state(state)
                if native is not None:
                    native.write(state)
                released = False
                last_valid_at = time.monotonic()
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
        if native is not None:
            native.close()
        sock.close()


if __name__ == "__main__":
    raise SystemExit(main())
