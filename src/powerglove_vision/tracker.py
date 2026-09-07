# Project: PowerGlove Vision
# File: src/powerglove_vision/tracker.py
# Purpose: Convert MediaPipe or Arduino hand landmarks into normalized observations and annotated frames.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-07 - Added geometry validation and benchmarkable pose-stable palm anchors.
#   2026-09-06 - Add opt-in independent native hand movement tracking.
#   2026-09-05 - Added clear proven and experimental backend display names.
#   2026-09-05 - Made legacy and Tasks tracker selection explicit for benchmarks.
#   2026-09-04 - Logged hand-tracker startup stage durations.
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Used 3D world landmarks for camera finger curl.
# Full history: docs/CHANGELOG.md and Git history.

"""Convert MediaPipe or Arduino hand landmarks into normalized observations and annotated frames."""

from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model import HandObservation


TRACKER_BACKEND_LABELS = {
    "legacy": "MediaPipe Hands",
    "tasks-video": "MediaPipe Tasks Video (experimental)",
}
# Existing calibration centres and reach spans were recorded from this anchor.
# Benchmark alternatives without silently changing that coordinate contract.
PALM_ANCHOR = "five_point_average"


def log_startup_stage(label: str, started: float) -> None:
    """Record startup durations without camera imagery or configuration secrets."""
    print(f"Vision startup: {label}: {time.monotonic() - started:.3f}s",
          file=sys.stderr, flush=True)


CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)


def _distance(a: Any, b: Any) -> float:
    """Return the two-dimensional Euclidean distance between landmarks."""
    return math.hypot(a.x - b.x, a.y - b.y)


def _angle(a: Any, b: Any, c: Any, use_depth: bool = False) -> float:
    """Return the stable interior angle formed by three landmarks."""
    ab = (a.x - b.x, a.y - b.y, (a.z - b.z) if use_depth else 0.0)
    cb = (c.x - b.x, c.y - b.y, (c.z - b.z) if use_depth else 0.0)
    denominator = math.sqrt(sum(v*v for v in ab) * sum(v*v for v in cb))
    if denominator < 1e-8:
        return math.pi
    cosine = max(-1.0, min(1.0, sum(x*y for x, y in zip(ab, cb)) / denominator))
    return math.acos(cosine)


def _curl(a: Any, b: Any, c: Any, use_depth: bool = False) -> float:
    # Straight is approximately pi radians; tightly bent is near pi/3.
    """Convert two finger-joint angles into a normalized curl amount."""
    return max(0.0, min(1.0, (math.pi - _angle(a, b, c, use_depth)) / (2 * math.pi / 3)))


@dataclass
class TrackingResult:
    """Bundle one normalized observation with its annotated video frame."""
    observation: HandObservation
    frame: Any
    diagnostics: dict = field(default_factory=dict)
    palm_points: list = field(default_factory=list)
    palm_anchors: dict = field(default_factory=dict)
    motion_only: bool = False
    gesture_observation: HandObservation | None = None
    motion_trace: dict = field(default_factory=dict)


@dataclass
class _Point:
    """Provide a minimal normalized landmark representation for Arduino bridge data."""
    x: float
    y: float
    z: float = 0.0


def _camera_curl_points(result: Any, landmarks: list, tasks: bool,
                        width: int, height: int) -> list:
    """Prefer metric world geometry; correct image aspect ratio in the fallback."""
    worlds = getattr(result, "hand_world_landmarks" if tasks else "multi_hand_world_landmarks", None)
    if worlds:
        points = worlds[0] if tasks else worlds[0].landmark
        if len(points) == 21:
            return points
    # MediaPipe normalized z uses approximately the same scale as normalized x.
    return [_Point(p.x, p.y * height / width, p.z) for p in landmarks]


def _landmarks_valid(landmarks: list) -> bool:
    """Reject malformed landmark sets without inventing a confidence score."""
    if len(landmarks) != 21:
        return False
    finite = all(
        math.isfinite(value)
        for point in landmarks
        for value in (point.x, point.y, point.z)
    )
    if not finite:
        return False
    # These two independent palm dimensions must have measurable area. This
    # rejects collapsed/corrupt results while allowing hands near image edges.
    return _distance(landmarks[0], landmarks[9]) > .005 \
        and _distance(landmarks[5], landmarks[17]) > .005


