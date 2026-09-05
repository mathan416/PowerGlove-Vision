# Project: PowerGlove Vision
# File: src/powerglove_vision/vision_app.py
# Purpose: Run camera capture, hand tracking, gesture mapping, profile control, diagnostics, and network output.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Preloaded vision libraries while keeping idle capture off.
#   2026-09-04 - Logged camera and first-frame startup stage durations.
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Added lazy vision activation and a persistent camera-free idle state.
#   2026-09-03 - Added temporary Learn-page vision with automatic state restoration.
#   2026-09-03 - Published startup timing for browser elapsed-time feedback.
#   2026-09-03 - Retain neutral calibration across worker and profile restarts.
#   2026-09-04 - Repaired persistent profile transport and asynchronous queue acknowledgements.
# Full history: docs/CHANGELOG.md and Git history.

"""Run camera capture, hand tracking, gesture mapping, profile control, diagnostics, and network output."""

from __future__ import annotations

import argparse
import importlib
import json
import signal
import sys
import time
import threading
import queue
from concurrent.futures import Future
from pathlib import Path

from .tuning import TuningManager
from .camera import CameraUnavailableError, camera_candidates
from .debug_server import SharedDebugState, start_debug_server
from .gesture import GestureConfig, GestureEngine, load_calibration, save_calibration
from .matrix import MatrixStatus, UnoQMatrix
from .model import ControllerState
from .profile_control import ProfileCommandServer, read_token
from .runtime_assets import ensure_hand_landmarker_model
from .tracker import MediaPipeTracker, log_startup_stage
from .transport import UdpSender


PRACTICE_PROFILE = "practice"


def _shutdown_on_signal(_signum: int, _frame: object) -> None:
    """Convert process termination into the vision loop's normal cleanup path."""
    raise KeyboardInterrupt


def _load_config(profile: str, path: Path | None) -> GestureConfig:
    """Load shared recognition thresholds while accepting legacy profile files."""
    if path is None:
        candidate = Path(__file__).resolve().parents[2] / "config" / "profiles.json"
        path = candidate if candidate.exists() else None
    if path is None:
        return GestureConfig()
    data = json.loads(path.read_text())
    return GestureConfig(**data.get("recognition", data.get(profile, data.get("program_defaults", {}))))


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
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument(
        "--inference-threads", type=int, default=4,
        help="CPU threads for the legacy MediaPipe inference calculators",
    )
    parser.add_argument(
        "--preview-fps", type=float, default=5.0,
        help="maximum diagnostic camera-preview rate",
    )
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
    parser.add_argument(
        "--launch-guard-ms", type=int, default=6000,
        help="pause controller packets after a RetroPie game-start request",
    )
    return parser


def _open_camera(args: argparse.Namespace):
    """Open and warm the selected UVC camera only when gestures are active."""
    started = time.monotonic()
    import cv2
    log_startup_stage("OpenCV import", started)
    started = time.monotonic()
    candidates = camera_candidates(args.camera)
    log_startup_stage("camera discovery", started)

    for camera_device in candidates:
        backend = cv2.CAP_V4L2 if sys.platform.startswith("linux") else cv2.CAP_ANY
        started = time.monotonic()
        candidate = cv2.VideoCapture(camera_device, backend)
        log_startup_stage("camera open", started)
        started = time.monotonic()
        candidate.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        candidate.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        candidate.set(cv2.CAP_PROP_FPS, args.fps)
        candidate.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        log_startup_stage("camera settings", started)
        started = time.monotonic()
        warmup_deadline = time.monotonic() + 5.0
        while candidate.isOpened() and time.monotonic() < warmup_deadline:
            ok, _frame = candidate.read()
            if ok:
                log_startup_stage("first camera frame", started)
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


_VISION_JOBS = queue.Queue(maxsize=1)
_VISION_IO_THREAD = None


