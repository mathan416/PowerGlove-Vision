# Project: PowerGlove Vision
# File: src/powerglove_vision/debug_server.py
# Purpose: Expose live worker status, camera frames, calibration, and controller state to the supervisor.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Expose live worker status, camera frames, calibration, and controller state to the supervisor."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable


PAGE = b"""<!doctype html>
<html><head><meta name=viewport content='width=device-width,initial-scale=1'>
<title>PowerGlove Vision</title>
<style>body{font:16px system-ui;background:#10131a;color:#eef;margin:24px auto;padding:0 18px;max-width:1000px}
img{width:100%;background:#000;border-radius:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:14px 0}
.card{background:#1b2130;padding:13px;border-radius:9px}.label{color:#9ca9c7;font-size:12px;text-transform:uppercase}.value{font-size:19px;margin-top:3px}
button{font-size:18px;padding:12px 20px;border:0;border-radius:8px;background:#287cff;color:white}</style></head>
<body><h1>PowerGlove Vision</h1><div class=grid>
<div class=card><div class=label>Game</div><div class=value id=game>Waiting...</div></div>
<div class=card><div class=label>Gesture profile</div><div class=value id=profile>Waiting...</div></div>
<div class=card><div class=label>Hand tracking</div><div class=value id=tracking>Waiting...</div></div>
<div class=card><div class=label>Selected by</div><div class=value id=source>Waiting...</div></div>
</div><img src=/stream><p><button onclick="fetch('/calibrate',{method:'POST'})">Center hand</button></p>
<script>
const names={bad_street_brawler:'Bad Street Brawler',super_glove_ball:'Super Glove Ball',off:'Off'};
function profileName(p){if(names[p])return names[p];if(p&&p.startsWith('program_'))return 'Program '+p.slice(-1).toUpperCase();return p||'Off'}
setInterval(async()=>{try{const s=await(await fetch('/status')).json();
game.textContent=s.game||'No game';profile.textContent=profileName(s.active_profile);
tracking.textContent=s.calibrating?'Centering - hold still':(s.detected?'Ready and tracking':'Show your hand');
source.textContent=s.profile_source||'Startup';}catch(e){}},250)</script></body></html>"""


class SharedDebugState:
    """Share the latest frame, diagnostics, and one-shot operator requests across threads."""
    def __init__(self, controller_enabled: bool = False) -> None:
        self.lock = threading.Lock()
        self.jpeg: bytes | None = None
        self.status: dict = {}
        self.calibrate_requested = False
        self.controller_enabled = controller_enabled
        self.controller_request: bool | None = None

    def update(self, jpeg: bytes, status: dict) -> None:
        """Atomically replace the current JPEG frame and worker status."""
        with self.lock:
            self.jpeg = jpeg
            self.status = status

    def request_calibration(self) -> None:
        """Queue one hand-centering request."""
        with self.lock:
            self.calibrate_requested = True

    def take_calibration_request(self) -> bool:
        """Consume and clear the pending calibration request."""
        with self.lock:
            requested = self.calibrate_requested
            self.calibrate_requested = False
            return requested

    def request_controller(self, enabled: bool) -> None:
        """Queue the requested controller transmission state."""
        with self.lock:
            self.controller_request = enabled

    def take_controller_request(self) -> bool | None:
        """Consume and clear a pending controller state change."""
        with self.lock:
            requested = self.controller_request
            self.controller_request = None
            return requested


def make_handler(shared: SharedDebugState) -> type[BaseHTTPRequestHandler]:
    """Build a local diagnostics handler bound to the supplied shared state."""
    class Handler(BaseHTTPRequestHandler):
        """Serve the worker status, MJPEG stream, and one-shot control requests."""
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def do_GET(self) -> None:
            if self.path == "/":
                self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(PAGE)
            elif self.path == "/status":
                with shared.lock:
                    body = json.dumps(shared.status, indent=2).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
            elif self.path == "/stream":
                self.send_response(200); self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame"); self.end_headers()
                try:
                    while True:
                        with shared.lock:
                            jpeg = shared.jpeg
                        if jpeg:
                            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
                        threading.Event().wait(0.05)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path == "/calibrate":
                shared.request_calibration()
                self.send_response(204); self.end_headers()
            elif self.path == "/controller":
                try:
                    length = min(int(self.headers.get("Content-Length", "0")), 1024)
                    body = json.loads(self.rfile.read(length) or b"{}")
                    enabled = body.get("enabled")
                    if not isinstance(enabled, bool):
                        raise ValueError("enabled must be true or false")
                    shared.request_controller(enabled)
                    response = json.dumps({"controller_enabled": enabled}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                except (ValueError, json.JSONDecodeError) as exc:
                    response = json.dumps({"error": str(exc)}).encode()
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
            else:
                self.send_error(404)
    return Handler


def start_debug_server(shared: SharedDebugState, host: str, port: int) -> ThreadingHTTPServer:
    """Start the worker diagnostics server in a daemon thread."""
    server = ThreadingHTTPServer((host, port), make_handler(shared))
    threading.Thread(target=server.serve_forever, name="debug-web", daemon=True).start()
    return server
