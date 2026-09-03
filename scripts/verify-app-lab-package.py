#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/verify-app-lab-package.py
# Purpose: Reject incomplete, unsafe, or private content in the generated App Lab installation ZIP.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added repeatable installation-package content and path verification.
#   2026-09-03 - Required the offline Help renderer in every installation ZIP.
#   2026-09-03 - Required only the allowlisted public PDF editions.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify the generated UNO Q App Lab installation ZIP before publication."""

from __future__ import annotations

import argparse
import hashlib
import stat
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVE = ROOT / "output" / "app-lab" / "PowerGlove-Vision-Uno-Q.zip"
PACKAGE_ROOT = PurePosixPath("PowerGlove-Vision")
PUBLIC_PDF_NAMES = {
    "Bad-Street-Brawler-Power-Glove-Programs.pdf",
    "PowerGlove-Vision-Changelog.pdf",
    "PowerGlove-Vision-Configuration-Reference.pdf",
    "PowerGlove-Vision-Contributing.pdf",
    "PowerGlove-Vision-Gameplay-Guide.pdf",
    "PowerGlove-Vision-Guide.pdf",
    "PowerGlove-Vision-Overview.pdf",
    "PowerGlove-Vision-Security.pdf",
    "PowerGlove-Vision-Third-Party-Components.pdf",
}
PUBLIC_PDF_PATHS = {f"output/pdf/{name}" for name in PUBLIC_PDF_NAMES}
REQUIRED_FILES = {
    "PowerGlove-Vision/LICENSE",
    "PowerGlove-Vision/README.md",
    "PowerGlove-Vision/app.yaml",
    "PowerGlove-Vision/docs/CONFIGURATION_REFERENCE.md",
    "PowerGlove-Vision/docs/CONTRIBUTING.md",
    "PowerGlove-Vision/docs/SECURITY.md",
    "PowerGlove-Vision/docs/THIRD_PARTY_COMPONENTS.md",
    "PowerGlove-Vision/python/main.py",
    "PowerGlove-Vision/sketch/sketch.ino",
    "PowerGlove-Vision/src/powerglove_vision/runtime_assets.py",
    "PowerGlove-Vision/src/powerglove_vision/help_content.py",
} | {f"PowerGlove-Vision/{path}" for path in PUBLIC_PDF_PATHS}
FORBIDDEN_PARTS = {".git", ".venv", "__pycache__", "data", "tests", "tmp"}
FORBIDDEN_NAMES = {".DS_Store", "cheatsheet.md", "hand_landmarker.task"}
FORBIDDEN_SUFFIXES = {".pyc"}


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of an archive read in bounded blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def archive_errors(path: Path) -> list[str]:
    """Return content, traversal, and accidental-disclosure errors for one ZIP."""
    errors = []
    try:
        with ZipFile(path) as archive:
            bad_member = archive.testzip()
            if bad_member:
                errors.append(f"corrupt member: {bad_member}")
            names = {info.filename for info in archive.infolist() if not info.is_dir()}
            for info in archive.infolist():
                member = PurePosixPath(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    errors.append(f"unsafe archive path: {info.filename}")
                if not member.parts or member.parts[0] != PACKAGE_ROOT.name:
                    errors.append(f"member outside {PACKAGE_ROOT}/: {info.filename}")
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    errors.append(f"symbolic link is not allowed in the App Lab installation ZIP: {info.filename}")
                relative_parts = set(member.parts[1:])
                relative = PurePosixPath(*member.parts[1:])
                if relative_parts & FORBIDDEN_PARTS:
                    errors.append(f"private or generated path included: {info.filename}")
                if member.name in FORBIDDEN_NAMES or member.suffix in FORBIDDEN_SUFFIXES:
                    errors.append(f"forbidden file included: {info.filename}")
                if not info.is_dir() and "output" in relative_parts and str(relative) not in PUBLIC_PDF_PATHS:
                    errors.append(f"unapproved output file included: {info.filename}")
                if member.suffix == ".pdf" and str(relative) not in PUBLIC_PDF_PATHS:
                    errors.append(f"unapproved PDF included: {info.filename}")
            for name in sorted(REQUIRED_FILES - names):
                errors.append(f"required package file is missing: {name}")
            wheels = [name for name in names if "/python/worker-wheels/mediapipe-" in name and name.endswith(".whl")]
            if len(wheels) != 1:
                errors.append(f"expected one UNO Q MediaPipe wheel, found {len(wheels)}")
    except (BadZipFile, FileNotFoundError) as exc:
        errors.append(str(exc))
    return errors


def build_parser() -> argparse.ArgumentParser:
    """Create the installation-package verification command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    return parser


def main() -> int:
    """Verify an archive, print its digest, and return a CI-friendly status."""
    path = build_parser().parse_args().archive
    errors = archive_errors(path)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"App Lab installation ZIP verified: {path}")
    print(f"SHA-256: {sha256_file(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
