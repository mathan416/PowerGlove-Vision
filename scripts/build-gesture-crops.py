#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/build-gesture-crops.py
# Purpose: Split the illustrated gesture sheets into reusable action images.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-03 - Added contextual gesture crops for the gameplay guide.
# Full history: docs/CHANGELOG.md and Git history.

"""Build transparent gesture images used beside gameplay instructions."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
GESTURES = ROOT / "docs" / "images" / "gestures"
OUTPUT = GESTURES / "actions"
CARD_SIZE = 560
PADDING = 18


SHEETS = {
    "directional-movement.png": {
        "move-left.png": (0, 0, 618, 520),
        "move-right.png": (618, 0, 1236, 520),
        "move-up.png": (0, 515, 618, 1272),
        "move-down.png": (618, 515, 1236, 1272),
    },
    "finger-and-menu-poses.png": {
        "finger-curl.png": (0, 0, 627, 610),
        "thumb-curl.png": (627, 0, 1254, 610),
        "v-sign.png": (0, 610, 627, 1254),
        "thumbs-up.png": (627, 610, 1254, 1254),
    },
    "wrist-and-depth.png": {
        "wrist-roll-right.png": (0, 0, 627, 575),
        "wrist-roll-left.png": (627, 0, 1254, 575),
        "push-toward-camera.png": (0, 575, 627, 1254),
        "pull-away-from-camera.png": (627, 575, 1254, 1254),
    },
}


def trim_alpha(image: Image.Image, padding: int = PADDING) -> Image.Image:
    """Trim transparent margins while retaining a small safety border."""

    image = image.convert("RGBA")
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        return image
    left = max(0, bounds[0] - padding)
    top = max(0, bounds[1] - padding)
    right = min(image.width, bounds[2] + padding)
    bottom = min(image.height, bounds[3] + padding)
    return image.crop((left, top, right, bottom))


def fit_card(image: Image.Image, size: int = CARD_SIZE) -> Image.Image:
    """Fit a crop into a consistent transparent square without distortion."""

    image = trim_alpha(image)
    image.thumbnail((size - 2 * PADDING, size - 2 * PADDING), Image.Resampling.LANCZOS)
    card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    card.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
    return card


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a bold system font, falling back safely on other platforms."""

    candidates = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def combine(name: str, source_names: tuple[str, ...]) -> None:
    """Combine related gesture cards into one compact table illustration."""

    sources = [Image.open(OUTPUT / source).convert("RGBA") for source in source_names]
    item_size = 300 if len(sources) <= 2 else 250
    columns = 2
    rows = (len(sources) + columns - 1) // columns
    canvas = Image.new("RGBA", (columns * item_size, rows * item_size), (0, 0, 0, 0))
    for index, source in enumerate(sources):
        source.thumbnail((item_size, item_size), Image.Resampling.LANCZOS)
        x = (index % columns) * item_size + (item_size - source.width) // 2
        y = (index // columns) * item_size + (item_size - source.height) // 2
        canvas.alpha_composite(source, (x, y))
    trim_alpha(canvas).save(OUTPUT / name, optimize=True)


def labeled_copy(name: str, source_name: str, label: str) -> None:
    """Add a concise label when one drawing represents a family of curls."""

    source = Image.open(OUTPUT / source_name).convert("RGBA")
    canvas = Image.new("RGBA", (CARD_SIZE, CARD_SIZE + 72), (0, 0, 0, 0))
    canvas.alpha_composite(source, (0, 0))
    draw = ImageDraw.Draw(canvas)
    font = load_font(34)
    bounds = draw.textbbox((0, 0), label, font=font)
    width = bounds[2] - bounds[0]
    x = (canvas.width - width) // 2
    draw.rounded_rectangle((x - 18, CARD_SIZE + 4, x + width + 18, CARD_SIZE + 58), 14, fill=(5, 31, 61, 230))
    draw.text((x, CARD_SIZE + 10), label, font=font, fill=(36, 216, 245, 255))
    trim_alpha(canvas).save(OUTPUT / name, optimize=True)


def main() -> None:
    """Create all individual and combined gameplay-guide illustrations."""

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for sheet_name, crops in SHEETS.items():
        sheet = Image.open(GESTURES / sheet_name).convert("RGBA")
        for output_name, bounds in crops.items():
            fit_card(sheet.crop(bounds)).save(OUTPUT / output_name, optimize=True)

    combine("horizontal-movement.png", ("move-left.png", "move-right.png"))
    combine("vertical-movement.png", ("move-up.png", "move-down.png"))
    combine(
        "whole-hand-movement.png",
        ("move-left.png", "move-right.png", "move-up.png", "move-down.png"),
    )
    combine("wrist-roll.png", ("wrist-roll-left.png", "wrist-roll-right.png"))
    combine("index-push-combination.png", ("finger-curl.png", "push-toward-camera.png"))
    combine("thumb-finger-combination.png", ("thumb-curl.png", "finger-curl.png"))
    labeled_copy("close-all-fingers.png", "finger-curl.png", "CLOSE ALL FINGERS")
    labeled_copy("keep-index-straight.png", "move-up.png", "KEEP INDEX STRAIGHT")
    print(f"Generated gesture crops in {OUTPUT}")


if __name__ == "__main__":
    main()
