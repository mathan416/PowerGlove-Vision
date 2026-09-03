# Project: PowerGlove Vision
# File: src/powerglove_vision/help_content.py
# Purpose: Render the bundled public Markdown guides as safe, offline Help pages.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added the built-in Help library and Markdown reading view.
# Full history: docs/CHANGELOG.md and Git history.

"""Render the bundled public Markdown guides as safe, offline Help pages."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any


DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"
HELP_ASSETS_ROOT = DOCS_ROOT / "images"
HELP_GUIDES = (
    {
        "slug": "field-guide",
        "title": "Build and operate",
        "file": "INSTALL_README.md",
        "description": "Installation, secure pairing, daily play, updates, and troubleshooting.",
        "group": "Use PowerGlove Vision",
    },
    {
        "slug": "gameplay",
        "title": "Game and gesture guide",
        "file": "GAMEPLAY_GUIDE.md",
        "description": "Illustrated controls and play tips for every configured game.",
        "group": "Use PowerGlove Vision",
    },
    {
        "slug": "programs",
        "title": "Programs A-I",
        "file": "bad-street-brawler-programs.md",
        "description": "The original Power Glove programs and their camera-based equivalents.",
        "group": "Use PowerGlove Vision",
    },
    {
        "slug": "configuration",
        "title": "Configuration reference",
        "file": "CONFIGURATION_REFERENCE.md",
        "description": "Every public setting, template, generated file, and installed location.",
        "group": "Maintain the project",
    },
    {
        "slug": "security",
        "title": "Security and privacy",
        "file": "SECURITY.md",
        "description": "Pairing boundaries, safe network use, shutdown permissions, and reporting.",
        "group": "Maintain the project",
    },
    {
        "slug": "components",
        "title": "Third-party components",
        "file": "THIRD_PARTY_COMPONENTS.md",
        "description": "MediaPipe, model, license, checksum, and runtime provenance.",
        "group": "Maintain the project",
    },
    {
        "slug": "contributing",
        "title": "Contributing",
        "file": "CONTRIBUTING.md",
        "description": "Source formatting, tests, documentation, packaging, and review expectations.",
        "group": "Maintain the project",
    },
    {
        "slug": "changelog",
        "title": "Changelog",
        "file": "CHANGELOG.md",
        "description": "User-visible additions, fixes, security changes, and documentation updates.",
        "group": "Maintain the project",
    },
)
GUIDES_BY_SLUG = {str(guide["slug"]): guide for guide in HELP_GUIDES}
SLUG_BY_FILE = {str(guide["file"]): str(guide["slug"]) for guide in HELP_GUIDES}

_INLINE_TOKEN = re.compile(r"(!?\[[^\]]*\]\([^)]*\)|`[^`]*`|\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*))")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET = re.compile(r"^\s*[-+*]\s+(.+)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.+)$")
_TABLE_DIVIDER = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def guide_for_slug(slug: str) -> dict[str, Any] | None:
    """Return the fixed public guide definition for a URL slug."""
    return GUIDES_BY_SLUG.get(slug)


def guide_markdown(slug: str) -> bytes | None:
    """Read an allowlisted guide as UTF-8 bytes for the raw Markdown route."""
    guide = guide_for_slug(slug)
    if guide is None:
        return None
    try:
        return (DOCS_ROOT / str(guide["file"])).read_bytes()
    except OSError:
        return None


def help_asset(relative_name: str) -> tuple[bytes, str] | None:
    """Read an image below docs/images while rejecting traversal and unknown types."""
    root = HELP_ASSETS_ROOT.resolve()
    try:
        requested = (root / relative_name).resolve()
        requested.relative_to(root)
    except (OSError, ValueError):
        return None
    content_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}
    content_type = content_types.get(requested.suffix.lower())
    if content_type is None or not requested.is_file():
        return None
    try:
        return requested.read_bytes(), content_type
    except OSError:
        return None


def help_index_content() -> str:
    """Build the Help landing-page body from the public guide registry."""
    sections = []
    for group in ("Use PowerGlove Vision", "Maintain the project"):
        cards = []
        for guide in HELP_GUIDES:
            if guide["group"] != group:
                continue
            cards.append(
                "<a class='guide-card' href='/help/{slug}'>"
                "<span class=guide-arrow aria-hidden=true>→</span>"
                "<h2>{title}</h2><p>{description}</p></a>".format(
                    slug=html.escape(str(guide["slug"]), quote=True),
                    title=html.escape(str(guide["title"])),
                    description=html.escape(str(guide["description"])),
                )
            )
        sections.append("<section class=help-group><h2>{}</h2><div class=guide-grid>{}</div></section>".format(group, "".join(cards)))
    return (
        "<h1>Help, without leaving the glove.</h1>"
        "<p class=lead>Read the maintained PowerGlove Vision guides directly on this UNO Q. "
        "Everything here works offline and comes from the same Markdown files used for the printable manuals.</p>"
        + "".join(sections)
    )


def help_document_content(slug: str) -> tuple[str, str] | None:
    """Return a styled reading-page body and browser title for one public guide."""
    guide = guide_for_slug(slug)
    source = guide_markdown(slug)
    if guide is None or source is None:
        return None
    rendered, headings = render_markdown(source.decode("utf-8"))
    contents = "".join(
        "<a class='toc-level-{level}' href='#{anchor}'>{title}</a>".format(
            level=level, anchor=html.escape(anchor, quote=True), title=html.escape(title)
        )
        for level, anchor, title in headings
        if level <= 3
    )
    guide_links = "".join(
        "<a class='{current}' href='/help/{slug}'>{title}</a>".format(
            current="current" if item["slug"] == slug else "",
            slug=html.escape(str(item["slug"]), quote=True),
            title=html.escape(str(item["title"])),
        )
        for item in HELP_GUIDES
    )
    body = (
        "<div class=help-toolbar><a href=/help>← All help</a>"
        f"<a href='/help/{html.escape(slug, quote=True)}.md'>View Markdown</a></div>"
        "<div class=help-layout><aside class=help-sidebar><div class=label>Guides</div>"
        f"<nav class=guide-nav>{guide_links}</nav>"
        + (f"<div class=toc><div class=label>On this page</div>{contents}</div>" if contents else "")
        + f"</aside><article class=markdown-body>{rendered}</article></div>"
    )
    return body, str(guide["title"])


def _anchor(text: str, used: set[str]) -> str:
    """Create a stable, unique HTML heading identifier from visible text."""
    base = re.sub(r"[^a-z0-9]+", "-", re.sub(r"[`*_]", "", text).lower()).strip("-") or "section"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _safe_target(target: str, image: bool = False) -> str:
    """Translate known documentation links and reject unsafe URL schemes."""
    target = target.strip()
    if image and target.startswith("images/"):
        return "/help-assets/" + target[len("images/"):]
    filename = target.split("#", 1)[0].rsplit("/", 1)[-1]
    if filename in SLUG_BY_FILE:
        anchor = "#" + target.split("#", 1)[1] if "#" in target else ""
        return "/help/" + SLUG_BY_FILE[filename] + anchor
    if target.startswith(("https://", "http://", "#")):
        return target
    return "#"


def _inline(text: str) -> str:
    """Render safe Markdown emphasis, code, links, and images within one block."""
    output = []
    position = 0
    for match in _INLINE_TOKEN.finditer(text):
        output.append(html.escape(text[position:match.start()]))
        token = match.group(0)
        if token.startswith("!["):
            image_match = re.match(r"!\[([^]]*)\]\(([^)]*)\)", token)
            if image_match:
                alt, target = image_match.groups()
                output.append(
                    "<img loading=lazy src='{src}' alt='{alt}'>".format(
                        src=html.escape(_safe_target(target, image=True), quote=True),
                        alt=html.escape(alt, quote=True),
                    )
                )
        elif token.startswith("["):
            link_match = re.match(r"\[([^]]*)\]\(([^)]*)\)", token)
            if link_match:
                label, target = link_match.groups()
                safe_target = _safe_target(target)
                external = " target=_blank rel='noopener noreferrer'" if safe_target.startswith(("http://", "https://")) else ""
                output.append(
                    "<a href='{target}'{external}>{label}</a>".format(
                        target=html.escape(safe_target, quote=True), external=external, label=html.escape(label)
                    )
                )
        elif token.startswith("`"):
            output.append("<code>{}</code>".format(html.escape(token[1:-1])))
        elif token.startswith("**"):
            output.append("<strong>{}</strong>".format(html.escape(token[2:-2])))
        else:
            output.append("<em>{}</em>".format(html.escape(token[1:-1])))
        position = match.end()
    output.append(html.escape(text[position:]))
    return "".join(output)


def _table_cells(line: str) -> list[str]:
    """Split one pipe-delimited Markdown table row into trimmed cells."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render_markdown(source: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Render the project's trusted Markdown subset into escaped HTML and a contents list."""
    lines = source.splitlines()
    blocks = []
    headings = []
    used_anchors: set[str] = set()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.lstrip().startswith("<"):
            index += 1
            continue
        if line.startswith("```"):
            language = line[3:].strip()
            code_lines = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index])
                index += 1
            index += 1 if index < len(lines) else 0
            blocks.append(
                "<pre><code class='language-{language}'>{code}</code></pre>".format(
                    language=html.escape(language, quote=True), code=html.escape("\n".join(code_lines))
                )
            )
            continue
        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            anchor = _anchor(title, used_anchors)
            headings.append((level, anchor, re.sub(r"[`*_]", "", title)))
            blocks.append(f"<h{level} id='{anchor}'>{_inline(title)}</h{level}>")
            index += 1
            continue
        if index + 1 < len(lines) and "|" in line and _TABLE_DIVIDER.match(lines[index + 1]):
            headers = _table_cells(line)
            index += 2
            rows = []
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(_table_cells(lines[index]))
                index += 1
            head = "".join(f"<th>{_inline(cell)}</th>" for cell in headers)
            body = "".join("<tr>{}</tr>".format("".join(f"<td>{_inline(cell)}</td>" for cell in row)) for row in rows)
            blocks.append(f"<div class=table-scroll><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")
            continue
        list_match = _BULLET.match(line) or _NUMBERED.match(line)
        if list_match:
            ordered = _NUMBERED.match(line) is not None
            pattern = _NUMBERED if ordered else _BULLET
            items = []
            while index < len(lines):
                item = pattern.match(lines[index])
                if item is None:
                    break
                items.append(f"<li>{_inline(item.group(1))}</li>")
                index += 1
            tag = "ol" if ordered else "ul"
            blocks.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue
        if line.startswith(">"):
            quoted = []
            while index < len(lines) and lines[index].startswith(">"):
                quoted.append(lines[index][1:].strip())
                index += 1
            blocks.append("<blockquote>{}</blockquote>".format(_inline(" ".join(quoted))))
            continue
        if re.match(r"^\s*([-*_])(?:\s*\1){2,}\s*$", line):
            blocks.append("<hr>")
            index += 1
            continue
        paragraph = [line.strip()]
        index += 1
        while index < len(lines) and lines[index].strip():
            upcoming = lines[index]
            if upcoming.startswith(("```", ">")) or upcoming.lstrip().startswith("<") or _HEADING.match(upcoming) or _BULLET.match(upcoming) or _NUMBERED.match(upcoming):
                break
            if index + 1 < len(lines) and "|" in upcoming and _TABLE_DIVIDER.match(lines[index + 1]):
                break
            paragraph.append(upcoming.strip())
            index += 1
        blocks.append("<p>{}</p>".format(_inline(" ".join(paragraph))))
    return "\n".join(blocks), headings