def _background_call(function, *args):
    """Run serialized camera I/O on one daemon thread, leaving control responsive."""
    global _VISION_IO_THREAD
    future = Future()

    def run():
        """Complete jobs serially; a blocked driver cannot spawn additional workers."""
        while True:
            result, operation, arguments = _VISION_JOBS.get()
            try:
                result.set_result(operation(*arguments))
            except Exception as exc:
                result.set_exception(exc)

    if _VISION_IO_THREAD is None:
        _VISION_IO_THREAD = threading.Thread(target=run, name="vision-io", daemon=True)
        _VISION_IO_THREAD.start()
    _VISION_JOBS.put_nowait((future, function, args))
    return future


def _preload_vision_libraries() -> None:
    """Warm library imports without opening the camera or constructing a tracker."""
    try:
        for module in ("cv2", "mediapipe"):
            started = time.monotonic()
            importlib.import_module(module)
            log_startup_stage(f"preload {module}", started)
    except Exception as exc:
        # Activation retries normally and reports an actionable error if needed.
        print(f"Vision preload unavailable; will retry on activation: {exc}",
              file=sys.stderr, flush=True)


def _prepare_vision(args):
    """Resolve the model and log camera/tracker startup stages in one I/O job."""
    preparation_started = time.monotonic()
    print("Vision startup: preparation started", file=sys.stderr, flush=True)
    capture = tracker = None
    try:
        model_path = args.model
        if model_path is None or model_path.name == "hand_landmarker.task":
            data_directory = model_path.parent.parent if model_path is not None else Path("data")
            model_path = ensure_hand_landmarker_model(data_directory)
        elif not model_path.is_file():
            raise RuntimeError(f"MediaPipe hand model not found: {model_path}")
        log_startup_stage("model verification/recovery", preparation_started)
        cv2, capture = _open_camera(args)
        tracker = MediaPipeTracker(
            args.glove_color,
            mirror=not args.no_mirror,
            model_path=model_path,
            inference_threads=args.inference_threads,
        )
        log_startup_stage("preparation total", preparation_started)
        return cv2, capture, tracker
    except Exception:
        _close_vision(capture, tracker)
        raise


def _effective_profile(profile: str | None, practice_mode: bool) -> str | None:
    """Choose a tracking profile while preserving an intentionally selected off state."""
    return PRACTICE_PROFILE if practice_mode else profile