def _polygon_centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Return the area-weighted centre of a simple polygon, with a safe fallback."""
    twice_area = 0.0
    x_total = y_total = 0.0
    for first, second in zip(points, points[1:] + points[:1]):
        cross = first[0] * second[1] - second[0] * first[1]
        twice_area += cross
        x_total += (first[0] + second[0]) * cross
        y_total += (first[1] + second[1]) * cross
    if abs(twice_area) < 1e-9:
        return (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )
    return x_total / (3.0 * twice_area), y_total / (3.0 * twice_area)


def _palm_anchor_candidates(landmarks: list) -> dict[str, tuple[float, float]]:
    """Calculate comparable palm anchors from one coherent landmark result."""
    ids = (0, 5, 9, 13, 17)
    points = [(float(landmarks[index].x), float(landmarks[index].y)) for index in ids]
    knuckles = points[1:]
    return {
        "five_point_average": (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        ),
        "four_knuckle_centroid": (
            sum(point[0] for point in knuckles) / len(knuckles),
            sum(point[1] for point in knuckles) / len(knuckles),
        ),
        "palm_polygon": _polygon_centroid(points),
        "weighted_wrist_knuckles": (
            (2 * points[0][0] + sum(point[0] for point in knuckles)) / 6,
            (2 * points[0][1] + sum(point[1] for point in knuckles)) / 6,
        ),
    }


def _finger_bends(points: list) -> dict:
    """Measure each joint separately so one deliberate bend is not averaged away."""
    result = {}
    for name, (a, b, c, d) in zip(
        ("thumb", "index", "middle", "ring", "pinky"),
        ((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12),
         (13, 14, 15, 16), (17, 18, 19, 20)),
    ):
        bends = [_curl(points[a], points[b], points[c], True),
                 _curl(points[b], points[c], points[d], True)]
        if name != "thumb":
            bends.insert(0, _curl(points[0], points[a], points[b], True))
        result[name] = bends
    return result


def _finger_curls(points: list) -> dict:
    """Use the strongest joint bend, including the fingers' base knuckles."""
    return {name + "_curl": max(bends) for name, bends in _finger_bends(points).items()}


def _finger_curls_from_bends(bends: dict) -> dict:
    """Collapse already-measured joints without repeating angle calculations."""
    return {name + "_curl": max(values) for name, values in bends.items()}


