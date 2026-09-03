#!/usr/bin/env python3
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
"""Build polished, distributable PowerGlove Vision PDF field guides."""

from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    CondPageBreak,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "pdf"
LOGO = ROOT / "assets" / "powerglove-vision-logo.png"

NIGHT = colors.HexColor("#07111F")
INK = colors.HexColor("#111827")
BLUE = colors.HexColor("#087EBD")
CYAN = colors.HexColor("#24D8F5")
RED = colors.HexColor("#F01846")
PAPER = colors.HexColor("#F4F7FB")
GRID = colors.HexColor("#C8D4E3")
MUTED = colors.HexColor("#526175")
PALE_BLUE = colors.HexColor("#E7F7FC")


def normalize(text: str) -> str:
    replacements = {
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
        "\u2014": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"',
        "\u201d": '"', "\u2026": "...", "\u2192": "->", "\u2190": "<-",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def inline(text: str) -> str:
    text = html.escape(normalize(text.strip()))
    text = re.sub(
        r"\[([^]]+)\]\(([^)]+)\)",
        r'<link href="\2" color="#087EBD"><u>\1</u></link>',
        text,
    )
    text = re.sub(r"`([^`]+)`", r'<font name="Courier" color="#087EBD">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(inline(text), style)


def image_flowable(path: Path, max_width: float, max_height: float) -> Image:
    reader = ImageReader(str(path))
    width, height = reader.getSize()
    scale = min(max_width / width, max_height / height)
    return Image(str(path), width=width * scale, height=height * scale)


def parse_table(lines: list[str], start: int, styles: dict[str, ParagraphStyle]):
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
        index += 1
    if len(rows) > 1:
        rows.pop(1)
    formatted = [
        [Paragraph(inline(cell), styles["table_head"] if row_number == 0 else styles["table"])
         for cell in row]
        for row_number, row in enumerate(rows)
    ]
    columns = max(len(row) for row in formatted)
    if columns == 2:
        widths = [2.05 * inch, 4.55 * inch]
    elif columns == 4:
        widths = [1.25 * inch, 1.25 * inch, 1.25 * inch, 2.85 * inch]
    else:
        widths = [6.6 * inch / columns] * columns
    table = Table(formatted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 0), (-1, 0), 2, CYAN),
        ("GRID", (0, 1), (-1, -1), 0.35, GRID),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table, index


def parse_list(lines: list[str], start: int, styles: dict[str, ParagraphStyle]):
    first = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", lines[start])
    ordered = bool(re.match(r"^\s*\d+\.", lines[start]))
    items: list[ListItem] = []
    index = start
    while index < len(lines):
        match = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.+)$", lines[index])
        if not match:
            break
        parts = [match.group(1).strip()]
        index += 1
        while index < len(lines) and lines[index].strip():
            candidate = lines[index]
            if re.match(r"^\s*(?:[-*]|\d+\.)\s+", candidate):
                break
            stripped = candidate.strip()
            if stripped.startswith(("#", "```", "|", ">", "![", "<p")):
                break
            parts.append(stripped)
            index += 1
        items.append(ListItem(paragraph(" ".join(parts), styles["body"]), leftIndent=10))
        if index < len(lines) and not lines[index].strip():
            lookahead = index + 1
            if lookahead < len(lines) and re.match(r"^\s*(?:[-*]|\d+\.)\s+", lines[lookahead]):
                index = lookahead
                continue
            break
    return ListFlowable(
        items,
        bulletType="1" if ordered else "bullet",
        leftIndent=24,
        bulletFontName="Helvetica-Bold",
        bulletFontSize=8,
        bulletColor=RED if ordered else BLUE,
        spaceAfter=9,
    ), index


