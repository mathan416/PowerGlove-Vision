# Project: PowerGlove Vision
# File: tests/test_realtime.py
# Purpose: Verify newest-frame capture and non-blocking diagnostic preview work.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-05 - Added low-latency camera and preview pipeline coverage.
# Full history: docs/CHANGELOG.md and Git history.

"""Verify the real-time pipeline without MediaPipe or camera hardware."""

import queue
import threading
import time
import unittest
from types import SimpleNamespace

from powerglove_vision.debug_server import SharedDebugState
from powerglove_vision.realtime import (
    LatestFrameCapture, LatestPreviewEncoder, RollingPerformance,
)


class QueuedCapture:
    """Supply deterministic frames to the capture worker."""

    def __init__(self):
        self.frames = queue.Queue()
        self.released = False

    def read(self):
        return self.frames.get(timeout=1)

    def release(self):
        self.released = True
        self.frames.put((False, None))


class FakeJpeg:
    def __init__(self, payload):
        self.payload = payload

    def tobytes(self):
        return self.payload


class FakeCv2:
    FONT_HERSHEY_SIMPLEX = 0
    IMWRITE_JPEG_QUALITY = 1

    def __init__(self, encoded=b"jpeg"):
        self.encoded = encoded
        self.drawn = []

    def putText(self, frame, label, *_args):
        self.drawn.append((frame, label))

    def imencode(self, _extension, _frame, _options):
        return True, FakeJpeg(self.encoded)


class RealtimePipelineTests(unittest.TestCase):
    def test_performance_window_reports_tail_latency(self):
        metrics = RollingPerformance(size=4)
        for value in (100, 10, 20, 30, 40):
            metrics.record(inference_ms=value)
        summary = metrics.snapshot()["inference_ms"]
        self.assertEqual(summary, {
            "latest": 40.0, "p50": 20.0, "p95": 40.0,
            "max": 40.0, "samples": 4,
        })
        metrics.record(inference_ms=-1, ignored=None)
        self.assertNotIn("ignored", metrics.snapshot())

    def test_capture_returns_only_the_latest_unprocessed_frame(self):
        source = QueuedCapture()
        capture = LatestFrameCapture(source, "first", metadata={"camera_format": "MJPG"})
        try:
            self.assertEqual(capture.metadata["camera_format"], "MJPG")
            first = capture.latest_after(0)
            self.assertEqual(first.frame, "first")
            source.frames.put((True, "second"))
            source.frames.put((True, "third"))
            deadline = time.monotonic() + 1
            latest = None
            while time.monotonic() < deadline:
                latest = capture.latest_after(first.sequence)
                if latest is not None and latest.frame == "third":
                    break
                time.sleep(0.005)
            self.assertIsNotNone(latest)
            self.assertEqual(latest.frame, "third")
            self.assertGreaterEqual(latest.sequence, 3)
            self.assertIsNone(capture.latest_after(latest.sequence))
        finally:
            capture.release()
        self.assertTrue(source.released)

    def test_capture_exception_becomes_a_reconnectable_failure(self):
        source = QueuedCapture()
        source.frames.put(RuntimeError("camera failed"))
        original_read = source.read

        def read():
            value = original_read()
            if isinstance(value, Exception):
                raise value
            return value

        source.read = read
        capture = LatestFrameCapture(source)
        try:
            deadline = time.monotonic() + 1
            failed = None
            while failed is None and time.monotonic() < deadline:
                failed = capture.latest_after(0)
                time.sleep(0.005)
            self.assertIsNotNone(failed)
            self.assertFalse(failed.ok)
            self.assertIsNone(failed.frame)
        finally:
            capture.release()

    def test_preview_encoder_publishes_without_replacing_status(self):
        shared = SharedDebugState()
        shared.update_status({"sequence": 9})
        published = threading.Event()

        def publish(payload):
            shared.update_frame(payload)
            published.set()

        encoder = LatestPreviewEncoder(publish)
        cv2 = FakeCv2()
        frame = SimpleNamespace(shape=(480, 640, 3))
        try:
            self.assertTrue(encoder.submit(frame, "PROGRAM H", (255, 255, 255), cv2))
            self.assertTrue(published.wait(1))
            self.assertEqual(shared.jpeg, b"jpeg")
            self.assertEqual(shared.status, {"sequence": 9})
            metrics = encoder.metrics()
            self.assertEqual(metrics["preview_submitted"], 1)
            self.assertEqual(metrics["preview_encoded"], 1)
            self.assertIsNone(metrics["preview_error"])
        finally:
            encoder.close()

    def test_preview_failure_is_contained(self):
        encoder = LatestPreviewEncoder(lambda _payload: None)
        cv2 = FakeCv2()
        cv2.imencode = lambda *_args: (_ for _ in ()).throw(RuntimeError("encode failed"))
        try:
            encoder.submit(SimpleNamespace(shape=(480, 640, 3)), "TEST", (0, 0, 0), cv2)
            deadline = time.monotonic() + 1
            while encoder.metrics()["preview_error"] is None and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(encoder.metrics()["preview_error"], "encode failed")
        finally:
            encoder.close()


if __name__ == "__main__":
    unittest.main()
