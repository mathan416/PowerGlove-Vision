# Copyright (c) 2026 Iain Bennett
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .debug_server import SharedDebugState, start_debug_server
from .gesture import GestureConfig, GestureEngine
from .matrix import MatrixStatus, UnoQMatrix
from .model import ControllerState
from .profile_control import ProfileCommandServer, read_token
from .tracker import MediaPipeTracker
from .transport import UdpSender


def _load_config(profile: str, path: Path | None) -> GestureConfig:
    if path is None:
        candidate = Path(__file__).resolve().parents[2] / "config" / "profiles.json"
        path = candidate if candidate.exists() else None
    if path is None:
        return GestureConfig()
    data = json.loads(path.read_text())
    return GestureConfig(**data.get(profile, data.get("program_defaults", {})))


def build_parser() -> argparse.ArgumentParser:
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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    matrix = UnoQMatrix(enabled=not args.no_matrix)
    matrix.set_status(MatrixStatus.LOADING)

    try:
        import cv2

        token = read_token(args.token, None)
        engine: GestureEngine | None = GestureEngine(args.profile, _load_config(args.profile, args.config))
        current_profile: str | None = args.profile
        current_game = "Startup default"
        candidates = range(10) if args.camera == "auto" else (int(args.camera),)
        capture = None
        for camera_index in candidates:
            candidate = cv2.VideoCapture(camera_index)
            candidate.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
            candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
            candidate.set(cv2.CAP_PROP_FPS, args.fps)
            ok, _frame = candidate.read()
            if candidate.isOpened() and ok:
                capture = candidate
                break
            candidate.release()
        if capture is None:
            raise RuntimeError(f"cannot find a usable camera ({args.camera})")
        tracker = MediaPipeTracker(args.glove_color, mirror=not args.no_mirror, model_path=args.model)
        sender = UdpSender(args.receiver, args.port, args.token)
        profile_server = ProfileCommandServer(args.profile_listen, args.profile_port, token)
        shared = SharedDebugState()
        server = start_debug_server(shared, args.web_host, args.web_port)
    except Exception:
        matrix.set_status(MatrixStatus.ERROR)
        raise

    matrix.set_status(MatrixStatus.READY)
    matrix.set_profile(current_profile)

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                time.sleep(0.02)
                continue
            request = profile_server.take()
            if request is not None:
                if engine is not None:
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
            sender.send(state)
            status = state.to_dict()
            status["calibrating"] = bool(engine is not None and not engine.calibrated)
            status["game"] = current_game
            status["active_profile"] = current_profile or "off"
            status["profile_source"] = "RetroPie launch hook" if request is not None or current_game != "Startup default" else "startup"
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
    except Exception:
        matrix.set_status(MatrixStatus.ERROR)
        raise
    finally:
        released = engine.update(type(result.observation)(time.monotonic(), False)) if engine is not None and 'result' in locals() else None
        if released:
            sender.send(released)
        capture.release()
        tracker.close()
        sender.close()
        profile_server.close()
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