def _launch_guard_active(deadline: float, now: float | None = None) -> bool:
    """Return whether RetroPie's pre-emulator input guard is still active."""
    return (time.monotonic() if now is None else now) < deadline


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
    calibration_path = Path(__file__).resolve().parents[2] / "data" / "calibration.json"
    retained_calibration = load_calibration(calibration_path)
    calibration_save_error = None
    matrix = UnoQMatrix(enabled=not args.no_matrix)
    current_profile: str | None = None if args.profile == "off" else args.profile
    current_game = "Startup default"
    profile_source = "startup"
    controller_enabled = args.controller_enabled
    practice_mode = False
    token = read_token(args.token, None)
    sender = UdpSender(args.receiver, args.port, args.token)
    profile_server = ProfileCommandServer(args.profile_listen, args.profile_port, token)
    shared = SharedDebugState()
    shared.tuning = TuningManager(calibration_path.with_name("gesture-tuning.json"))
    server = start_debug_server(shared, args.web_host, args.web_port)
    capture = tracker = engine = cv2 = None
    vision_job = _background_call(_preload_vision_libraries)
    vision_operation = "preload"
    vision_started_at = time.time()
    startup_timer = None
    retry_at = 0.0
    read_failures = 0
    preview_at = 0.0
    latest_diagnostics = {}
    vision_error: str | None = None
    launch_guard_until = 0.0

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
                # A terminal release must never share a session with later frames.
                sender.new_session()
                current_profile = requested_profile
                if profile_requested:
                    if request is not None:
                        current_game = request.rom or request.system or "No game"
                        profile_source = "RetroPie launch hook"
                        # runcommand-onstart fires before RetroArch owns the
                        # display. Keep an already-enabled glove from driving
                        # the launch/configuration menu, then resume without
                        # changing the user's explicit Start/Stop choice.
                        if request.profile is not None:
                            guard_ms = max(0, int(getattr(args, "launch_guard_ms", 6000)))
                            launch_guard_until = time.monotonic() + guard_ms / 1000.0
                    else:
                        assert dashboard_request is not None
                        profile_source = dashboard_request[1]
                        current_game = dashboard_request[2]
                if practice_request is not None:
                    practice_mode = practice_request

                vision_profile = _effective_profile(current_profile, practice_mode)
                if vision_profile != old_vision_profile:
                    # Reuse camera/tracker between active profiles; I/O cleanup is asynchronous.
                    engine = None
                    shared.update_status(
                        _base_status(
                            current_profile, current_game, profile_source,
                            controller_enabled, practice_mode=practice_mode,
                        ),
                        clear_frame=True,
                    )
                    retry_at = 0.0
                    read_failures = 0
                    vision_error = None
                matrix.set_profile(None if practice_mode else current_profile)
                if practice_mode:
                    matrix.set_status(MatrixStatus.TUNING if shared.tuning.active() else MatrixStatus.LEARNING)
                elif vision_profile is None:
                    matrix.set_status(MatrixStatus.GESTURES_IDLE)
                elif vision_profile != old_vision_profile:
                    matrix.set_status(MatrixStatus.LOADING)
                elif engine is not None:
                    matrix.set_status(MatrixStatus.READY)

            controller_request = shared.take_controller_request()
            if shared.tuning.active():
                controller_request = False
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
            completed_frame = None
            if vision_job is not None and vision_job.done():
                try:
                    result = vision_job.result()
                    if vision_operation == "open":
                        cv2, capture, tracker = result
                        vision_error = None
                    elif vision_operation == "read":
                        completed_frame = result
                except Exception as exc:
                    if vision_operation == "read":
                        completed_frame = (False, None)
                    vision_error = str(exc)
                    retry_at = time.monotonic() + 5.0
                    print(f"PowerGlove Vision: {exc}", file=sys.stderr, flush=True)
                finally:
                    vision_job = None
                    vision_operation = None

            if vision_profile is None:
                # Do not wait for an in-flight camera open/read/close to apply off.
                if capture is not None and vision_job is None:
                    vision_job = _background_call(_close_vision, capture, tracker)
                    vision_operation = "close"
                    capture = tracker = engine = cv2 = None
                status = _base_status(None, current_game, profile_source, controller_enabled)
                status["vision_state"] = "idle"
                shared.update_status(status, clear_frame=True)
                matrix.set_status(MatrixStatus.GESTURES_IDLE)
                time.sleep(0.1)
                continue

            if capture is None or tracker is None or cv2 is None:
                status = _base_status(current_profile, current_game, profile_source,
                                      controller_enabled, practice_mode=practice_mode)
                if time.monotonic() < retry_at:
                    status.update({"vision_state": "error", "vision_error": vision_error or "Camera unavailable; retrying"})
                else:
                    if vision_job is None:
                        startup_timer = time.monotonic()
                        vision_job = _background_call(_prepare_vision, args)
                        vision_operation = "open"
                        vision_started_at = time.time()
                    status.update({"vision_state": "starting", "vision_started_at": vision_started_at})
                shared.update_status(status, clear_frame=True)
                matrix.set_status(MatrixStatus.ERROR if vision_error else (
                    (MatrixStatus.TUNING if shared.tuning.active() else MatrixStatus.LEARNING) if practice_mode else MatrixStatus.LOADING))
                time.sleep(0.01)
                continue

            if engine is None:
                engine_base_config = _load_config(vision_profile, args.config)
                engine = GestureEngine(vision_profile, shared.tuning.configuration(engine_base_config),
                                       calibration=retained_calibration)
            if completed_frame is None:
                if vision_job is None:
                    vision_job = _background_call(capture.read)
                    vision_operation = "read"
                # Poll quickly enough that a completed camera frame does not
                # spend a visible fraction of the tracking interval waiting.
                time.sleep(0.002)
                continue
            ok, frame = completed_frame
            if not ok:
                read_failures += 1
                if read_failures >= max(10, args.fps * 2):
                    vision_job = _background_call(_close_vision, capture, tracker)
                    vision_operation = "close"
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
            inference_started = time.monotonic()
            preview_watched = shared.has_stream_clients()
            preview_due = preview_watched and inference_started >= preview_at
            tracker.preview_enabled = preview_due
            tracker.diagnostics_enabled = preview_due
            result = tracker.process(frame)
            if preview_due:
                latest_diagnostics = result.diagnostics
            if startup_timer is not None:
                log_startup_stage("first inference", inference_started)
            engine.config = shared.tuning.configuration(engine_base_config)
            state = engine.update(result.observation)
            shared.tuning.observe(result.observation, engine.calibration, engine.config, engine.calibrated)
            if engine.calibrated and engine.calibration is not retained_calibration:
                retained_calibration = engine.calibration
                try:
                    save_calibration(calibration_path, retained_calibration)
                    calibration_save_error = None
                except OSError as exc:
                    calibration_save_error = str(exc)
                    print(f"Calibration retained in memory but not saved: {exc}", file=sys.stderr, flush=True)
            inference_finished = time.monotonic()
            # Gameplay output takes priority over matrix RPC and browser preview work.
            launch_guard_active = _launch_guard_active(launch_guard_until)
            receiver_available = sender.send(state) if (
                controller_enabled and not practice_mode and not shared.tuning.active()
                and not launch_guard_active
            ) else False
            sent_at = time.monotonic()
            matrix.set_status(
                (MatrixStatus.TUNING if shared.tuning.active() else MatrixStatus.LEARNING)
                if practice_mode
                else (
                    MatrixStatus.TRACKING
                    if state.detected and state.calibrated
                    else MatrixStatus.READY
                )
            )
            status = state.to_dict()
            status["inference_ms"] = round((inference_finished - inference_started) * 1000, 1)
            status["send_ms"] = round((sent_at - inference_finished) * 1000, 1)
            status["calibration_save_error"] = calibration_save_error
            status["calibration_retained"] = retained_calibration is not None
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
                else (
                    "RetroPie launch guard; controller transmission is paused"
                    if controller_enabled and launch_guard_active
                    else (sender.last_error if controller_enabled else "Controller connection stopped")
                )
            )
            status["launch_guard_active"] = launch_guard_active
            status["launch_guard_remaining_ms"] = max(
                0, round((launch_guard_until - time.monotonic()) * 1000)
            )
            status["controller_enabled"] = controller_enabled
            status["camera_available"] = True
            status["vision_state"] = "active"
            status["menu_gesture"] = engine.menu_feedback()
            status["push_gesture"] = engine.push_feedback(result.observation)
            status["pull_gesture"] = engine.pull_feedback(result.observation)
            status["finger_active"] = engine.curl_feedback(result.observation)
            status["recognition"] = engine.recognition_feedback()
            status["finger_curls"] = result.observation.fingers
            status["curl_threshold"] = engine.config.pair("index")[0]
            status["tuning"] = shared.tuning.snapshot()
            status.update(latest_diagnostics)
            # Publish control feedback every inference; encode video at most 15 fps.
            shared.update_status(status)
            if startup_timer is not None:
                log_startup_stage("activation to active status", startup_timer)
                startup_timer = None
            if not preview_due:
                continue
            preview_at = time.monotonic() + 1.0 / max(1.0, args.preview_fps)
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
        # A driver call may be stuck. The process owns its resources and the supervisor
        # can terminate it; never race cleanup against an in-flight I/O operation.
        if vision_job is None:
            _close_vision(capture, tracker)
        sender.close()
        profile_server.close()
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
