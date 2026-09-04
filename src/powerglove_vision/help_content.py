# Project: PowerGlove Vision
# File: src/powerglove_vision/help_content.py
# Purpose: Render the bundled public Markdown guides as safe, offline Help pages.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added the built-in Help library and Markdown reading view.
#   2026-09-03 - Added a live, non-secret cabinet connection reference.
#   2026-09-03 - Renamed the installation route while preserving its original alias.
#   2026-09-03 - Rendered allowlisted inline gesture images used in guide tables.
#   2026-09-03 - Added allowlisted PDF downloads for every public guide.
#   2026-09-03 - Support an unconfigured first-run receiver without blocking local practice.
# Full history: docs/CHANGELOG.md and Git history.

"""Render the bundled public Markdown guides as safe, offline Help pages."""

from __future__ import annotations

import html
import ipaddress
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DOCS_ROOT = Path(__file__).resolve().parents[2] / "docs"
HELP_ASSETS_ROOT = DOCS_ROOT / "images"
HELP_PDFS_ROOT = DOCS_ROOT.parent / "output" / "pdf"
HELP_GUIDES = (
    {"slug": "early-start", "title": "Early sketch startup", "file": "EARLY_START.md", "description": "Install, inspect, and remove the optional UNO Q startup helper.", "group": "Maintain the project"},
    {"slug": "matrix", "title": "Matrix display guide", "file": "MATRIX_GUIDE.md", "description": "Recognize startup, glove animations, Academy letters, game profiles, pairing, and errors.", "group": "Use PowerGlove Vision"},
    {"slug": "architecture", "title": "Architecture and flows", "file": "ARCHITECTURE.md", "description": "System boundaries, recognition, tuning, game input, and deployment diagrams.", "group": "Maintain the project"},
    {
        "slug": "cabinet",
        "title": "This cabinet",
        "file": None,
        "description": "Live UNO Q links and the active RetroPie connection, generated for this cabinet.",
        "group": "Use PowerGlove Vision",
    },
    {
        "slug": "installation",
        "title": "Build and operate",
        "file": "INSTALL_README.md",
        "description": "Installation, secure pairing, the Play Checklist, updates, and troubleshooting.",
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
LEGACY_SLUGS = {"field-guide": "installation"}
SLUG_BY_FILE = {
    str(guide["file"]): str(guide["slug"])
    for guide in HELP_GUIDES
    if guide["file"] is not None
}
HELP_PDFS = {
    "matrix": "PowerGlove-Vision-Matrix-Guide.pdf",
    "architecture": "PowerGlove-Vision-Architecture.pdf",
    "overview": "PowerGlove-Vision-Overview.pdf",
    "installation": "PowerGlove-Vision-Guide.pdf",
    "gameplay": "PowerGlove-Vision-Gameplay-Guide.pdf",
    "programs": "Bad-Street-Brawler-Power-Glove-Programs.pdf",
    "configuration": "PowerGlove-Vision-Configuration-Reference.pdf",
    "security": "PowerGlove-Vision-Security.pdf",
    "components": "PowerGlove-Vision-Third-Party-Components.pdf",
    "contributing": "PowerGlove-Vision-Contributing.pdf",
    "changelog": "PowerGlove-Vision-Changelog.pdf",
}

_HTML_IMAGE_PATTERN = r'<img\s+src="([^"]+)"\s+alt="([^"]*)"\s+width="([0-9]{1,3})"\s*/?>'
_HTML_IMAGE = re.compile(_HTML_IMAGE_PATTERN, re.IGNORECASE)
_INLINE_TOKEN = re.compile(
    r"(" + _HTML_IMAGE_PATTERN + r"|!?\[[^\]]*\]\([^)]*\)|`[^`]*`|\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*))",
    re.IGNORECASE,
)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET = re.compile(r"^\s*[-+*]\s+(.+)$")
_NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.+)$")
_TABLE_DIVIDER = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def guide_for_slug(slug: str) -> dict[str, Any] | None:
    """Return the fixed public guide definition for a URL slug."""
    return GUIDES_BY_SLUG.get(LEGACY_SLUGS.get(slug, slug))


def guide_markdown(slug: str) -> bytes | None:
    """Read an allowlisted guide as UTF-8 bytes for the raw Markdown route."""
    guide = guide_for_slug(slug)
    if guide is None or guide["file"] is None:
        return None
    try:
        return (DOCS_ROOT / str(guide["file"])).read_bytes()
    except OSError:
        return None


def guide_pdf(slug: str) -> tuple[bytes, str] | None:
    """Read one allowlisted public PDF without exposing cabinet-specific files."""
    filename = HELP_PDFS.get(LEGACY_SLUGS.get(slug, slug))
    if filename is None:
        return None
    try:
        return (HELP_PDFS_ROOT / filename).read_bytes(), filename
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
        "The manuals work offline from their Markdown sources, while This cabinet fills in the live connection details.</p>"
        "<p><a class=button href='/help-pdf/overview.pdf'>Open project overview PDF</a></p>"
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
    body = _reading_shell(
        slug,
        rendered,
        contents,
        "<span class=document-actions>"
        f"<a href='/help/{html.escape(slug, quote=True)}.md'>View Markdown</a>"
        f"<a href='/help-pdf/{html.escape(slug, quote=True)}.pdf'>Open PDF</a>"
        "</span>",
    )
    return body, str(guide["title"])


def request_browser_address(host_header: str) -> str:
    """Return a safe hostname or IP literal derived from the browser Host header."""
    try:
        hostname = urlsplit("//" + host_header.strip()).hostname
    except ValueError:
        hostname = None
    if not hostname or len(hostname) > 253:
        return "UNO-Q-NAME.local"
    try:
        address = ipaddress.ip_address(hostname)
        return f"[{address}]" if address.version == 6 else str(address)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", hostname):
            return "UNO-Q-NAME.local"
        return hostname


def cabinet_reference_content(host_header: str, config: dict[str, Any]) -> tuple[str, str]:
    """Build a non-secret cabinet reference from the request address and public settings."""
    board = request_browser_address(host_header)
    receiver = str(config.get("receiver", "")) or "Not configured"
    port = str(config.get("port", 55355))
    profile = str(config.get("profile", "off"))
    profile_names = {
        "bad_street_brawler": "Bad Street Brawler",
        "super_glove_ball": "Super Glove Ball",
        "off": "Gestures off",
    }
    profile_name = profile_names.get(profile, "Program " + profile[-1:].upper() if profile.startswith("program_") else profile)
    tracking_aid = {"none": "Bare hand", "white": "White glove", "black": "Black glove"}.get(
        str(config.get("glove_color", "none")), str(config.get("glove_color", "none"))
    )
    paired = "Configured" if config.get("paired") else "Not configured"
    controller = "Started" if config.get("controller_enabled") else "Stopped"
    http_root = f"http://{board}:8088"
    https_root = f"https://{board}:8443"

    def row(label: str, value: str) -> str:
        """Render one escaped reference-table row."""
        return f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"

    url_rows = "".join(
        "<tr><th>{label}</th><td><a href='{url}'>{url}</a></td></tr>".format(
            label=html.escape(label), url=html.escape(url, quote=True)
        )
        for label, url in (
            ("Dashboard", http_root + "/dashboard"),
            ("Glove Academy", http_root + "/learn"),
            ("Help center", http_root + "/help"),
            ("Connection setup", http_root + "/setup"),
            ("Secure pairing", https_root + "/setup"),
            ("System status", http_root + "/status"),
        )
    )
    settings_rows = "".join(
        (
            row("RetroPie console", receiver),
            row("Controller port", port),
            row("Startup profile", profile_name),
            row("Tracking aid", tracking_aid),
            row("Camera", str(config.get("camera", "auto"))),
            row("Pairing token", paired + " (value never shown)"),
            row("Controller transmission", controller),
        )
    )
    article = (
        "<h1>This cabinet</h1>"
        "<p>These values are generated from the address used to open this page and the UNO Q's active public configuration. They update without editing a guide.</p>"
        "<h2>UNO Q</h2><div class=table-scroll><table><tbody>"
        + row("Address used by this browser", board)
        + row("Web workshop", http_root)
        + row("Secure setup", https_root)
        + "</tbody></table></div>"
        "<h2>Browser URLs</h2><div class=table-scroll><table><tbody>"
        + url_rows
        + "</tbody></table></div>"
        "<h2>Connected RetroPie</h2><div class=table-scroll><table><tbody>"
        + settings_rows
        + "</tbody></table></div>"
        "<blockquote><strong>Private by design</strong> The shared token and passwords are never returned to Help. If you open this page with an IP address, its links use that IP; if you open it with a <code>.local</code> name, the links keep that name.</blockquote>"
    )
    return _reading_shell("cabinet", article, "", ""), "This cabinet"


def _reading_shell(slug: str, rendered: str, contents: str, toolbar_extra: str) -> str:
    """Wrap rendered Help content in the shared toolbar, guide navigation, and contents pane."""
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
        f"{toolbar_extra}</div>"
        "<div class=help-layout><aside class=help-sidebar><div class=label>Guides</div>"
        f"<nav class=guide-nav>{guide_links}</nav>"
        + (f"<div class=toc><div class=label>On this page</div>{contents}</div>" if contents else "")
        + f"</aside><article class=markdown-body>{rendered}</article></div>"
    )
    return body


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
    if image and target in {"../assets/powerglove-vision-logo.png", "assets/powerglove-vision-logo.png"}:
        return "/assets/powerglove-vision-logo.png"
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
        if token.lower().startswith("<img"):
            image_match = _HTML_IMAGE.fullmatch(token)
            if image_match:
                target, alt, width_text = image_match.groups()
                safe_target = _safe_target(target, image=True)
                width = int(width_text)
                maximum_width = 760 if safe_target == "/assets/powerglove-vision-logo.png" else 320
                if safe_target != "#" and 24 <= width <= maximum_width:
                    output.append(
                        "<img loading=lazy src='{src}' alt='{alt}' width='{width}'>".format(
                            src=html.escape(safe_target, quote=True),
                            alt=html.escape(alt, quote=True),
                            width=width,
                        )
                    )
                else:
                    output.append(html.escape(token))
        elif token.startswith("!["):
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
        if _HTML_IMAGE.fullmatch(line.strip()):
            blocks.append("<p>" + _inline(line.strip()) + "</p>")
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
