# Project: PowerGlove Vision
# File: src/powerglove_vision/retropie_hook.py
# Purpose: Translate RetroPie launch and exit events into authenticated PowerGlove profile requests.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-04 - Repaired persistent profile transport and asynchronous queue acknowledgements.
# Full history: docs/CHANGELOG.md and Git history.

"""Translate RetroPie launch and exit events into authenticated PowerGlove profile requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .profile_control import load_registry, read_token, select_profile, send_request


def build_parser() -> argparse.ArgumentParser:
    """Create the parser for RetroPie runcommand lifecycle arguments."""
    parser = argparse.ArgumentParser(description="RetroPie PowerGlove launch hook")
    parser.add_argument("action", choices=("start", "end"))
    parser.add_argument("system", nargs="?", default="")
    parser.add_argument("emulator", nargs="?", default="")
    parser.add_argument("rom", nargs="?", default="")
    parser.add_argument("command", nargs="?", default="")
    parser.add_argument("--settings", type=Path, default=Path("/etc/powerglove/launcher.json"))
    return parser


def main() -> int:
    """Select and request a profile without ever blocking the game launch on failure."""
    args = build_parser().parse_args()
    try:
        settings = json.loads(args.settings.read_text())
        token = read_token(None, Path(settings["token_file"]))
        profile = None
        if args.action == "start":
            registry_path = Path(settings.get("registry", "/etc/powerglove/games.json"))
            profile = select_profile(load_registry(registry_path), args.system, args.rom)
        ack = send_request(
            settings["uno_q"], int(settings.get("port", 55356)), token,
            profile, args.system, args.rom, float(settings.get("timeout", 0.4)),
        )
    except (OSError, TimeoutError, ValueError, KeyError, TypeError) as exc:
        # Never prevent a game from launching if the gesture controller is down.
        print(f"PowerGlove unavailable: {exc}")
        return 0
    if ack.get("accepted") is True and ack.get("profile") == profile:
        state = "queued" if ack.get("queued") else "acknowledged"
        print(f"PowerGlove profile {state}: {profile or 'off'}")
    else:
        print(f"PowerGlove profile rejected: requested {profile or 'off'}; UNO Q reported {ack.get('profile') or 'off'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
