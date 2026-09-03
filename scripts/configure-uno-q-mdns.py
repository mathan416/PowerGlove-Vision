# Project: PowerGlove Vision
# File: scripts/configure-uno-q-mdns.py
# Purpose: Resolve .local names through the host Avahi socket inside App Lab containers.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added persistent host mDNS resolution without pinned IP addresses.
# Full history: docs/CHANGELOG.md and Git history.

"""Add the resolver brick include and a compatibility mount to existing Compose output."""
import sys
from pathlib import Path


def configure(path):
    """Preserve existing settings while supporting deployment before App Lab regeneration."""
    text = path.read_text()
    brick = path.resolve().parents[1] / "bricks/local/avahi_resolver/brick_compose.yaml"
    if "bricks/local/avahi_resolver/brick_compose.yaml" not in text:
        if "include:" in text:
            raise ValueError("Run App Lab start to regenerate the resolver brick include")
        import json
        text += "\ninclude:\n  - " + json.dumps(str(brick)) + "\n"
    if "target: /run/avahi-daemon" in text:
        path.write_text(text)
        return
    anchor = "    volumes:\n"
    if text.count(anchor) != 1:
        raise ValueError("Expected one App Lab main-service volumes section")
    block = ("    - type: bind\n      source: /run/avahi-daemon\n"
             "      target: /run/avahi-daemon\n      read_only: true\n")
    path.write_text(text.replace(anchor, anchor + block, 1))


if __name__ == "__main__":
    configure(Path(sys.argv[1]))
