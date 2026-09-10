# Project: PowerGlove Vision
# File: src/powerglove_vision/process_capture.py
# Purpose: Isolate direct camera capture from long hand-inference calls.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-09 - Added an opt-in Direct V4L2 latest-frame capture process.
# Full history: docs/CHANGELOG.md and Git history.

"""Opt-in process-isolated Direct V4L2 capture with one replaceable frame."""

from __future__ import annotations

import multiprocessing
import time
from typing import Any

from .realtime import CapturedFrame


def _publish(frame, captured_at, source, pixels, state, lock, numpy) -> None:
    """Atomically replace the shared frame and its non-image metadata."""
    target = numpy.frombuffer(pixels, dtype=numpy.uint8).reshape((480, 640, 3))
    if frame.shape != target.shape or frame.dtype != numpy.uint8:
        raise RuntimeError(f"unexpected camera frame {frame.shape} {frame.dtype}")
    details = source.last_metadata
    with lock:
        target[:] = frame
        state[1] = 1
        state[2] = int(captured_at * 1_000_000_000)
        state[3] = int(details.get("camera_driver_sequence", 0))
        state[4] = int(bool(details.get("camera_driver_timestamp", False)))
        state[5] = int(float(details.get("camera_driver_to_dequeue_ms", 0)) * 1000)
        state[6] = int(details.get("camera_driver_buffers_drained", 0))
        state[0] += 1


def _publish_failure(state, lock) -> None:
    """Publish one failed read while allowing the camera child to continue."""
    with lock:
        state[1] = 0
        state[2] = time.monotonic_ns()
        state[0] += 1


def _capture_worker(path, buffers, pixels, state, lock, stop, control,
                    manual_exposure, manual_gain) -> None:
    """Own Direct V4L2 and decoding until the parent requests shutdown."""
    import cv2
    import numpy

    from .camera_controls import configure_manual_on_fd, restore_automatic_on_fd
    from .v4l2_capture import DirectV4L2Capture

    source = None
    try:
        source = DirectV4L2Capture(path, buffers, cv2, numpy)
        manual_report = None
        first_deadline = time.monotonic() + 5.0
        first = None
        while not stop.is_set() and time.monotonic() < first_deadline:
            try:
                ok, frame, captured_at = source.read_with_timestamp()
            except Exception:
                _publish_failure(state, lock)
                continue
            if ok:
                first = (frame, captured_at)
                break
        if first is None:
            raise RuntimeError("process-isolated camera produced no first frame")
        # Match the proven direct-camera lifecycle: establish a streaming frame
        # before changing controls on the same descriptor.
        if manual_exposure is not None:
            manual_report = configure_manual_on_fd(source.fd, manual_exposure, manual_gain)
            if not manual_report.get("applied"):
                restore_automatic_on_fd(source.fd)
                raise RuntimeError(manual_report.get(
                    "reason", "camera rejected process-isolated manual exposure"
                ))
            source.before_close = restore_automatic_on_fd
        _publish(first[0], first[1], source, pixels, state, lock, numpy)
        control.send({"ready": True, "manual": manual_report})
        while not stop.is_set():
            try:
                ok, frame, captured_at = source.read_with_timestamp()
            except Exception:
                _publish_failure(state, lock)
                stop.wait(0.005)
                continue
            if not ok:
                _publish_failure(state, lock)
                continue
            _publish(frame, captured_at, source, pixels, state, lock, numpy)
    except BaseException as exc:
        _publish_failure(state, lock)
        try:
            control.send({"ready": False, "error": str(exc)})
        except (BrokenPipeError, OSError):
            pass
    finally:
        if source is not None:
            source.close()
        control.close()


class ProcessDirectV4L2Capture:
    """Publish the newest direct camera frame from an isolated child process."""

    def __init__(self, path: str, buffers: int, numpy: Any, *,
                 metadata: dict | None = None, manual_exposure: int | None = None,
                 manual_gain: int | None = None) -> None:
        if (manual_exposure is None) != (manual_gain is None):
            raise ValueError("manual exposure and gain must be supplied together")
        context = multiprocessing.get_context("spawn")
        self._numpy = numpy
        self._pixels = context.RawArray("B", 640 * 480 * 3)
        self._state = context.RawArray("q", 7)
        self._lock = context.Lock()
        self._stop = context.Event()
        parent, child = context.Pipe(duplex=False)
        self._control = parent
        self._process = context.Process(
            target=_capture_worker,
            args=(str(path), int(buffers), self._pixels, self._state, self._lock,
                  self._stop, child, manual_exposure, manual_gain),
            name="powerglove-camera-sidecar", daemon=True,
        )
        self.metadata = dict(metadata or {})
        self.metadata.update({
            "capture_isolation_requested": "process",
            "capture_isolation": "process",
            "capture_isolation_fallback": None,
        })
        self._closed = False
        self._synthetic_sequence = 0
        self._process.start()
        child.close()
        if not self._control.poll(7.0):
            self.release()
            raise RuntimeError("process-isolated camera startup timed out")
        message = self._control.recv()
        if not message.get("ready"):
            self.release()
            raise RuntimeError(message.get("error", "process-isolated camera failed"))
        manual = message.get("manual")
        if manual:
            self.metadata.update({
                "camera_exposure_supported": bool(manual.get("supported")),
                "camera_exposure_applied": bool(manual.get("applied")),
                "camera_manual_limits": manual.get("limits", {}),
            })

    def latest_after(self, sequence: int) -> CapturedFrame | None:
        """Return a coherent copy only when a newer shared frame exists."""
        try:
            if self._control.poll():
                message = self._control.recv()
                if message.get("error"):
                    self.metadata["capture_process_error"] = message["error"]
        except (EOFError, OSError):
            pass
        with self._lock:
            current = int(self._state[0])
            if current <= sequence:
                if self._process.is_alive():
                    return None
                self._synthetic_sequence = max(self._synthetic_sequence, sequence) + 1
                return CapturedFrame(
                    self._synthetic_sequence, time.monotonic(), False, None,
                    time.monotonic(),
                )
            ok = bool(self._state[1])
            captured_at = self._state[2] / 1_000_000_000
            driver_sequence = int(self._state[3])
            timestamp_valid = bool(self._state[4])
            driver_to_dequeue_ms = self._state[5] / 1000
            drained = int(self._state[6])
            frame = None
            if ok:
                frame = self._numpy.frombuffer(
                    self._pixels, dtype=self._numpy.uint8
                ).reshape((480, 640, 3)).copy()
        self.metadata.update({
            "camera_driver_sequence": driver_sequence,
            "camera_driver_timestamp": timestamp_valid,
            "camera_driver_to_dequeue_ms": driver_to_dequeue_ms,
            "camera_driver_buffers_drained": drained,
        })
        return CapturedFrame(current, captured_at, ok, frame if ok else None,
                             time.monotonic())

    def release(self) -> None:
        """Stop capture, restore camera automation in the child, and reap it."""
        if self._closed:
            return
        self._closed = True
        self._stop.set()
        self._process.join(timeout=2.0)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout=2.0)
        self._control.close()
