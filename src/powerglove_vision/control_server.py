# Project: PowerGlove Vision
# File: src/powerglove_vision/control_server.py
# Purpose: Serve the UNO Q dashboard, local play, setup, pairing, controller controls, and guarded shutdown request.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-09 - Exposed direction-aware tracking as an independent experimental setting.
#   2026-09-08 - Listed discovered cameras in Setup while preserving Automatic selection.
#   2026-09-08 - Added portable automatic/manual exposure and gain settings.
#   2026-09-07 - Added portable camera backend and exposure settings.
#   2026-09-06 - Separate maintained browser pages from HTTP routing.
#   2026-09-06 - Implement approved player and connectivity refinements.
#   2026-09-06 - Address Setup review reliability and private configuration findings.
#   2026-09-06 - Add a persistent idle attract setting without restarting vision.
#   2026-09-06 - Add player controls, exact version details, and responsive layouts.
#   2026-09-06 - Replace the completed lesson panel with the Glove Master award.
#   2026-09-06 - Added the camera-controlled Rock Paper Scissors page.
#   2026-09-05 - Persisted the player's armed controller choice across app restarts.
#   2026-09-05 - Displayed fresh-frame and controller-transition latency.
#   2026-09-05 - Made every Academy lesson and completion control transition atomic.
#   2026-09-05 - Added Pixel Pal's trophy artwork to Academy completion.
#   2026-09-05 - Forwarded Dashboard and Academy calibration requests to the worker.
#   2026-09-05 - Replaced broken Academy camera images with a retrying status panel.
#   2026-09-05 - Displayed plain-language tracker backend names.
#   2026-09-05 - Made Academy lesson navigation atomic against recognition polls.
#   2026-09-05 - Added live capture and inference performance diagnostics.

"""Serve the UNO Q dashboard, local play, setup, pairing, and controller controls."""

from __future__ import annotations

import html
import json
import hashlib
import os
import secrets
import socket
import ssl
import subprocess
import threading
import time
import urllib.parse
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .game_registry import registry_request, validate_document, MAX_REQUEST
from .play_game import PLAY_CONTENT, PLAY_SCRIPT, PLAY_STYLE
from .setup_web import SETUP_CONTENT, SETUP_SCRIPT
from .games_web import GAMES_CONTENT, GAMES_SCRIPT
from .statistics_web import STATISTICS_CONTENT, STATISTICS_SCRIPT
from .web_common import _page, _profile_options, PROFILE_LABELS, VISION_STARTUP_SCRIPT
from .dashboard_web import DASHBOARD
from .academy_web import LEARN
from . import __version__
from .versioning import current_identity
from .resolver import resolve_ipv4
from .camera import camera_device_options

from .help_content import (
    cabinet_reference_content, help_asset, help_document_content,
    help_index_content, guide_markdown, guide_pdf,
)
from .pairing import PAIRING_PORT, certificate_identity, generate_certificate, pair_over_ssh, pair_with_code


WORKER_URL = "http://127.0.0.1:8089"
HTTPS_PORT = 8443
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "powerglove-vision-logo.png"
PROFILES = {
    "bad_street_brawler", "super_glove_ball", "off",
    *(f"program_{letter}" for letter in "abcdefghi"),
}


def _camera_fps(value: Any, *, strict: bool = False) -> str | int:
    """Normalize the portable camera-rate preference without accepting booleans."""
    if value == "auto":
        return "auto"
    if type(value) is int and value in (30, 60):
        return value
    if isinstance(value, str) and value in ("30", "60"):
        return int(value)
    if strict:
        raise ValueError("Choose Automatic, 30 fps, or 60 fps for the camera rate.")
    return "auto"


def _choice(value: Any, choices: tuple[str, ...], fallback: str, message: str,
            *, strict: bool = False) -> str:
    """Normalize one public fixed-choice setting."""
    if isinstance(value, str) and value in choices:
        return value
    if strict:
        raise ValueError(message)
    return fallback


def _manual_camera_value(value: Any, *, gain: bool = False,
                         strict: bool = False) -> int:
    """Normalize a saved manual control before the camera checks exact limits."""
    fallback = 96 if gain else 78
    try:
        if isinstance(value, bool) or isinstance(value, float):
            raise ValueError
        result = int(value)
    except (TypeError, ValueError):
        if strict:
            raise ValueError("Manual camera values must be whole numbers.") from None
        return fallback
    minimum = 0 if gain else 1
    if not minimum <= result <= 10_000:
        if strict:
            label = "gain" if gain else "exposure"
            raise ValueError(f"Manual {label} is outside the safe configuration range.")
        return fallback
    return result


class ForbiddenActionError(Exception):
    """Raised when a sensitive browser action lacks its CSRF safeguard."""


PLAY = _page(
    "Rock Paper Scissors",
    PLAY_CONTENT,
    VISION_STARTUP_SCRIPT + PLAY_SCRIPT,
)


