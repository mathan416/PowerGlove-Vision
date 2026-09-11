#!/usr/bin/env python3
# Project: VirtualGlove
# File: scripts/build-matrix-animation-preview.py
# Purpose: Render the actual sketch idle frames as a reviewable animation.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Compile the idle renderer on the host and export its LED frames.
# Full history: docs/CHANGELOG.md and Git history.

"""Requires a C++ compiler and Pillow; simulated brightness is not LED calibration."""

from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw


def main():
    """Run the sketch's renderer with a matrix sink, preserving frame durations."""
    root = Path(__file__).resolve().parent.parent
    source = (root / "sketch/sketch.ino").read_text()
    artwork = source[source.index("const char* const idleOpenGlove"):
                     source.index("// Five-pixel-wide glyphs")]
    renderer = source[source.index("// Raise one matrix pixel"):
                      source.index("// Router Bridge endpoint:")]
    harness = """#include <cstdint>
#include <cstdio>
struct Matrix {
  void draw(uint8_t* pixels) {
    for (int i = 0; i < 104; ++i) std::printf(" %u", pixels[i]);
    std::puts("");
  }
} matrix;
""" + artwork + renderer + """int main() {
  for (unsigned i = 0; i < sizeof(idleFrameDurations)/sizeof(uint16_t); ++i) {
    std::printf("%u", idleFrameDurations[i]);
    drawIdleFrame(i);
  }
}
"""
    with tempfile.TemporaryDirectory() as temporary:
        cpp = Path(temporary) / "preview.cpp"
        executable = Path(temporary) / "preview"
        cpp.write_text(harness)
        subprocess.run(["c++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                        str(cpp), "-o", str(executable)], check=True)
        rows = subprocess.check_output([str(executable)], text=True).splitlines()
    frames, durations = [], []
    colors = [(15, 29, 46)] + [(12 + n * 7, 40 + n * 26, 65 + n * 27)
                              for n in range(1, 8)]
    for row in rows:
        duration, *pixels = map(int, row.split())
        assert len(pixels) == 104 and all(0 <= value <= 7 for value in pixels)
        frame = Image.new("RGB", (520, 352), "#07101d")
        draw = ImageDraw.Draw(frame)
        for index, value in enumerate(pixels):
            x, y = 26 + index % 13 * 39, 25 + index // 13 * 39
            draw.rounded_rectangle((x-12, y-12, x+12, y+12), radius=5,
                                   fill=colors[value])
        draw.text((18, 331), "VirtualGlove | simulated LED brightness", fill="#94acc4")
        frames.append(frame)
        durations.append(duration)
    output = root / "docs/images/matrix"
    frames[0].save(output / "idle-animation.gif", save_all=True,
                   append_images=frames[1:], duration=durations, loop=0, disposal=2)
    frames[14].save(output / "idle-glove.png")
    selected = [(0, "Lightning"), (6, "Cuff arrives"), (9, "Hand rises"),
                (14, "Open"), (11, "Curl"), (12, "Fist"),
                (18, "Spark"), (25, "Glow"), (28, "Rest")]
    sheet = Image.new("RGB", (780, 582), "#07101d")
    draw = ImageDraw.Draw(sheet)
    for cell, (index, label) in enumerate(selected):
        x, y = cell % 3 * 260, cell // 3 * 194
        sheet.paste(frames[index].resize((260, 176)), (x, y))
        draw.text((x+10, y+179), label, fill="white")
    sheet.save(output / "idle-storyboard.png")
    print("Rendered %d frames, %d ms loop" % (len(frames), sum(durations)))


if __name__ == "__main__":
    main()
