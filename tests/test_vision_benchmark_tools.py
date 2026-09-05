# Project: PowerGlove Vision
# File: tests/test_vision_benchmark_tools.py
# Purpose: Verify fixed and guided vision benchmark schedules and lifecycle.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-05 - Added coverage for user-paced guided benchmark capture.
# Full history: docs/CHANGELOG.md and Git history.

"""Tests for the temporary local vision benchmark tools."""

from __future__ import annotations

import importlib.util
import tempfile
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    """Load a hyphenated development script as a test module."""
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VisionBenchmarkToolTests(unittest.TestCase):
    """Verify schedule compatibility and safe guided-capture completion."""

    def test_fixed_and_guided_schedules_cover_the_same_actions(self) -> None:
        """Both capture styles must label the same recognition evidence."""
        fixed = load_script("record-vision-benchmark.py")
        guided = load_script("guided-vision-benchmark.py")
        self.assertEqual([cue[2] for cue in fixed.CUES], [cue[0] for cue in guided.CUES])
        self.assertEqual(fixed.CUES[-1][1], 30)
        self.assertEqual(sum(cue[3] for cue in guided.CUES), 52)
        self.assertIn("Live camera preview", guided.PAGE)
        self.assertIn("Record this step", guided.PAGE)

    def test_guided_capture_releases_camera_when_final_step_finishes(self) -> None:
        """Completing capture must not leave the camera owned by the helper."""
        guided = load_script("guided-vision-benchmark.py")
        guided.CUES = (("neutral", "Neutral", "Hold still", 0.01),)

        class Frame:
            shape = (480, 640, 3)

            def copy(self):
                return self

        class Camera:
            released = False

            def read(self):
                return True, Frame()

            def release(self):
                self.released = True

        class Writer:
            released = False

            def write(self, _frame):
                pass

            def release(self):
                self.released = True

        class Cv2:
            FONT_HERSHEY_SIMPLEX = 0
            LINE_AA = 0
            IMWRITE_JPEG_QUALITY = 1

            @staticmethod
            def putText(*_args):
                pass

            @staticmethod
            def imencode(*_args):
                return False, None

        with tempfile.TemporaryDirectory() as directory:
            capture = guided.GuidedCapture.__new__(guided.GuidedCapture)
            capture.cv2 = Cv2()
            capture.output = Path(directory) / "guided.avi"
            capture.width, capture.height, capture.fps = 640, 480, 30.0
            capture.lock = threading.Lock()
            capture.condition = threading.Condition(capture.lock)
            capture.index = 0
            capture.phase = "recording"
            capture.phase_started = time.monotonic() - 0.02
            capture.latest_jpeg = None
            capture.frames = 0
            capture.frame_times = []
            capture.cue_records = []
            capture.timeline = 0.0
            capture.complete = False
            capture.closed = False
            capture.capture = Camera()
            capture.writer = Writer()

            capture._camera_loop()

            self.assertTrue(capture.complete)
            self.assertTrue(capture.capture.released)
            self.assertIsNone(capture.writer)
            self.assertTrue((Path(directory) / "guided.avi.json").is_file())


if __name__ == "__main__":
    unittest.main()