def markdown_story(source: Path, styles: dict[str, ParagraphStyle]):
    lines = source.read_text(encoding="utf-8").splitlines()
    story = []
    index = 0
    skipped_html = False
    skipped_title = False
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("<p"):
            skipped_html = True
            index += 1
            continue
        if skipped_html:
            if line.endswith("</p>"):
                skipped_html = False
            index += 1
            continue
        if line == "---":
            story.append(Spacer(1, 8))
            index += 1
            continue

        image_match = re.fullmatch(r"!\[([^]]*)\]\(([^)]+)\)", line)
        if image_match:
            image_path = (source.parent / image_match.group(2)).resolve()
            if image_path.exists():
                image = image_flowable(image_path, 6.1 * inch, 2.85 * inch)
                story.extend([Spacer(1, 8), image, paragraph(image_match.group(1), styles["caption"]), Spacer(1, 10)])
            index += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2)
            if level == 1 and not skipped_title:
                skipped_title = True
                index += 1
                continue
            if level == 2 and story and (
                title.startswith("Stage ")
                or title.startswith("Daily ")
                or title.startswith("Workshop")
                or title in {"Troubleshooting", "Program cards", "How PowerGlove Vision selects a program"}
            ):
                story.append(CondPageBreak(2.25 * inch))
            story.append(paragraph(title, styles[f"h{level}"]))
            index += 1
            continue

        if line.startswith(">"):
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip()[1:].strip())
                index += 1
            callout = Table([[paragraph(" ".join(quote), styles["callout"]) ]], colWidths=[6.6 * inch])
            callout.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.6, GRID),
                ("LINEBEFORE", (0, 0), (0, -1), 4, RED),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]))
            story.extend([callout, Spacer(1, 10)])
            continue

        if line.startswith("```"):
            language = line[3:].strip()
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(normalize(lines[index]).replace("\t", "    "))
                index += 1
            index += 1
            label = f"{language.upper()}\n" if language and language != "text" else ""
            code_box = Table(
                [[Preformatted(label + "\n".join(code), styles["code"])]],
                colWidths=[6.6 * inch],
                hAlign="LEFT",
            )
            code_box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), NIGHT),
                ("LINEBEFORE", (0, 0), (0, -1), 3, CYAN),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.extend([code_box, Spacer(1, 8)])
            continue

        if line.startswith("|") and index + 1 < len(lines) and re.match(r"^\|?\s*:?-+", lines[index + 1].strip()):
            table, index = parse_table(lines, index, styles)
            story.extend([table, Spacer(1, 10)])
            continue

        if re.match(r"^\s*(?:[-*]|\d+\.)\s+", lines[index]):
            listing, index = parse_list(lines, index, styles)
            story.append(listing)
            continue

        parts = [line]
        index += 1
        while index < len(lines) and lines[index].strip():
            candidate = lines[index].strip()
            if candidate.startswith(("#", "```", "|", "<p", "![", ">")) or candidate == "---" or re.match(r"^\s*(?:[-*]|\d+\.)\s+", lines[index]):
                break
            parts.append(candidate)
            index += 1
        story.append(paragraph(" ".join(parts), styles["body"]))
    return story


def style_sheet():
    base = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle("CoverKicker", fontName="Courier-Bold", fontSize=10, leading=13, textColor=CYAN, alignment=TA_CENTER, spaceAfter=14),
        "cover_title": ParagraphStyle("CoverTitle", fontName="Helvetica-Bold", fontSize=27, leading=31, textColor=colors.white, alignment=TA_CENTER, spaceAfter=12),
        "cover_subtitle": ParagraphStyle("CoverSubtitle", fontName="Helvetica", fontSize=12, leading=17, textColor=colors.HexColor("#DCEAF4"), alignment=TA_CENTER, leftIndent=40, rightIndent=40),
        "cover_meta": ParagraphStyle("CoverMeta", fontName="Courier-Bold", fontSize=8.5, leading=11, textColor=CYAN, alignment=TA_CENTER),
        "h1": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25, leading=29, textColor=INK, alignment=TA_CENTER, spaceAfter=16),
        "h2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.white, backColor=NIGHT, borderPadding=(8, 10, 8, 10), spaceBefore=16, spaceAfter=10, keepWithNext=True),
        "h3": ParagraphStyle("H3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=BLUE, spaceBefore=12, spaceAfter=5, keepWithNext=True),
        "h4": ParagraphStyle("H4", parent=base["Heading4"], fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=RED, spaceBefore=9, spaceAfter=4, keepWithNext=True),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.25, leading=13.2, textColor=INK, spaceAfter=8),
        "table": ParagraphStyle("Table", parent=base["BodyText"], fontName="Helvetica", fontSize=7.7, leading=10, textColor=INK),
        "table_head": ParagraphStyle("TableHead", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.8, leading=10, textColor=colors.white),
        "code": ParagraphStyle("Code", parent=base["Code"], fontName="Courier", fontSize=7.1, leading=9.5, textColor=colors.white),
        "caption": ParagraphStyle("Caption", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=7.5, leading=9.5, textColor=MUTED, alignment=TA_CENTER, spaceBefore=4),
        "callout": ParagraphStyle("Callout", parent=base["BodyText"], fontName="Helvetica", fontSize=8.8, leading=12.5, textColor=INK, alignment=TA_LEFT),
    }


