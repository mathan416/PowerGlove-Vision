#!/usr/bin/env python3
# Project: VirtualGlove
# File: scripts/flash-matrix-firmware.py
# Purpose: Verify and flash the release's precompiled UNO Q Matrix firmware.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-11 - Added checksum-gated installation through factory OpenOCD.
# Full history: docs/CHANGELOG.md and Git history.

"""Flash a checksum-verified release image without installing a compiler."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

OPENOCD = Path("/opt/openocd/bin/openocd")
OPENOCD_ROOT = Path("/opt/openocd")
COMPATIBLE = Path("/proc/device-tree/compatible")
EXPECTED = {
    "format": 1,
    "fqbn": "arduino:zephyr:unoq",
    "platform": "arduino:zephyr@1.0.0",
    "boot_mode": "wait_for_app",
}
ARTIFACTS = {
    "virtualglove-matrix.elf-zsk.bin",
    "zephyr-arduino_uno_q_stm32u585xx.elf",
    "flash_sketch.cfg",
}
OFFICIAL_HASHES = {
    "zephyr-arduino_uno_q_stm32u585xx.elf":
        "39d4a4fd47241663323f6e04f94dd8f5a9f9ad6582cf1df37f9709b74026adcd",
    "flash_sketch.cfg":
        "38706cee1f9ff2e53364a47129d1c1aea9bb9687ed26d7d70b4a9f9bc5bca60c",
}


def digest(path):
    """Return one artifact's SHA-256."""
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def verify(directory):
    """Validate board identity, manifest shape, hashes, sizes, and image headers."""
    compatible = COMPATIBLE.read_bytes().split(b"\0")
    if b"arduino,imola" not in compatible:
        raise ValueError("Precompiled Matrix firmware supports the Arduino UNO Q only")
    if not OPENOCD.is_file() or not (OPENOCD_ROOT / "openocd_gpiod.cfg").is_file():
        raise ValueError("Complete UNO Q provisioning with Arduino App Lab first")
    manifest = json.loads((directory / "manifest.json").read_text())
    for key, value in EXPECTED.items():
        if manifest.get(key) != value:
            raise ValueError("Unsupported Matrix firmware " + key)
    if not re.fullmatch(r"[0-9a-f]{64}", manifest.get("firmware_source_id", "")):
        raise ValueError("Invalid Matrix firmware source identity")
    if set(manifest.get("artifacts", {})) != ARTIFACTS:
        raise ValueError("Incomplete Matrix firmware manifest")
    for name in ARTIFACTS:
        path = directory / name
        record = manifest["artifacts"][name]
        if (not path.is_file() or path.is_symlink() or record.get("size") != path.stat().st_size
                or record.get("sha256") != digest(path)):
            raise ValueError("Matrix firmware artifact failed verification: " + name)
        if name in OFFICIAL_HASHES and record.get("sha256") != OFFICIAL_HASHES[name]:
            raise ValueError("Matrix firmware upstream artifact is not the pinned version: " + name)
    sketch = (directory / "virtualglove-matrix.elf-zsk.bin").read_bytes()
    if (len(sketch) < 16 or len(sketch) > 786432 or sketch[:4] != b"\x7fELF"
            or sketch[7] != 1 or sketch[12:14] != b"A#"
            or not sketch[14] & 8 or sketch[14] & 4):
        raise ValueError("Invalid UNO Q Matrix sketch image")
    loader = directory / "zephyr-arduino_uno_q_stm32u585xx.elf"
    if loader.stat().st_size > 4 * 1024 * 1024 or loader.read_bytes()[:4] != b"\x7fELF":
        raise ValueError("Invalid UNO Q Zephyr loader image")
    config = (directory / "flash_sketch.cfg").read_text()
    required = ("flash verify_image ${filename0}",
                "flash verify_image ${filename1} 0x8100000 bin",
                "mww 0x40036400 0xCAFFEEEE", "shutdown")
    if not all(item in config for item in required):
        raise ValueError("Unexpected UNO Q flash configuration")
    return manifest


def flash(directory):
    """Run the official board recipe using only factory OpenOCD and bundled artifacts."""
    manifest = verify(directory)
    loader = directory / "zephyr-arduino_uno_q_stm32u585xx.elf"
    sketch = directory / "virtualglove-matrix.elf-zsk.bin"
    config = directory / "flash_sketch.cfg"
    subprocess.run([
        str(OPENOCD), "-d2", "-s", str(OPENOCD_ROOT),
        "-s", str(OPENOCD_ROOT / "share/openocd/scripts"),
        "-f", "openocd_gpiod.cfg", "-c", "set filename " + str(loader),
        "-c", "set filename0 " + str(loader),
        "-c", "set filename1 " + str(sketch), "-f", str(config),
    ], check=True, timeout=120)
    print("PASS  Matrix firmware verified and ready: " + manifest["firmware_source_id"])


def main():
    """Accept an explicitly selected firmware directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    flash(args.directory.resolve())


if __name__ == "__main__":
    main()
