#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/check-documentation.py
# Purpose: Validate project documentation layout, local links, configuration coverage, and PDF editions.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added documentation and generated-PDF consistency checks.
#   2026-09-03 - Registered the illustrated gameplay handbook and PDF edition.
#   2026-09-03 - Added Help-library and registered-game coverage checks.
#   2026-09-03 - Allowed the Gun Smoke display title for its punctuated ROM basename.
# Full history: docs/CHANGELOG.md and Git history.

"""Check that maintained documentation is complete, linked, and publishable."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")
HTML_LINK = re.compile(r"(?:href|src)=[\"']([^\"']+)[\"']", re.IGNORECASE)
HELP_FILE = re.compile(r'[\"\x27]file[\"\x27]\s*:\s*[\"\x27]([^\"\x27]+\.md)[\"\x27]')
CONFIGURATION_FILES = (
    "config/device.example.json",
    "config/games.json",
    "config/launcher.example.json",
    "config/profiles.json",
    "app.yaml",
    "sketch/sketch.yaml",
    "pyproject.toml",
    "retropie/retroarch/PowerGlove Vision.cfg",
    "retropie/powerglove-receiver.service",
    "retropie/powerglove-receiver.timer",
    "retropie/powerglove-games.service",
    "uno-q/powerglove-system-shutdown.path",
    "uno-q/powerglove-system-shutdown.service",
    "uno-q/powerglove-system-shutdown.conf",
    ".github/workflows/quality.yml",
)
PDF_EDITIONS = {
    "docs/ARCHITECTURE.md": "PowerGlove-Vision-Architecture.pdf",
    "README.md": "PowerGlove-Vision-Overview.pdf",
    "docs/INSTALL_README.md": "PowerGlove-Vision-Guide.pdf",
    "docs/cheatsheet.md": "PowerGlove-Vision-Quick-Reference.pdf",
    "docs/bad-street-brawler-programs.md": "Bad-Street-Brawler-Power-Glove-Programs.pdf",
    "docs/THIRD_PARTY_COMPONENTS.md": "PowerGlove-Vision-Third-Party-Components.pdf",
    "docs/CHANGELOG.md": "PowerGlove-Vision-Changelog.pdf",
    "docs/CONFIGURATION_REFERENCE.md": "PowerGlove-Vision-Configuration-Reference.pdf",
    "docs/SECURITY.md": "PowerGlove-Vision-Security.pdf",
    "docs/CONTRIBUTING.md": "PowerGlove-Vision-Contributing.pdf",
    "docs/GAMEPLAY_GUIDE.md": "PowerGlove-Vision-Gameplay-Guide.pdf",
}


def tracked_markdown() -> list[Path]:
    """Return Markdown files tracked by Git in stable path order."""
    output = subprocess.check_output(
        ["git", "ls-files", "-z", "*.md"], cwd=ROOT
    ).decode().split("\0")
    return sorted(Path(name) for name in output if name)


def local_targets(path: Path) -> list[Path]:
    """Extract repository-local Markdown and HTML link targets from one document."""
    text = (ROOT / path).read_text()
    targets = [*MARKDOWN_LINK.findall(text), *HTML_LINK.findall(text)]
    resolved = []
    for raw in targets:
        value = raw.strip().strip("<>").split(maxsplit=1)[0]
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or value.startswith(("#", "/")):
            continue
        relative = unquote(parsed.path)
        if relative:
            resolved.append(path.parent / relative)
    return resolved


def check_pdfs(errors: list[str]) -> None:
    """Verify the exact PDF set, readable text, and absence of renderer placeholders."""
    try:
        from pypdf import PdfReader
    except ImportError:
        errors.append("pypdf is required for --require-pdfs")
        return
    output = ROOT / "output" / "pdf"
    expected = set(PDF_EDITIONS.values())
    present = {path.name for path in output.glob("*.pdf")}
    for name in sorted(expected - present):
        errors.append(f"missing PDF edition: output/pdf/{name}")
    for name in sorted(present - expected):
        errors.append(f"unregistered PDF edition: output/pdf/{name}")
    for name in sorted(expected & present):
        path = output / name
        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        if len(text) < 500:
            errors.append(f"PDF has unexpectedly little extractable text: {path.relative_to(ROOT)}")
        if "@@TOKEN" in text:
            errors.append(f"PDF contains unresolved renderer placeholder: {path.relative_to(ROOT)}")


def check_help_coverage(markdown: list[Path], errors: list[str]) -> None:
    """Require every portable guide to appear in the built-in Help library."""
    source = (ROOT / "src" / "powerglove_vision" / "help_content.py").read_text()
    help_files = set(HELP_FILE.findall(source))
    portable_guides = {
        path.name
        for path in markdown
        if path.parts[:1] == ("docs",) and path.name != "cheatsheet.md"
    }
    for name in sorted(portable_guides - help_files):
        errors.append(f"public guide is missing from the Help library: docs/{name}")


def check_gameplay_coverage(errors: list[str]) -> None:
    """Require an illustrated gameplay section for every registered game title."""
    try:
        registry = json.loads((ROOT / "config" / "games.json").read_text())["games"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        errors.append(f"cannot check gameplay coverage: {exc}")
        return
    gameplay = (ROOT / "docs" / "GAMEPLAY_GUIDE.md").read_text()
    titles = {
        re.sub(r"\s*\([^)]*\)$", "", Path(filename).stem)
        for filename in registry
    }
    for title in sorted(titles):
        display_title = {"Gun.Smoke": "Gun Smoke", "Sesame Street 123": "Sesame Street 1-2-3"}.get(title, title)
        if f"## {display_title}" not in gameplay:
            errors.append(f"registered game is missing from the gameplay guide: {title}")


def build_parser() -> argparse.ArgumentParser:
    """Create the documentation-audit command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-pdfs",
        action="store_true",
        help="also require and inspect every registered PDF edition",
    )
    return parser


def main() -> int:
    """Run documentation checks and return a CI-friendly process status."""
    args = build_parser().parse_args()
    errors: list[str] = []
    markdown = tracked_markdown()
    for path in markdown:
        # Distribution-wide licensing notices stay beside the root LICENSE.
        if path not in {Path("README.md"), Path("THIRD_PARTY_NOTICES.md")} and path.parts[0] != "docs":
            errors.append(f"project Markdown must be under docs/: {path}")
        for target in local_targets(path):
            if not (ROOT / target).exists():
                errors.append(f"broken local link in {path}: {target}")

    check_help_coverage(markdown, errors)
    check_gameplay_coverage(errors)

    reference = (ROOT / "docs" / "CONFIGURATION_REFERENCE.md").read_text()
    for name in CONFIGURATION_FILES:
        if name not in reference:
            errors.append(f"configuration reference does not describe {name}")
    for path in sorted((ROOT / "config").glob("*.json")):
        try:
            json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON in {path.relative_to(ROOT)}: {exc}")

    missing_sources = sorted(set(PDF_EDITIONS) - {str(path) for path in markdown})
    for name in missing_sources:
        errors.append(f"PDF source is not tracked Markdown: {name}")
    if args.require_pdfs:
        check_pdfs(errors)

    if errors:
        print("\n".join(errors))
        return 1
    suffix = " and PDF editions" if args.require_pdfs else ""
    print(f"Documentation audit passed for {len(markdown)} Markdown files{suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
