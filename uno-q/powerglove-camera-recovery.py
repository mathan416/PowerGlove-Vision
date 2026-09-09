#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: uno-q/powerglove-camera-recovery.py
# Purpose: Recover the single UVC camera through its most recently observed parent USB hub.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-08 - Reset an enrolled hub when UVC streaming fails despite USB enumeration.
#   2026-09-05 - Added guarded camera USB recovery and autosuspend prevention.
#   2026-09-05 - Added first-use camera enrollment and automatic parent-hub updates.
# Full history: docs/CHANGELOG.md and Git history.

"""Consume one camera recovery request without granting the app general root access."""

from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import time
from pathlib import Path


APP_DATA = Path("/home/arduino/ArduinoApps/powerglove-vision/data")
REQUEST = APP_DATA / "camera-recovery-request"
RESULT = APP_DATA / "camera-recovery-result"
USB_DEVICES = Path("/sys/bus/usb/devices")
VIDEO_CLASS = Path("/sys/class/video4linux")
USB_DRIVER = Path("/sys/bus/usb/drivers/usb")
CONFIG = Path("/etc/powerglove-camera-recovery.json")
LOCK = Path("/run/powerglove-camera-recovery.lock")
STAMP = Path("/run/powerglove-camera-recovery.stamp")
COOLDOWN_SECONDS = 60.0
USB_NAME = re.compile(r"^[0-9]+-[0-9]+(?:\.[0-9]+)*$")


def _read(path: Path, default: str = "") -> str:
    """Read and trim one sysfs value, returning a safe default on failure."""
    try:
        return path.read_text().strip()
    except OSError:
        return default


def _identity(device: Path) -> tuple[str, str] | None:
    """Return a lowercase USB vendor/product identity when both are present."""
    vendor = _read(device / "idVendor").lower()
    product = _read(device / "idProduct").lower()
    return (vendor, product) if vendor and product else None


def _usb_device_for(path: Path) -> Path | None:
    """Walk upward from a video node to its first identified USB device."""
    try:
        current = path.resolve()
    except OSError:
        return None
    for candidate in (current, *current.parents):
        if _identity(candidate):
            return candidate
    return None


def _parent_hub(camera: Path) -> Path | None:
    """Locate the camera's nearest identified USB hub ancestor."""
    for candidate in camera.parents:
        if (
            USB_NAME.fullmatch(candidate.name)
            and _identity(candidate)
            and _read(candidate / "bDeviceClass").lower() == "09"
        ):
            return candidate
    return None


def _discover_cameras() -> list[dict[str, object]]:
    """Discover primary UVC video nodes with resettable parent USB hubs."""
    cameras: dict[str, dict[str, object]] = {}
    if not VIDEO_CLASS.exists():
        return []
    for video in sorted(VIDEO_CLASS.glob("video*")):
        if _read(video / "index") not in ("", "0"):
            continue
        camera = _usb_device_for(video / "device")
        if camera is None:
            continue
        hub = _parent_hub(camera)
        if hub is None:
            continue
        camera_id = _identity(camera)
        hub_id = _identity(hub)
        if camera_id is None or hub_id is None:
            continue
        key = str(camera.resolve())
        cameras[key] = {
            "camera": {
                "vendor_id": camera_id[0],
                "product_id": camera_id[1],
                "name": _read(video / "name", _read(camera / "product", "USB camera")),
            },
            "hub": {
                "vendor_id": hub_id[0],
                "product_id": hub_id[1],
                "name": _read(hub / "product", "USB hub"),
                "sysfs_name": hub.name,
            },
            "camera_path": camera,
            "hub_path": hub,
        }
    return list(cameras.values())


def _public_config(discovery: dict[str, object]) -> dict[str, object]:
    """Discard transient paths and retain only the validated enrollment record."""
    return {"schema": 1, "camera": discovery["camera"], "hub": discovery["hub"]}


