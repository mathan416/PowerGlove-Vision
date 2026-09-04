# Project: PowerGlove Vision
# File: src/powerglove_vision/camera.py
# Purpose: Discover usable Linux camera capture devices while excluding codec-only video nodes.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Linux camera discovery helpers for PowerGlove Vision."""

from __future__ import annotations

from pathlib import Path


_NON_CAMERA_MARKERS = ("codec", "decoder", "encoder", "m2m", "venus")


class CameraUnavailableError(RuntimeError):
    """Raised when a configured camera cannot provide video frames."""


def discover_camera_devices(
    dev_root: Path = Path("/dev"),
    sys_root: Path = Path("/sys/class/video4linux"),
) -> list[Path]:
    """Return likely capture devices, preferring stable USB-camera paths.

    Linux exposes hardware codecs as ``/dev/video*`` nodes too. Treating every
    such node as a camera made the UNO Q repeatedly probe its Qualcomm Venus
    encoder and decoder when no USB camera was attached.
    """
    devices: list[Path] = []
    resolved: set[Path] = set()

    for link in sorted((dev_root / "v4l" / "by-id").glob("*-video-index0")):
        try:
            target = link.resolve(strict=True)
        except OSError:
            continue
        devices.append(link)
        resolved.add(target)

    if not sys_root.exists():
        return devices

    for entry in sorted(sys_root.glob("video*")):
        node = dev_root / entry.name
        if not node.exists():
            continue
        try:
            name = (entry / "name").read_text().strip().lower()
        except OSError:
            continue
        if any(marker in name for marker in _NON_CAMERA_MARKERS):
            continue
        try:
            interface_index = (entry / "index").read_text().strip()
        except OSError:
            interface_index = "0"
        if interface_index != "0":
            continue
        target = node.resolve()
        if target not in resolved:
            devices.append(node)
            resolved.add(target)
    return devices


def camera_candidates(
    selection: str,
    dev_root: Path = Path("/dev"),
    sys_root: Path = Path("/sys/class/video4linux"),
) -> list[str | int]:
    """Resolve ``auto``, a numeric index, or an explicit device path."""
    value = str(selection).strip()
    if value.lower() == "auto":
        return [str(path) for path in discover_camera_devices(dev_root, sys_root)]
    try:
        return [int(value)]
    except ValueError:
        return [value]
