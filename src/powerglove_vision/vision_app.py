# Project: PowerGlove Vision
# File: src/powerglove_vision/vision_app.py
# Purpose: Run camera capture, hand tracking, gesture mapping, profile control, diagnostics, and network output.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Added lazy vision activation and a persistent camera-free idle state.
#   2026-09-03 - Added temporary Learn-page vision with automatic state restoration.
# Full history: docs/CHANGELOG.md and Git history.

"""Run camera capture, hand tracking, gesture mapping, profile control, diagnostics, and network output."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path

from .camera import CameraUnavailableError, camera_candidates
from .debug_server import SharedDebugState, start_debug_server
from .gesture import GestureConfig, GestureEngine
from .matrix import MatrixStatus, UnoQMatrix
from .model import ControllerState
from .profile_control import ProfileCommandServer, read_token
from .runtime_assets import ensure_hand_landmarker_model
from .tracker import MediaPipeTracker
from .transport import UdpSender


PRACTICE_PROFILE = "program_h"


def _shutdown_on_signal(_signum: int, _frame: object) -> None:
    """Convert process termination into the vision loop's normal cleanup path."""
    raise KeyboardInterrupt


def _load_config(profile: str, path: Path | None) -> GestureConfig:
    """Load profile thresholds from an explicit or default configuration file."""
    if path is None:
        candidate = Path(__file__).resolve().parents[2] / "config" / "profiles.json"
        path = candidate if candidate.exists() else None
    if path is None:
        return GestureConfig()
    data = json.loads(path.read_text())
    return GestureConfig(**data.get(profile, data.get("program_defaults", {})))


