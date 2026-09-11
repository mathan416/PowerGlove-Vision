#!/usr/bin/env python3
# Project: VirtualGlove
# File: scripts/build-engineering-tools-package.py
# Purpose: Build a separate source toolkit for repeatable research and diagnostics.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Added the optional Engineering Tools archive.
# Full history: docs/CHANGELOG.md and Git history.

"""Package development tools without adding them to ordinary installers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = runpy.run_path(str(Path(__file__).with_name("package-inventory.py")))
ENGINEERING_FILES = INVENTORY["ENGINEERING_FILES"]
SUPPORT_ROOTS = ("src/powerglove_vision/", "native/", "config/")
SUPPORT_FILES = {"LICENSE", "THIRD_PARTY_NOTICES.md", "pyproject.toml"}


def selected_files(root: Path = ROOT) -> list[str]:
    """Return the self-contained, source-only engineering toolkit."""
    tracked = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    ).decode().split("\0")
    selected = []
    for name in tracked:
        path = root / name
        if not name or not path.is_file() or path.is_symlink():
            continue
        if name in ENGINEERING_FILES or name in SUPPORT_FILES or name.startswith(SUPPORT_ROOTS):
            selected.append(name)
    missing = sorted(name for name in ENGINEERING_FILES if not (root / name).is_file())
    if missing:
        raise ValueError("Engineering inventory is missing: " + ", ".join(missing))
    return sorted(set(selected))


def build(version: str, output: Path) -> Path:
    """Create and verify one deterministic-path Engineering Tools ZIP."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", version):
        raise ValueError("Use a release tag without slashes or whitespace")
    output.parent.mkdir(parents=True, exist_ok=True)
    root_name = "VirtualGlove-Engineering-Tools"
    readme = (
        "VirtualGlove Engineering Tools\n\n"
        "These research, replay, tracing, benchmark, documentation-build, and soak-test tools are "
        "not required for normal installation or calibration. Run them from this extracted directory "
        "and follow the matching technical documentation. No ROMs, recordings, device settings, "
        "credentials, caches, compiled cores, or private calibration data are included.\n"
    )
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(root_name + "/README.txt", readme)
        archive.writestr(root_name + "/engineering-tools.json", json.dumps({
            "format": 1, "version": version, "tool_files": sorted(ENGINEERING_FILES),
        }, indent=2) + "\n")
        for name in selected_files():
            info = zipfile.ZipInfo(root_name + "/" + name)
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.external_attr = ((0o755 if (ROOT / name).stat().st_mode & stat.S_IXUSR else 0o644) << 16)
            archive.writestr(info, (ROOT / name).read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or "../" in "\n".join(archive.namelist()):
            raise ValueError("Engineering Tools archive validation failed")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(digest + "  " + output.name + "\n")
    return output


def main() -> None:
    """Build the optional source toolkit without publishing it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/install/VirtualGlove-Engineering-Tools.zip")
    args = parser.parse_args()
    print("Built " + str(build(args.version, args.output)))


if __name__ == "__main__":
    main()
