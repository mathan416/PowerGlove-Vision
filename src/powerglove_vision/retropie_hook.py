# Copyright (c) 2026 Iain Bennett. All rights reserved.
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .profile_control import load_registry, read_token, select_profile, send_request


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RetroPie PowerGlove launch hook")
    parser.add_argument("action", choices=("start", "end"))
    parser.add_argument("system", nargs="?", default="")
    parser.add_argument("emulator", nargs="?", default="")
    parser.add_argument("rom", nargs="?", default="")
    parser.add_argument("command", nargs="?", default="")
    parser.add_argument("--settings", type=Path, default=Path("/etc/powerglove/launcher.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = json.loads(args.settings.read_text())
    token = read_token(None, Path(settings["token_file"]))
    profile = None
    if args.action == "start":
        registry_path = Path(settings.get("registry", "/etc/powerglove/games.json"))
        profile = select_profile(load_registry(registry_path), args.system, args.rom)
    try:
        ack = send_request(
            settings["uno_q"], int(settings.get("port", 55356)), token,
            profile, args.system, args.rom, float(settings.get("timeout", 0.4)),
        )
    except (OSError, TimeoutError, ValueError) as exc:
        # Never prevent a game from launching if the gesture controller is down.
        print(f"PowerGlove unavailable: {exc}")
        return 0
    print(f"PowerGlove profile acknowledged: {ack.get('profile') or 'off'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
