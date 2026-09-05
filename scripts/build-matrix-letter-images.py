#!/usr/bin/env python3
# Project: PowerGlove Vision
# File: scripts/build-matrix-letter-images.py
# Purpose: Render documentation diagrams from the sketch's program glyphs.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added reproducible rounded LED diagrams for programs B-I.
# Full history: docs/CHANGELOG.md and Git history.

"""Build matching SVG and PNG diagrams without modifying the supplied photos."""

from pathlib import Path
import re
from PIL import Image, ImageDraw


def main() -> None:
    """Read the real glyph bitmaps and place each in its 13-by-8 display grid."""
    root = Path(__file__).resolve().parent.parent
    source = (root / 'sketch/sketch.ino').read_text()
    block = re.search(r'programGlyphs\[9\]\[7\] = \{(.*?)\n\};', source, re.S).group(1)
    glyphs = [[int(n) for n in re.findall(r'\d+', row)] for row in re.findall(r'\{([^}]+)\}', block)]
    assert len(glyphs) == 9 and all(len(g) == 7 for g in glyphs)
    out = root / 'docs/images/matrix/programs'
    out.mkdir(parents=True, exist_ok=True)
    for letter, glyph in zip('ABCDEFGHI', glyphs):
        if letter == 'A':
            continue
        # A compact, deliberately illustrated display; retain the sketch's position.
        image = Image.new('RGB', (520, 328), 'white')
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((0, 0, 519, 327), radius=25, fill='#071526', outline='#16364f', width=3)
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="520" height="328" viewBox="0 0 520 328">', '<rect width="520" height="328" rx="25" fill="#071526"/>']
        for y in range(8):
            for x in range(13):
                lit = y < 7 and 4 <= x < 9 and bool(glyph[y] & (1 << (8-x)))
                cx, cy = 26 + x*39, 27 + y*39
                color = '#40ceff' if lit else '#17354c'
                if lit:
                    draw.ellipse((cx-15, cy-15, cx+15, cy+15), fill='#083c94')
                    svg.append('<circle cx="%d" cy="%d" r="15" fill="#083c94"/>' % (cx, cy))
                draw.rounded_rectangle((cx-9, cy-9, cx+9, cy+9), radius=5, fill=color)
                svg.append('<rect x="%d" y="%d" width="18" height="18" rx="5" fill="%s"/>' % (cx-9, cy-9, color))
        image.save(out / (letter+'.png'))
        (out / (letter+'.svg')).write_text('\n'.join(svg+['</svg>'])+'\n')


if __name__ == '__main__':
    main()
