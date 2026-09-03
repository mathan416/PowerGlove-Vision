# Project: PowerGlove Vision
# File: src/powerglove_vision/control_server.py
# Purpose: Serve the UNO Q dashboard, setup, pairing, controller controls, and guarded shutdown request.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-02 - Added to PowerGlove Vision.
#   2026-09-03 - Standardized source documentation and maintenance metadata.
# Full history: docs/CHANGELOG.md and Git history.

"""Serve the UNO Q dashboard, setup, pairing, controller controls, and guarded shutdown request."""

from __future__ import annotations

import html
import json
import os
import secrets
import socket
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .pairing import PAIRING_PORT, certificate_identity, generate_certificate, pair_over_ssh, pair_with_code


WORKER_URL = "http://127.0.0.1:8089"
HTTPS_PORT = 8443
LOGO_PATH = Path(__file__).resolve().parents[2] / "assets" / "powerglove-vision-logo.png"
PROFILES = {
    "bad_street_brawler", "super_glove_ball", "off",
    *(f"program_{letter}" for letter in "abcdefghi"),
}


class ForbiddenActionError(Exception):
    """Raised when a sensitive browser action lacks its CSRF safeguard."""


def _page(title: str, content: str, script: str) -> bytes:
    """Assemble a complete branded HTML page as UTF-8 bytes."""
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<title>{html.escape(title)} · PowerGlove Vision</title>
<style>
:root{{--ink:#f7f8ff;--muted:#a6aec5;--panel:#161a25;--line:#303748;--blue:#3d75ff;--cyan:#36dbe8;--red:#e64047;--green:#54e389}}
*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);font:16px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;background:#090b11 radial-gradient(circle at 75% 0,#182449 0,transparent 38%)}}
header,main{{width:min(1100px,calc(100% - 32px));margin:auto}}header{{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:7px 0;border-bottom:2px solid var(--line)}}
.brand{{display:block;width:clamp(230px,30vw,300px);max-width:70%}}.brand img{{display:block;width:100%;height:auto}}nav a{{color:var(--ink);text-decoration:none;margin-left:18px}}nav a:hover{{color:var(--cyan)}}
main{{padding:16px 0 30px}}h1{{font:900 clamp(28px,5vw,42px)/1 system-ui;margin:0 0 6px;letter-spacing:-2px}}h2{{font:800 20px system-ui;margin:0 0 14px}}p.lead{{color:var(--muted);max-width:720px;margin:0 0 18px}}.dashboard-lead{{max-width:none!important;margin-bottom:14px!important}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}.card{{background:linear-gradient(145deg,#1b2030,#11141d);border:1px solid var(--line);border-radius:14px;padding:18px;box-shadow:0 16px 40px #0005}}
.status-grid{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}}.status-grid .card{{padding:12px;min-height:82px}}.status-grid .value{{font-size:17px}}
.label{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1.5px}}.value{{font:800 21px system-ui;margin-top:6px;overflow-wrap:anywhere}}.good{{color:var(--green)}}.warn{{color:#ffd75e}}.bad{{color:#ff6f75}}
.camera{{width:100%;aspect-ratio:4/3;object-fit:contain;background:#050608;border:1px solid var(--line);border-radius:14px;margin-top:14px}}
.dashboard-workspace{{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(430px,.95fr);gap:14px;align-items:start;margin-top:14px}}.dashboard-workspace .camera{{height:min(38vh,340px);aspect-ratio:auto;margin:0}}.dashboard-controls{{margin:10px 0 0}}
.diagnostic-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.diagnostic-grid .card{{padding:10px}}.diagnostic-grid h2{{font-size:15px;margin-bottom:6px}}.diagnostic-grid .label{{font-size:9px}}.diagnostic-grid .bits{{gap:5px;margin-top:6px}}.diagnostic-grid .bit{{padding:3px 5px;font-size:12px}}.diagnostic-grid .meter{{height:6px;margin-top:4px}}.diagnostic-grid .events{{height:110px}}
.controls{{display:flex;gap:10px;flex-wrap:wrap;margin:15px 0}}button,.button{{border:0;border-radius:8px;padding:12px 16px;background:var(--blue);color:white;font:800 15px system-ui;cursor:pointer;text-decoration:none}}button.secondary{{background:#272d3c}}button.danger{{background:var(--red)}}button:disabled{{opacity:.5;cursor:wait}}
.meter{{height:8px;background:#080a10;border-radius:9px;margin-top:10px;overflow:hidden}}.meter i{{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--blue),var(--cyan));transition:width .15s}}
.bits{{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}}.bit{{padding:6px 9px;border:1px solid var(--line);border-radius:7px;color:var(--muted)}}.bit.on{{color:#081109;background:var(--green);border-color:var(--green)}}
.events{{height:170px;overflow:auto;background:#080a10;border-radius:9px;padding:12px;color:#c9d2ec;font-size:13px}}.events div{{padding:3px 0;border-bottom:1px solid #171b25}}
.learn-grid{{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(340px,.8fr);gap:14px;align-items:start}}.learn-camera{{position:relative}}.learn-camera .camera{{height:min(55vh,500px);aspect-ratio:auto;margin:0}}.practice-badge{{position:absolute;left:12px;top:12px;padding:7px 10px;border-radius:999px;background:#090b11dc;border:1px solid var(--green);color:var(--green);font-size:12px}}.lesson-number{{color:var(--cyan);font-size:12px;letter-spacing:1.5px;text-transform:uppercase}}.lesson-title{{font:900 clamp(26px,4vw,40px)/1.05 system-ui;margin:8px 0}}.lesson-cue{{color:var(--muted);min-height:72px}}.lesson-result{{border:1px solid var(--line);border-radius:10px;padding:12px;margin:14px 0;background:#090b11}}.lesson-result.ready{{border-color:var(--green);color:var(--green)}}.lesson-progress{{display:flex;gap:5px;margin:14px 0}}.lesson-progress i{{height:7px;flex:1;border-radius:9px;background:#303748}}.lesson-progress i.done{{background:var(--green)}}.lesson-progress i.current{{background:var(--cyan)}}.live-readout{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px}}.live-readout>div{{padding:10px;border-radius:9px;background:#090b11;text-align:center}}.live-readout strong{{display:block;font:800 18px system-ui;margin-top:4px}}
form{{display:grid;gap:16px}}.formgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}}label{{display:grid;gap:7px;color:var(--muted);font-size:13px}}input,select{{width:100%;background:#090b11;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:12px;font:16px inherit}}input:focus,select:focus{{outline:2px solid var(--blue);border-color:transparent}}.check{{display:flex;align-items:center;gap:10px}}.check input{{width:auto}}.notice{{min-height:24px;color:var(--cyan)}}code{{color:var(--cyan)}}
details.advanced{{margin-top:18px;padding-top:14px;border-top:1px solid var(--line)}}details.advanced summary{{color:var(--cyan);cursor:pointer;font-weight:800}}details.advanced p{{color:var(--muted);max-width:760px}}
@media(max-width:900px){{.status-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.dashboard-workspace,.learn-grid{{grid-template-columns:1fr}}.dashboard-workspace .camera,.learn-camera .camera{{height:auto;aspect-ratio:4/3}}}}
@media(max-width:600px){{header{{align-items:center}}.brand{{max-width:68%}}nav{{display:grid;gap:7px}}nav a{{margin:0}}.diagnostic-grid{{grid-template-columns:1fr}}}}
</style></head><body><header><a class=brand href=/debug aria-label='PowerGlove Vision dashboard'><img src=/assets/powerglove-vision-logo.png alt='PowerGlove Vision'></a><nav><a href=/debug>Dashboard</a><a href=/learn>Learn</a><a href=/setup>Setup</a></nav></header><main>{content}</main><script>{script}</script></body></html>""".encode()


DASHBOARD = _page(
    "Dashboard",
    """<h1>I love the Power Glove. It’s so bad.</h1><p class='lead dashboard-lead'>Live vision, gesture and controller diagnostics from your camera-only Power Glove.</p>
<div class=status-grid>
 <div class=card><div class=label>System</div><div class=value id=system>Starting</div></div>
 <div class=card><div class=label>Active profile</div><div class=value id=profile>—</div></div>
 <div class=card><div class=label>Game</div><div class=value id=game>—</div></div>
 <div class=card><div class=label>Hand tracking</div><div class=value id=tracking>—</div><div class=meter><i id=confidence></i></div></div>
 <div class=card><div class=label>RetroPie receiver</div><div class=value id=receiver>Starting</div></div>
</div>
<div class=dashboard-workspace><div><img class=camera src=/stream alt='Live camera view'>
<div class='controls dashboard-controls'><button id=center>Center hand</button><button id=controller-toggle>Start controller</button><a class=button href=/setup>Connection setup</a><button class=danger id=shutdown-system>Shutdown system</button></div></div>
<div class=diagnostic-grid>
 <section class=card><h2>Controller output</h2><div class=label>Directions</div><div class=bits id=dpad></div><div class=label style='margin-top:14px'>Buttons</div><div class=bits id=buttons></div></section>
 <section class=card><h2>Axes</h2><div id=axes></div></section>
 <section class=card><h2>Finger curl</h2><div id=fingers></div></section>
 <section class='card events-card'><h2>Recent events</h2><div class=events id=events><div>Waiting for tracker…</div></div></section>
</div></div>""",
    r"""const $=id=>document.getElementById(id), names={bad_street_brawler:'Bad Street Brawler',super_glove_ball:'Super Glove Ball',off:'Off'};
const pretty=p=>names[p]||(p&&p.startsWith('program_')?'Program '+p.slice(-1).toUpperCase():p||'—');
const bits=(id,obj)=>{$(id).innerHTML=Object.entries(obj||{}).map(([k,v])=>`<span class="bit ${v?'on':''}">${k.toUpperCase()}</span>`).join('')||'<span class=bit>None</span>'};
const bars=(id,obj,max=32767)=>{$(id).innerHTML=Object.entries(obj||{}).map(([k,v])=>`<div class=label>${k}: ${v}</div><div class=meter><i style="width:${Math.min(100,Math.abs(v)/max*100)}%"></i></div>`).join('')||'—'};
let seen=[]; async function update(){try{const s=await(await fetch('/status',{cache:'no-store'})).json();
$('system').textContent=s.worker_running?(s.detected?'Tracking':'Ready'):(s.camera_available?'Starting tracker':'Camera not found'); $('system').className='value '+(s.worker_running?'good':'warn');
$('profile').textContent=pretty(s.active_profile||s.configured_profile); $('game').textContent=s.game||'Startup default';
$('receiver').textContent=s.controller_enabled?(s.receiver_available===true?'Sending controls':'Waiting for console'):'Stopped'; $('receiver').className='value '+(s.receiver_available===true?'good':'warn');
$('controller-toggle').textContent=s.controller_enabled?'Stop controller':'Start controller'; $('controller-toggle').className=s.controller_enabled?'danger':''; $('controller-toggle').dataset.enabled=s.controller_enabled?'true':'false';
$('tracking').textContent=s.calibrating?'Centering — hold still':(s.detected?`${Math.round((s.confidence||0)*100)}% confidence`:'Show your hand'); $('confidence').style.width=`${Math.round((s.confidence||0)*100)}%`;
bits('dpad',s.dpad);bits('buttons',s.buttons);bars('axes',s.axes);bars('fingers',s.fingers,2);
for(const event of (s.events||[])) seen.unshift(`${new Date().toLocaleTimeString()}  ${event}`);seen=seen.slice(0,30);if(seen.length)$('events').innerHTML=seen.map(x=>`<div>${x}</div>`).join('');
}catch(e){$('system').textContent='Dashboard disconnected';$('system').className='value bad'}} setInterval(update,250);update();
$('center').onclick=async()=>{await fetch('/calibrate',{method:'POST'});};
$('controller-toggle').onclick=async()=>{const b=$('controller-toggle'),enabled=b.dataset.enabled!=='true';b.disabled=true;await fetch('/api/controller',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled})});b.disabled=false;update();};
$('shutdown-system').onclick=()=>shutdownSystem($('shutdown-system'));
async function shutdownSystem(button){if(!confirm('Shut down the entire UNO Q system? Controller input will stop and Linux will shut down safely. To start it again, restore or cycle power.'))return;button.disabled=true;button.textContent='Shutting down…';try{const r=await fetch('/api/system/shutdown',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'shutdown'},body:JSON.stringify({confirm:'SHUTDOWN'})}),x=await r.json();if(!r.ok)throw new Error(x.error||'Shutdown request failed.');$('system').textContent='Shutting down safely';$('system').className='value warn';}catch(e){button.disabled=false;button.textContent='Shutdown system';alert(e.message);}}""",
)


LEARN = _page(
    "Learn gestures",
    """<h1>Train your hand.</h1><p class='lead dashboard-lead'>Practice gesture recognition without a RetroPie connection. Controller transmission is stopped while this page is open.</p>
<div class=learn-grid><div class=learn-camera><img class=camera src=/stream alt='Live camera view for gesture practice'><div class=practice-badge>● PRACTICE ONLY</div></div>
<section class=card><div class=lesson-number id=lesson-number>Lesson 1 of 10</div><div class=lesson-title id=lesson-title>Show your hand</div><p class=lesson-cue id=lesson-cue>Hold one hand inside the camera frame with your palm facing the camera.</p>
<div class=lesson-result id=lesson-result>Waiting for your hand…</div><div class=lesson-progress id=lesson-progress></div>
<div class=controls><button class=secondary id=previous type=button>Previous</button><button id=next type=button>Skip lesson</button><button class=secondary id=center type=button>Re-center</button></div>
<div class=live-readout><div><span class=label>Tracking</span><strong id=tracking>—</strong></div><div><span class=label>Recognized</span><strong id=recognized>None</strong></div><div><span class=label>Confidence</span><strong id=confidence>0%</strong></div></div></section></div>""",
    r"""const $=id=>document.getElementById(id);
const lessons=[
 {title:'Show your hand',cue:'Hold one hand inside the camera frame with your palm facing the camera.',ok:s=>s.detected,result:'Hand found — great!' },
 {title:'Find neutral',cue:'Keep your palm centered and relaxed. Select Re-center if the direction stays active.',ok:s=>s.detected&&s.calibrated&&!Object.values(s.dpad||{}).some(Boolean),result:'Neutral position learned.'},
 {title:'Move left',cue:'Move your whole hand left from the centered position.',ok:s=>s.dpad?.left,result:'LEFT recognized.'},
 {title:'Move right',cue:'Move your whole hand right from the centered position.',ok:s=>s.dpad?.right,result:'RIGHT recognized.'},
 {title:'Move up',cue:'Raise your whole hand above the centered position.',ok:s=>s.dpad?.up,result:'UP recognized.'},
 {title:'Move down',cue:'Lower your whole hand below the centered position.',ok:s=>s.dpad?.down,result:'DOWN recognized.'},
 {title:'Curl your index finger',cue:'Keep your palm visible and curl your index finger toward it.',ok:s=>(s.fingers?.index||0)>=2,result:'Index curl recognized.'},
 {title:'Make the V sign',cue:'Extend index and middle fingers, close ring and pinky, then hold for a moment. This is START.',ok:s=>s.buttons?.start,result:'START recognized.'},
 {title:'Give a thumbs-up',cue:'Extend your thumb and close all four fingers, then hold. This is SELECT.',ok:s=>s.buttons?.select,result:'SELECT recognized.'},
 {title:'Push toward the camera',cue:'Move your open hand closer to the camera in one deliberate push.',ok:s=>s.buttons?.glove_zap||(s.events||[]).includes('glove_zap'),result:'Push recognized — training complete!'}
];
let index=0,completed=new Set(),holdStarted=0,lastSequence=-1,advancing=false;
function action(s){const d=Object.entries(s.dpad||{}).find(([,v])=>v);if(d)return d[0].toUpperCase();const b=Object.entries(s.buttons||{}).find(([,v])=>v);if(b)return b[0].replace('_',' ').toUpperCase();const f=Object.entries(s.fingers||{}).filter(([,v])=>v>=2).map(([k])=>k);return f.length?f.join(' + '):'None'}
function draw(s={}){const lesson=lessons[index];$('lesson-number').textContent=`Lesson ${index+1} of ${lessons.length}`;$('lesson-title').textContent=lesson.title;$('lesson-cue').textContent=lesson.cue;$('lesson-progress').innerHTML=lessons.map((_,i)=>`<i class="${completed.has(i)?'done':i===index?'current':''}"></i>`).join('');$('previous').disabled=index===0;$('next').textContent=index===lessons.length-1?'Start again':'Skip lesson';$('tracking').textContent=s.detected?'Hand found':'No hand';$('recognized').textContent=action(s);$('confidence').textContent=`${Math.round((s.confidence||0)*100)}%`;}
async function update(){try{const s=await(await fetch('/status',{cache:'no-store'})).json();if(s.sequence===lastSequence)return;lastSequence=s.sequence;const passed=lessons[index].ok(s),box=$('lesson-result');if(passed){if(!holdStarted)holdStarted=Date.now();const remaining=Math.max(0,600-(Date.now()-holdStarted));box.textContent=remaining?`Hold it… ${Math.ceil(remaining/100)/10}s`:lessons[index].result;box.className='lesson-result ready';if(!remaining&&!advancing){completed.add(index);advancing=true;draw(s);setTimeout(()=>{if(index<lessons.length-1)index++;holdStarted=0;advancing=false;draw(s)},700)}}else if(!advancing){holdStarted=0;box.textContent=s.worker_running?(s.detected?'Try the gesture shown above.':'Show your hand to begin.'):(s.camera_available?'Gesture tracker is starting…':'Camera is offline.');box.className='lesson-result';}draw(s)}catch(e){$('lesson-result').textContent='Waiting for the gesture tracker…';$('lesson-result').className='lesson-result'}}
$('previous').onclick=()=>{index=Math.max(0,index-1);holdStarted=0;advancing=false;draw()};$('next').onclick=()=>{index=index===lessons.length-1?0:index+1;if(index===0)completed.clear();holdStarted=0;advancing=false;draw()};$('center').onclick=()=>fetch('/calibrate',{method:'POST'});
fetch('/api/controller',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:false})}).catch(()=>{});draw();setInterval(update,150);update();""",
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
<div class=controls><button type=submit>Save & restart tracker</button><button class=secondary type=button id=test>Test console name</button><button type=button id=controller-toggle>Start controller</button><button class=danger type=button id=shutdown-system>Shutdown system</button></div><div class=notice id=notice></div></form></section>
<div class=grid style='margin-top:14px'><div class=card><div class=label>Pairing</div><div class=value id=paired>Checking…</div><p>Your matching token remains in <code>data/device.json</code> and must also be installed at <code>/etc/powerglove/token</code> on RetroPie.</p></div><div class=card><div class=label>Address</div><div class=value><code>/setup</code></div><p>Bookmark this page at your UNO Q's <code>.local:8088</code> address.</p></div></div>
<section class=card style='margin-top:14px'><h2>Pair with RetroPie</h2><p id=secure-note></p><div id=pairing-fields class=formgrid>
<label>RetroPie address<input id=pair-host placeholder=retropieconsole.local autocomplete=off></label>
<label>RetroPie username<input id=pair-user value=pi autocomplete=username></label>
<label>RetroPie password<input id=pair-password type=password autocomplete=current-password></label>
<label>UNO Q approval PIN<input id=device-code inputmode=numeric maxlength=6 placeholder='Shown on the LED matrix' autocomplete=one-time-code></label></div>
<label class=check><input id=verified type=checkbox disabled> I compared the browser certificate fingerprint with the matrix ID</label>
<div class=controls><button type=button id=pair-ssh>Prepare password pairing</button></div><div class=notice id=pair-notice></div>
<details class=advanced><summary>Advanced: pair without a RetroPie password</summary><p>Run <code>sudo /opt/powerglove/bin/powerglove-pair</code> on RetroPie, then enter its temporary code here. Use this when SSH password login is disabled.</p><div class=formgrid><label>RetroPie one-time code<input id=pair-code placeholder=ABCDE-FGHIJ-23456-7ABCD autocomplete=one-time-code></label></div><div class=controls><button class=secondary type=button id=pair-code-button>Prepare one-time code</button></div></details></section>""",
    r"""const $=id=>document.getElementById(id),secure=location.protocol==='https:';let prepared='';async function load(){const c=await(await fetch('/api/config')).json();for(const k of ['receiver','port','profile','glove_color','camera'])$(k).value=c[k];$('pair-host').value=$('pair-host').value||c.receiver;$('paired').textContent=c.paired?'Private token configured':'Not paired';$('controller-toggle').textContent=c.controller_enabled?'Stop controller':'Start controller';$('controller-toggle').className=c.controller_enabled?'danger':'';$('controller-toggle').dataset.enabled=c.controller_enabled?'true':'false'}load();
$('secure-note').innerHTML=secure?'Pairing requires physical confirmation on the UNO Q. For password pairing, compare the matrix ID with the beginning of the certificate SHA-256 fingerprint shown by your browser before entering the password.':`Pairing is disabled over HTTP. Open <a href="https://${location.hostname}:8443/setup">the secure setup page</a>.`;
for(const id of ['pair-host','pair-user','pair-code','pair-ssh','pair-code-button'])$(id).disabled=!secure;for(const id of ['pair-password','device-code'])$(id).disabled=true;
$('form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;$('notice').textContent='Saving…';const payload={receiver:$('receiver').value.trim(),port:Number($('port').value),profile:$('profile').value,glove_color:$('glove_color').value,camera:$('camera').value.trim(),rotate_token:$('rotate_token').checked};const r=await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const x=await r.json();$('notice').textContent=r.ok?'Saved. The tracker is restarting with the new settings.':x.error||'Could not save.';$('rotate_token').checked=false;b.disabled=false;load()};
$('test').onclick=async()=>{$('notice').textContent='Testing name…';const r=await fetch('/api/test-connection',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({receiver:$('receiver').value.trim()})});const x=await r.json();$('notice').textContent=x.ok?`Found ${x.receiver} at ${x.address}. UDP controller delivery can now be attempted.`:x.error};
$('controller-toggle').onclick=async()=>{const b=$('controller-toggle'),enabled=b.dataset.enabled!=='true';b.disabled=true;const r=await fetch('/api/controller',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled})});const x=await r.json();$('notice').textContent=r.ok?(enabled?'Controller started.':'Controller stopped and controls released.'):(x.error||'Could not change controller state.');b.disabled=false;load()};
$('shutdown-system').onclick=async()=>{const b=$('shutdown-system');if(!confirm('Shut down the entire UNO Q system? Controller input will stop and Linux will shut down safely. To start it again, restore or cycle power.'))return;b.disabled=true;b.textContent='Shutting down…';$('notice').textContent='Requesting a safe system shutdown…';try{const r=await fetch('/api/system/shutdown',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'shutdown'},body:JSON.stringify({confirm:'SHUTDOWN'})}),x=await r.json();if(!r.ok)throw new Error(x.error||'Shutdown request failed.');$('notice').textContent='System is shutting down safely. Restore or cycle power to start it again.';}catch(e){b.disabled=false;b.textContent='Shutdown system';$('notice').textContent=e.message;}};
async function prepare(method,button){button.disabled=true;$('pair-notice').textContent='Showing verification on the UNO Q…';try{const r=await fetch('/api/pair/begin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({host:$('pair-host').value.trim(),method})}),x=await r.json();if(!r.ok){$('pair-notice').textContent=x.error||'Could not begin pairing.';return}prepared=method;$('device-code').disabled=false;$('verified').disabled=false;$('pair-notice').textContent=`Matrix: ID ${x.certificate_id}, then PIN. Verify the browser certificate SHA-256 begins ${x.certificate_id}; check the confirmation, enter the PIN, and select Complete pairing.`;button.textContent='Complete pairing';}finally{button.disabled=false;}}
function resetPairing(){prepared='';$('verified').checked=false;$('verified').disabled=true;$('pair-password').disabled=true;$('device-code').disabled=true;$('pair-ssh').textContent='Prepare password pairing';$('pair-code-button').textContent='Prepare one-time code';}
$('verified').onchange=()=>{$('pair-password').disabled=!(prepared==='ssh'&&$('verified').checked);if($('verified').checked)$('device-code').focus();};
async function pair(method,path,payload,button){if(prepared!==method){await prepare(method,button);return}if(!$('verified').checked){$('pair-notice').textContent='Compare the browser certificate fingerprint with the matrix ID first.';return}button.disabled=true;$('pair-notice').textContent='Pairing…';payload.device_code=$('device-code').value;try{const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),x=await r.json();$('pair-notice').textContent=r.ok?'Paired. RetroPie receiver restarted with the new private token.':x.error||'Pairing failed.';resetPairing();}finally{$('pair-password').value='';$('device-code').value='';button.disabled=false;}}
$('pair-ssh').onclick=()=>pair('ssh','/api/pair/ssh',{host:$('pair-host').value.trim(),username:$('pair-user').value.trim(),password:$('pair-password').value},$('pair-ssh'));
$('pair-code-button').onclick=()=>pair('code','/api/pair/code',{host:$('pair-host').value.trim(),code:$('pair-code').value.trim()},$('pair-code-button'));""",
)


class ControlState:
    """Synchronize persistent settings, supervisor health, worker status, and pairing authorization."""
    def __init__(self, config_path: Path, pairing_display: Callable[[str, str], None] | None = None) -> None:
        self.config_path = config_path
        self.lock = threading.Lock()
        self.revision = 0
        self.worker_status: dict[str, Any] = {}
        self.camera_available = False
        self.worker_running = False
        self.last_error: str | None = None
        self._controller_enabled = False
        self._pairing_display = pairing_display
        self._pairing_identity = ""
        self._pairing_session: dict[str, Any] | None = None
        self._pairing_locked_until = 0.0
        self._shutdown_scheduled = False
        self.started_at = time.time()

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

    def controller_enabled(self) -> bool:
        """Return the operator-selected controller transmission state."""
        with self.lock:
            return self._controller_enabled

    def set_controller_enabled(self, enabled: bool) -> None:
        """Queue a controller start or stop request for the vision worker."""
        with self.lock:
            self._controller_enabled = enabled

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
            """Create the fixed request file after allowing the HTTP response to complete."""
            path = data_directory / "shutdown-request"
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(path, flags, 0o600)
                with os.fdopen(descriptor, "w") as request:
                    request.write("shutdown\n")
            except FileExistsError:
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
            "receiver": config.get("receiver", "retropieconsole.local"),
            "port": int(config.get("port", 55355)),
            "profile": config.get("profile", "bad_street_brawler"),
            "glove_color": config.get("glove_color", "none"),
            "camera": str(config.get("camera", "auto")),
            "paired": bool(config.get("token")),
            "controller_enabled": self.controller_enabled(),
        }

    def save_config(self, incoming: dict[str, Any]) -> dict[str, Any]:
        """Validate and persist browser-submitted non-secret device settings."""
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
        """Return a thread-safe dashboard snapshot of configuration and runtime health."""
        with self.lock:
            status = dict(self.worker_status)
            status.update({
                "camera_available": self.camera_available,
                "worker_running": self.worker_running,
                "last_error": self.last_error,
                "controller_enabled": self._controller_enabled,
                "uptime_seconds": round(time.time() - self.started_at),
            })
        status.setdefault("configured_profile", self.public_config()["profile"])
        return status

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
        with self.lock:
            self.worker_status = status
            self.worker_running = True
            self.last_error = None


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
            if length > 8192:
                raise ValueError("Request is too large.")
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/":
                self.send_response(302); self.send_header("Location", "/debug"); self.end_headers()
            elif path == "/debug":
                _send(self, 200, DASHBOARD, "text/html; charset=utf-8")
            elif path == "/learn":
                _send(self, 200, LEARN, "text/html; charset=utf-8")
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
                elif path == "/api/controller":
                    enabled = self.json_body().get("enabled")
                    if not isinstance(enabled, bool):
                        raise ValueError("enabled must be true or false")
                    state.set_controller_enabled(enabled)
                    request = urllib.request.Request(
                        WORKER_URL + "/controller",
                        method="POST",
                        data=json.dumps({"enabled": enabled}).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    try:
                        with urllib.request.urlopen(request, timeout=1):
                            pass
                    except (OSError, urllib.error.URLError):
                        pass
                    _send(self, 200, json.dumps({"controller_enabled": enabled}).encode(), "application/json")
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
                    pair_with_code(
                        host, PAIRING_PORT,
                        str(incoming.get("code", "")), str(state.load_config()["token"]),
                    )
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
                    _send(self, 200, b'{"paired":true}', "application/json")
                elif path == "/api/pair/begin":
                    self.require_secure_pairing()
                    incoming = self.json_body(require_json=True)
                    result = state.begin_pairing(
                        str(incoming.get("host", "")).strip(), str(incoming.get("method", ""))
                    )
                    _send(self, 200, json.dumps(result).encode(), "application/json")
                elif path == "/calibrate":
                    request = urllib.request.Request(WORKER_URL + "/calibrate", method="POST", data=b"")
                    with urllib.request.urlopen(request, timeout=1):
                        pass
                    _send(self, 204, b"", "text/plain")
                else:
                    self.send_error(404)
            except (ValueError, json.JSONDecodeError) as exc:
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
) -> tuple[ControlServerGroup, ControlState]:
    """Start public diagnostics and protected setup servers and return their shared state."""
    state = ControlState(config_path, pairing_display)
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
