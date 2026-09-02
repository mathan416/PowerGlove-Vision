"""Arduino App Lab entry point for PowerGlove Vision."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = APP_ROOT / "data" / "device.json"
sys.path.insert(0, str(APP_ROOT / "src"))


def load_device_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    # A useful, portable first-run default. The same token must be copied to
    # the RetroPie receiver before controller packets will be accepted.
    settings = {
        "receiver": "retropieconsole.local",
        "token": secrets.token_urlsafe(24),
        "profile": "bad_street_brawler",
        "glove_color": "none",
        "camera": "auto",
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(settings, indent=2) + "\n")
    return settings


def main() -> int:
    settings = load_device_config()
    from powerglove_vision.matrix import MatrixStatus, UnoQMatrix
    matrix = UnoQMatrix()
    matrix.set_status(MatrixStatus.LOADING)
    matrix.set_profile(str(settings.get("profile", "bad_street_brawler")))

    wheel = next((APP_ROOT / "python" / "worker-wheels").glob("mediapipe-0.10.18-*.whl"))
    command = [
        "uv", "run", "--python", "3.12", "--with", str(wheel),
        "python", "-m", "powerglove_vision.vision_app",
        "--receiver", str(settings["receiver"]),
        "--port", str(settings.get("port", 55355)),
        "--token", str(settings["token"]),
        "--profile", str(settings.get("profile", "bad_street_brawler")),
        "--glove-color", str(settings.get("glove_color", "none")),
        "--camera", str(settings.get("camera", "auto")),
        "--no-matrix",
    ]
    environment = dict(os.environ)
    environment.update({
        "PYTHONPATH": str(APP_ROOT / "src"),
        "UV_CACHE_DIR": str(APP_ROOT / "data" / "uv-cache"),
        "UV_PYTHON_INSTALL_DIR": str(APP_ROOT / "data" / "uv-python"),
    })

    # Keep App Lab alive without a camera. The worker is retried so plugging a
    # UVC camera in later is enough; no reboot or terminal command is needed.
    while True:
        if not list(Path("/dev/v4l/by-id").glob("*-video-index0")):
            matrix.set_status(MatrixStatus.ERROR)
            time.sleep(2)
            continue
        matrix.set_status(MatrixStatus.LOADING)
        process = subprocess.Popen(command, cwd=APP_ROOT, env=environment)
        while process.poll() is None:
            try:
                with urllib.request.urlopen("http://127.0.0.1:8088/status", timeout=0.3) as response:
                    status = json.load(response)
                active_profile = status.get("active_profile")
                matrix.set_profile(None if active_profile == "off" else active_profile)
                matrix.set_status(
                    MatrixStatus.TRACKING
                    if status.get("detected") and status.get("calibrated")
                    else MatrixStatus.READY
                )
            except (OSError, ValueError, TimeoutError):
                pass
            time.sleep(0.25)
        matrix.set_status(MatrixStatus.ERROR)
        time.sleep(5)


if __name__ == "__main__":
    raise SystemExit(main())
