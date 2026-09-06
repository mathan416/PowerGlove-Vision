# Project: PowerGlove Vision
# File: src/powerglove_vision/web_common.py
# Purpose: Render the shared page shell, profile options, and camera startup behavior.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-06 - Separate maintained web modules without changing rendered pages.

"""Render the shared page shell, profile options, and camera startup behavior."""

import html
from .play_game import PLAY_STYLE
from . import __version__

PROFILE_LABELS = (
    ("bad_street_brawler", "Bad Street Brawler"),
    ("super_glove_ball", "Super Glove Ball"),
    ("off", "Gestures off"),
    ("program_a", "A: Pinball"),
    ("program_b", "B: Joust"),
    ("program_c", "C: Gyruss"),
    ("program_d", "D: Challenge"),
    ("program_e", "E: Defender II"),
    ("program_f", "F: Sesame Street"),
    ("program_g", "G: Gun Smoke"),
    ("program_h", "H: General"),
    ("program_i", "I: Knight Rider"),
)


def _profile_options() -> str:
    """Render the shared profile list while preserving stable configuration IDs."""
    return "".join(
        f"<option value={profile}>{html.escape(label)}</option>"
        for profile, label in PROFILE_LABELS
    )


def _page(title: str, content: str, script: str) -> bytes:
    """Assemble a complete branded HTML page as UTF-8 bytes."""
    if title in ("Dashboard", "Rock Paper Scissors", "Glove Academy", "Setup", "Help"):
        introduction, separator, remainder = content.partition("</p>")
        if separator:
            content = (
                "<div class=pal-intro><div>" + introduction + separator + "</div>"
                "<img class=pixel-pal src=/help-assets/gestures/v2/pixel-pal-web.png "
                "alt='Pixel Pal waving hello' width=112 height=112></div>" + remainder
            )
    started = "<span id=app-started>Application last started: checking…</span>" if title in ("Glove Academy", "Setup") else ""
    metadata_script = """(()=>{const el=document.getElementById('app-started');async function refresh(){try{const r=await fetch('/status',{cache:'no-store'});if(!r.ok)throw Error();const s=await r.json();const b=s.build||{},f=s.firmware||{};const info=document.getElementById('build-identity');if(info){info.textContent='Software: '+(b.release||s.version||'unknown')+' · '+(b.commit||'commit unavailable')+(b.dirty?' · modified source':'')+' | Matrix firmware: '+(f.running||'unavailable — older firmware or bridge offline')+(f.state==='different'?' · update available':'');}if(!el)return;const date=new Date(s.app_started_at*1000);if(!s.app_started_at||isNaN(date.getTime()))throw Error();el.textContent='Application last started: '+new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'long'}).format(date);el.title='Application start time, shown in your browser time zone';}catch(e){if(el)el.textContent='Application last started: unavailable'}}refresh();setInterval(refresh,30000)})();"""
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<link rel="icon" type="image/vnd.microsoft.icon" sizes="16x16 32x32 48x48" href="/favicon.ico?v=faee57fda59e">
<link rel=apple-touch-icon sizes=180x180 href="/assets/apple-touch-icon.png?v=48a3ff7c60d3">
<title>{html.escape(title)} · PowerGlove Vision</title>
<style>
:root{{--ink:#f7f8ff;--muted:#a6aec5;--panel:#161a25;--line:#303748;--blue:#3d75ff;--cyan:#36dbe8;--red:#e64047;--green:#54e389}}
*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);font:16px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;background:#090b11 radial-gradient(circle at 75% 0,#182449 0,transparent 38%)}}
body{{min-height:100vh;display:flex;flex-direction:column}}main{{flex:1}}.app-footer{{width:min(1100px,calc(100% - 32px));margin:0 auto;padding:12px 0 20px;border-top:1px solid var(--line);color:var(--muted);font-size:12px;display:flex;flex-wrap:wrap;gap:8px 24px}}
header,main{{width:min(1100px,calc(100% - 32px));margin:auto}}header{{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:7px 0;border-bottom:2px solid var(--line)}}
.brand{{display:block;width:clamp(230px,30vw,300px);max-width:70%}}.brand img{{display:block;width:100%;height:auto}}nav a{{color:var(--ink);text-decoration:none;margin-left:18px}}nav a:hover{{color:var(--cyan)}}
main{{padding:16px 0 30px}}h1{{font:900 clamp(28px,5vw,42px)/1 system-ui;margin:0 0 6px;letter-spacing:-2px}}h2{{font:800 20px system-ui;margin:0 0 14px}}p.lead{{color:var(--muted);max-width:720px;margin:0 0 18px}}.dashboard-lead{{max-width:none!important;margin-bottom:14px!important}}
.pal-intro{{display:grid;grid-template-columns:minmax(0,1fr) 112px;gap:24px;align-items:center;margin-bottom:18px}}.pal-intro p.lead{{margin-bottom:0!important}}.pixel-pal{{display:block;width:112px;height:112px;object-fit:contain}}.pal-celebration{{width:180px;height:200px;margin:0 auto 12px}}#achievement button,#achievement .button{{display:inline-block;margin:6px 3px 0}}@media(max-width:600px){{.pal-intro{{display:block;position:relative}}.pal-intro h1{{padding-right:84px;min-height:72px;display:flex;align-items:center}}.pal-intro .pixel-pal{{position:absolute;right:0;top:0;width:72px;height:72px}}}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}.card{{background:linear-gradient(145deg,#1b2030,#11141d);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 16px 40px #0005}}
.status-grid{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}}.status-grid .card{{padding:12px;min-height:82px}}.status-grid .value{{font-size:17px}}
.label{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1.5px}}.value{{font:800 21px system-ui;margin-top:6px;overflow-wrap:anywhere}}.good{{color:var(--green)}}.warn{{color:#ffd75e}}.bad{{color:#ff6f75}}
.camera{{width:100%;aspect-ratio:4/3;object-fit:contain;background:#050608;border:1px solid var(--line);border-radius:14px;margin-top:14px}}
.dashboard-workspace{{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(430px,.95fr);gap:14px;align-items:start;margin-top:14px}}.dashboard-workspace .camera{{height:min(38vh,340px);aspect-ratio:auto;margin:0}}.dashboard-controls{{margin:10px 0 0}}
.camera-stage{{position:relative}}.camera-idle{{display:none;height:min(38vh,340px);align-items:center;justify-content:center;flex-direction:column;text-align:center;padding:30px;background:radial-gradient(circle,#17284b,#050608 62%);border:1px solid var(--line);border-radius:14px;color:var(--cyan);font:900 24px/1.25 system-ui}}.camera-idle small{{display:block;margin-top:10px;color:var(--muted);font:14px/1.45 ui-monospace,monospace}}.profile-select{{margin-top:6px;padding:7px 9px;font:800 15px system-ui}}
.diagnostic-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.diagnostic-grid .card{{padding:10px}}.diagnostic-grid h2{{font-size:15px;margin-bottom:6px}}.diagnostic-grid .label{{font-size:9px}}.diagnostic-grid .bits{{gap:5px;margin-top:6px}}.diagnostic-grid .bit{{padding:3px 5px;font-size:12px}}.diagnostic-grid .meter{{height:6px;margin-top:4px}}.diagnostic-grid .events{{height:110px}}
.controls{{display:flex;gap:10px;flex-wrap:wrap;margin:15px 0}}button,.button{{border:0;border-radius:8px;padding:12px 16px;background:var(--blue);color:white;font:800 15px system-ui;cursor:pointer;text-decoration:none}}button.secondary{{background:#272d3c}}button.danger{{background:var(--red)}}button:disabled{{opacity:.5;cursor:wait}}button:active,.button:active{{transform:translateY(2px);filter:brightness(.75)}}button:focus-visible,.button:focus-visible{{outline:3px solid #8edfff;outline-offset:3px}}button.danger:disabled{{opacity:1}}.dashboard-controls{{gap:8px}}.dashboard-controls button,.dashboard-controls .button{{padding:11px 12px;font-size:14px;white-space:nowrap}}
.meter{{height:8px;background:#080a10;border-radius:9px;margin-top:10px;overflow:hidden}}.meter i{{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--blue),var(--cyan));transition:width .15s}}
.bits{{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}}.bit{{padding:6px 9px;border:1px solid var(--line);border-radius:7px;color:var(--muted)}}.bit.on{{color:#081109;background:var(--green);border-color:var(--green)}}
.events{{height:170px;overflow:auto;background:#080a10;border-radius:9px;padding:12px;color:#c9d2ec;font-size:13px}}.events div{{padding:3px 0;border-bottom:1px solid #171b25}}
.learn-grid{{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(340px,.8fr);gap:14px;align-items:start}}.learn-camera{{position:relative}}.learn-camera .camera{{height:min(55vh,500px);aspect-ratio:auto;margin:0}}.practice-badge{{position:absolute;left:12px;top:12px;padding:7px 10px;border-radius:999px;background:#090b11dc;border:1px solid var(--green);color:var(--green);font-size:12px}}.lesson-number{{color:var(--cyan);font-size:12px;letter-spacing:1.5px;text-transform:uppercase}}.lesson-title{{font:900 clamp(26px,4vw,40px)/1.05 system-ui;margin:8px 0}}.lesson-cue{{color:var(--muted);min-height:72px}}.lesson-result{{border:1px solid var(--line);border-radius:10px;padding:12px;margin:14px 0;background:#090b11}}.lesson-result.ready{{border-color:var(--green);color:var(--green)}}.lesson-progress{{display:flex;gap:5px;margin:14px 0}}.lesson-progress i{{height:7px;flex:1;border-radius:9px;background:#303748}}.lesson-progress i.done{{background:var(--green)}}.lesson-progress i.current{{background:var(--cyan)}}.live-readout{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}}.live-readout>div{{padding:10px;border-radius:9px;background:#090b11;text-align:center}}.live-readout strong{{display:block;font:800 18px system-ui;margin-top:4px}}
header nav{{display:flex;flex-wrap:wrap;gap:10px 16px;justify-content:flex-end}}header nav a{{margin:0;min-height:44px;display:inline-flex;align-items:center}}main,.card,.learn-grid>*,.rps-layout>*,.pal-intro>*,.formgrid>*{{min-width:0}}p,label,.notice,.lesson-cue,.build-details{{overflow-wrap:anywhere}}button,.button,summary{{min-height:44px}}.build-details{{width:100%}}.advanced-tuning{{min-width:0;overflow-x:auto}}.build-details p{{font-size:12px}}.player-card{{margin:0 0 14px}}.player-card h2{{margin-top:0}}.player-row{{display:flex;align-items:end;flex-wrap:wrap;gap:10px}}.player-row label{{flex:1;min-width:150px}}.player-card details{{margin-top:12px}}.player-card .button{{display:inline-flex;align-items:center;cursor:pointer}}.controls{{flex-wrap:wrap}}input,select,textarea{{max-width:100%;min-width:0}}[hidden]{{display:none!important}}
@media(max-width:700px){{header{{flex-direction:column;align-items:flex-start;gap:4px}}.brand{{width:230px;max-width:85%}}header nav{{justify-content:flex-start;gap:0 14px;width:100%}}.learn-grid,.rps-layout{{grid-template-columns:minmax(0,1fr)!important}}.learn-camera .camera,.rps-camera .camera{{height:clamp(180px,28vh,280px)}}.pal-intro p.lead{{font-size:14px}}.formgrid{{grid-template-columns:minmax(0,1fr)}}.player-row>button{{flex:1}}.live-readout{{grid-template-columns:repeat(3,minmax(0,1fr))}}.live-readout strong{{font-size:15px}}.document-actions,.help-toolbar{{flex-wrap:wrap}}}}
{PLAY_STYLE}
form{{display:grid;gap:16px}}.formgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}}label{{display:grid;gap:7px;color:var(--muted);font-size:13px}}input,select{{width:100%;background:#090b11;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:12px;font:16px inherit}}input:focus,select:focus{{outline:2px solid var(--blue);border-color:transparent}}.check{{display:flex;align-items:center;gap:10px}}.check input{{width:auto}}.notice{{min-height:24px;color:var(--cyan)}}code{{color:var(--cyan)}}
details.advanced{{margin-top:18px;padding-top:14px;border-top:1px solid var(--line)}}details.advanced summary{{color:var(--cyan);cursor:pointer;font-weight:800}}details.advanced p{{color:var(--muted);max-width:760px}}.markdown-body details.extra-digit-answer{{margin-top:42px;padding:18px;border:2px solid #087ebd;border-radius:12px;background:#e7f7fc}}.markdown-body details.extra-digit-answer summary{{cursor:pointer;color:#075fc4;font-weight:800;font-size:18px}}.markdown-body details.extra-digit-answer h2{{margin-top:20px}}
.help-group{{margin-top:28px}}.help-group>h2{{margin-bottom:12px;color:var(--cyan)}}.guide-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}}
.guide-card{{position:relative;display:block;min-height:145px;padding:20px 52px 20px 20px;color:var(--ink);text-decoration:none;background:linear-gradient(145deg,#1b2030,#11141d);border:1px solid var(--line);border-radius:14px;transition:transform .15s,border-color .15s}}
.guide-card:hover{{transform:translateY(-2px);border-color:var(--cyan)}}.guide-card h2{{margin:0 0 8px}}.guide-card p{{margin:0;color:var(--muted)}}.guide-arrow{{position:absolute;right:20px;top:17px;color:var(--cyan);font-size:25px}}
.help-toolbar{{display:flex;justify-content:space-between;gap:16px;margin:0 0 14px}}.help-toolbar a{{color:var(--cyan);text-decoration:none}}.document-actions{{display:flex;gap:16px}}.help-layout{{display:grid;grid-template-columns:250px minmax(0,1fr);gap:18px;align-items:start}}
.help-sidebar{{position:sticky;top:12px;max-height:calc(100vh - 24px);overflow:auto;padding:16px;background:#11141d;border:1px solid var(--line);border-radius:12px}}.guide-nav,.toc{{display:grid;gap:2px;margin-top:8px}}.guide-nav a,.toc a{{padding:7px 9px;color:var(--muted);text-decoration:none;border-radius:7px;font-size:13px}}.guide-nav a:hover,.toc a:hover,.guide-nav a.current{{color:var(--ink);background:#202636}}.toc{{margin-top:18px;padding-top:14px;border-top:1px solid var(--line)}}.toc-level-3{{padding-left:20px!important}}
.markdown-body{{min-width:0;padding:clamp(20px,4vw,46px);background:#f8f9fc;color:#151927;border-radius:14px;font:16px/1.65 system-ui,sans-serif}}.markdown-body h1,.markdown-body h2,.markdown-body h3,.markdown-body h4{{color:#101522;scroll-margin-top:20px}}.markdown-body h1{{font-size:clamp(30px,5vw,46px);letter-spacing:-1.5px}}.markdown-body h2{{margin-top:38px;font-size:27px;border-bottom:2px solid #d9dfeb;padding-bottom:7px}}.markdown-body h3{{margin-top:28px;font-size:21px}}.markdown-body a{{color:#075fc4}}.markdown-body code{{color:#005dc7;background:#e9eef7;border-radius:4px;padding:2px 5px}}.markdown-body td code{{overflow-wrap:anywhere}}.markdown-body pre{{overflow:auto;padding:16px;background:#0b1220;border-left:4px solid var(--cyan);border-radius:8px}}.markdown-body pre code{{padding:0;color:#eaf2ff;background:none}}.markdown-body blockquote{{margin:20px 0;padding:14px 18px;border-left:5px solid #0b78d1;background:#e9f4fd}}.markdown-body ul,.markdown-body ol{{margin:16px 0 20px;padding-left:1.75rem}}.markdown-body li{{margin:7px 0;padding-left:.3rem}}.markdown-body li::marker{{color:#087ebd;font-weight:800}}.markdown-body ol li::marker{{color:#d51f42}}.markdown-body img{{display:block;max-width:100%;height:auto;margin:22px auto;border-radius:9px}}.table-scroll{{overflow-x:auto;margin:18px 0}}.markdown-body table{{width:100%;border-collapse:collapse;font-size:14px}}.markdown-body table.network-exposure{{table-layout:fixed;min-width:650px}}.markdown-body .network-exposure th:nth-child(1){{width:92px}}.markdown-body .network-exposure th:nth-child(2){{width:92px}}.markdown-body .network-exposure th:nth-child(3){{width:34%}}.markdown-body .network-exposure td:first-child code{{white-space:nowrap;overflow-wrap:normal}}.markdown-body table.reproducible-inputs{{table-layout:fixed;min-width:700px}}.markdown-body .reproducible-inputs th:nth-child(1){{width:20%}}.markdown-body .reproducible-inputs th:nth-child(2){{width:35%}}.markdown-body .reproducible-inputs th:nth-child(3){{width:45%}}.markdown-body .reproducible-inputs td{{overflow-wrap:anywhere}}.markdown-body table.rom-input-audit{{table-layout:fixed;min-width:700px}}.markdown-body .rom-input-audit th:nth-child(1){{width:20%}}.markdown-body .rom-input-audit th:nth-child(2){{width:23%}}.markdown-body .rom-input-audit th:nth-child(3){{width:39%}}.markdown-body .rom-input-audit th:nth-child(4){{width:18%}}.markdown-body .rom-input-audit td{{overflow-wrap:anywhere}}.markdown-body table.program-starters{{table-layout:fixed;min-width:760px}}.markdown-body table.program-starters th:nth-child(1){{width:16%}}.markdown-body table.program-starters th:nth-child(2){{width:31%}}.markdown-body table.program-starters th:nth-child(3),.markdown-body table.program-starters th:nth-child(4){{width:26.5%}}.markdown-body th{{background:#101827;color:white;text-align:left}}.markdown-body th,.markdown-body td{{padding:10px 12px;border:1px solid #cbd3e2;vertical-align:top}}.markdown-body th.art-column{{text-align:center}}.markdown-body td.art-cell{{text-align:center;vertical-align:middle}}.markdown-body td.art-cell img{{margin:0 auto}}.markdown-body tr:nth-child(even) td{{background:#eef2f8}}
@media(max-width:900px){{.status-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.dashboard-workspace,.learn-grid,.rps-layout{{grid-template-columns:1fr}}.dashboard-workspace .camera,.learn-camera .camera,.rps-camera .camera{{height:auto;aspect-ratio:4/3}}}}
@media(max-width:900px){{.help-layout{{grid-template-columns:1fr}}.help-sidebar{{position:static;max-height:none}}.guide-nav{{grid-template-columns:repeat(2,minmax(0,1fr))}}.toc{{display:none}}}}
@media(max-width:600px){{header{{align-items:center}}.brand{{max-width:58%}}nav{{display:grid;grid-template-columns:repeat(2,auto);gap:5px 12px}}nav a{{margin:0}}.diagnostic-grid{{grid-template-columns:1fr}}.guide-nav{{grid-template-columns:1fr}}.markdown-body{{padding:20px 17px}}}}
</style></head><body><header><a class=brand href=/dashboard aria-label='PowerGlove Vision dashboard'><img src=/assets/powerglove-vision-logo.png alt='PowerGlove Vision'></a><nav><a href=/dashboard>Dashboard</a><a href=/play>Play</a><a href=/learn>Glove Academy</a><a href=/help>Help</a><a href="/setup">Setup</a></nav></header><main>{content}</main><footer class=app-footer><span>PowerGlove Vision v{html.escape(__version__)}</span>{started}<details class=build-details><summary>Software and matrix firmware</summary><p id=build-identity>Checking installed versions…</p></details></footer><script>{metadata_script}</script><script>{script}</script></body></html>""".encode()


VISION_STARTUP_SCRIPT = r"""
let startupObservedAt=null;
function startupMessage(s){
 if(s.vision_state!=='starting'){startupObservedAt=null;return ''}
 if(startupObservedAt===null)startupObservedAt=Date.now();
 const since=Number(s.vision_started_at)*1000||startupObservedAt;
 const seconds=Math.max(0,Math.floor((Date.now()-since)/1000));
 return `Starting camera and gesture tracking… First startup can take longer. ${seconds}s elapsed.`;
}
"""