def cover_story(title: str, subtitle: str, kind: str, styles: dict[str, ParagraphStyle]):
    logo = image_flowable(LOGO, 6.55 * inch, 2.5 * inch)
    return [
        Spacer(1, 0.35 * inch), logo, Spacer(1, 0.55 * inch),
        paragraph(kind.upper(), styles["cover_kicker"]),
        paragraph(title, styles["cover_title"]),
        paragraph(subtitle, styles["cover_subtitle"]),
        Spacer(1, 1.0 * inch),
        paragraph(f"2026 EDITION  /  IAIN BENNETT  /  MIT LICENSE", styles["cover_meta"]),
        PageBreak(),
    ]


def cover_page(canvas, document):
    canvas.saveState()
    width, height = letter
    canvas.setFillColor(NIGHT)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(RED)
    canvas.rect(0, 0, width, 0.16 * inch, fill=1, stroke=0)
    canvas.setFillColor(CYAN)
    canvas.rect(0, 0.16 * inch, width * 0.72, 0.05 * inch, fill=1, stroke=0)
    canvas.restoreState()


def page_decor(canvas, document):
    canvas.saveState()
    width, height = letter
    canvas.setFillColor(NIGHT)
    canvas.rect(0, height - 0.28 * inch, width, 0.28 * inch, fill=1, stroke=0)
    canvas.setFillColor(CYAN)
    canvas.rect(0, height - 0.31 * inch, width * 0.68, 0.03 * inch, fill=1, stroke=0)
    canvas.setStrokeColor(GRID)
    canvas.line(document.leftMargin, 0.47 * inch, width - document.rightMargin, 0.47 * inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(document.leftMargin, 0.27 * inch, "POWERGLOVE VISION  /  IAIN BENNETT")
    canvas.drawRightString(width - document.rightMargin, 0.27 * inch, f"PAGE {document.page - 1}")
    canvas.restoreState()


def build(source: Path, destination: Path, title: str, subtitle: str, kind: str):
    destination.parent.mkdir(parents=True, exist_ok=True)
    styles = style_sheet()
    document = SimpleDocTemplate(
        str(destination), pagesize=letter,
        rightMargin=0.7 * inch, leftMargin=0.7 * inch,
        topMargin=0.55 * inch, bottomMargin=0.67 * inch,
        title=title, subject=subtitle, author="Iain Bennett",
        creator="PowerGlove Vision documentation builder",
    )
    story = cover_story(title, subtitle, kind, styles) + markdown_story(source, styles)
    document.build(story, onFirstPage=cover_page, onLaterPages=page_decor)


def main():
    install = ROOT / "INSTALL_README.md"
    programs = ROOT / "docs" / "bad-street-brawler-programs.md"
    build(
        install, OUTPUT / "PowerGlove-Vision-Guide.pdf",
        "PowerGlove Vision Field Guide",
        "Build, pair, and play with camera-based hand controls on Arduino UNO Q and RetroPie.",
        "Maker's field guide",
    )
    build(
        programs, OUTPUT / "Bad-Street-Brawler-Power-Glove-Programs.pdf",
        "Programs A-I",
        "The cartridge-free field manual for PowerGlove Vision profiles.",
        "Profile handbook",
    )
    print(f"Built 2 PDF guides on {date.today().isoformat()}")


if __name__ == "__main__":
    main()
