# Project: PowerGlove Vision
# File: src/powerglove_vision/vision_app.py
# Purpose: Run camera capture, hand tracking, gesture mapping, profile control, diagnostics, and network output.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-06 - Support measured opt-in Kiyo Pro capture controls and buffer count.
#   2026-09-06 - Add opt-in independent native hand movement tracking.
#   2026-09-06 - Add opt-in correlated latency diagnostics without changing input formats.
#   2026-09-06 - Implement approved player and connectivity refinements.
#   2026-09-06 - Address Setup review reliability and private configuration findings.
#   2026-09-06 - Add complete hand-setup backups and explicit calibration restoration.
#   2026-09-06 - Require fresh centering after player changes before delivery.
#   2026-09-05 - Resumed armed controls from renewable RetroPie game leases.
#   2026-09-05 - Measured fresh-frame publication and controller-transition latency.
#   2026-09-05 - Reported clear proven and experimental tracker names.
#   2026-09-05 - Added latest-frame capture, timing telemetry, and async previews.
#   2026-09-04 - Preloaded vision libraries while keeping idle capture off.
#   2026-09-04 - Logged camera and first-frame startup stage durations.
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Added lazy vision activation and a persistent camera-free idle state.
#   2026-09-03 - Added temporary Learn-page vision with automatic state restoration.
#   2026-09-03 - Published startup timing for browser elapsed-time feedback.
#   2026-09-03 - Retain neutral calibration across worker and profile restarts.
#   2026-09-04 - Repaired persistent profile transport and asynchronous queue acknowledgements.

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
from .diagnostic_trace import session_key
from .model import ControllerState
from .profile_control import ActiveGameLease, ProfileCommandServer, ProfileRequest, read_token
from .realtime import LatestFrameCapture, LatestPreviewEncoder, RollingPerformance
from .runtime_assets import ensure_hand_landmarker_model
from .tracker import MediaPipeTracker, log_startup_stage
from .transport import UdpSender


PRACTICE_PROFILE = "practice"


def _controller_signature(state: ControllerState) -> tuple:
    """Return gameplay-visible state without sequence, time, or confidence noise."""
    return (
        state.profile,
        state.detected,
        state.calibrated,
        tuple(sorted(state.axes.items())),
        tuple(sorted(state.dpad.items())),
        tuple(sorted(state.buttons.items())),
        tuple(sorted(state.fingers.items())),
        tuple(state.events),
    )


