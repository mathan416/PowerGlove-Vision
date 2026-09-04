#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/build-install-packages.py
# Purpose: Build validated versioned installers and checksums for both target machines.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added versioned two-machine installation packages.
# Full history: docs/CHANGELOG.md and Git history.

"""Build release assets after generating the public PDFs and App Lab ZIP."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load_installer():
    """Reuse installation-time archive validation before distributing any package."""
    spec = importlib.util.spec_from_file_location("package_installer", ROOT / "scripts/install-package.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(version, destination):
    """Create two packages from the verified App Lab bundle and emit their checksums."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", version):
        raise ValueError("Use a release tag without slashes or whitespace")
    import runpy
    archive = ROOT / "output/app-lab/PowerGlove-Vision-Uno-Q.zip"
    errors = runpy.run_path(str(ROOT / "scripts/verify-app-lab-package.py"))["archive_errors"](archive)
    if errors:
        raise ValueError("\n".join(errors))
    destination.mkdir(parents=True, exist_ok=True)
    assets = []
    with zipfile.ZipFile(archive) as original:
        for machine, name in (("uno-q", "Uno-Q"), ("retropie", "RetroPie")):
            output = destination / ("PowerGlove-Vision-" + name + ".zip")
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as package:
                for item in original.infolist():
                    relative = Path(item.filename).parts[1:]
                    if not relative or relative == ("install-release.json",):
                        continue
                    if machine == "retropie" and relative[0] not in (
                            "scripts", "src", "retropie", "config", "licenses", "LICENSE", "THIRD_PARTY_NOTICES.md"):
                        continue
                    package.writestr(copy.copy(item), original.read(item.filename))
                package.writestr("PowerGlove-Vision/install-release.json", json.dumps(
                    {"format": 1, "machine": machine, "version": version}) + "\n")
            with tempfile.TemporaryDirectory() as directory:
                load_installer().unpack(output, Path(directory), machine, version)
            assets.append(output)
    for name in ("install-uno-q.sh", "install-retropie.sh", "install-package.py"):
        target = destination / name
        shutil.copy2(str(ROOT / "scripts" / name), str(target))
        assets.append(target)
    lines = []
    for path in assets:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        lines.append(digest.hexdigest() + "  " + path.name)
    (destination / "SHA256SUMS").write_text("\n".join(lines) + "\n")
    print("Validated release assets: " + str(destination))


def main():
    """Build explicit release assets without publishing or creating a Git tag."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Exact release tag, including development prerelease tags")
    parser.add_argument("--output", type=Path, default=ROOT / "output/install")
    args = parser.parse_args()
    build(args.version, args.output)


if __name__ == "__main__":
    main()
