# Project: PowerGlove Vision
# File: tests/test_versioning.py
# Purpose: Verify release and dev labels survive exported application builds.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Derive the displayed version from release and build metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify checkout and exported build version labels."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from powerglove_vision import versioning


class VersionTests(unittest.TestCase):
    def test_main_and_dev_labels(self):
        for branch, expected in [("main", "0.2.5"), ("dev", "0.2.5-dev")]:
            self.assertEqual(versioning.display_version({"version": "0.2.5", "branch": branch}), expected)

    def test_exported_app_uses_stamp_without_git(self):
        with tempfile.TemporaryDirectory() as d:
            module = Path(d) / "src/powerglove_vision/versioning.py"
            module.parent.mkdir(parents=True)
            for branch, expected in [("main", "0.2.5"), ("dev", "0.2.5-dev")]:
                module.with_name("_build_info.json").write_text(json.dumps({"version": "0.2.5", "branch": branch}))
                with patch.object(versioning, "__file__", str(module)):
                    self.assertEqual(versioning.current_version(), expected)

    def test_checkout_uses_project_version_and_branch(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".git").mkdir()
            (root / "pyproject.toml").write_text('[build-system]\nrequires=[]\n[project]\nversion = "0.2.6"\n[tool.other]\nversion = "wrong"\n')
            with patch.object(versioning.subprocess, "check_output", return_value="dev\n"):
                self.assertEqual(versioning.build_identity(root), {"version": "0.2.6", "branch": "dev"})