def _academy_image_quality(frame, diagnostics: dict, cv2) -> dict:
    """Return advisory hand framing and lighting feedback without retaining pixels."""
    points = diagnostics.get("hand_landmarks") or []
    if len(points) != 21:
        return {"whole_hand_visible": False, "warning": "Show your whole hand clearly."}
    xs = [max(0.0, min(1.0, float(point[0]))) for point in points]
    ys = [max(0.0, min(1.0, float(point[1]))) for point in points]
    margin = min(min(xs), min(ys), 1 - max(xs), 1 - max(ys))
    whole = margin >= .025
    height, width = frame.shape[:2]
    left, right = max(0, int(min(xs) * width)), min(width, int(max(xs) * width) + 1)
    top, bottom = max(0, int(min(ys) * height)), min(height, int(max(ys) * height) + 1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    hand_luma = float(gray[top:bottom, left:right].mean()) if right > left and bottom > top else 0.0
    background_luma = float(gray.mean())
    warning = ""
    if not whole:
        warning = "Move a little farther into the frame so every fingertip is visible."
    elif hand_luma < 55:
        warning = "Your hand looks dark. Add light in front of you if recognition is difficult."
    elif background_luma - hand_luma > 50:
        warning = "The background is much brighter than your hand. Face a light or turn away from the bright window."
    return {"whole_hand_visible": whole, "hand_luma": round(hand_luma, 1),
            "background_luma": round(background_luma, 1), "warning": warning}


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
    tokens = parser.add_mutually_exclusive_group(required=True)
    tokens.add_argument("--token", help="shared receiver token (prefer a private file)")
    tokens.add_argument("--token-file", type=Path, help="private file containing the shared token")
    tokens.add_argument("--device-config", type=Path, help="private device JSON containing the shared token")
    parser.add_argument("--profile", default="bad_street_brawler", help="startup profile; may be changed by RetroPie")
    parser.add_argument("--camera", default="auto", help="camera index, or 'auto'")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--camera-buffers", type=int, choices=(1, 2), default=1,
                        help="V4L2 capture buffers; measured UNO Q candidate uses two")
    parser.add_argument("--kiyo-hdr-off", action="store_true",
                        help="Kiyo Pro only: volatile HDR-off and automatic fixed-rate exposure")
    parser.add_argument(
        "--camera-format", choices=("MJPG", "YUYV"), default="MJPG",
        help="requested V4L2 pixel format for controlled capture benchmarks",
    )
    parser.add_argument(
        "--inference-threads", type=int, default=2,
        help="CPU threads for the legacy MediaPipe inference calculators",
    )
    parser.add_argument(
        "--tracker-backend", choices=("legacy", "tasks-video"), default="legacy",
        help=("MediaPipe Hands (legacy) or MediaPipe Tasks Video "
              "(experimental; tasks-video)"),
    )
    parser.add_argument(
        "--preview-fps", type=float, default=5.0,
        help="maximum diagnostic camera-preview rate",
    )
    parser.add_argument("--motion-tracking", action="store_true",
                        help="experimental asynchronous palm flow for native Super Glove Ball X/Y")
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
        kiyo_applied = False
        camera_control_error = None
        if getattr(args, "kiyo_hdr_off", False):
            from .kiyo_camera import configure_kiyo
            try:
                kiyo_applied = configure_kiyo(camera_device)
            except (OSError, ValueError, RuntimeError) as exc:
                camera_control_error = str(exc)
                print(f"Camera controls unavailable: {exc}", file=sys.stderr, flush=True)
        candidate = cv2.VideoCapture(camera_device, backend)
        log_startup_stage("camera open", started)
        started = time.monotonic()
        candidate.set(
            cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*args.camera_format)
        )
        candidate.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        candidate.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        candidate.set(cv2.CAP_PROP_FPS, args.fps)
        requested_buffers = getattr(args, "camera_buffers", 1)
        buffers_accepted = candidate.set(cv2.CAP_PROP_BUFFERSIZE, requested_buffers)
        log_startup_stage("camera settings", started)
        started = time.monotonic()
        warmup_deadline = time.monotonic() + 5.0
        while candidate.isOpened() and time.monotonic() < warmup_deadline:
            ok, _frame = candidate.read()
            if ok:
                log_startup_stage("first camera frame", started)
                fourcc = int(candidate.get(cv2.CAP_PROP_FOURCC))
                negotiated_format = "".join(
                    chr((fourcc >> (8 * index)) & 0xFF) for index in range(4)
                ).rstrip("\x00")
                metadata = {
                    "camera_format": negotiated_format or args.camera_format,
                    "camera_width": round(candidate.get(cv2.CAP_PROP_FRAME_WIDTH)),
                    "camera_height": round(candidate.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "camera_fps": round(candidate.get(cv2.CAP_PROP_FPS), 1),
                    "camera_buffers_requested": requested_buffers,
                    "camera_buffers": candidate.get(cv2.CAP_PROP_BUFFERSIZE),
                    "camera_buffers_accepted": buffers_accepted,
                    "camera_hdr_off_requested": getattr(args, "kiyo_hdr_off", False),
                    "camera_hdr_off_command_sent": kiyo_applied,
                    "camera_control_error": camera_control_error,
                }
                return cv2, LatestFrameCapture(candidate, _frame, metadata=metadata)
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
        model_path = None
        if args.tracker_backend == "tasks-video":
            model_path = args.model
            if model_path is None or model_path.name == "hand_landmarker.task":
                data_directory = model_path.parent.parent if model_path is not None else Path("data")
                model_path = ensure_hand_landmarker_model(data_directory)
            elif not model_path.is_file():
                raise RuntimeError(f"MediaPipe hand model not found: {model_path}")
        log_startup_stage("tracker asset selection", preparation_started)
        cv2, capture = _open_camera(args)
        tracker = MediaPipeTracker(
            args.glove_color,
            mirror=not args.no_mirror,
            model_path=model_path,
            inference_threads=args.inference_threads,
            backend=args.tracker_backend,
        )
        if getattr(args, "motion_tracking", False):
            from .motion import MotionTracker
            tracker = MotionTracker(tracker)
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


def _consume_game_lease(
    request: ProfileRequest | None, lease: ActiveGameLease, now: float,
) -> tuple[ProfileRequest | None, bool]:
    """Reduce a profile signal to a real transition and an optional lease expiry."""
    if request is not None and request.session_id is not None:
        if not lease.refresh(request, now):
            request = None
    elif request is not None:
        lease.clear()
    return request, lease.expire(now)


def _controller_context_active(lease: ActiveGameLease, profile_source: str) -> bool:
    """Allow output only for a live registered game or an intentional manual context."""
    return lease.session_id is not None or profile_source in {
        "Dashboard", "RetroPie launch hook",
    }


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


def load_worker_token(args: argparse.Namespace) -> str:
    """Read the pairing secret without putting it in the supervised process arguments."""
    configured = json.loads(args.device_config.read_text()).get("token") if args.device_config else args.token
    if configured is not None and not isinstance(configured, str):
        raise ValueError("device token must be text")
    return read_token(configured, args.token_file)


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
    token = load_worker_token(args)
    sender = UdpSender(args.receiver, args.port, token)
    trace = getattr(sender, "trace", None)
    profile_server = ProfileCommandServer(args.profile_listen, args.profile_port, token)
    shared = SharedDebugState()
    shared.tuning = TuningManager(calibration_path.with_name("gesture-tuning.json"))
    preview_encoder = LatestPreviewEncoder(shared.update_frame)
    performance = RollingPerformance()
    last_motion_mode = None
    server = start_debug_server(shared, args.web_host, args.web_port)
    capture = tracker = engine = cv2 = None
    vision_job = _background_call(_preload_vision_libraries)
    vision_operation = "preload"
    vision_started_at = time.time()
    startup_timer = None
    retry_at = 0.0
    read_failures = 0
    capture_failure_since = None
    last_capture_sequence = 0
    last_capture_at = None
    capture_skipped_total = 0
    last_inference_started = None
    last_controller_signature = None
    preview_at = 0.0
    latest_diagnostics = {}
    vision_error: str | None = None
    launch_guard_until = 0.0
    active_game_lease = ActiveGameLease()
    last_launch_session = None

    matrix.set_status(MatrixStatus.GESTURES_IDLE if current_profile is None else MatrixStatus.LOADING)
    matrix.set_profile(current_profile)
    signal.signal(signal.SIGTERM, _shutdown_on_signal)

    try:
        while True:
            old_vision_profile = _effective_profile(current_profile, practice_mode)
            request, lease_expired = _consume_game_lease(
                profile_server.take(), active_game_lease, time.monotonic()
            )
            # Give the authenticated game lifecycle command priority without
            # consuming a simultaneous Dashboard request; it remains queued
            # for the following loop iteration.
            dashboard_request = None if request is not None or lease_expired else shared.take_profile_request()
            requested_profile = None if lease_expired else request.profile if request is not None else (
                dashboard_request[0] if dashboard_request is not None else current_profile
            )
            profile_requested = request is not None or dashboard_request is not None or lease_expired
            practice_request = shared.take_practice_request()
            if request is not None and request.session_id and request.profile is not None:
                if request.session_id != last_launch_session:
                    last_launch_session = request.session_id
                    shared.game_controller_transition(
                        last_launch_session, True,
                        not (practice_mode if practice_request is None else practice_request)
                        and not shared.tuning.active(),
                    )
            elif lease_expired or (request is not None and request.profile is None):
                shared.game_controller_transition(last_launch_session, False)
            transition_requested = profile_requested or practice_request is not None
            if transition_requested:
                last_controller_signature = None
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
                        # display. Keep newly started or already-enabled output
                        # from driving the launch/configuration menu.
                        if request.profile is not None:
                            # A leased request is not sent until RetroArch is
                            # actually running, so it needs only a short input
                            # initialization guard. Legacy one-shot hooks keep
                            # the full pre-emulator guard.
                            guard_ms = 1000 if request.session_id else max(
                                0, int(getattr(args, "launch_guard_ms", 6000))
                            )
                            launch_guard_until = time.monotonic() + guard_ms / 1000.0
                    elif lease_expired:
                        current_game = "No game"
                        profile_source = "RetroPie game session expired"
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
                    capture_failure_since = None
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

            try:
                restored_calibration = shared.tuning.apply_calibration_restore()
                if restored_calibration is not None:
                    shared.request_controller(False)
                    retained_calibration = restored_calibration
                    if engine is not None:
                        engine = GestureEngine(engine.profile, config=engine.config,
                                               calibration=restored_calibration)
                    last_controller_signature = None
                    calibration_save_error = None
            except OSError as exc:
                calibration_save_error = "Hand-setup restore is paused: " + str(exc)

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
                if controller_enabled and active_game_lease.session_id is None \
                        and profile_source == "startup":
                    profile_source = "Dashboard"
                    current_game = "Manual selection"

            if shared.take_calibration_request() and engine is not None:
                shared.tuning.begin_center()
                engine.begin_calibration()
                last_controller_signature = None

            vision_profile = _effective_profile(current_profile, practice_mode)
            if vision_job is not None and vision_job.done():
                try:
                    result = vision_job.result()
                    if vision_operation == "open":
                        cv2, capture, tracker = result
                        last_capture_sequence = 0
                        last_capture_at = None
                        capture_failure_since = None
                        vision_error = None
                except Exception as exc:
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
                status.update(active_game_lease.snapshot(time.monotonic()))
                status["controller_context_active"] = _controller_context_active(
                    active_game_lease, profile_source
                )
                status["vision_state"] = "idle"
                shared.update_status(status, clear_frame=True)
                matrix.set_status(MatrixStatus.GESTURES_IDLE)
                time.sleep(0.1)
                continue

            if capture is None or tracker is None or cv2 is None:
                status = _base_status(current_profile, current_game, profile_source,
                                      controller_enabled, practice_mode=practice_mode)
                status.update(active_game_lease.snapshot(time.monotonic()))
                status["controller_context_active"] = _controller_context_active(
                    active_game_lease, profile_source
                )
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
            captured_frame = capture.latest_after(last_capture_sequence)
            if captured_frame is None:
                time.sleep(0.001)
                continue
            previous_capture_sequence = last_capture_sequence
            last_capture_sequence = captured_frame.sequence
            capture_skipped_total += max(
                0, captured_frame.sequence - previous_capture_sequence - 1
            )
            if not captured_frame.ok:
                read_failures += 1
                if capture_failure_since is None:
                    capture_failure_since = captured_frame.captured_at
                if time.monotonic() - capture_failure_since >= 2.0:
                    vision_job = _background_call(_close_vision, capture, tracker)
                    vision_operation = "close"
                    capture = tracker = engine = cv2 = None
                    retry_at = time.monotonic() + 1.0
                    vision_error = "Camera stopped delivering frames; reconnecting"
                    status = _base_status(
                        current_profile, current_game, profile_source,
                        controller_enabled, practice_mode=practice_mode,
                    )
                    status.update(active_game_lease.snapshot(time.monotonic()))
                    status["controller_context_active"] = _controller_context_active(
                        active_game_lease, profile_source
                    )
                    status.update({"vision_state": "error", "vision_error": vision_error})
                    shared.update_status(status, clear_frame=True)
                    matrix.set_status(MatrixStatus.ERROR)
                else:
                    time.sleep(0.005)
                continue
            read_failures = 0
            capture_failure_since = None
            frame = captured_frame.frame
            inference_started = time.monotonic()
            capture_age_ms = max(
                0.0, (inference_started - captured_frame.captured_at) * 1000
            )
            capture_interval_ms = (
                None if last_capture_at is None
                else max(0.0, (captured_frame.captured_at - last_capture_at) * 1000)
            )
            inference_interval_ms = (
                None if last_inference_started is None
                else max(0.0, (inference_started - last_inference_started) * 1000)
            )
            last_capture_at = captured_frame.captured_at
            last_inference_started = inference_started
            preview_watched = shared.has_stream_clients()
            preview_due = preview_watched and inference_started >= preview_at
            tracker.preview_enabled = preview_due
            tracker.diagnostics_enabled = preview_due or shared.tuning.active()
            if getattr(args, "motion_tracking", False):
                result = tracker.process(
                    frame, timestamp=captured_frame.captured_at,
                    fast=(engine.profile == "super_glove_ball" and engine.calibrated
                          and not practice_mode and not shared.tuning.active()
                          and not shared.tuning.needs_center()),
                )
            else:
                result = tracker.process(frame)
            motion_mode = getattr(result, "motion_only", False)
            if motion_mode != last_motion_mode:
                performance = RollingPerformance()
                latest_diagnostics = {}
                inference_interval_ms = None
                last_controller_signature = None
                last_motion_mode = motion_mode
            tracking_finished_ns = time.monotonic_ns() if trace and trace.enabled else None
            if preview_due:
                latest_diagnostics = result.diagnostics
            if startup_timer is not None:
                log_startup_stage("first inference", inference_started)
            engine.config = shared.tuning.configuration(engine_base_config)
            state = (engine.update_native_motion(result.observation, result.gesture_observation)
                     if motion_mode else engine.update(result.observation))
            if engine.calibrated and engine.calibration is not retained_calibration:
                retained_calibration = engine.calibration
                try:
                    save_calibration(calibration_path, retained_calibration)
                    shared.tuning.finish_center(retained_calibration)
                    calibration_save_error = None
                except OSError as exc:
                    calibration_save_error = str(exc)
                    print(f"Calibration retained in memory but not saved: {exc}", file=sys.stderr, flush=True)
            inference_finished = time.monotonic()
            # Gameplay output takes priority over matrix RPC and browser preview work.
            launch_guard_active = _launch_guard_active(launch_guard_until)
            controller_context_active = _controller_context_active(
                active_game_lease, profile_source
            )
            receiver_available = sender.send(state) if (
                controller_enabled and not practice_mode and not shared.tuning.active()
                and not shared.tuning.needs_center()
                and controller_context_active and not launch_guard_active
            ) else False
            sent_at = time.monotonic()
            if trace and trace.enabled:
                trace.record(dict(event="vision", session=session_key(sender.session),
                    sequence=state.sequence, capture_sequence=captured_frame.sequence,
                    capture_ns=int(captured_frame.captured_at * 1e9),
                    start_ns=int(inference_started * 1e9), tracking_end_ns=tracking_finished_ns,
                    end_ns=int(inference_finished * 1e9),
                    sent=receiver_available, detected=state.detected, calibrated=state.calibrated,
                    x=state.axes.get("x", 0), y=state.axes.get("y", 0),
                    buttons=sum(1 << i for i, name in enumerate(("a", "b", "start", "select",
                        "glove_zap", "menu_guard", "closed_hand", "index_point")) if state.buttons.get(name))))
            inference_ms = (inference_finished - inference_started) * 1000
            send_ms = (sent_at - inference_finished) * 1000
            sample_age_ms = max(0.0, (sent_at - captured_frame.captured_at) * 1000)
            signature = _controller_signature(state)
            transition_age_ms = None
            if receiver_available and signature != last_controller_signature:
                transition_age_ms = sample_age_ms
            if receiver_available:
                last_controller_signature = signature
            performance.record(
                capture_age_ms=capture_age_ms,
                capture_interval_ms=capture_interval_ms,
                inference_ms=inference_ms,
                inference_interval_ms=inference_interval_ms,
                send_ms=send_ms,
                sample_age_ms=sample_age_ms,
                controller_transition_age_ms=transition_age_ms,
            )
            recognition = engine.recognition_feedback()
            push_feedback = engine.push_feedback(result.observation)
            pull_feedback = engine.pull_feedback(result.observation)
            recognized = [name for name, active in state.dpad.items() if active]
            recognized.extend(name for name, active in state.buttons.items() if active)
            recognized.extend(name for name, active in recognition.items() if active)
            if push_feedback["active"]:
                recognized.append("push")
            if pull_feedback["active"]:
                recognized.append("pull")
            image_quality = _academy_image_quality(result.frame, result.diagnostics, cv2) \
                if shared.tuning.active() else {}
            shared.tuning.observe(
                result.observation, engine.calibration, engine.config, engine.calibrated,
                frame=result.frame, image_quality=image_quality,
                performance={"inference_ms": inference_ms, "sample_age_ms": sample_age_ms},
                recognized=recognized,
            )
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
            # Raw camera coordinates let reach calibration avoid filtered/clipped axes.
            status["palm_position"] = (
                {"x": result.observation.palm_x, "y": result.observation.palm_y}
                if result.observation.detected else None
            )
            status["inference_ms"] = round(inference_ms, 1)
            status["send_ms"] = round(send_ms, 1)
            status["sample_age_ms"] = round(sample_age_ms, 1)
            status["tracker_backend"] = tracker.backend
            status["tracker_backend_label"] = tracker.backend_label
            status.update(capture.metadata)
            status["capture_sequence"] = captured_frame.sequence
            status["capture_age_ms"] = round(capture_age_ms, 1)
            status["capture_interval_ms"] = (
                None if capture_interval_ms is None else round(capture_interval_ms, 1)
            )
            status["capture_skipped_total"] = capture_skipped_total
            status["inference_interval_ms"] = (
                None if inference_interval_ms is None else round(inference_interval_ms, 1)
            )
            status["inference_hz"] = (
                None if not inference_interval_ms else round(1000.0 / inference_interval_ms, 1)
            )
            status["performance"] = performance.snapshot()
            status.update(preview_encoder.metrics())
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
                    else (
                        "Armed; waiting for a registered game or manual profile"
                        if controller_enabled and not controller_context_active
                        else (sender.last_error if controller_enabled else "Controller connection stopped")
                    )
                )
            )
            status["launch_guard_active"] = launch_guard_active
            status["launch_guard_remaining_ms"] = max(
                0, round((launch_guard_until - time.monotonic()) * 1000)
            )
            status.update(active_game_lease.snapshot(time.monotonic()))
            status["controller_enabled"] = controller_enabled
            status["controller_context_active"] = controller_context_active
            status["camera_available"] = True
            status["vision_state"] = "active"
            status["menu_gesture"] = engine.menu_feedback()
            status["push_gesture"] = push_feedback
            status["pull_gesture"] = pull_feedback
            status["finger_active"] = engine.curl_feedback(result.observation)
            status["recognition"] = recognition
            status["finger_curls"] = result.observation.fingers
            status["curl_threshold"] = engine.config.pair("index")[0]
            status["tuning"] = shared.tuning.snapshot()
            status.update(latest_diagnostics)
            status["motion_tracking"] = motion_mode
            if motion_mode:
                status.update(result.diagnostics)
                status["processing_timing_scope"] = "motion loop; recognition_inference_ms is separate"
            # Publish control feedback every inference; encode previews asynchronously.
            shared.update_status(status)
            if startup_timer is not None:
                log_startup_stage("activation to active status", startup_timer)
                startup_timer = None
            if not preview_due:
                continue
            preview_at = time.monotonic() + 1.0 / max(1.0, args.preview_fps)
            preview_encoder.submit(
                result.frame,
                "PRACTICE" if practice_mode else (
                    "CALIBRATING - hold still" if not engine.calibrated else vision_profile.replace("_", " ").upper()
                ),
                (0, 210, 255) if engine is not None and not engine.calibrated else (255, 255, 255),
                cv2,
            )
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
        preview_encoder.close()
        profile_server.close()
        server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
