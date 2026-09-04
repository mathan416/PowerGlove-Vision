#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/application-payload.py
# Purpose: Stage one public application payload for releases and Wi-Fi deployment.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Unified release and maintenance file selection.
# Full history: docs/CHANGELOG.md and Git history.

"""Stage public source and PDFs; omit ignored exports and private cabinet files."""
import argparse
from pathlib import Path
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOTS = {"src", "python", "scripts", "sketch", "config", "docs", "models", "licenses", "retropie", "uno-q", "bricks"}
PUBLIC_FILES = {"README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "pyproject.toml", "app.yaml", "assets/powerglove-vision-logo.png"}


def selected_files(root):
    """Select Git-visible application sources, including new nonignored source files."""
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=str(root)
    ).decode().split("\0")
    pdfs = runpy.run_path(str(root / "scripts/verify-app-lab-package.py"))["PUBLIC_PDF_PATHS"]
    selected = set()
    for name in names:
        path = Path(name)
        if not name or not (root / path).is_file():
            continue
        if name in pdfs:
            selected.add(name)
            continue
        if (name not in PUBLIC_FILES and path.parts[0] not in PUBLIC_ROOTS
                or name == "docs/cheatsheet.md" or path.suffix == ".pdf"
                or set(path.parts) & {"data", ".cache", "__pycache__", ".venv", "tmp"}
                or path.suffix in {".pyc", ".pyo"} or path.name in {".DS_Store", "CODE_REVIEW_MAP.txt"}
                or name == "src/powerglove_vision/_build_info.json"):
            continue
        selected.add(name)
    if not pdfs <= selected:
        raise ValueError("Build and track all public PDF editions before packaging")
    return sorted(selected)


def stage(root, destination):
    """Copy the selected files and stamp identity without exporting Git metadata."""
    for name in selected_files(root):
        source = root / name
        if source.is_symlink():
            raise ValueError("Refusing a symbolic application source: " + name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(target))
    subprocess.run(["python3", str(root / "scripts/stamp-build-version.py"),
                    str(destination / "src/powerglove_vision/_build_info.json")], check=True)


def main():
    """Build the shared payload in a caller-owned empty staging directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.destination.exists() and any(args.destination.iterdir()):
        parser.error("Use an empty staging directory")
    stage(ROOT, args.destination)


if __name__ == "__main__":
    main()
