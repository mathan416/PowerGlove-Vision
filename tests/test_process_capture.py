# Project: PowerGlove Vision
# File: tests/test_process_capture.py
# Purpose: Verify coherent latest-only process capture and failure publication.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Added process-isolated capture contract coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Test the process capture shared slot without camera hardware."""

import threading
import time
import unittest

import numpy

from powerglove_vision.process_capture import (
    ProcessDirectV4L2Capture, _publish, _publish_failure,
)


class _Source:
    last_metadata = {
        "camera_driver_sequence": 27,
        "camera_driver_timestamp": True,
        "camera_driver_to_dequeue_ms": 3.25,
        "camera_driver_buffers_drained": 1,
    }


class _Process:
    def __init__(self, alive=True):
        self.alive = alive

    def is_alive(self):
        return self.alive


class _Control:
    def poll(self):
        return False


class ProcessCaptureTests(unittest.TestCase):
    def capture(self):
        capture = ProcessDirectV4L2Capture.__new__(ProcessDirectV4L2Capture)
        capture._numpy = numpy
        capture._pixels = bytearray(640 * 480 * 3)
        capture._state = [0] * 7
        capture._lock = threading.Lock()
        capture._process = _Process()
        capture._control = _Control()
        capture._synthetic_sequence = 0
        capture.metadata = {}
        return capture

    def test_publish_and_read_are_coherent_and_latest_only(self):
        capture = self.capture()
        frame = numpy.full((480, 640, 3), 17, dtype=numpy.uint8)
        _publish(frame, 12.5, _Source(), capture._pixels,
                 capture._state, capture._lock, numpy)
        result = capture.latest_after(0)
        self.assertTrue(result.ok)
        self.assertEqual(result.sequence, 1)
        self.assertEqual(result.captured_at, 12.5)
        self.assertTrue(numpy.array_equal(result.frame, frame))
        self.assertIsNone(capture.latest_after(1))
        self.assertEqual(capture.metadata["camera_driver_sequence"], 27)
        frame[:] = 99
        self.assertEqual(result.frame[0, 0, 0], 17)

    def test_dead_child_repeatedly_publishes_failure_for_recovery_timer(self):
        capture = self.capture()
        capture._process.alive = False
        first = capture.latest_after(0)
        second = capture.latest_after(first.sequence)
        self.assertFalse(first.ok)
        self.assertFalse(second.ok)
        self.assertGreater(second.sequence, first.sequence)
        self.assertLess(abs(second.captured_at - time.monotonic()), .1)

    def test_transient_failed_read_can_be_replaced_by_a_valid_frame(self):
        capture = self.capture()
        _publish_failure(capture._state, capture._lock)
        failed = capture.latest_after(0)
        self.assertFalse(failed.ok)
        frame = numpy.full((480, 640, 3), 23, dtype=numpy.uint8)
        _publish(frame, 14.0, _Source(), capture._pixels,
                 capture._state, capture._lock, numpy)
        recovered = capture.latest_after(failed.sequence)
        self.assertTrue(recovered.ok)
        self.assertEqual(recovered.captured_at, 14.0)

    def test_partial_manual_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            ProcessDirectV4L2Capture('/dev/video0', 2, numpy,
                                     manual_exposure=78)


if __name__ == "__main__":
    unittest.main()
