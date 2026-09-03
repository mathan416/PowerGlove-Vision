# Project: PowerGlove Vision
# File: python/main.py
# Purpose: Supervise the UNO Q App Lab vision worker, web controls, model retrieval, and camera recovery.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
#   2026-09-03 - Delegated idle and active vision lifecycle to the persistent worker.
#   2026-09-03 - Displayed a dedicated matrix state during Learn sessions.
#   2026-09-03 - Support an unconfigured first-run receiver without blocking local practice.
# Full history: docs/CHANGELOG.md and Git history.

"""Arduino App Lab entry point for PowerGlove Vision."""

from __future__ import annotations

import json
import os
import secrets
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = APP_ROOT / "data" / "device.json"
sys.path.insert(0, str(APP_ROOT / "src"))

def _shutdown_on_signal(_signum: int, _frame: object) -> None:
    """Convert process termination into the supervisor's normal cleanup path."""
    raise KeyboardInterrupt


def load_device_config() -> dict:
    """Load persistent device settings, creating safe first-run defaults when absent."""
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    # A useful, portable first-run default. The same token must be copied to
    # the RetroPie receiver before controller packets will be accepted.
    settings = {
        "receiver": "",
        "token": secrets.token_urlsafe(24),
        "profile": "bad_street_brawler",
        "glove_color": "none",
        "camera": "auto",
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(settings, indent=2) + "\n")
    return settings


def worker_command(settings: dict, model_path: Path, controller_enabled: bool = False) -> list[str]:
    """Build the isolated MediaPipe worker command from validated runtime settings."""
    wheel = next((APP_ROOT / "python" / "worker-wheels").glob("mediapipe-0.10.18-*.whl"))
    command = [
        # The repository supports the RetroPie receiver on Python 3.7, while
        # MediaPipe requires a newer interpreter. Keep the worker resolution
        # independent of project-wide Python compatibility metadata.
        "uv", "run", "--no-project", "--python", "3.12", "--with", str(wheel),
        "python", "-m", "powerglove_vision.vision_app",
        "--receiver", str(settings.get("receiver", "")),
        "--port", str(settings.get("port", 55355)),
        "--token", str(settings["token"]),
        "--profile", str(settings.get("profile", "bad_street_brawler")),
        "--glove-color", str(settings.get("glove_color", "none")),
        "--camera", str(settings.get("camera", "auto")),
        "--model", str(model_path),
        "--web-host", "127.0.0.1", "--web-port", "8089", "--no-matrix",
    ]
    if controller_enabled:
        command.append("--controller-enabled")
    return command


def main() -> int:
    """Supervise the worker, control server, matrix, camera availability, and clean shutdown."""
    settings = load_device_config()
    from powerglove_vision.matrix import MatrixStatus, UnoQMatrix, status_from_worker
    matrix = UnoQMatrix()
    from powerglove_vision.control_server import start_control_server
    control_server, control = start_control_server(CONFIG_PATH, pairing_display=matrix.show_pairing)
    matrix.set_status(MatrixStatus.LOADING)
    matrix.set_profile(str(settings.get("profile", "bad_street_brawler")))

    environment = dict(os.environ)
    # App Lab uses a bootstrap virtual environment. The vision worker manages
    # its own Python runtime with uv, so inheriting this emits a false warning.
    environment.pop("VIRTUAL_ENV", None)
    environment.update({
        "PYTHONPATH": str(APP_ROOT / "src"),
        "UV_CACHE_DIR": str(APP_ROOT / "data" / "uv-cache"),
        "UV_PYTHON_INSTALL_DIR": str(APP_ROOT / "data" / "uv-python"),
    })

    process: subprocess.Popen | None = None
    model_path = APP_ROOT / "data" / "models" / "hand_landmarker.task"
    signal.signal(signal.SIGTERM, _shutdown_on_signal)
    try:
        # The worker keeps its lightweight control plane alive while gestures
        # are paused and owns lazy camera/model activation for active profiles.
        while True:
            settings = load_device_config()
            matrix.set_profile(str(settings.get("profile", "bad_street_brawler")))
            matrix.set_status(MatrixStatus.LOADING)
            revision = control.revision
            process = subprocess.Popen(
                worker_command(settings, model_path, control.controller_enabled()), cwd=APP_ROOT, env=environment
            )
            control.update_supervisor(camera=False, running=True)
            configuration_changed = False
            while process.poll() is None:
                if revision != control.revision:
                    configuration_changed = True
                    process.terminate()
                    try:
                        process.wait(timeout=7)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    break
                try:
                    with urllib.request.urlopen("http://127.0.0.1:8089/status", timeout=0.3) as response:
                        status = json.load(response)
                    control.update_worker(status)
                    active_profile = status.get("active_profile")
                    matrix.set_profile(
                        None if status.get("practice_mode") or active_profile == "off"
                        else active_profile
                    )
                    matrix.set_status(status_from_worker(status))
                except (OSError, ValueError, TimeoutError):
                    pass
                time.sleep(0.25)
            process = None
            if configuration_changed:
                matrix.set_status(MatrixStatus.LOADING)
                control.update_supervisor(camera=False, running=False)
                continue
            matrix.set_status(MatrixStatus.ERROR)
            control.update_supervisor(camera=False, running=False, error="Vision worker stopped; retrying")
            time.sleep(5)
    except KeyboardInterrupt:
        matrix.set_status(MatrixStatus.OFF)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=7)
            except subprocess.TimeoutExpired:
                process.kill()
        return 0
    finally:
        control_server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