def _validate_section(section: object, fields: tuple[str, ...]) -> dict[str, str]:
    """Validate one camera or hub configuration section and USB identifiers."""
    if not isinstance(section, dict):
        raise RuntimeError("camera recovery configuration is malformed")
    result = {}
    for field in fields:
        value = section.get(field)
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"camera recovery configuration is missing {field}")
        result[field] = value
    for field in ("vendor_id", "product_id"):
        if not re.fullmatch(r"[0-9a-f]{4}", result[field].lower()):
            raise RuntimeError(f"camera recovery configuration has an invalid {field}")
        result[field] = result[field].lower()
    return result


def _config_is_secure() -> bool:
    """Require the enrollment file to be root-owned and not broadly writable."""
    try:
        status = CONFIG.stat()
    except OSError:
        return False
    return status.st_uid == 0 and status.st_mode & 0o022 == 0


def _load_config(optional: bool = False) -> dict[str, object] | None:
    """Load and validate the root-owned camera/hub enrollment document."""
    if optional and not CONFIG.exists():
        return None
    if not _config_is_secure():
        raise RuntimeError(f"{CONFIG} must be root-owned and not be group/world writable")
    try:
        document = json.loads(CONFIG.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot read camera recovery configuration: {error}") from error
    if not isinstance(document, dict) or document.get("schema") != 1:
        raise RuntimeError("unsupported camera recovery configuration schema")
    camera = _validate_section(document.get("camera"), ("vendor_id", "product_id", "name"))
    hub = _validate_section(document.get("hub"), ("vendor_id", "product_id", "name", "sysfs_name"))
    if not USB_NAME.fullmatch(hub["sysfs_name"]):
        raise RuntimeError("camera recovery configuration has an unsafe hub path")
    return {"schema": 1, "camera": camera, "hub": hub}


def _write_config(discovery: dict[str, object]) -> None:
    """Atomically persist the last healthy camera and parent-hub identity."""
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG.with_name(CONFIG.name + ".tmp")
    temporary.write_text(json.dumps(_public_config(discovery), indent=2, sort_keys=True) + "\n")
    os.chmod(temporary, 0o644)
    os.replace(temporary, CONFIG)


def _enroll_if_present(required: bool) -> int:
    """Enroll exactly one visible camera, optionally deferring when absent."""
    if os.geteuid() != 0:
        raise PermissionError("camera recovery configuration must run as root")
    cameras = _discover_cameras()
    if not cameras and not required:
        print("PowerGlove camera recovery: no camera connected; enrollment deferred until first use")
        return 0
    if len(cameras) != 1:
        raise RuntimeError(
            f"expected exactly one UVC camera with a resettable parent hub; found {len(cameras)}"
        )
    discovery = cameras[0]
    _write_config(discovery)
    camera = discovery["camera"]
    hub = discovery["hub"]
    print(
        "PowerGlove camera recovery enrolled:\n"
        f"  camera: {camera['name']} ({camera['vendor_id']}:{camera['product_id']})\n"
        f"  hub: {hub['name']} ({hub['vendor_id']}:{hub['product_id']}) at {hub['sysfs_name']}"
    )
    return 0


def _approved_hub(config: dict[str, object]) -> Path:
    """Resolve the allowlisted hub only when its current identity still matches."""
    hub_config = config["hub"]
    hub = USB_DEVICES / hub_config["sysfs_name"]
    expected = (hub_config["vendor_id"], hub_config["product_id"])
    if not hub.exists() or _identity(hub) != expected:
        raise RuntimeError("the last observed USB hub is absent or has changed identity")
    if _read(hub / "bDeviceClass").lower() != "09":
        raise RuntimeError("the last observed USB device is no longer a hub")
    return hub


def _keep_awake(device: Path) -> None:
    """Disable USB autosuspend for one enrolled device when supported."""
    control = device / "power" / "control"
    if control.exists():
        control.write_text("on")


def _consume_request() -> str | None:
    """Consume and validate one unprivileged, narrowly classified request."""
    try:
        reason = REQUEST.read_text().strip()
        REQUEST.unlink()
        # Empty files were written by versions before request classification.
        if reason == "":
            return "legacy"
        if reason not in ("enroll", "recover"):
            raise RuntimeError("camera recovery request has an unknown action")
        return reason
    except FileNotFoundError:
        return None


def _publish_result(status: str) -> None:
    """Atomically tell the unprivileged supervisor that the guarded action ended."""
    APP_DATA.mkdir(parents=True, exist_ok=True)
    temporary = RESULT.with_name(RESULT.name + "." + str(os.getpid()) + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(str(temporary), flags, 0o644)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"schema": 1, "status": status}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(RESULT))
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _within_cooldown(now: float) -> bool:
    """Report whether a prior physical reset is still inside the cooldown."""
    try:
        return now - float(STAMP.read_text().strip()) < COOLDOWN_SECONDS
    except (OSError, ValueError):
        return False


