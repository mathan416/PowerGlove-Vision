#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/build-help-images.py
# Purpose: Generate compact gesture illustrations for Help and Glove Academy.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added web-sized gesture derivatives without changing print originals.
# Full history: docs/CHANGELOG.md and Git history.

"""Resize gesture artwork for web display while preserving alpha and aspect ratio."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / 'docs/images'


def main():
    """Build deterministic palette PNGs; original files remain untouched."""
    before = after = count = 0
    for source in sorted((ROOT / 'gestures').rglob('*.png')):
        if source.name.endswith('-web.png'):
            continue
        limit = 960 if source.parent == ROOT / 'gestures' else 320
        with Image.open(source) as original:
            image = original.convert('RGBA')
            image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
            image = image.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
            target = ROOT / 'web' / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, optimize=True)
        before += source.stat().st_size
        after += target.stat().st_size
        count += 1
    print('%d images: %d -> %d bytes (%.1f%% smaller)' % (count,before,after,100*(1-after/before)))


if __name__ == '__main__':
    main()
