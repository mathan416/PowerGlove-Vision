# Project: PowerGlove Vision
# File: scripts/configure-uno-q-mdns.py
# Purpose: Resolve .local names through the host Avahi socket inside App Lab containers.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added persistent host mDNS resolution without pinned IP addresses.
# Full history: docs/CHANGELOG.md and Git history.

"""Add the host resolver socket directory to the existing App Lab Compose file."""
import sys
from pathlib import Path


def configure(path):
    """Insert one read-only Avahi directory mount, preserving other configuration."""
    text = path.read_text()
    if "target: /run/avahi-daemon" in text:
        return
    anchor = "    volumes:\n"
    if text.count(anchor) != 1:
        raise ValueError("Expected one App Lab main-service volumes section")
    block = ("    - type: bind\n      source: /run/avahi-daemon\n"
             "      target: /run/avahi-daemon\n      read_only: true\n")
    path.write_text(text.replace(anchor, anchor + block, 1))


if __name__ == "__main__":
    configure(Path(sys.argv[1]))