def _recover() -> int:
    """Handle one request by enrolling a healthy camera or resetting its hub."""
    APP_DATA.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        reason = _consume_request()
        if reason is None:
            return 0
        if os.geteuid() != 0:
            raise PermissionError("camera recovery must run as root")

        # A healthy sighting is authoritative for enrollment. A stream-failure
        # request remains a recovery request even when sysfs/lsusb can still see
        # the device: UVC negotiation can wedge without USB disconnection.
        cameras = _discover_cameras()
        if len(cameras) > 1:
            raise RuntimeError(f"expected one UVC camera; found {len(cameras)}")
        if cameras:
            discovery = cameras[0]
            previous = _load_config(optional=True)
            current = _public_config(discovery)
            if previous != current:
                _write_config(discovery)
                print("PowerGlove camera recovery: camera and parent hub enrollment updated")
            _keep_awake(discovery["camera_path"])
            _keep_awake(discovery["hub_path"])
            if reason != "recover":
                print("PowerGlove camera recovery: camera present; autosuspend disabled")
                return 0

        config = _load_config(optional=True)
        if config is None:
            raise RuntimeError(
                "no camera has been enrolled yet; reconnect or power-cycle it once so it can be observed"
            )
        now = time.monotonic()
        if _within_cooldown(now):
            print("PowerGlove camera recovery: request ignored during cooldown")
            return 0
        hub = _approved_hub(config)
        hub_name = hub.name
        _keep_awake(hub)
        STAMP.write_text(str(now))
        unbound = False
        try:
            (USB_DRIVER / "unbind").write_text(hub_name)
            unbound = True
            time.sleep(2.0)
            (USB_DRIVER / "bind").write_text(hub_name)
            unbound = False
        finally:
            if unbound:
                (USB_DRIVER / "bind").write_text(hub_name)

        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            cameras = _discover_cameras()
            if len(cameras) == 1:
                discovery = cameras[0]
                _write_config(discovery)
                _keep_awake(discovery["camera_path"])
                _keep_awake(discovery["hub_path"])
                print(f"PowerGlove camera recovery: {hub_name} reset; camera returned")
                return 0
            if len(cameras) > 1:
                raise RuntimeError(f"hub reset returned {len(cameras)} UVC cameras; refusing enrollment")
            time.sleep(0.25)
        raise RuntimeError(f"reset {hub_name}, but the enrolled camera did not return")


def main(argv: list[str] | None = None) -> int:
    """Dispatch installation-time enrollment or one guarded recovery request."""
    arguments = sys.argv[1:] if argv is None else argv
    if arguments == ["--configure"]:
        return _enroll_if_present(required=True)
    if arguments == ["--configure-if-present"]:
        return _enroll_if_present(required=False)
    if arguments:
        raise SystemExit("usage: powerglove-camera-recovery [--configure|--configure-if-present]")
    try:
        result = _recover()
    except Exception:
        _publish_result("failed")
        raise
    _publish_result("ready")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
