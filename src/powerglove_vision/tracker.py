# Copyright (c) 2026 Iain Bennett
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model import HandObservation


CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)


def _distance(a: Any, b: Any) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def _angle(a: Any, b: Any, c: Any) -> float:
    ab = (a.x - b.x, a.y - b.y)
    cb = (c.x - b.x, c.y - b.y)
    denominator = math.hypot(*ab) * math.hypot(*cb)
    if denominator < 1e-8:
        return math.pi
    cosine = max(-1.0, min(1.0, (ab[0] * cb[0] + ab[1] * cb[1]) / denominator))
    return math.acos(cosine)


def _curl(a: Any, b: Any, c: Any) -> float:
    # Straight is approximately pi radians; tightly bent is near pi/3.
    return max(0.0, min(1.0, (math.pi - _angle(a, b, c)) / (2 * math.pi / 3)))


@dataclass
class TrackingResult:
    observation: HandObservation
    frame: Any


@dataclass
class _Point:
    x: float
    y: float
    z: float = 0.0


def observation_from_landmarks(
    values: list,
    confidence: float,
    *,
    width: int = 640,
    height: int = 480,
    timestamp: float | None = None,
) -> HandObservation:
    """Convert Arduino Gesture Recognition Brick landmarks to controller input."""
    now = time.monotonic() if timestamp is None else timestamp
    if len(values) < 21:
        return HandObservation(now, False)
    landmarks = [
        _Point(float(point[0]) / width, float(point[1]) / height, float(point[2]))
        for point in values[:21]
    ]
    palm_ids = (0, 5, 9, 13, 17)
    palm_x = sum(landmarks[i].x for i in palm_ids) / len(palm_ids)
    palm_y = sum(landmarks[i].y for i in palm_ids) / len(palm_ids)
    palm_scale = (_distance(landmarks[0], landmarks[9]) + _distance(landmarks[5], landmarks[17])) / 2
    return HandObservation(
        timestamp=now,
        detected=True,
        confidence=confidence,
        palm_x=palm_x,
        palm_y=palm_y,
        palm_scale=palm_scale,
        roll=math.atan2(landmarks[5].y - landmarks[17].y, landmarks[5].x - landmarks[17].x),
        thumb_curl=(_curl(landmarks[1], landmarks[2], landmarks[3]) + _curl(landmarks[2], landmarks[3], landmarks[4])) / 2,
        index_curl=(_curl(landmarks[5], landmarks[6], landmarks[7]) + _curl(landmarks[6], landmarks[7], landmarks[8])) / 2,
        middle_curl=(_curl(landmarks[9], landmarks[10], landmarks[11]) + _curl(landmarks[10], landmarks[11], landmarks[12])) / 2,
        ring_curl=(_curl(landmarks[13], landmarks[14], landmarks[15]) + _curl(landmarks[14], landmarks[15], landmarks[16])) / 2,
        pinky_curl=(_curl(landmarks[17], landmarks[18], landmarks[19]) + _curl(landmarks[18], landmarks[19], landmarks[20])) / 2,
    )


class MediaPipeTracker:
    def __init__(
        self,
        glove_color: str = "none",
        mirror: bool = True,
        model_path: Path | str | None = None,
    ) -> None:
        try:
            import cv2
            import mediapipe as mp
        except ImportError as exc:
            raise RuntimeError(
                "camera tracking requires the 'vision' dependencies; "
                "install with: pip install -e '.[vision]'"
            ) from exc
        self.cv2 = cv2
        self.mp = mp
        self.glove_color = glove_color
        self.mirror = mirror
        self._last_timestamp_ms = -1
        self._tasks = not hasattr(mp, "solutions")
        if self._tasks:
            if model_path is None:
                model_path = Path(__file__).resolve().parents[2] / "models" / "hand_landmarker.task"
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
            self.hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=0,
                min_detection_confidence=0.55,
                min_tracking_confidence=0.55,
            )

    def close(self) -> None:
        self.hands.close()

    def process(self, frame: Any, timestamp: float | None = None) -> TrackingResult:
        cv2 = self.cv2
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
        palm_ids = (0, 5, 9, 13, 17)
        palm_x = sum(landmarks[i].x for i in palm_ids) / len(palm_ids)
        palm_y = sum(landmarks[i].y for i in palm_ids) / len(palm_ids)
        palm_scale = (_distance(landmarks[0], landmarks[9]) + _distance(landmarks[5], landmarks[17])) / 2
        roll = math.atan2(
            landmarks[5].y - landmarks[17].y,
            landmarks[5].x - landmarks[17].x,
        )

        curls = {
            "thumb_curl": (_curl(landmarks[1], landmarks[2], landmarks[3]) + _curl(landmarks[2], landmarks[3], landmarks[4])) / 2,
            "index_curl": (_curl(landmarks[5], landmarks[6], landmarks[7]) + _curl(landmarks[6], landmarks[7], landmarks[8])) / 2,
            "middle_curl": (_curl(landmarks[9], landmarks[10], landmarks[11]) + _curl(landmarks[10], landmarks[11], landmarks[12])) / 2,
            "ring_curl": (_curl(landmarks[13], landmarks[14], landmarks[15]) + _curl(landmarks[14], landmarks[15], landmarks[16])) / 2,
            "pinky_curl": (_curl(landmarks[17], landmarks[18], landmarks[19]) + _curl(landmarks[18], landmarks[19], landmarks[20])) / 2,
        }
        observation = HandObservation(
            timestamp=now,
            detected=True,
            confidence=hand_score,
            palm_x=palm_x,
            palm_y=palm_y,
            palm_scale=palm_scale,
            roll=roll,
            **curls,
        )
        height, width = frame.shape[:2]
        for start, end in CONNECTIONS:
            a, b = landmarks[start], landmarks[end]
            cv2.line(frame, (int(a.x * width), int(a.y * height)),
                     (int(b.x * width), int(b.y * height)), (255, 180, 30), 2)
        for point in landmarks:
            cv2.circle(frame, (int(point.x * width), int(point.y * height)), 3, (20, 255, 120), -1)
        label = f"{hand_label} {hand_score:.2f}  glove hint: {self.glove_color}"
        cv2.putText(frame, label, (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 240, 100), 2)
        return TrackingResult(observation, frame)
