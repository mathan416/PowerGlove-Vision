# Copyright (c) 2026 Iain Bennett. All rights reserved.
from __future__ import annotations

import html
import json
import os
import secrets
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


WORKER_URL = "http://127.0.0.1:8089"
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "powerglove-vision-logo.png"
PROFILES = {
    "bad_street_brawler", "super_glove_ball", "off",
    *(f"program_{letter}" for letter in "abcdefghi"),
}


def _page(title: str, content: str, script: str) -> bytes:
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>{html.escape(title)} · PowerGlove Vision</title>
<style>
:root{{--ink:#f7f8ff;--muted:#a6aec5;--panel:#161a25;--line:#303748;--blue:#3d75ff;--cyan:#36dbe8;--red:#e64047;--green:#54e389}}
*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);font:16px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;background:#090b11 radial-gradient(circle at 75% 0,#182449 0,transparent 38%)}}
header,main{{width:min(1100px,calc(100% - 32px));margin:auto}}header{{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:16px 0 12px;border-bottom:2px solid var(--line)}}
.brand{{display:block;width:clamp(230px,38vw,410px);max-width:70%}}.brand img{{display:block;width:100%;height:auto}}nav a{{color:var(--ink);text-decoration:none;margin-left:18px}}nav a:hover{{color:var(--cyan)}}
main{{padding:26px 0 50px}}h1{{font:900 clamp(28px,6vw,54px)/1 system-ui;margin:0 0 8px;letter-spacing:-2px}}h2{{font:800 20px system-ui;margin:0 0 14px}}p.lead{{color:var(--muted);max-width:720px;margin:0 0 26px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}.card{{background:linear-gradient(145deg,#1b2030,#11141d);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 16px 40px #0005}}
.label{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1.5px}}.value{{font:800 21px system-ui;margin-top:6px;overflow-wrap:anywhere}}.good{{color:var(--green)}}.warn{{color:#ffd75e}}.bad{{color:#ff6f75}}
.camera{{width:100%;aspect-ratio:4/3;object-fit:contain;background:#050608;border:1px solid var(--line);border-radius:14px;margin-top:14px}}
.controls{{display:flex;gap:10px;flex-wrap:wrap;margin:15px 0}}button,.button{{border:0;border-radius:8px;padding:12px 16px;background:var(--blue);color:white;font:800 15px system-ui;cursor:pointer;text-decoration:none}}button.secondary{{background:#272d3c}}button.danger{{background:var(--red)}}button:disabled{{opacity:.5;cursor:wait}}
.meter{{height:8px;background:#080a10;border-radius:9px;margin-top:10px;overflow:hidden}}.meter i{{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--blue),var(--cyan));transition:width .15s}}
.bits{{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}}.bit{{padding:6px 9px;border:1px solid var(--line);border-radius:7px;color:var(--muted)}}.bit.on{{color:#081109;background:var(--green);border-color:var(--green)}}
.events{{height:170px;overflow:auto;background:#080a10;border-radius:9px;padding:12px;color:#c9d2ec;font-size:13px}}.events div{{padding:3px 0;border-bottom:1px solid #171b25}}
form{{display:grid;gap:16px}}.formgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}}label{{display:grid;gap:7px;color:var(--muted);font-size:13px}}input,select{{width:100%;background:#090b11;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:12px;font:16px inherit}}input:focus,select:focus{{outline:2px solid var(--blue);border-color:transparent}}.check{{display:flex;align-items:center;gap:10px}}.check input{{width:auto}}.notice{{min-height:24px;color:var(--cyan)}}code{{color:var(--cyan)}}
@media(max-width:600px){{header{{align-items:center}}.brand{{max-width:68%}}nav{{display:grid;gap:7px}}nav a{{margin:0}}}}
</style></head><body><header><a class=brand href=/debug aria-label='PowerGlove Vision dashboard'><img src=/assets/powerglove-vision-logo.png alt='PowerGlove Vision'></a><nav><a href=/debug>Dashboard</a><a href=/setup>Setup</a></nav></header><main>{content}</main><script>{script}</script></body></html>""".encode()


DASHBOARD = _page(
    "Dashboard",
    """<h1>It's so bad.</h1><p class=lead>Live vision, gesture and controller diagnostics from your camera-only Power Glove.</p>
<div class=grid>
 <div class=card><div class=label>System</div><div class=value id=system>Starting</div></div>
 <div class=card><div class=label>Active profile</div><div class=value id=profile>—</div></div>
 <div class=card><div class=label>Game</div><div class=value id=game>—</div></div>
 <div class=card><div class=label>Hand tracking</div><div class=value id=tracking>—</div><div class=meter><i id=confidence></i></div></div>
</div>
<img class=camera src=/stream alt='Live camera view'>
<div class=controls><button id=center>Center hand</button><a class=button href=/setup>Connection setup</a></div>
<div class=grid>
 <section class=card><h2>Controller output</h2><div class=label>Directions</div><div class=bits id=dpad></div><div class=label style='margin-top:14px'>Buttons</div><div class=bits id=buttons></div></section>
 <section class=card><h2>Axes</h2><div id=axes></div></section>
 <section class=card><h2>Finger curl</h2><div id=fingers></div></section>
 <section class=card><h2>Recent events</h2><div class=events id=events><div>Waiting for tracker…</div></div></section>
</div>""",
    r"""const $=id=>document.getElementById(id), names={bad_street_brawler:'Bad Street Brawler',super_glove_ball:'Super Glove Ball',off:'Off'};
const pretty=p=>names[p]||(p&&p.startsWith('program_')?'Program '+p.slice(-1).toUpperCase():p||'—');
const bits=(id,obj)=>{$(id).innerHTML=Object.entries(obj||{}).map(([k,v])=>`<span class="bit ${v?'on':''}">${k.toUpperCase()}</span>`).join('')||'<span class=bit>None</span>'};
const bars=(id,obj,max=32767)=>{$(id).innerHTML=Object.entries(obj||{}).map(([k,v])=>`<div class=label>${k}: ${v}</div><div class=meter><i style="width:${Math.min(100,Math.abs(v)/max*100)}%"></i></div>`).join('')||'—'};
let seen=[]; async function update(){try{const s=await(await fetch('/status',{cache:'no-store'})).json();
$('system').textContent=s.worker_running?(s.detected?'Tracking':'Ready'):(s.camera_available?'Starting tracker':'Camera not found'); $('system').className='value '+(s.worker_running?'good':'warn');
$('profile').textContent=pretty(s.active_profile||s.configured_profile); $('game').textContent=s.game||'Startup default';
$('tracking').textContent=s.calibrating?'Centering — hold still':(s.detected?`${Math.round((s.confidence||0)*100)}% confidence`:'Show your hand'); $('confidence').style.width=`${Math.round((s.confidence||0)*100)}%`;
bits('dpad',s.dpad);bits('buttons',s.buttons);bars('axes',s.axes);bars('fingers',s.fingers,2);
for(const event of (s.events||[])) seen.unshift(`${new Date().toLocaleTimeString()}  ${event}`);seen=seen.slice(0,30);if(seen.length)$('events').innerHTML=seen.map(x=>`<div>${x}</div>`).join('');
}catch(e){$('system').textContent='Dashboard disconnected';$('system').className='value bad'}} setInterval(update,250);update();
$('center').onclick=async()=>{await fetch('/calibrate',{method:'POST'});};""",
)


SETUP = _page(
    "Setup",
    """<h1>Let's get connected.</h1><p class=lead>Tell PowerGlove Vision where your RetroPie console lives. Settings are saved on this UNO Q and the private pairing token is never shown.</p>
<section class=card><form id=form><div class=formgrid>
<label>RetroPie console name<input id=receiver name=receiver required placeholder=retropieconsole.local></label>
<label>Controller port<input id=port name=port type=number min=1 max=65535 required></label>
<label>Startup profile<select id=profile name=profile><option value=bad_street_brawler>Bad Street Brawler</option><option value=super_glove_ball>Super Glove Ball</option><option value=off>Gestures off</option><optgroup label='Power Glove programs A–I'>""" + "".join(f"<option value=program_{x.lower()}>Program {x}</option>" for x in "ABCDEFGHI") + """</optgroup></select></label>
<label>Tracking aid<select id=glove_color name=glove_color><option value=none>Bare hand</option><option value=white>White glove</option><option value=black>Black glove</option></select></label>
<label>Camera<input id=camera name=camera placeholder=auto></label></div>
<label class=check><input id=rotate_token type=checkbox> Generate a new private pairing token</label>
<div class=controls><button type=submit>Save & restart tracker</button><button class=secondary type=button id=test>Test console name</button></div><div class=notice id=notice></div></form></section>
<div class=grid style='margin-top:14px'><div class=card><div class=label>Pairing</div><div class=value id=paired>Checking…</div><p>Your matching token remains in <code>data/device.json</code> and must also be installed at <code>/etc/powerglove/token</code> on RetroPie.</p></div><div class=card><div class=label>Address</div><div class=value><code>/setup</code></div><p>Bookmark this page at your UNO Q's <code>.local:8088</code> address.</p></div></div>""",
    r"""const $=id=>document.getElementById(id);async function load(){const c=await(await fetch('/api/config')).json();for(const k of ['receiver','port','profile','glove_color','camera'])$(k).value=c[k];$('paired').textContent=c.paired?'Private token configured':'Not paired'}load();
$('form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;$('notice').textContent='Saving…';const payload={receiver:$('receiver').value.trim(),port:Number($('port').value),profile:$('profile').value,glove_color:$('glove_color').value,camera:$('camera').value.trim(),rotate_token:$('rotate_token').checked};const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const x=await r.json();$('notice').textContent=r.ok?'Saved. The tracker is restarting with the new settings.':x.error||'Could not save.';$('rotate_token').checked=false;b.disabled=false;load()};
$('test').onclick=async()=>{$('notice').textContent='Testing name…';const r=await fetch('/api/test-connection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({receiver:$('receiver').value.trim()})});const x=await r.json();$('notice').textContent=x.ok?`Found ${x.receiver} at ${x.address}. UDP controller delivery can now be attempted.`:x.error};""",
)


class ControlState:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.lock = threading.Lock()
        self.revision = 0
        self.worker_status: dict[str, Any] = {}
        self.camera_available = False
        self.worker_running = False
        self.last_error: str | None = None
        self.started_at = time.time()

    def load_config(self) -> dict[str, Any]:
        return json.loads(self.config_path.read_text())

    def public_config(self) -> dict[str, Any]:
        config = self.load_config()
        return {
            "receiver": config.get("receiver", "retropieconsole.local"),
            "port": int(config.get("port", 55355)),
            "profile": config.get("profile", "bad_street_brawler"),
            "glove_color": config.get("glove_color", "none"),
            "camera": str(config.get("camera", "auto")),
            "paired": bool(config.get("token")),
        }

    def save_config(self, incoming: dict[str, Any]) -> dict[str, Any]:
        receiver = str(incoming.get("receiver", "")).strip()
        if not receiver or len(receiver) > 253 or any(ch.isspace() for ch in receiver):
            raise ValueError("Enter a valid console hostname or IP address.")
        try:
            port = int(incoming.get("port", 55355))
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
        token = secrets.token_urlsafe(24) if incoming.get("rotate_token") else current.get("token")
        if not token:
            token = secrets.token_urlsafe(24)
        saved = {"receiver": receiver, "port": port, "token": token, "profile": profile, "glove_color": glove_color, "camera": camera}
        temporary = self.config_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(saved, indent=2) + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.config_path)
        with self.lock:
            self.revision += 1
        return self.public_config()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            status = dict(self.worker_status)
            status.update({
                "camera_available": self.camera_available,
                "worker_running": self.worker_running,
                "last_error": self.last_error,
                "uptime_seconds": round(time.time() - self.started_at),
            })
        status.setdefault("configured_profile", self.public_config()["profile"])
        return status

    def update_supervisor(self, *, camera: bool, running: bool, error: str | None = None) -> None:
        with self.lock:
            self.camera_available = camera
            self.worker_running = running
            self.last_error = error
            if not running:
                self.worker_status = {}

    def update_worker(self, status: dict[str, Any]) -> None:
        status.pop("token", None)
        with self.lock:
            self.worker_status = status
            self.worker_running = True
            self.last_error = None


def _send(handler: BaseHTTPRequestHandler, status: int, body: bytes, content_type: str) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(state: ControlState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 8192:
                raise ValueError("Request is too large.")
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/":
                self.send_response(302); self.send_header("Location", "/debug"); self.end_headers()
            elif path == "/debug":
                _send(self, 200, DASHBOARD, "text/html; charset=utf-8")
            elif path == "/setup":
                _send(self, 200, SETUP, "text/html; charset=utf-8")
            elif path == "/assets/powerglove-vision-logo.png":
                try:
                    _send(self, 200, LOGO_PATH.read_bytes(), "image/png")
                except OSError:
                    self.send_error(404)
            elif path == "/status":
                _send(self, 200, json.dumps(state.snapshot()).encode(), "application/json")
            elif path == "/api/config":
                _send(self, 200, json.dumps(state.public_config()).encode(), "application/json")
            elif path == "/stream":
                self.proxy_stream()
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            try:
                if path == "/api/config":
                    result = state.save_config(self.json_body())
                    _send(self, 200, json.dumps(result).encode(), "application/json")
                elif path == "/api/test-connection":
                    receiver = str(self.json_body().get("receiver", "")).strip()
                    address = socket.getaddrinfo(receiver, None, type=socket.SOCK_DGRAM)[0][4][0]
                    _send(self, 200, json.dumps({"ok": True, "receiver": receiver, "address": address}).encode(), "application/json")
                elif path == "/calibrate":
                    request = urllib.request.Request(WORKER_URL + "/calibrate", method="POST", data=b"")
                    with urllib.request.urlopen(request, timeout=1):
                        pass
                    _send(self, 204, b"", "text/plain")
                else:
                    self.send_error(404)
            except (ValueError, json.JSONDecodeError) as exc:
                _send(self, 400, json.dumps({"error": str(exc)}).encode(), "application/json")
            except (OSError, urllib.error.URLError) as exc:
                _send(self, 503, json.dumps({"error": f"Not reachable: {exc}"}).encode(), "application/json")

        def proxy_stream(self) -> None:
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


def start_control_server(config_path: Path, host: str = "0.0.0.0", port: int = 8088) -> tuple[ThreadingHTTPServer, ControlState]:
    state = ControlState(config_path)
    server = ThreadingHTTPServer((host, port), make_handler(state))
    threading.Thread(target=server.serve_forever, name="control-web", daemon=True).start()
    return server, state
