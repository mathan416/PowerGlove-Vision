# Project: PowerGlove Vision
# File: src/powerglove_vision/vision_app.py
# Purpose: Run camera capture, hand tracking, gesture mapping, profile control, diagnostics, and network output.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
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
from .tracker import MediaPipeTracker
from .transport import UdpSender


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


def main() -> int:
    """Run the complete vision-to-controller worker until shutdown or camera loss."""
    args = build_parser().parse_args()
    matrix = UnoQMatrix(enabled=not args.no_matrix)
    matrix.set_status(MatrixStatus.LOADING)

    try:
        import cv2

        token = read_token(args.token, None)
        engine: GestureEngine | None = GestureEngine(args.profile, _load_config(args.profile, args.config))
        current_profile: str | None = args.profile
        current_game = "Startup default"
        candidates = camera_candidates(args.camera)
        capture = None
        for camera_device in candidates:
            backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
            candidate = cv2.VideoCapture(camera_device, backend)
            candidate.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            candidate.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
            candidate.set(cv2.CAP_PROP_FPS, args.fps)
            candidate.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            # UVC cameras such as the Razer Kiyo can need several seconds to
            # wake and negotiate a stream after boot or an application restart.
            warmup_deadline = time.monotonic() + 5.0
            while candidate.isOpened() and time.monotonic() < warmup_deadline:
                ok, _frame = candidate.read()
                if ok:
                    capture = candidate
                    break
                time.sleep(0.1)
            if capture is not None:
                break
            candidate.release()
        if capture is None:
            raise CameraUnavailableError(f"camera '{args.camera}' is unavailable; waiting for a USB camera")
        tracker = MediaPipeTracker(args.glove_color, mirror=not args.no_mirror, model_path=args.model)
        sender = UdpSender(args.receiver, args.port, args.token)
        profile_server = ProfileCommandServer(args.profile_listen, args.profile_port, token)
        shared = SharedDebugState(args.controller_enabled)
        server = start_debug_server(shared, args.web_host, args.web_port)
    except CameraUnavailableError as exc:
        matrix.set_status(MatrixStatus.ERROR)
        print(f"PowerGlove Vision: {exc}", file=sys.stderr, flush=True)
        return 2
    except Exception:
        matrix.set_status(MatrixStatus.ERROR)
        raise

    matrix.set_status(MatrixStatus.READY)
    matrix.set_profile(current_profile)
    signal.signal(signal.SIGTERM, _shutdown_on_signal)
    controller_enabled = args.controller_enabled

    try:
        read_failures = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                read_failures += 1
                if read_failures >= max(10, args.fps * 2):
                    raise CameraUnavailableError("camera stopped delivering frames; reconnecting")
                time.sleep(0.05)
                continue
            read_failures = 0
            request = profile_server.take()
            if request is not None:
                if controller_enabled and engine is not None:
                    sender.send(ControllerState.released(
                        2_147_483_647, time.monotonic(), current_profile or "off", engine.calibrated
                    ))
                sender.new_session()
                current_profile = request.profile
                current_game = request.rom or request.system or "No game"
                engine = (
                    GestureEngine(current_profile, _load_config(current_profile, args.config))
                    if current_profile else None
                )
                matrix.set_profile(current_profile)
                matrix.set_status(MatrixStatus.READY)
                profile_server.acknowledge(request, True, current_profile)

            controller_request = shared.take_controller_request()
            if controller_request is not None and controller_request != controller_enabled:
                if not controller_request and engine is not None:
                    sender.send(ControllerState.released(
                        2_147_483_647, time.monotonic(), current_profile or "off", engine.calibrated
                    ))
                sender.new_session()
                controller_enabled = controller_request

            if shared.take_calibration_request() and engine is not None:
                engine.begin_calibration()
            result = tracker.process(frame)
            state = (
                engine.update(result.observation)
                if engine is not None
                else ControllerState.released(0, result.observation.timestamp, "off")
            )
            matrix.set_status(
                MatrixStatus.TRACKING
                if current_profile and state.detected and state.calibrated
                else MatrixStatus.READY
            )
            receiver_available = sender.send(state) if controller_enabled else False
            status = state.to_dict()
            status["calibrating"] = bool(engine is not None and not engine.calibrated)
            status["game"] = current_game
            status["active_profile"] = current_profile or "off"
            status["profile_source"] = "RetroPie launch hook" if request is not None or current_game != "Startup default" else "startup"
            status["receiver_available"] = receiver_available
            status["receiver_error"] = sender.last_error if controller_enabled else "Controller connection stopped"
            status["controller_enabled"] = controller_enabled
            cv2.putText(
                result.frame,
                "GESTURES OFF" if engine is None else (
                    "CALIBRATING - hold still" if not engine.calibrated else current_profile.replace("_", " ").upper()
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
    except CameraUnavailableError as exc:
        matrix.set_status(MatrixStatus.ERROR)
        print(f"PowerGlove Vision: {exc}", file=sys.stderr, flush=True)
        return 2
    except Exception:
        matrix.set_status(MatrixStatus.ERROR)
        raise
    finally:
        released = engine.update(type(result.observation)(time.monotonic(), False)) if engine is not None and 'result' in locals() else None
        if released and controller_enabled:
            sender.send(released)
        capture.release()
        tracker.close()
        sender.close()
        profile_server.close()
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
