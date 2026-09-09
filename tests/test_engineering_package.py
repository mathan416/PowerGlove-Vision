# Project: PowerGlove Vision
# File: tests/test_engineering_package.py
# Purpose: Keep research tools separate from ordinary release installers.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Added Engineering Tools package coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify the optional tools archive is complete, private-data-free, and separate."""

import json
from pathlib import Path
import runpy
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BUILDER = runpy.run_path(str(ROOT / "scripts/build-engineering-tools-package.py"))


class EngineeringPackageTests(unittest.TestCase):
    def test_archive_contains_tools_and_shared_source_but_no_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tools.zip"
            BUILDER["build"]("0.4.0-test", output)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                prefix = "PowerGlove-Vision-Engineering-Tools/"
                manifest = json.loads(archive.read(prefix + "engineering-tools.json"))
                self.assertIn("scripts/benchmark-vision-replay.py", manifest["tool_files"])
                self.assertIn(prefix + "scripts/benchmark-vision-replay.py", names)
                self.assertIn(prefix + "src/powerglove_vision/gesture.py", names)
                self.assertIn(prefix + "native/nestopia-powerglove/diagnostic_trace.h", names)
                self.assertFalse(any("/data/" in name or "/tests/" in name
                                     or name.endswith((".mov", ".mp4", ".nes", ".7z"))
                                     for name in names))
            self.assertTrue(output.with_suffix(".zip.sha256").is_file())


if __name__ == "__main__":
    unittest.main()