def _legacy_hands(mp, cpu_threads: int, tracking_confidence: float = .55):
    """Build the lite legacy graph, enabling safe CPU parallelism when supported."""
    settings = {
        "static_image_mode": False,
        "max_num_hands": 1,
        "model_complexity": 0,
        "min_detection_confidence": 0.55,
        "min_tracking_confidence": tracking_confidence,
    }
    base = mp.solutions.hands.Hands(**settings)
    if cpu_threads <= 1:
        return base
    try:
        from google.protobuf import text_format
        from mediapipe.calculators.tensor import inference_calculator_pb2
        from mediapipe.framework import calculator_pb2
        from mediapipe.python.solution_base import SolutionBase

        graph = calculator_pb2.CalculatorGraphConfig()
        text_format.Parse(base._graph.text_config, graph)
        modified = 0
        for node in graph.node:
            if node.calculator != "InferenceCalculatorCpu":
                continue
            options = node.options.Extensions[
                inference_calculator_pb2.InferenceCalculatorOptions.ext
            ]
            options.cpu_num_thread = cpu_threads
            # XNNPACK uses its own thread pool, independent of the interpreter.
            if options.delegate.HasField("xnnpack"):
                options.delegate.xnnpack.num_threads = cpu_threads
            modified += 1
        if modified != 2:
            raise RuntimeError(f"expected two CPU inference nodes, found {modified}")
        threaded = SolutionBase(
            graph_config=graph,
            side_inputs={
                "model_complexity": 0,
                "num_hands": 1,
                "use_prev_landmarks": True,
            },
            outputs=[
                "multi_hand_landmarks",
                "multi_hand_world_landmarks",
                "multi_handedness",
            ],
        )
    except Exception as exc:
        print(
            f"Vision startup: parallel MediaPipe inference unavailable: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return base
    base.close()
    return threaded


class MediaPipeTracker:
    """Run single-hand tracking and produce normalized controller observations."""
    def __init__(
        self,
        glove_color: str = "none",
        mirror: bool = True,
        model_path: Path | str | None = None,
        inference_threads: int = 2,
        tracking_confidence: float = .55,
        backend: str = "legacy",
    ) -> None:
        try:
            import cv2
            started = time.monotonic()
            import mediapipe as mp
            log_startup_stage("MediaPipe import", started)
            started = time.monotonic()
        except ImportError as exc:
            raise RuntimeError(
                "camera tracking requires the 'vision' dependencies; "
                "install with: pip install -e '.[vision]'"
            ) from exc
        self.cv2 = cv2
        self.mp = mp
        self.glove_color = glove_color
        self.mirror = mirror
        self.preview_enabled = True
        self.diagnostics_enabled = True
        self.inference_threads = max(1, int(inference_threads))
        self.tracking_confidence = max(0.0, min(1.0, float(tracking_confidence)))
        self._last_timestamp_ms = -1
        if backend not in TRACKER_BACKEND_LABELS:
            raise ValueError(f"unsupported tracker backend: {backend}")
        if backend == "legacy" and not hasattr(mp, "solutions"):
            raise RuntimeError("this MediaPipe build does not provide the legacy Hands API")
        self.backend = backend
        self.backend_label = TRACKER_BACKEND_LABELS[backend]
        self._tasks = backend == "tasks-video"
        if self._tasks:
            if model_path is None:
                model_path = (
                    Path(__file__).resolve().parents[2]
                    / "data" / "models" / "hand_landmarker.task"
                )
            model_path = Path(model_path)
            if not model_path.is_file():
                raise RuntimeError(f"MediaPipe hand model not found: {model_path}")
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=0.55,
                min_hand_presence_confidence=0.55,
                min_tracking_confidence=0.55,
            )
            self.hands = mp.tasks.vision.HandLandmarker.create_from_options(options)
        else:
            self.hands = _legacy_hands(
                mp, self.inference_threads, self.tracking_confidence,
            )

        log_startup_stage("tracker construction", started)

    def close(self) -> None:
        """Release the underlying MediaPipe hand tracker."""
        self.hands.close()

    def process(self, frame: Any, timestamp: float | None = None) -> TrackingResult:
        """Track and annotate one frame, returning a neutral observation when no hand is found."""
        cv2 = self.cv2
        annotate = self.preview_enabled
        now = time.monotonic() if timestamp is None else timestamp
        if self.mirror:
            frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        if self._tasks:
            timestamp_ms = max(self._last_timestamp_ms + 1, int(now * 1000))
            self._last_timestamp_ms = timestamp_ms
            image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
            result = self.hands.detect_for_video(image, timestamp_ms)
            detected = result.hand_landmarks
        else:
            result = self.hands.process(rgb)
            detected = result.multi_hand_landmarks
        if not detected:
            if not annotate:
                return TrackingResult(HandObservation(now, False), frame)
            cv2.putText(
                frame, "Show one hand to the camera", (20, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (30, 80, 255), 2,
            )
            return TrackingResult(HandObservation(now, False), frame)

        if self._tasks:
            landmarks = result.hand_landmarks[0]
            handedness = result.handedness[0][0]
            hand_label = handedness.category_name or "Hand"
            hand_score = float(handedness.score or 0.0)
        else:
            landmarks = result.multi_hand_landmarks[0].landmark
            handedness = result.multi_handedness[0].classification[0]
            hand_label = handedness.label
            hand_score = float(handedness.score)
        if not _landmarks_valid(landmarks):
            return TrackingResult(HandObservation(now, False), frame,
                                  {"landmark_validation": "invalid"})
        palm_ids = (0, 5, 9, 13, 17)
        palm_anchors = _palm_anchor_candidates(landmarks)
        palm_x, palm_y = palm_anchors[PALM_ANCHOR]
        palm_scale = (_distance(landmarks[0], landmarks[9]) + _distance(landmarks[5], landmarks[17])) / 2
        roll = math.atan2(
            landmarks[5].y - landmarks[17].y,
            landmarks[5].x - landmarks[17].x,
        )

        height, width = frame.shape[:2]
        curl_points = _camera_curl_points(result, landmarks, self._tasks, width, height)
        bends = _finger_bends(curl_points)
        curls = _finger_curls_from_bends(bends)
        observation = HandObservation(
            timestamp=now,
            detected=True,
            confidence=hand_score,
            confidence_source="handedness",
            palm_x=palm_x,
            palm_y=palm_y,
            palm_scale=palm_scale,
            roll=roll,
            **curls,
        )
        if annotate:
            height, width = frame.shape[:2]
            for start, end in CONNECTIONS:
                a, b = landmarks[start], landmarks[end]
                cv2.line(frame, (int(a.x * width), int(a.y * height)),
                         (int(b.x * width), int(b.y * height)), (255, 180, 30), 2)
            for point in landmarks:
                cv2.circle(frame, (int(point.x * width), int(point.y * height)), 3, (20, 255, 120), -1)
            label = f"{hand_label} {hand_score:.2f}  glove hint: {self.glove_color}"
            cv2.putText(frame, label, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 240, 100), 2)
        diagnostics = {}
        if self.diagnostics_enabled:
            diagnostics = {
                "tracker_backend": self.backend,
                "tracker_backend_label": self.backend_label,
                "palm_anchor": PALM_ANCHOR,
                "confidence_source": "handedness",
                "finger_bends": bends,
                "hand_landmarks": [[p.x, p.y] for p in landmarks],
            }
        return TrackingResult(observation, frame, diagnostics,
                              palm_points=[(landmarks[i].x, landmarks[i].y) for i in palm_ids],
                              palm_anchors=palm_anchors)
