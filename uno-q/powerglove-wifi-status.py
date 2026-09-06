#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: uno-q/powerglove-wifi-status.py
# Purpose: Publish read-only host Wi-Fi link health without network names or credentials.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-06 - Add an unprivileged, bounded host Wi-Fi status sampler.

"""Read Linux wireless carrier state; never configure a network interface."""
import json
import os
import tempfile
import time
from pathlib import Path

OUTPUT = Path('/home/arduino/ArduinoApps/powerglove-vision/data/wifi-status.json')


def wifi_state(root=Path('/sys/class/net')):
    """Distinguish associated Wi-Fi from disconnected or unavailable telemetry."""
    observed = []
    try:
        for interface in root.iterdir():
            if not ((interface/'wireless').exists() or (interface/'phy80211').exists()):
                continue
            try:
                observed.append((interface/'carrier').read_text().strip() == '1')
            except OSError:
                try:
                    observed.append(False if (interface/"operstate").read_text().strip() == "down" else None)
                except OSError:
                    observed.append(None)
    except OSError:
        return 'unavailable'
    return 'connected' if any(v is True for v in observed) else 'disconnected' if observed and all(v is False for v in observed) else 'unavailable'


def publish(path=OUTPUT):
    """Atomically replace a small public health record as the Arduino user."""
    if path.is_symlink():
        raise ValueError('Wi-Fi status path must not be a symlink')
    payload = json.dumps({'version':1,'state':wifi_state(),'observed_at':time.time()})+'\n'
    fd, temporary = tempfile.mkstemp(prefix='.wifi-status-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w') as stream:
            os.fchmod(stream.fileno(),0o644)
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,str(path))
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


if __name__ == '__main__':
    publish()
