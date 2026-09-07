# Project: PowerGlove Vision
# File: src/powerglove_vision/motion.py
# Purpose: Track native X/Y between asynchronous hand-recognition results.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Add experimental bounded palm optical flow and asynchronous recognition.
# Full history: docs/CHANGELOG.md and Git history.

"""Keep camera motion independent of recognition, with bounded source-frame age."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import time

from .model import HandObservation
from .tracker import TrackingResult


class PalmFlow:
    """Track textured palm features with forward/backward consistency checks."""

    def __init__(self, cv2):
        import numpy as np
        self.cv2 = cv2
        self.np = np
        self.gray = self.points = self.center = None

    def seed(self, gray, observation, landmarks):
        """Restrict feature acquisition to the recognized palm polygon."""
        cv2, np = self.cv2, self.np
        self.gray = self.points = self.center = None
        if not observation.detected or len(landmarks) != 5:
            return False
        h, w = gray.shape
        polygon = np.asarray([(x * w, y * h) for x, y in landmarks], dtype=np.float32)
        if not np.isfinite(polygon).all():
            return False
        mask = np.zeros_like(gray)
        cv2.fillConvexPoly(mask, cv2.convexHull(polygon.astype(np.int32)), 255)
        points = cv2.goodFeaturesToTrack(gray, maxCorners=40, qualityLevel=.01,
                                        minDistance=4, mask=mask, blockSize=3)
        if points is None or len(points) < 6:
            return False
        self.gray, self.points = gray, points
        self.center = np.array([observation.palm_x * w, observation.palm_y * h])
        return True

    def advance(self, gray):
        """Reject inconsistent, out-of-frame, or insufficient feature tracks."""
        cv2, np = self.cv2, self.np
        if self.points is None or gray.shape != self.gray.shape:
            self.points = None
            return None
        settings = dict(winSize=(21, 21), maxLevel=3,
                        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, .03))
        nxt, status, _ = cv2.calcOpticalFlowPyrLK(self.gray, gray, self.points, None, **settings)
        if nxt is None:
            self.points = None
            return None
        back, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, self.gray, nxt, None, **settings)
        if back is None:
            self.points = None
            return None
        old, new = self.points.reshape(-1, 2), nxt.reshape(-1, 2)
        h, w = gray.shape
        valid = (status.ravel() != 0) & (back_status.ravel() != 0)
        valid &= np.isfinite(new).all(axis=1) & np.isfinite(back.reshape(-1, 2)).all(axis=1)
        valid &= np.linalg.norm(back.reshape(-1, 2) - old, axis=1) < 1.5
        valid &= (new[:, 0] >= 0) & (new[:, 0] < w) & (new[:, 1] >= 0) & (new[:, 1] < h)
        if valid.sum() < max(6, len(old) * .5):
            self.points = None
            return None
        delta = np.median((new - old)[valid], axis=0)
        valid &= np.linalg.norm(new - old - delta, axis=1) < 3.0
        if valid.sum() < max(6, len(old) * .5) or np.linalg.norm(delta) > .20 * min(w, h):
            self.points = None
            return None
        self.center += np.median((new - old)[valid], axis=0)
        if not (0 <= self.center[0] < w and 0 <= self.center[1] < h):
            self.points = None
            return None
        self.gray, self.points = gray, new[valid].reshape(-1, 1, 2)
        return float(self.center[0] / w), float(self.center[1] / h)


class MotionTracker:
    """Own one recognition worker and a short, in-memory motion correction history."""

    def __init__(self, tracker, max_age=.250, clock=time.monotonic):
        self.tracker = tracker
        self.cv2 = tracker.cv2
        self.backend = tracker.backend
        self.backend_label = tracker.backend_label
        self.preview_enabled = self.diagnostics_enabled = True
        self.max_age, self.clock = max_age, clock
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hand-recognition")
        self.pending = None
        self.history = deque(maxlen=32)
        self.flow = PalmFlow(self.cv2)
        self.anchor = None
        self.inference_ms = None
        self.error = None
        self.active = False

    def _recognize(self, frame, timestamp):
        """Use an owned frame; keep tracker settings private to this worker."""
        started = self.clock()
        self.tracker.preview_enabled = False
        self.tracker.diagnostics_enabled = True
        result = self.tracker.process(frame, timestamp=timestamp)
        return result, (self.clock() - started) * 1000

    def _reset(self):
        """Discard corrections and motion when changing processing mode."""
        self.history.clear()
        self.anchor = None
        self.flow = PalmFlow(self.cv2)

    def process(self, frame, timestamp=None, fast=False):
        """Return fresh camera motion without waiting for an in-flight recognition."""
        timestamp = self.clock() if timestamp is None else timestamp
        if not fast:
            if self.pending is not None:
                # Mode changes are uncommon; never call MediaPipe concurrently.
                try:
                    self.pending.result()
                finally:
                    self.pending = None
            self._reset()
            self.active = False
            self.tracker.preview_enabled = self.preview_enabled
            self.tracker.diagnostics_enabled = self.diagnostics_enabled
            return self.tracker.process(frame, timestamp=timestamp)
        self.active = True
        display = self.cv2.flip(frame, 1) if self.tracker.mirror else frame.copy()
        gray = self.cv2.cvtColor(display, self.cv2.COLOR_BGR2GRAY)
        self.history.append((timestamp, gray))
        while self.history and timestamp - self.history[0][0] > self.max_age:
            self.history.popleft()
        position = self.flow.advance(gray) if self.anchor is not None else None
        if self.anchor is not None and position is None:
            # Keep the freshest valid recognition when the image has too little
            # texture for optical flow; a flow miss is not hand loss.
            position = (self.anchor.palm_x, self.anchor.palm_y)
        gesture = None
        if self.pending is not None and self.pending.done():
            try:
                result, self.inference_ms = self.pending.result()
                self.error = None
            except Exception as exc:
                result = None
                self.error = type(exc).__name__
            self.pending = None
            self.anchor = None
            position = None
            if result is not None:
                source = result.observation
                history = list(self.history)
                origin = next((i for i, (at, _) in enumerate(history) if at == source.timestamp), None)
                if (origin is not None and self.clock() - source.timestamp <= self.max_age
                        and source.confidence >= .70):
                    # A valid recognition result remains authoritative even if
                    # palm flow cannot seed on a textureless hand.
                    position = (source.palm_x, source.palm_y)
                    tracked = self.flow.seed(history[origin][1], source, result.palm_points)
                    if tracked:
                        for _, subsequent in history[origin + 1:]:
                            position = self.flow.advance(subsequent)
                            if position is None:
                                break
                    if position is not None:
                        self.anchor = source
                        gesture = source
        if self.pending is None:
            self.pending = self.worker.submit(self._recognize, frame.copy(), timestamp)
        age = None if self.anchor is None else self.clock() - self.anchor.timestamp
        if position is None or age is None or age > self.max_age:
            self.anchor = None
            gesture = None
            observation = HandObservation(timestamp, False)
        else:
            observation = replace(self.anchor, timestamp=timestamp,
                                  palm_x=position[0], palm_y=position[1])
        diagnostics = {
            "motion_tracking": True,
            "motion_valid": observation.detected,
            "gesture_age_ms": None if age is None else round(age * 1000, 1),
            "recognition_inference_ms": self.inference_ms,
            "recognition_error": self.error,
            "tracker_backend": self.backend,
            "tracker_backend_label": self.backend_label + " + experimental palm flow",
        }
        if observation.detected and self.preview_enabled:
            h, w = gray.shape
            self.cv2.circle(display, (int(observation.palm_x*w), int(observation.palm_y*h)),
                            6, (20, 255, 120), 2)
        return TrackingResult(observation, display, diagnostics,
                              motion_only=True, gesture_observation=gesture)

    def close(self):
        """Finish the sole in-flight job before releasing its MediaPipe instance."""
        self.worker.shutdown(wait=True)
        self.tracker.close()
        self._reset()
