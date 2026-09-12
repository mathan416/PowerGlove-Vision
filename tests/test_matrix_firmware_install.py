#!/usr/bin/env python3
# Project: VirtualGlove
# File: tests/test_matrix_firmware_install.py
# Purpose: Verify checksum and board gates for precompiled Matrix installation.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-11 - Kept mock-call inspection compatible with Python 3.7.
#   2026-09-11 - Added precompiled firmware installer coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Exercise release firmware verification without touching a board."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "flash_matrix", ROOT / "scripts/flash-matrix-firmware.py")
FLASH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FLASH)


class MatrixFirmwareInstallTests(unittest.TestCase):
    def fixture(self, root):
        """Create the minimum structurally valid, self-consistent release bundle."""
        firmware = root / "firmware"
        firmware.mkdir()
        sketch = b"\x7fELF\x01\x01\x01\x01\x00\x00\x00\x00A#\x08\x00"
        loader = b"\x7fELF" + b"\x00" * 20
        config = ("flash verify_image ${filename0}\n"
                  "flash verify_image ${filename1} 0x8100000 bin\n"
                  "mww 0x40036400 0xCAFFEEEE\nshutdown\n").encode()
        values = {
            "virtualglove-matrix.elf-zsk.bin": sketch,
            "zephyr-arduino_uno_q_stm32u585xx.elf": loader,
            "flash_sketch.cfg": config,
        }
        for name, data in values.items():
            (firmware / name).write_bytes(data)
        manifest = {
            **FLASH.EXPECTED,
            "firmware_source_id": "a" * 64,
            "artifacts": {name: {"size": len(data),
                                  "sha256": hashlib.sha256(data).hexdigest()}
                          for name, data in values.items()},
        }
        (firmware / "manifest.json").write_text(json.dumps(manifest))
        compatible = root / "compatible"
        compatible.write_bytes(b"arduino,imola\0")
        openocd = root / "openocd"
        (openocd / "bin").mkdir(parents=True)
        (openocd / "bin/openocd").write_text("binary")
        (openocd / "openocd_gpiod.cfg").write_text("factory")
        return firmware, compatible, openocd

    def test_valid_bundle_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            firmware, compatible, openocd = self.fixture(Path(directory))
            with patch.object(FLASH, "COMPATIBLE", compatible), \
                    patch.object(FLASH, "OPENOCD_ROOT", openocd), \
                    patch.object(FLASH, "OPENOCD", openocd / "bin/openocd"), \
                    patch.object(FLASH, "OFFICIAL_HASHES", {}):
                self.assertEqual(FLASH.verify(firmware)["firmware_source_id"], "a" * 64)
                (firmware / "virtualglove-matrix.elf-zsk.bin").write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "failed verification"):
                    FLASH.verify(firmware)

    def test_flash_uses_factory_openocd_recipe(self):
        with tempfile.TemporaryDirectory() as directory:
            firmware, compatible, openocd = self.fixture(Path(directory))
            with patch.object(FLASH, "COMPATIBLE", compatible), \
                    patch.object(FLASH, "OPENOCD_ROOT", openocd), \
                    patch.object(FLASH, "OPENOCD", openocd / "bin/openocd"), \
                    patch.object(FLASH, "OFFICIAL_HASHES", {}), \
                    patch.object(FLASH.subprocess, "run") as command:
                FLASH.flash(firmware)
            # Tuple indexing also works with Python 3.7's mock implementation.
            args = command.call_args[0][0]
            self.assertIn("openocd_gpiod.cfg", args)
            self.assertIn("set filename1 " + str(firmware / "virtualglove-matrix.elf-zsk.bin"), args)
            self.assertEqual(command.call_args.kwargs["timeout"], 120)


if __name__ == "__main__":
    unittest.main()
