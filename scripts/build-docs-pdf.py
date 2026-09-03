#!/usr/bin/env python3
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
"""Build the distributable PowerGlove Vision PDF guides from Markdown."""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
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

INK = colors.HexColor("#101420")
BLUE = colors.HexColor("#0BA8E6")
CYAN = colors.HexColor("#39D9F5")
RED = colors.HexColor("#EF3340")
PAPER = colors.HexColor("#F7F8FC")
GRID = colors.HexColor("#CBD3E1")
MUTED = colors.HexColor("#4D586A")


def normalize(text: str) -> str:
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u2192": "->",
        "\u2190": "<-",
        "\u00a0": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def inline(text: str) -> str:
    text = html.escape(normalize(text.strip()))
    text = re.sub(
        r"\[([^]]+)\]\(([^)]+)\)",
        r'<link href="\2" color="#087EA4"><u>\1</u></link>',
        text,
    )
    text = re.sub(r"`([^`]+)`", r'<font name="Courier" color="#087EA4">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(inline(text), style)


def parse_table(lines: list[str], start: int, styles: dict[str, ParagraphStyle]):
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        row = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        rows.append(row)
        index += 1
    rows.pop(1)
    formatted = [
        [Paragraph(inline(cell), styles["table_head"] if row_index == 0 else styles["table"])
         for cell in row]
        for row_index, row in enumerate(rows)
    ]
    columns = max(len(row) for row in formatted)
    widths = [6.85 * inch / columns] * columns
    table = Table(formatted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.45, GRID),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table, index


def markdown_story(source: Path, styles: dict[str, ParagraphStyle]):
    lines = source.read_text(encoding="utf-8").splitlines()
    story = []
    if LOGO.exists():
        story.extend([Image(str(LOGO), width=6.7 * inch, height=2.5125 * inch), Spacer(1, 10)])

    index = 0
    skipped_html = False
    while index < len(lines):
        raw = lines[index]
        line = raw.strip()
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

        image_match = re.fullmatch(r"!\[([^]]*)\]\(([^)]+)\)", line)
        if image_match:
            image_path = (source.parent / image_match.group(2)).resolve()
            if image_path.exists():
                story.extend(
                    [
                        Spacer(1, 8),
                        Image(str(image_path), width=6.7 * inch, height=3.76875 * inch),
                        Paragraph(inline(image_match.group(1)), styles["caption"]),
                        Spacer(1, 8),
                    ]
                )
            index += 1
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            if level == 1 and story:
                story.append(Spacer(1, 4))
            story.append(paragraph(heading.group(2), styles[f"h{level}"]))
            index += 1
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
            story.extend([Preformatted(label + "\n".join(code), styles["code"]), Spacer(1, 7)])
            continue

        if (
            line.startswith("|")
            and index + 1 < len(lines)
            and re.match(r"^\|?\s*:?-+", lines[index + 1].strip())
        ):
            table, index = parse_table(lines, index, styles)
            story.extend([table, Spacer(1, 9)])
            continue

        list_match = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", line)
        if list_match:
            ordered = bool(re.match(r"^\d+\.", line))
            items = []
            while index < len(lines):
                match = re.match(r"^(?:[-*]|\d+\.)\s+(.+)$", lines[index].strip())
                if not match:
                    break
                items.append(ListItem(paragraph(match.group(1), styles["body"]), leftIndent=10))
                index += 1
            story.append(
                ListFlowable(
                    items,
                    bulletType="1" if ordered else "bullet",
                    leftIndent=22,
                    bulletFontName="Helvetica",
                    bulletFontSize=8,
                    spaceAfter=7,
                )
            )
            continue

        paragraph_lines = [line]
        index += 1
        while index < len(lines) and lines[index].strip():
            candidate = lines[index].strip()
            if (
                candidate.startswith(("#", "```", "|", "<p", "!["))
                or re.match(r"^(?:[-*]|\d+\.)\s+", candidate)
            ):
                break
            paragraph_lines.append(candidate)
            index += 1
        story.append(paragraph(" ".join(paragraph_lines), styles["body"]))

    return story


def style_sheet():
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=25,
            leading=29, textColor=INK, alignment=TA_CENTER, spaceAfter=16,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=17,
            leading=21, textColor=BLUE, spaceBefore=15, spaceAfter=7, keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "H3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=13,
            leading=16, textColor=INK, spaceBefore=11, spaceAfter=5, keepWithNext=True,
        ),
        "h4": ParagraphStyle(
            "H4", parent=base["Heading4"], fontName="Helvetica-Bold", fontSize=10.5,
            leading=13, textColor=RED, spaceBefore=8, spaceAfter=4, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="Helvetica", fontSize=9.2,
            leading=12.6, textColor=INK, spaceAfter=7,
        ),
        "table": ParagraphStyle(
            "Table", parent=base["BodyText"], fontName="Helvetica", fontSize=7.5,
            leading=9.3, textColor=INK,
        ),
        "table_head": ParagraphStyle(
            "TableHead", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7.5,
            leading=9.3, textColor=colors.white,
        ),
        "code": ParagraphStyle(
            "Code", parent=base["Code"], fontName="Courier", fontSize=7.1,
            leading=9.3, textColor=colors.white, backColor=INK, leftIndent=7,
            rightIndent=7, borderPadding=7, spaceBefore=3,
        ),
        "caption": ParagraphStyle(
            "Caption", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=7.5,
            leading=9, textColor=MUTED, alignment=TA_CENTER, spaceBefore=3,
        ),
    }


def page_decor(canvas, document):
    canvas.saveState()
    width, _ = letter
    canvas.setStrokeColor(CYAN)
    canvas.setLineWidth(1.2)
    canvas.line(document.leftMargin, 0.47 * inch, width - document.rightMargin, 0.47 * inch)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(document.leftMargin, 0.27 * inch, "PowerGlove Vision - Iain Bennett")
    canvas.drawRightString(width - document.rightMargin, 0.27 * inch, f"Page {document.page}")
    canvas.restoreState()


def build(source: Path, destination: Path, title: str):
    destination.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(destination),
        pagesize=letter,
        rightMargin=0.57 * inch,
        leftMargin=0.57 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.62 * inch,
        title=title,
        author="Iain Bennett",
    )
    document.build(markdown_story(source, style_sheet()), onFirstPage=page_decor, onLaterPages=page_decor)


def main():
    build(INSTALL := ROOT / "INSTALL_README.md", OUTPUT / "PowerGlove-Vision-Guide.pdf", "PowerGlove Vision Installation Guide")
    build(
        ROOT / "docs" / "bad-street-brawler-programs.md",
        OUTPUT / "Bad-Street-Brawler-Power-Glove-Programs.pdf",
        "Bad Street Brawler's Power Glove Programs",
    )
    print(f"Built PDFs from {INSTALL.relative_to(ROOT)} and docs/bad-street-brawler-programs.md")


if __name__ == "__main__":
    main()