SETUP = _page("Setup", SETUP_CONTENT.replace("{{PROFILE_OPTIONS}}", _profile_options()), SETUP_SCRIPT)

SETUP = SETUP.replace(b'</main>', (GAMES_CONTENT + STATISTICS_CONTENT).encode() + b'</main>', 1)
SETUP = SETUP.replace(b'</body>', b'<script>' + (GAMES_SCRIPT + '\n' + STATISTICS_SCRIPT).encode() + b'</script></body>', 1)


def help_index_page() -> bytes:
    """Build the Help library page from the bundled public-guide registry."""
    return _page("Help", help_index_content(), "")


def help_document_page(slug: str) -> bytes | None:
    """Build one styled Help reading page or return None for an unknown guide."""
    document = help_document_content(slug)
    if document is None:
        return None
    content, title = document
    return _page(title, content, "")


def cabinet_reference_page(host_header: str, state: "ControlState") -> bytes:
    """Build the live, non-secret cabinet reference for the address used by this browser."""
    content, title = cabinet_reference_content(host_header, state.public_config())
    return _page(title, content, "")


class ControlState:
    """Synchronize persistent settings, supervisor health, worker status, and pairing authorization."""
    def __init__(self, config_path: Path, pairing_display: Callable[[str, str], None] | None = None,
                 pairing_finished: Callable[[], None] | None = None) -> None:
        self.config_path = config_path
        self.lock = threading.Lock()
        self.config_lock = threading.RLock()
        self._controller_flush_lock = threading.Lock()
        self._controller_pending = None
        self._controller_revision = 0
        self._controller_retry_at = 0.0
        self._last_controller_choice = 0.0
        self._last_game_event = None
        self._game_session_marker = config_path.with_name("controller-last-game")
        self._last_auto_session = None
        if self._game_session_marker.is_file() and not self._game_session_marker.is_symlink():
            previous = self._game_session_marker.read_text().strip()
            if len(previous) == 64 and all(c in "0123456789abcdef" for c in previous):
                self._last_auto_session = previous
        self._auto_start_error = None
        self.revision = 0
        self.worker_status: dict[str, Any] = {}
        self.camera_available = False
        self.worker_running = False
        self.last_error: str | None = None
        self._controller_marker = config_path.with_name("controller-armed")
        self._controller_enabled = (
            self._controller_marker.is_file() and not self._controller_marker.is_symlink()
        )
        self._pairing_display = pairing_display
        self._pairing_finished = pairing_finished
        self._pairing_identity = ""
        self._pairing_session: dict[str, Any] | None = None
        self._pairing_locked_until = 0.0
        self._shutdown_scheduled = False
        self.started_at = time.time()
        self.build_identity = current_identity()
        self.firmware_identity = None
        self.connection_probe = None
        self._statistics_until = 0.0

    def request_statistics(self, seconds: float = 1.0) -> None:
        """Lease detailed worker telemetry while a visible Dashboard requests it."""
        with self.lock:
            self._statistics_until = max(self._statistics_until, time.monotonic() + seconds)

    def statistics_requested(self) -> bool:
        """Return whether the supervisor should request detailed worker status."""
        with self.lock:
            return time.monotonic() < self._statistics_until

    def configure_pairing_identity(self, identity: str) -> None:
        """Publish the current certificate identity used for physical verification."""
        self._pairing_identity = identity

    def begin_pairing(self, host: str, method: str) -> dict[str, Any]:
        """Create a short-lived physical authorization PIN for one host and pairing method."""
        if not host or len(host) > 253 or any(character.isspace() for character in host):
            raise ValueError("enter a valid RetroPie hostname or IP address")
        if method not in {"ssh", "code"}:
            raise ValueError("choose a supported pairing method")
        now = time.monotonic()
        with self.lock:
            if now < self._pairing_locked_until:
                raise ValueError("pairing is temporarily locked; wait for the current window to expire")
            if self._pairing_session and now < self._pairing_session["expires"]:
                session = self._pairing_session
                if session["host"] != host or session["method"] != method:
                    raise ValueError("another pairing window is already active")
            else:
                pin = f"{secrets.randbelow(1_000_000):06d}"
                session = {
                    "host": host, "method": method, "pin": pin,
                    "expires": now + 120, "attempts": 0,
                }
                self._pairing_session = session
        if self._pairing_display is not None:
            displayed = self._pairing_display(self._pairing_identity, str(session["pin"]))
            if displayed is False:
                with self.lock:
                    self._pairing_session = None
                raise ValueError("the UNO Q matrix is unavailable; physical pairing confirmation is required")
        else:
            with self.lock:
                self._pairing_session = None
            raise ValueError("the UNO Q matrix is unavailable; physical pairing confirmation is required")
        return {"certificate_id": self._pairing_identity, "expires_in": max(0, round(session["expires"] - now))}

    def authorize_pairing(self, host: str, method: str, pin: str) -> None:
        """Consume a matching one-time physical PIN or reject the pairing attempt."""
        now = time.monotonic()
        with self.lock:
            session = self._pairing_session
            if session is None or now >= session["expires"]:
                self._pairing_session = None
                raise ValueError("pairing window expired; prepare pairing again")
            if session["host"] != host or session["method"] != method:
                raise ValueError("pairing request does not match the prepared device and method")
            session["attempts"] += 1
            if not secrets.compare_digest(str(session["pin"]), pin):
                if session["attempts"] >= 5:
                    self._pairing_session = None
                    self._pairing_locked_until = session["expires"]
                raise ValueError("UNO Q approval PIN was rejected")
            self._pairing_session = None

    def finish_pairing_display(self) -> None:
        """Release the consumed PIN display without interrupting a newer confirmation."""
        with self.lock:
            if self._pairing_session is None and self._pairing_finished is not None:
                self._pairing_finished()

    def controller_enabled(self) -> bool:
        """Return the operator-selected controller transmission state."""
        with self.lock:
            return self._controller_enabled

    def set_controller_enabled(self, enabled: bool) -> None:
        """Serialize persisted controller intent with device configuration writes."""
        with self.config_lock:
            self._set_controller_enabled(enabled)

    def _set_controller_enabled(self, enabled: bool, *, automatic: bool = False) -> None:
        """Queue a controller start or stop request for the vision worker."""
        if not automatic:
            self._last_controller_choice = time.monotonic()
            self._auto_start_error = None
        if enabled:
            with self.lock:
                if self.worker_status.get("player", {}).get("needs_center"):
                    raise ValueError("Select Center hand on Dashboard or in Glove Academy before starting controls for this player.")
            config = self.load_config()
            if not str(config.get("receiver", "")).strip() or not config.get("token"):
                raise ValueError("Configure your RetroPie destination and pairing in Connection before starting controls.")
        self._persist_controller_enabled(enabled)
        with self.lock:
            self._controller_enabled = enabled
            self._controller_revision += 1
            self._controller_pending = (self._controller_revision, enabled)
            self._controller_retry_at = 0.0

    def flush_controller_request(self) -> bool:
        """Serialize delivery attempts while retaining any newer intent."""
        if not self._controller_flush_lock.acquire(blocking=False):
            return False
        try:
            return self._flush_controller_request()
        finally:
            self._controller_flush_lock.release()

    def _flush_controller_request(self) -> bool:
        """Retry only the newest explicit Start/Stop intent until the worker acknowledges it."""
        with self.lock:
            pending = self._controller_pending
            if pending is None:
                return True
            if time.monotonic() < self._controller_retry_at:
                return False
            self._controller_retry_at = time.monotonic() + 1.0
        _, enabled = pending
        request = urllib.request.Request(
            WORKER_URL + "/controller", method="POST",
            data=json.dumps({"enabled": enabled}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=1) as response:
                result = json.load(response)
            if not isinstance(result, dict) or result.get("controller_enabled") is not enabled:
                return False
        except urllib.error.HTTPError as exc:
            if exc.code >= 500:
                return False
            with self.config_lock:
                with self.lock:
                    current = self._controller_pending == pending
                if enabled and current:
                    self.set_controller_enabled(False)
            raise ValueError("The worker rejected the controller request. Check centering and try again.") from exc
        except (OSError, ValueError, RecursionError):
            return False
        with self.lock:
            if self._controller_pending == pending:
                self._controller_pending = None
                return True
        return False

    def _persist_controller_enabled(self, enabled: bool) -> None:
        """Atomically retain the explicit Start/Stop choice without storing it in settings."""
        path = self._controller_marker
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError("Controller state path is not a regular file.")
        if not enabled:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            return
        temporary = path.with_name("." + path.name + "." + secrets.token_hex(8) + ".tmp")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(str(temporary), flags, 0o600)
        try:
            with os.fdopen(descriptor, "w") as marker:
                marker.write("armed\n")
                marker.flush()
                os.fsync(marker.fileno())
            os.replace(str(temporary), str(path))
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def schedule_system_shutdown(self, delay_seconds: float = 2.0) -> None:
        """Ask the root-owned host helper to power off after the HTTP reply."""
        data_directory = self.config_path.parent
        if not (data_directory / ".shutdown-enabled").is_file():
            raise FileNotFoundError("System shutdown helper is not installed on this UNO Q.")
        with self.lock:
            if self._shutdown_scheduled:
                return
            self._shutdown_scheduled = True

        def trigger() -> None:
            """Publish a complete fixed request after allowing the HTTP response to finish."""
            path = data_directory / "shutdown-request"
            temporary = data_directory / f".shutdown-request.{secrets.token_hex(8)}.tmp"
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(temporary, flags, 0o600)
                with os.fdopen(descriptor, "w") as request:
                    request.write("shutdown\n")
                    request.flush()
                    os.fsync(request.fileno())
                os.replace(temporary, path)
            finally:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass

        timer = threading.Timer(delay_seconds, trigger)
        timer.daemon = True
        timer.start()

    def load_config(self) -> dict[str, Any]:
        """Load the complete private device configuration from disk."""
        return json.loads(self.config_path.read_text())

    def public_config(self) -> dict[str, Any]:
        """Return browser-safe settings with all secrets removed."""
        config = self.load_config()
        return {
            "receiver": config.get("receiver", ""),
            "port": int(config.get("port", 55355)),
            "profile": config.get("profile", "bad_street_brawler"),
            "glove_color": config.get("glove_color", "none"),
            "camera": str(config.get("camera", "auto")),
            "camera_options": camera_device_options(),
            "camera_fps": _camera_fps(config.get("camera_fps", "auto")),
            "camera_backend": _choice(
                config.get("camera_backend", "opencv"),
                ("opencv", "direct-v4l2"), "opencv", "Choose a camera reader.",
            ),
            "camera_exposure": _choice(
                "kiyo-low-latency" if config.get("kiyo_hdr_off") is True else
                    config.get("camera_exposure", "auto"),
                ("auto", "low-latency", "kiyo-low-latency", "manual"), "auto",
                "Choose an exposure mode.",
            ),
            "camera_manual_exposure": _manual_camera_value(
                config.get("camera_manual_exposure", 78)
            ),
            "camera_manual_gain": _manual_camera_value(
                config.get("camera_manual_gain", 96), gain=True
            ),
            "matrix_attract": config.get("matrix_attract", "on"),
            "paired": bool(config.get("receiver") and config.get("token")),
            "connection_configured": bool(str(config.get("receiver", "")).strip() and config.get("token")),
            "controller_enabled": self.controller_enabled(),
        }

    def save_attract(self, incoming):
        """Serialize preference updates with connection saves."""
        with self.config_lock:
            return self._save_attract(incoming)

    def _save_attract(self, incoming):
        """Persist an idle display preference without restarting or arming the worker."""
        from .game_registry import atomic_write
        mode = incoming.get("mode")
        if mode not in ("on", "dim", "off"):
            raise ValueError("Choose On, Dim, or Off for attract mode.")
        current = self.load_config()
        current["matrix_attract"] = mode
        atomic_write(self.config_path, json.dumps(current, indent=2) + "\n")
        return {"mode": mode}

    def save_config(self, incoming: dict[str, Any]) -> dict[str, Any]:
        """Serialize full configuration writes with display preference changes."""
        with self.config_lock:
            return self._save_config(incoming)

    def _save_config(self, incoming: dict[str, Any]) -> dict[str, Any]:
        """Validate and persist browser-submitted non-secret device settings."""
        receiver = str(incoming.get("receiver", "")).strip()
        if len(receiver) > 253 or any(ch.isspace() for ch in receiver):
            raise ValueError("Enter a valid console hostname or IP address.")
        try:
            raw_port = incoming.get("port", 55355)
            if isinstance(raw_port, bool) or isinstance(raw_port, float):
                raise ValueError("Controller port must be a whole number.")
            port = int(raw_port)
        except (TypeError, ValueError) as exc:
            raise ValueError("Controller port must be a number.") from exc
        if not 1 <= port <= 65535:
            raise ValueError("Controller port must be between 1 and 65535.")
        profile = str(incoming.get("profile", ""))
        if profile not in PROFILES:
            raise ValueError("Choose a supported gesture profile.")
        glove_color = str(incoming.get("glove_color", "none"))
        if glove_color not in {"none", "white", "black"}:
            raise ValueError("Choose bare hand, white glove, or black glove.")
        camera = str(incoming.get("camera", "auto")).strip().lower()
        if camera != "auto" and (not camera.isdigit() or int(camera) > 99):
            raise ValueError("Camera must be 'auto' or a camera number.")
        current = self.load_config()
        camera_fps = _camera_fps(
            incoming.get("camera_fps", current.get("camera_fps", "auto")),
            strict=True,
        )
        camera_backend = _choice(
            incoming.get("camera_backend", current.get("camera_backend", "opencv")),
            ("opencv", "direct-v4l2"), "opencv",
            "Choose OpenCV or Direct V4L2 for camera reading.", strict=True,
        )
        camera_exposure = _choice(
            incoming.get("camera_exposure", current.get("camera_exposure", "auto")),
            ("auto", "low-latency", "kiyo-low-latency", "manual"), "auto",
            "Choose Automatic, Low latency, Kiyo Pro tested, or Manual exposure.", strict=True,
        )
        manual_exposure = _manual_camera_value(
            incoming.get("camera_manual_exposure",
                         current.get("camera_manual_exposure", 78)), strict=True,
        )
        manual_gain = _manual_camera_value(
            incoming.get("camera_manual_gain", current.get("camera_manual_gain", 96)),
            gain=True, strict=True,
        )
        if camera_exposure == "manual" and camera_backend != "direct-v4l2":
            raise ValueError("Manual exposure requires the Direct V4L2 camera reader.")
        token = secrets.token_urlsafe(24) if incoming.get("rotate_token") else current.get("token")
        if not token:
            token = secrets.token_urlsafe(24)
        saved = dict(current)
        saved.update({
            "receiver": receiver, "port": port, "token": token,
            "profile": profile, "glove_color": glove_color,
            "camera": camera, "camera_fps": camera_fps,
            "camera_backend": camera_backend, "camera_exposure": camera_exposure,
            "camera_manual_exposure": manual_exposure,
            "camera_manual_gain": manual_gain,
            "matrix_attract": current.get("matrix_attract", "on"),
        })
        saved.pop("kiyo_hdr_off", None)
        from .game_registry import atomic_write
        atomic_write(self.config_path, json.dumps(saved, indent=2) + "\n")
        if not receiver or incoming.get("rotate_token"):
            self.set_controller_enabled(False)
        with self.lock:
            self.revision += 1
        return self.public_config()

    def snapshot(self) -> dict[str, Any]:
        """Return a thread-safe dashboard snapshot of configuration and runtime health."""
        with self.lock:
            status = dict(self.worker_status)
            if self._auto_start_error and not self._controller_enabled:
                status["receiver_error"] = self._auto_start_error
            status.update({
                "camera_available": self.camera_available,
                "worker_running": self.worker_running,
                "last_error": self.last_error,
                "controller_enabled": self._controller_enabled,
                "controller_request_pending": self._controller_pending is not None,
                "uptime_seconds": round(time.time() - self.started_at),
                "app_started_at": self.started_at,
                "version": __version__,
                "build": dict(self.build_identity),
                "firmware": {"running": self.firmware_identity,
                    "expected": self.build_identity.get("firmware_expected"),
                    "state": "unavailable" if not self.firmware_identity else
                        "matched" if self.firmware_identity == self.build_identity.get("firmware_expected") else "different"},
            })
        config = self.public_config()
        from .wifi_status import read_wifi_status
        status["wifi_status"] = read_wifi_status()
        status["connection_configured"] = config["connection_configured"]
        status.setdefault("configured_profile", config["profile"])
        status.setdefault("native_xy_mode", "latest")
        return status

    def connection_status(self):
        """Return the same cached checks used by the four idle matrix pixels."""
        if self.connection_probe is not None:
            return self.connection_probe(self.load_config(), refresh=True)
        from .wifi_status import read_wifi_status, read_network_status
        return {"app": True, "console_configured": bool(self.public_config().get("receiver")),
                "console_service": None, "console_authenticated": None,
                "wifi": read_wifi_status(), "networking": read_network_status(), "checked_seconds_ago": None}

    def update_firmware(self, identity):
        """Publish only the identity read from the running sketch."""
        with self.lock:
            self.firmware_identity = identity

    def update_supervisor(self, *, camera: bool, running: bool, error: str | None = None) -> None:
        """Publish camera, worker, and supervisor-error state for the dashboard."""
        with self.lock:
            self.camera_available = camera
            self.worker_running = running
            self.last_error = error
            if not running:
                self.worker_status = {}

    def update_worker(self, status: dict[str, Any]) -> None:
        """Merge the latest worker diagnostics into shared dashboard state."""
        status.pop("token", None)
        game_event = status.pop("_game_controller_event", None)
        with self.lock:
            self.worker_status = status
            self.worker_running = True
            self.camera_available = bool(status.get("camera_available", False))
            self.last_error = None
        self._apply_game_controller_event(game_event, status)

    def _apply_game_controller_event(self, event, status):
        """Consume a private worker launch once, with explicit operator choices winning."""
        if not isinstance(event, dict):
            return
        with self.config_lock:
            identity = (event.get("session"), event.get("enabled"), event.get("at"))
            if identity == self._last_game_event:
                return
            self._last_game_event = identity
            enabled = event.get("enabled")
            if type(enabled) is not bool:
                return
            if enabled:
                raw_session = event.get("session")
                if not isinstance(raw_session, str) or not raw_session:
                    return
                session = hashlib.sha256(raw_session.encode()).hexdigest()
                if session == self._last_auto_session:
                    return
                if self._game_session_marker.is_symlink():
                    return
                from .game_registry import atomic_write
                atomic_write(self._game_session_marker, session + "\n")
                self._last_auto_session = session
            if event.get("at", 0) <= self._last_controller_choice:
                return
            if enabled and (not event.get("eligible") or status.get("practice_mode")
                            or status.get("tuning", {}).get("active")):
                return
            try:
                self._set_controller_enabled(enabled, automatic=True)
                self._auto_start_error = None
            except ValueError as error:
                self._auto_start_error = str(error)


def _send(handler: BaseHTTPRequestHandler, status: int, body: bytes, content_type: str) -> None:
    """Send one HTTP response with explicit content type and length."""
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(state: ControlState) -> type[BaseHTTPRequestHandler]:
    """Build the request handler bound to one shared control state."""
    class Handler(BaseHTTPRequestHandler):
        """Handle public diagnostics and protected local administration routes."""
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def json_body(self, require_json: bool = False) -> dict[str, Any]:
            """Read a size-bounded JSON request body and require an object value."""
            if require_json and self.headers.get_content_type() != "application/json":
                raise ValueError("Content-Type must be application/json")
            length = int(self.headers.get("Content-Length", "0"))
            limit = MAX_REQUEST if self.path == "/api/games" else 8192
            if not 0 <= length <= limit:
                raise ValueError("Request is too large.")
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("Request must be an object.")
            return data

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path in ("/", "/debug"):
                self.send_response(302); self.send_header("Location", "/dashboard"); self.end_headers()
            elif path == "/dashboard":
                _send(self, 200, DASHBOARD, "text/html; charset=utf-8")
            elif path == "/play":
                _send(self, 200, PLAY, "text/html; charset=utf-8")
            elif path == "/games":
                self.send_response(302)
                self.send_header("Location", "/setup#games-section")
                self.end_headers()
            elif path == "/learn":
                _send(self, 200, LEARN, "text/html; charset=utf-8")
            elif path == "/setup":
                _send(self, 200, SETUP, "text/html; charset=utf-8")
            elif path == "/help":
                _send(self, 200, help_index_page(), "text/html; charset=utf-8")
            elif path == "/help/cabinet":
                _send(self, 200, cabinet_reference_page(self.headers.get("Host", ""), state), "text/html; charset=utf-8")
            elif path.startswith("/help/") and path.endswith(".md"):
                source = guide_markdown(path[len("/help/"):-len(".md")])
                if source is None:
                    self.send_error(404)
                else:
                    _send(self, 200, source, "text/markdown; charset=utf-8")
            elif path.startswith("/help-pdf/") and path.endswith(".pdf"):
                document = guide_pdf(path[len("/help-pdf/"):-len(".pdf")])
                if document is None:
                    self.send_error(404)
                else:
                    body, _filename = document
                    _send(self, 200, body, "application/pdf")
            elif path.startswith("/help/"):
                page = help_document_page(path[len("/help/"):])
                if page is None:
                    self.send_error(404)
                else:
                    _send(self, 200, page, "text/html; charset=utf-8")
            elif path.startswith("/help-assets/"):
                asset = help_asset(path[len("/help-assets/"):])
                if asset is None:
                    self.send_error(404)
                else:
                    body, content_type = asset
                    _send(self, 200, body, content_type)
            elif path == "/favicon.ico":
                try:
                    _send(self, 200, (LOGO_PATH.parent / "favicon.ico").read_bytes(), "image/vnd.microsoft.icon")
                except OSError:
                    self.send_error(404)
            elif path in ("/assets/powerglove-vision-icon.png", "/assets/favicon-32.png", "/assets/apple-touch-icon.png"):
                try:
                    _send(self, 200, (LOGO_PATH.parent / path.rsplit("/", 1)[1]).read_bytes(), "image/png")
                except OSError:
                    self.send_error(404)
            elif path == "/assets/powerglove-vision-logo.png":
                try:
                    _send(self, 200, LOGO_PATH.read_bytes(), "image/png")
                except OSError:
                    self.send_error(404)
            elif path == "/status":
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                if query.get("statistics") == ["1"]:
                    state.request_statistics()
                _send(self, 200, json.dumps(state.snapshot()).encode(), "application/json")
            elif path == "/api/connection-status":
                _send(self, 200, json.dumps(state.connection_status()).encode(), "application/json")
            elif path == "/api/config":
                _send(self, 200, json.dumps(state.public_config()).encode(), "application/json")
            elif path == "/stream":
                self.proxy_stream()
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            try:
                origin = self.headers.get("Origin")
                if (self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site" or
                        (origin and origin not in ("http://"+self.headers.get("Host", ""), "https://"+self.headers.get("Host", "")))):
                    raise ForbiddenActionError("Open this control from the Controller website.")
                if path in ("/api/games", "/api/tuning", "/api/players", "/api/attract"):
                    expected = path.rsplit("/", 1)[-1]
                    origin = self.headers.get("Origin")
                    if (self.headers.get("X-PowerGlove-Action") != expected
                            or self.headers.get("Sec-Fetch-Site", "") == "cross-site"
                            or (origin and origin not in ("http://" + self.headers.get("Host", ""), "https://" + self.headers.get("Host", "")))):
                        raise ForbiddenActionError("Open this control from the UNO website.")
                    incoming = self.json_body(require_json=True)
                    if path == "/api/attract":
                        result = state.save_attract(incoming)
                    elif path == "/api/games":
                        action = incoming.get("action")
                        if action in ("validate", "format"):
                            data = validate_document(incoming.get("document"))
                            result = {"valid": True, "document": json.dumps(data, indent=2) + "\n"}
                        elif action in ("read", "save", "restore"):
                            result = registry_request(state.load_config(), action,
                                {"document": incoming.get("document"), "revision": incoming.get("revision")})
                        else:
                            raise ValueError("Unknown Games action.")
                    else:
                        if path == "/api/players" and incoming.get("action") in ("create", "select", "delete", "restore", "reuse_calibration"):
                            # Persist stop before changing players, including across a supervisor restart.
                            state.set_controller_enabled(False)
                        request = urllib.request.Request(WORKER_URL + ("/players" if path == "/api/players" else "/tuning"), method="POST",
                            data=json.dumps(incoming).encode(), headers={"Content-Type": "application/json"})
                        try:
                            with urllib.request.urlopen(request, timeout=2) as response:
                                result = json.load(response)
                        except urllib.error.HTTPError as exc:
                            raise ValueError(json.loads(exc.read()).get("error", "Tuning request failed.")) from None
                        if incoming.get("action") == "begin":
                            state.set_controller_enabled(False)
                    _send(self, 200, json.dumps(result).encode(), "application/json")
                elif path == "/api/config":
                    result = state.save_config(self.json_body(require_json=True))
                    _send(self, 200, json.dumps(result).encode(), "application/json")
                elif path == "/api/test-connection":
                    receiver = str(self.json_body().get("receiver", "")).strip()
                    if not receiver:
                        raise ValueError("Enter your RetroPie hostname or IP address first.")
                    address = resolve_ipv4(receiver)
                    _send(self, 200, json.dumps({"ok": True, "receiver": receiver, "address": address}).encode(), "application/json")
                elif path == "/api/controller":
                    enabled = self.json_body().get("enabled")
                    if not isinstance(enabled, bool):
                        raise ValueError("enabled must be true or false")
                    state.set_controller_enabled(enabled)
                    delivered = state.flush_controller_request()
                    _send(self, 200 if delivered else 202, json.dumps({
                        "controller_enabled": enabled, "pending": not delivered}).encode(), "application/json")
                elif path == "/api/profile":
                    profile = str(self.json_body(require_json=True).get("profile", ""))
                    if profile not in PROFILES:
                        raise ValueError("Choose a supported gesture profile.")
                    request = urllib.request.Request(
                        WORKER_URL + "/profile",
                        method="POST",
                        data=json.dumps({"profile": profile}).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(request, timeout=1) as response:
                        result = response.read()
                    _send(self, 202, result, "application/json")
                elif path == "/api/practice":
                    incoming = self.json_body(require_json=True)
                    enabled = incoming.get("enabled")
                    if not isinstance(enabled, bool):
                        raise ValueError("enabled must be true or false")
                    payload = {
                        "session": str(incoming.get("session", "")),
                        "enabled": enabled,
                        "reset": incoming.get("reset") is True,
                    }
                    request = urllib.request.Request(
                        WORKER_URL + "/practice",
                        method="POST",
                        data=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(request, timeout=1) as response:
                        result = response.read()
                    _send(self, 200, result, "application/json")
                elif path == "/calibrate":
                    request = urllib.request.Request(
                        WORKER_URL + "/calibrate", method="POST"
                    )
                    with urllib.request.urlopen(request, timeout=1):
                        pass
                    _send(self, 204, b"", "application/json")
                elif path == "/api/system/shutdown":
                    incoming = self.json_body(require_json=True)
                    if self.headers.get("X-PowerGlove-Action") != "shutdown":
                        raise ForbiddenActionError("Shutdown request is missing its browser-action safeguard.")
                    if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
                        raise ForbiddenActionError("Cross-site shutdown requests are not allowed.")
                    if incoming.get("confirm") != "SHUTDOWN":
                        raise ValueError("Confirm the system shutdown before continuing.")
                    state.schedule_system_shutdown()
                    state.set_controller_enabled(False)
                    request = urllib.request.Request(
                        WORKER_URL + "/controller", method="POST",
                        data=b'{"enabled":false}', headers={"Content-Type": "application/json"},
                    )
                    try:
                        with urllib.request.urlopen(request, timeout=1):
                            pass
                    except (OSError, urllib.error.URLError):
                        pass
                    _send(self, 202, b'{"shutting_down":true}', "application/json")
                elif path == "/api/pair/code":
                    self.require_secure_pairing()
                    incoming = self.json_body(require_json=True)
                    host = str(incoming.get("host", "")).strip()
                    state.authorize_pairing(host, "code", str(incoming.get("device_code", "")))
                    try:
                        pair_with_code(
                            host, PAIRING_PORT,
                            str(incoming.get("code", "")), str(state.load_config()["token"]),
                        )
                    finally:
                        state.finish_pairing_display()
                    _send(self, 200, b'{"paired":true}', "application/json")
                elif path == "/api/pair/ssh":
                    self.require_secure_pairing()
                    incoming = self.json_body(require_json=True)
                    host = str(incoming.get("host", "")).strip()
                    state.authorize_pairing(host, "ssh", str(incoming.get("device_code", "")))
                    password = str(incoming.get("password", ""))
                    try:
                        pair_over_ssh(
                            host,
                            str(incoming.get("username", "")).strip(), password,
                            str(state.load_config()["token"]),
                            state.config_path.parent / "ssh" / "known_hosts",
                        )
                    finally:
                        password = ""
                        incoming["password"] = ""
                        state.finish_pairing_display()
                    _send(self, 200, b'{"paired":true}', "application/json")
                elif path == "/api/pair/begin":
                    self.require_secure_pairing()
                    incoming = self.json_body(require_json=True)
                    result = state.begin_pairing(
                        str(incoming.get("host", "")).strip(), str(incoming.get("method", ""))
                    )
                    _send(self, 200, json.dumps(result).encode(), "application/json")
                else:
                    self.send_error(404)
            except (ValueError, json.JSONDecodeError, RecursionError) as exc:
                _send(self, 400, json.dumps({"error": str(exc)}).encode(), "application/json")
            except ForbiddenActionError as exc:
                _send(self, 403, json.dumps({"error": str(exc)}).encode(), "application/json")
            except PermissionError as exc:
                _send(self, 426, json.dumps({"error": str(exc)}).encode(), "application/json")
            except (OSError, urllib.error.URLError, subprocess.SubprocessError) as exc:
                _send(self, 503, json.dumps({"error": f"Not reachable: {exc}"}).encode(), "application/json")

        def require_secure_pairing(self) -> None:
            """Reject credential-bearing requests that did not arrive through HTTPS."""
            if not isinstance(self.connection, ssl.SSLSocket):
                raise PermissionError(f"Pairing credentials require HTTPS on port {HTTPS_PORT}.")

        def proxy_stream(self) -> None:
            """Relay the worker MJPEG stream while tolerating temporary worker loss."""
            try:
                with urllib.request.urlopen(WORKER_URL + "/stream", timeout=2) as response:
                    self.send_response(200)
                    self.send_header("Content-Type", response.headers.get("Content-Type", "multipart/x-mixed-replace; boundary=frame"))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    while True:
                        chunk = response.read(16384)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except (OSError, urllib.error.URLError, BrokenPipeError, ConnectionResetError):
                if not self.wfile.closed:
                    body = b"<svg xmlns='http://www.w3.org/2000/svg' width='640' height='480'><rect width='100%' height='100%' fill='%23050608'/><text x='50%' y='50%' fill='%23a6aec5' font-family='monospace' font-size='24' text-anchor='middle'>CAMERA OFFLINE</text></svg>"
                    try:
                        _send(self, 503, body, "image/svg+xml")
                    except OSError:
                        pass
    return Handler


class ControlServerGroup:
    """Own the HTTP and HTTPS control servers as one shutdown unit."""
    def __init__(self, servers: list[ThreadingHTTPServer]) -> None:
        self.servers = servers

    def shutdown(self) -> None:
        """Stop and close every managed control server."""
        for server in self.servers:
            server.shutdown()
            server.server_close()


def start_control_server(
    config_path: Path,
    host: str = "0.0.0.0",
    port: int = 8088,
    https_port: int = HTTPS_PORT,
    pairing_display: Callable[[str, str], None] | None = None,
    pairing_finished: Callable[[], None] | None = None,
) -> tuple[ControlServerGroup, ControlState]:
    """Start public diagnostics and protected setup servers and return their shared state."""
    state = ControlState(config_path, pairing_display, pairing_finished)
    server = ThreadingHTTPServer((host, port), make_handler(state))
    threading.Thread(target=server.serve_forever, name="control-web", daemon=True).start()
    servers = [server]
    try:
        tls_directory = config_path.parent / "tls"
        certificate = tls_directory / "pairing-cert.pem"
        private_key = tls_directory / "pairing-key.pem"
        if not certificate.exists() or not private_key.exists():
            hostname = socket.gethostname().split(".", 1)[0] + ".local"
            certificate, private_key, _pem = generate_certificate(tls_directory, hostname, days=3650)
        pem = certificate.read_text()
        state.configure_pairing_identity(certificate_identity(pem))
        secure_server = ThreadingHTTPServer((host, https_port), make_handler(state))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, private_key)
        secure_server.socket = context.wrap_socket(secure_server.socket, server_side=True)
        threading.Thread(target=secure_server.serve_forever, name="control-https", daemon=True).start()
        servers.append(secure_server)
    except (OSError, subprocess.CalledProcessError, ssl.SSLError) as exc:
        print(f"PowerGlove Vision: secure setup unavailable: {exc}", flush=True)
    return ControlServerGroup(servers), state
