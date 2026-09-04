# Project: PowerGlove Vision
# File: scripts/configure-uno-q-mdns.py
# Purpose: Resolve .local names through the host Avahi socket inside App Lab containers.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added persistent host mDNS resolution without pinned IP addresses.
#   2026-09-04 - Repaired persistent profile transport and asynchronous queue acknowledgements.
# Full history: docs/CHANGELOG.md and Git history.

"""Preserve resolver and UDP profile bricks when updating generated Compose output."""
import json
import sys
from pathlib import Path


def configure(path):
    """Preserve existing settings while supporting deployment before App Lab regeneration."""
    text = path.read_text()
    for name in ("avahi_resolver", "profile_control"):
        relative = "bricks/local/" + name + "/brick_compose.yaml"
        if relative in text:
            continue
        brick = path.resolve().parents[1] / relative
        entry = "- " + json.dumps(str(brick)) + "\n"
        if "include:\n" in text:
            text = text.replace("include:\n", "include:\n" + entry, 1)
        else:
            text += "\ninclude:\n" + entry
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