def build_parser() -> argparse.ArgumentParser:
    """Create the vision worker command-line parser."""
    parser = argparse.ArgumentParser(description="Camera-only Power Glove controller")
    parser.add_argument("--receiver", required=True, help="Raspberry Pi hostname or address")
    parser.add_argument("--port", type=int, default=55355)
    parser.add_argument("--token", required=True, help="shared receiver token")
    parser.add_argument("--profile", default="bad_street_brawler", help="startup profile; may be changed by RetroPie")
    parser.add_argument("--camera", default="auto", help="camera index, or 'auto'")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--glove-color", choices=("none", "white", "black"), default="none")
    parser.add_argument("--no-mirror", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--model", type=Path, help="MediaPipe hand-landmarker model")
    parser.add_argument("--web-host", default="0.0.0.0")
    parser.add_argument("--web-port", type=int, default=8088)
    parser.add_argument("--no-matrix", action="store_true", help="disable the UNO Q LED matrix bridge")
    parser.add_argument("--profile-listen", default="0.0.0.0")
    parser.add_argument("--profile-port", type=int, default=55356)
    parser.add_argument("--controller-enabled", action="store_true", help="begin sending controller packets")
    return parser


def _open_camera(args: argparse.Namespace):
    """Open and warm the selected UVC camera only when gestures are active."""
    import cv2

    for camera_device in camera_candidates(args.camera):
        backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
        candidate = cv2.VideoCapture(camera_device, backend)
        candidate.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        candidate.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        candidate.set(cv2.CAP_PROP_FPS, args.fps)
        candidate.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        warmup_deadline = time.monotonic() + 5.0
        while candidate.isOpened() and time.monotonic() < warmup_deadline:
            ok, _frame = candidate.read()
            if ok:
                return cv2, candidate
            time.sleep(0.1)
        candidate.release()
    raise CameraUnavailableError(f"camera '{args.camera}' is unavailable; waiting for a USB camera")


def _close_vision(capture, tracker) -> None:
    """Release optional camera and MediaPipe resources after a profile transition."""
    if capture is not None:
        capture.release()
    if tracker is not None:
        tracker.close()


def _effective_profile(profile: str | None, practice_mode: bool) -> str | None:
    """Choose a tracking profile while preserving an intentionally selected off state."""
    return profile or (PRACTICE_PROFILE if practice_mode else None)


def _base_status(
    profile: str | None,
    game: str,
    source: str,
    controller_enabled: bool,
    *,
    practice_mode: bool = False,
) -> dict:
    """Build a neutral dashboard state for idle, starting, and error modes."""
    vision_profile = _effective_profile(profile, practice_mode)
    status = ControllerState.released(0, time.monotonic(), vision_profile or "off").to_dict()
    status.update({
        "calibrating": False,
        "game": game,
        "active_profile": profile or "off",
        "vision_profile": vision_profile or "off",
        "practice_mode": practice_mode,
        "profile_source": source,
        "receiver_available": False,
        "receiver_error": (
            "Practice mode; controller transmission is paused"
            if practice_mode
            else ("Gestures are paused" if profile is None else "Vision is not ready")
        ),
        "controller_enabled": controller_enabled,
        "camera_available": False,
    })
    return status


def main() -> int:
    """Keep profile control online while starting vision resources only when needed."""
    args = build_parser().parse_args()
    matrix = UnoQMatrix(enabled=not args.no_matrix)
    current_profile: str | None = None if args.profile == "off" else args.profile
    current_game = "Startup default"
    profile_source = "startup"
    controller_enabled = args.controller_enabled
    practice_mode = False
    token = read_token(args.token, None)
    sender = UdpSender(args.receiver, args.port, args.token)
    profile_server = ProfileCommandServer(args.profile_listen, args.profile_port, token)
    shared = SharedDebugState(controller_enabled)
    server = start_debug_server(shared, args.web_host, args.web_port)
    capture = tracker = engine = cv2 = None
    retry_at = 0.0
    read_failures = 0
    vision_error: str | None = None

    matrix.set_status(MatrixStatus.GESTURES_IDLE if current_profile is None else MatrixStatus.LOADING)
    matrix.set_profile(current_profile)
    signal.signal(signal.SIGTERM, _shutdown_on_signal)

    try:
        while True:
            old_vision_profile = _effective_profile(current_profile, practice_mode)
            request = profile_server.take()
            # Give the authenticated game lifecycle command priority without
            # consuming a simultaneous Dashboard request; it remains queued
            # for the following loop iteration.
            dashboard_request = None if request is not None else shared.take_profile_request()
            requested_profile = request.profile if request is not None else (
                dashboard_request[0] if dashboard_request is not None else current_profile
            )
            profile_requested = request is not None or dashboard_request is not None
            practice_request = shared.take_practice_request()
            transition_requested = profile_requested or practice_request is not None
            if transition_requested:
                if controller_enabled and engine is not None:
                    sender.send(ControllerState.released(
                        2_147_483_647, time.monotonic(), engine.profile, engine.calibrated
                    ))
                current_profile = requested_profile
                if profile_requested:
                    if request is not None:
                        current_game = request.rom or request.system or "No game"
                        profile_source = "RetroPie launch hook"
                    else:
                        assert dashboard_request is not None
                        profile_source = dashboard_request[1]
                        current_game = dashboard_request[2]
                if practice_request is not None:
                    practice_mode = practice_request

                vision_profile = _effective_profile(current_profile, practice_mode)
                if vision_profile != old_vision_profile:
                    _close_vision(capture, tracker)
                    capture = tracker = engine = cv2 = None
                    shared.update_status(
                        _base_status(
                            current_profile, current_game, profile_source,
                            controller_enabled, practice_mode=practice_mode,
                        ),
                        clear_frame=True,
                    )
                    sender.new_session()
                    retry_at = 0.0
                    read_failures = 0
                    vision_error = None
                matrix.set_profile(None if practice_mode else current_profile)
                if practice_mode:
                    matrix.set_status(MatrixStatus.LEARNING)
                elif vision_profile is None:
                    matrix.set_status(MatrixStatus.GESTURES_IDLE)
                elif vision_profile != old_vision_profile:
                    matrix.set_status(MatrixStatus.LOADING)
                elif engine is not None:
                    matrix.set_status(MatrixStatus.READY)
                if request is not None:
                    profile_server.acknowledge(request, True, current_profile)

            controller_request = shared.take_controller_request()
            if controller_request is not None and controller_request != controller_enabled:
                if not controller_request and engine is not None and not practice_mode:
                    sender.send(ControllerState.released(
                        2_147_483_647, time.monotonic(), current_profile or "off", engine.calibrated
                    ))
                sender.new_session()
                controller_enabled = controller_request

            if shared.take_calibration_request() and engine is not None:
                engine.begin_calibration()

            vision_profile = _effective_profile(current_profile, practice_mode)
            if vision_profile is None:
                status = _base_status(None, current_game, profile_source, controller_enabled)
                status["vision_state"] = "idle"
                shared.update_status(status, clear_frame=True)
                matrix.set_status(MatrixStatus.GESTURES_IDLE)
                time.sleep(0.1)
                continue

            if capture is None or tracker is None or engine is None or cv2 is None:
                now = time.monotonic()
                status = _base_status(
                    current_profile, current_game, profile_source,
                    controller_enabled, practice_mode=practice_mode,
                )
                if now < retry_at:
                    status.update({
                        "vision_state": "error",
                        "vision_error": vision_error or "Camera or tracker unavailable; retrying",
                    })
                    shared.update_status(status, clear_frame=True)
                    time.sleep(0.1)
                    continue
                status["vision_state"] = "starting"
                shared.update_status(status, clear_frame=True)
                matrix.set_status(
                    MatrixStatus.LEARNING if practice_mode else MatrixStatus.LOADING
                )
                try:
                    model_path = args.model
                    if model_path is None or model_path.name == "hand_landmarker.task":
                        data_directory = model_path.parent.parent if model_path is not None else Path("data")
                        model_path = ensure_hand_landmarker_model(data_directory)
                    elif not model_path.is_file():
                        raise RuntimeError(f"MediaPipe hand model not found: {model_path}")
                    cv2, capture = _open_camera(args)
                    tracker = MediaPipeTracker(
                        args.glove_color, mirror=not args.no_mirror, model_path=model_path
                    )
                    engine = GestureEngine(vision_profile, _load_config(vision_profile, args.config))
                    vision_error = None
                    matrix.set_status(
                        MatrixStatus.LEARNING if practice_mode else MatrixStatus.READY
                    )
                except (CameraUnavailableError, OSError, RuntimeError) as exc:
                    _close_vision(capture, tracker)
                    capture = tracker = engine = cv2 = None
                    retry_at = time.monotonic() + 5.0
                    vision_error = str(exc)
                    status.update({"vision_state": "error", "vision_error": vision_error})
                    shared.update_status(status, clear_frame=True)
                    matrix.set_status(MatrixStatus.ERROR)
                    print(f"PowerGlove Vision: {exc}", file=sys.stderr, flush=True)
                continue

            ok, frame = capture.read()
            if not ok:
                read_failures += 1
                if read_failures >= max(10, args.fps * 2):
                    _close_vision(capture, tracker)
                    capture = tracker = engine = cv2 = None
                    retry_at = time.monotonic() + 1.0
                    vision_error = "Camera stopped delivering frames; reconnecting"
                    status = _base_status(
                        current_profile, current_game, profile_source,
                        controller_enabled, practice_mode=practice_mode,
                    )
                    status.update({"vision_state": "error", "vision_error": vision_error})
                    shared.update_status(status, clear_frame=True)
                    matrix.set_status(MatrixStatus.ERROR)
                else:
                    time.sleep(0.05)
                continue
            read_failures = 0
            result = tracker.process(frame)
            state = engine.update(result.observation)
            matrix.set_status(
                MatrixStatus.LEARNING
                if practice_mode
                else (
                    MatrixStatus.TRACKING
                    if state.detected and state.calibrated
                    else MatrixStatus.READY
                )
            )
            receiver_available = sender.send(state) if controller_enabled and not practice_mode else False
            status = state.to_dict()
            status["calibrating"] = bool(engine is not None and not engine.calibrated)
            status["game"] = current_game
            status["active_profile"] = current_profile or "off"
            status["vision_profile"] = vision_profile
            status["practice_mode"] = practice_mode
            status["profile_source"] = profile_source
            status["receiver_available"] = receiver_available
            status["receiver_error"] = (
                "Practice mode; controller transmission is paused"
                if practice_mode
                else (sender.last_error if controller_enabled else "Controller connection stopped")
            )
            status["controller_enabled"] = controller_enabled
            status["camera_available"] = True
            status["vision_state"] = "active"
            cv2.putText(
                result.frame,
                "PRACTICE" if practice_mode else (
                    "CALIBRATING - hold still" if not engine.calibrated else vision_profile.replace("_", " ").upper()
                ),
                (20, result.frame.shape[0] - 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (0, 210, 255) if engine is not None and not engine.calibrated else (255, 255, 255), 2,
            )
            encoded, jpeg = cv2.imencode(".jpg", result.frame, [cv2.IMWRITE_JPEG_QUALITY, 78])
            if encoded:
                shared.update(jpeg.tobytes(), status)
    except KeyboardInterrupt:
        matrix.set_status(MatrixStatus.OFF)
        return 0
    except Exception:
        matrix.set_status(MatrixStatus.ERROR)
        raise
    finally:
        if engine is not None and controller_enabled and not practice_mode:
            sender.send(ControllerState.released(
                2_147_483_647, time.monotonic(), engine.profile, engine.calibrated
            ))
        _close_vision(capture, tracker)
        sender.close()
        profile_server.close()
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
