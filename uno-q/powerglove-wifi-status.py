#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: uno-q/powerglove-wifi-status.py
# Purpose: Publish read-only host Wi-Fi and Ethernet link health without network names or credentials.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-06 - Add an unprivileged, bounded host Wi-Fi status sampler.

"""Read Linux physical network carrier state; never configure a network interface."""
import json
import os
import tempfile
import time
from pathlib import Path

OUTPUT = Path('/home/arduino/ArduinoApps/powerglove-vision/data/wifi-status.json')


def link_state(root=Path('/sys/class/net'), wireless_only=False):
    """Read physical Wi-Fi/Ethernet carrier; ignore loopback and virtual bridges."""
    observed = []
    try:
        for interface in root.iterdir():
            wireless = (interface/'wireless').exists() or (interface/'phy80211').exists()
            if not wireless:
                if wireless_only or not (interface/'device').exists():
                    continue
                try:
                    if (interface/'type').read_text().strip() != '1':
                        continue
                except OSError:
                    observed.append(None)
                    continue
            try:
                carrier = (interface/'carrier').read_text().strip()
                observed.append(True if carrier == '1' else False if carrier == '0' else None)
            except OSError:
                try:
                    observed.append(False if (interface/'operstate').read_text().strip() == 'down' else None)
                except OSError:
                    observed.append(None)
    except OSError:
        return 'unavailable'
    return 'connected' if any(v is True for v in observed) else 'disconnected' if observed and all(v is False for v in observed) else 'unavailable'


def wifi_state(root=Path('/sys/class/net')):
    """Retain the wireless-only field for older application versions."""
    return link_state(root, wireless_only=True)


def publish(path=OUTPUT):
    """Atomically replace a small public health record as the Arduino user."""
    if path.is_symlink():
        raise ValueError('Wi-Fi status path must not be a symlink')
    payload = json.dumps({'version':1,'state':wifi_state(),'networking':link_state(),'observed_at':time.time()})+'\n'
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
