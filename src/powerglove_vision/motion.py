# Project: PowerGlove Vision
# File: src/powerglove_vision/motion.py
# Purpose: Archive the inactive optical-flow experiment for possible future reference.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Use validated landmark usability in the archived flow experiment.
#   2026-09-07 - Drew the experimental flow marker in full preview coordinates.
#   2026-09-07 - Bound source-to-current correction and overlap recognition dispatch.
#   2026-09-06 - Add experimental bounded palm optical flow and asynchronous recognition.
# Full history: docs/CHANGELOG.md and Git history.

"""Archived optical-flow experiment; the live worker no longer imports this module."""

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

    def __init__(self, tracker, max_age=.250, clock=time.monotonic,
                 flow_width=320, correction_budget=.025):
        self.tracker = tracker
        self.cv2 = tracker.cv2
        self.backend = tracker.backend
        self.backend_label = tracker.backend_label
        self.preview_enabled = self.diagnostics_enabled = True
        self.max_age, self.clock = max_age, clock
        self.flow_width = flow_width
        self.correction_budget = correction_budget
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
        finished = self.clock()
        return result, (finished - started) * 1000, finished

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
        # Flow coordinates remain normalized; recognition still sees the original
        # camera pixels. Bound pyramid work and history memory independently of capture.
        h, w = gray.shape
        if w > self.flow_width:
            gray = self.cv2.resize(gray, (self.flow_width, max(1, round(h*self.flow_width/w))),
                                   interpolation=self.cv2.INTER_AREA)
        self.history.append((timestamp, gray))
        while self.history and timestamp - self.history[0][0] > self.max_age:
            self.history.popleft()
        gesture = None
        result = None
        completed = self.pending is not None and self.pending.done()
        pickup_ms = correction_ms = source_age_ms = None
        correction_steps = 0
        failure = None
        fallback = None
        if completed:
            try:
                result, self.inference_ms, finished = self.pending.result()
                pickup_ms = max(0.0, (self.clock() - finished) * 1000)
                self.error = None
            except Exception as exc:
                self.error = type(exc).__name__
                failure = "recognition_error"
            self.pending = None
        # Start recognition on this fresh frame before correction. Otherwise the
        # replay cost ages the next job's source before inference even begins.
        if self.pending is None:
            self.pending = self.worker.submit(self._recognize, frame.copy(), timestamp)
        position = None
        flow_position = None
        if completed:
            correction_started = self.clock()
            self.anchor = None
            if result is not None:
                source = result.observation
                source_age_ms = (self.clock() - source.timestamp) * 1000
                history = list(self.history)
                origin = next((i for i, (at, _) in enumerate(history) if at == source.timestamp), None)
                if not source.usable:
                    failure = "recognition_invalid"
                elif not 0 <= self.clock() - source.timestamp <= self.max_age:
                    failure = "recognition_stale"
                else:
                    position = (source.palm_x, source.palm_y)
                    tracked = origin is not None and self.flow.seed(
                        history[origin][1], source, result.palm_points)
                    if not tracked:
                        fallback = "history_missing" if origin is None else "flow_seed_unavailable"
                    if tracked and origin != len(history) - 1:
                        # One source-to-current correction, with the same
                        # forward/backward and displacement checks as normal flow.
                        # Replaying N old frames here makes correction work grow
                        # with recognition delay, which in turn delays the next job.
                        if self.clock() - correction_started < self.correction_budget:
                            position = self.flow.advance(gray)
                            flow_position = position
                            correction_steps = 1
                            if position is None:
                                fallback = "correction_flow_lost"
                        else:
                            position = None
                            fallback = "correction_budget"
                    if self.clock() - correction_started >= self.correction_budget:
                        position = None
                        fallback = "correction_budget"
                    if fallback is not None:
                        # A failed motion estimate does not invalidate recognition.
                        # Jump to its measured point; never interpolate a missing path
                        # or reuse flow seeded on an incompatible frame.
                        position = (source.palm_x, source.palm_y)
                        self.flow = PalmFlow(self.cv2)
                    self.anchor = source
                    gesture = source
            correction_ms = (self.clock() - correction_started) * 1000
        elif self.anchor is not None:
            position = self.flow.advance(gray)
            flow_position = position
            if position is None:
                # Preserve the existing recognition-only fallback for a palm
                # without usable texture, still bounded by original source age.
                position = (self.anchor.palm_x, self.anchor.palm_y)
                fallback = "flow_unavailable"
        age = None if self.anchor is None else self.clock() - self.anchor.timestamp
        if position is None or age is None or not 0 <= age <= self.max_age:
            failure = failure or ("gesture_stale" if age is not None else "awaiting_recognition")
            self.anchor = None
            gesture = None
            observation = HandObservation(timestamp, False)
        else:
            observation = replace(self.anchor, timestamp=timestamp,
                                  palm_x=position[0], palm_y=position[1])
        diagnostics = {
            "motion_tracking": True,
            "motion_failure": failure,
            "motion_fallback_reason": fallback,
            "motion_flow_width": gray.shape[1],
            "motion_correction_ms": None if correction_ms is None else round(correction_ms, 3),
            "motion_correction_steps": correction_steps,
            "recognition_pickup_ms": None if pickup_ms is None else round(pickup_ms, 3),
            "recognition_source_age_ms": None if source_age_ms is None else round(source_age_ms, 3),
            "motion_valid": observation.detected,
            "gesture_age_ms": None if age is None else round(age * 1000, 1),
            "recognition_inference_ms": self.inference_ms,
            "recognition_error": self.error,
            "tracker_backend": self.backend,
            "tracker_backend_label": self.backend_label + " + experimental palm flow",
        }
        if observation.detected and self.preview_enabled:
            # The flow image may be downscaled, but normalized coordinates are
            # drawn on the full-resolution preview returned to the browser.
            h, w = display.shape[:2]
            self.cv2.circle(display, (int(observation.palm_x*w), int(observation.palm_y*h)),
                            6, (20, 255, 120), 2)
        return TrackingResult(observation, display, diagnostics,
                              motion_only=True, gesture_observation=gesture,
                              motion_trace={
                                  "recognition_completed": completed,
                                  "recognized_capture_ns": None if result is None else int(result.observation.timestamp * 1e9),
                                  "recognized_xy": None if result is None else [result.observation.palm_x, result.observation.palm_y],
                                  "recognized_detected": None if result is None else result.observation.detected,
                                  "recognized_confidence": None if result is None else result.observation.confidence,
                                  "anchor_capture_ns": None if self.anchor is None else int(self.anchor.timestamp * 1e9),
                                  "flow_xy": flow_position,
                                  "flow_accepted": observation.detected and fallback is None and flow_position is not None,
                                  "selected_xy": [observation.palm_x, observation.palm_y] if observation.detected else None,
                                  "fallback_reason": fallback,
                                  "failure": failure,
                              })

    def close(self):
        """Finish the sole in-flight job before releasing its MediaPipe instance."""
        self.worker.shutdown(wait=True)
        self.tracker.close()
        self._reset()
