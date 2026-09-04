# Project: PowerGlove Vision
# File: src/powerglove_vision/versioning.py
# Purpose: Identify the release version and source branch in checkouts and deployed builds.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Derive the displayed version from release and build metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Release and build identity without requiring Git on the deployed accessory."""

import json
import os
import re
import subprocess
from pathlib import Path


def build_identity(root):
    """Read the authoritative release number and detect the source branch."""
    text = (root / "pyproject.toml").read_text()
    project = re.search(r"(?ms)^\[project\]\s*$(.*?)(?=^\[|\Z)", text).group(1)
    version = re.search(r'^version\s*=\s*"([^"]+)"', project, re.M).group(1)
    branch = "unknown"
    if (root / ".git").exists():
        try:
            branch = subprocess.check_output(
                ["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd=str(root),
                stderr=subprocess.DEVNULL, universal_newlines=True, timeout=5,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or "unknown"
    return {"version": version, "branch": branch}


def display_version(identity):
    """Mark dev builds while keeping main release numbers unchanged."""
    return identity["version"] + ("-dev" if identity["branch"] == "dev" else "")


def current_version():
    """Prefer live checkout identity, otherwise read the packaged build stamp."""
    root = Path(__file__).resolve().parents[2]
    stamp = Path(__file__).with_name("_build_info.json")
    if (root / ".git").exists():
        return display_version(build_identity(root))
    if stamp.is_file():
        return display_version(json.loads(stamp.read_text()))
    if (root / "pyproject.toml").is_file():
        return display_version(build_identity(root))
    try:
        from importlib.metadata import version
        return version("powerglove-vision")
    except (ImportError, LookupError):
        return "unknown"
