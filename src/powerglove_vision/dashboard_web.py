# Project: PowerGlove Vision
# File: src/powerglove_vision/dashboard_web.py
# Purpose: Render Dashboard controls and live controller status.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-07 - Identified the active native X/Y coordinate source.
#   2026-09-06 - Add opt-in independent native hand movement tracking.
#   2026-09-06 - Separate maintained web modules without changing rendered pages.

"""Render Dashboard controls and live controller status."""

from .web_common import _page, _profile_options, VISION_STARTUP_SCRIPT

DASHBOARD = _page(
    "Dashboard",
    """<h1>I love the Power Glove. It’s so bad.</h1><p class='lead dashboard-lead'>Live vision, gesture and controller diagnostics from your camera-only Power Glove.</p>
<div class=status-grid>
 <div class=card><div class=label>System</div><div class=value id=system>Starting</div></div>
 <div class=card><label class=label for=player-select>Player</label><select class=profile-select id=player-select disabled></select><div class=label id=player-notice role=status aria-live=polite style='margin-top:6px'></div></div>
 <div class=card><label class=label for=profile-selector>Active profile</label><select class=profile-select id=profile-selector>""" + _profile_options() + """</select><div class=label id=profile-source style='margin-top:6px'>—</div></div>
 <div class=card><div class=label>Game</div><div class=value id=game>—</div><div class=label id=game-session style='margin-top:6px'>Starting</div></div>
 <div class=card><div class=label>Hand tracking</div><div class=value id=tracking>—</div><div class=meter><i id=confidence></i></div></div>
 <div class=card><div class=label>Controller delivery</div><div class=value id=receiver>Starting</div></div>
 <div class=card><label class=label for=native-xy-mode>Super Glove Ball movement</label><select class=profile-select id=native-xy-mode><option value=bounded>Bounded speed curve</option><option value=latest>Latest coordinate</option></select><div class=label id=native-xy-note style='margin-top:6px'>MediaPipe Hands</div></div>
</div>
<div class=dashboard-workspace><div><div class=camera-stage><img class=camera id=camera data-src=/stream alt='Live camera view'><div class=camera-idle id=camera-idle role=status>POWER GLOVE VISION<small>Gestures are paused. Select a profile to resume.</small></div></div>
<div class='controls dashboard-controls'><button id=center>Center hand</button><button id=controller-toggle>Start controller</button><a class=button href=/setup>Connection</a><button class=danger id=shutdown-system>Shutdown</button></div><p id=center-guidance role=status></p><div class=notice id=dashboard-notice role=status aria-live=polite></div></div>
<div class=diagnostic-grid>
 <section class=card><h2>Controller output</h2><div class=label>Directions</div><div class=bits id=dpad></div><div class=label style='margin-top:14px'>Buttons</div><div class=bits id=buttons></div></section>
 <section class=card><h2>Axes</h2><div id=axes></div></section>
 <section class=card><h2>Finger curl</h2><div id=fingers></div></section>
 <section class=card><h2>Performance</h2><div id=performance>Waiting for samples…</div></section>
 <section class='card events-card'><h2>Recent events</h2><div class=events id=events><div>Waiting for tracker…</div></div></section>
</div></div>""",
    VISION_STARTUP_SCRIPT + r"""const $=id=>document.getElementById(id);
function buttonText(b,text){if(b.textContent!==text)b.textContent=text;}
let controllerBusy=false;
let calibrationPending=false,calibrationSeen=false,calibrationStarted=0,calibrationDoneUntil=0;
function updateCalibration(s){const b=$('center');if(s.calibrating){calibrationSeen=true;calibrationPending=true;if(!calibrationStarted)calibrationStarted=Date.now()}
if(calibrationPending&&calibrationSeen&&s.calibrated&&!s.calibrating){calibrationPending=false;calibrationSeen=false;calibrationStarted=0;calibrationDoneUntil=Date.now()+1800}
if(calibrationPending&&Date.now()-calibrationStarted>20000){calibrationPending=false;calibrationSeen=false;calibrationStarted=0;b.title='Calibration did not finish. Show a relaxed hand and try again.'}
b.disabled=s.vision_state!=='active'||calibrationPending;b.classList.toggle('danger',calibrationPending);b.setAttribute('aria-busy',String(calibrationPending));buttonText(b,calibrationPending?'Centering…':Date.now()<calibrationDoneUntil?'Center saved ✓':'Center hand');}
async function calibrate(){if(calibrationPending)return;calibrationPending=true;calibrationSeen=false;calibrationStarted=Date.now();calibrationDoneUntil=0;updateCalibration({vision_state:'active'});try{const r=await fetch('/calibrate',{method:'POST'});if(!r.ok)throw Error('Centering request failed');}catch(e){calibrationPending=false;calibrationStarted=0;updateCalibration({vision_state:'active'});$('center').textContent='Try setting center again';$('center').title=e.message}}

const bits=(id,obj)=>{$(id).innerHTML=Object.entries(obj||{}).map(([k,v])=>`<span class="bit ${v?'on':''}">${k.toUpperCase()}</span>`).join('')||'<span class=bit>None</span>'};
const bars=(id,obj,max=32767)=>{$(id).innerHTML=Object.entries(obj||{}).map(([k,v])=>`<div class=label>${k}: ${v}</div><div class=meter><i style="width:${Math.min(100,Math.abs(v)/max*100)}%"></i></div>`).join('')||'—'};
const performance=s=>{const p=s.performance||{},inference=p.inference_ms||{},age=p.capture_age_ms||{},sample=p.sample_age_ms||{},transition=p.controller_transition_age_ms||{},mode=s.native_xy_mode==='latest'?'Latest coordinate':'Bounded speed curve',source=s.native_xy_source==='mediapipe'?`MediaPipe — ${mode}`:'Inactive';return [`Model: ${s.tracker_backend_label||s.tracker_backend||'—'}`,`Native X/Y: ${source}`,`Inference: ${s.inference_hz??'—'} Hz`,`Inference p50 / p95: ${inference.p50??'—'} / ${inference.p95??'—'} ms`,`Camera read → send p50 / p95: ${sample.p50??'—'} / ${sample.p95??'—'} ms`,`Changed control → send p50 / p95: ${transition.p50??'—'} / ${transition.p95??'—'} ms`,`Frame waiting before inference p50 / p95: ${age.p50??'—'} / ${age.p95??'—'} ms`,`Superseded camera frames: ${s.capture_skipped_total??0}`,`Preview encode: ${s.preview_encode_ms??'—'} ms`].map(x=>`<div class=label style="margin:5px 0">${x}</div>`).join('')};
let seen=[],switching=false,desiredProfile='',nativeSwitching=false; async function update(){try{const s=await(await fetch('/status',{cache:'no-store'})).json(),active=s.active_profile||s.configured_profile,idle=s.vision_state==='idle'||active==='off',starting=s.vision_state==='starting',ready=s.vision_state==='active',startup=startupMessage(s);
$('system').textContent=idle?'Gestures idle':(s.vision_state==='error'?(s.vision_error||'Vision unavailable'):(s.vision_state==='starting'?'Starting vision':s.worker_running?(s.detected?'Tracking':'Ready'):(s.camera_available?'Starting tracker':'Camera not found'))); $('system').className='value '+(s.vision_state==='error'?'bad':(idle||ready?'good':'warn'));
if(switching&&active===desiredProfile){switching=false;$('profile-selector').disabled=false}if(!switching)$('profile-selector').value=active;$('profile-source').textContent=s.profile_source||'Startup'; $('game').textContent=s.game||'Startup default';
const nativeMode=s.native_xy_mode==='latest'?'latest':'bounded';if(nativeSwitching&&$('native-xy-mode').value===nativeMode){nativeSwitching=false;$('native-xy-mode').disabled=false}if(!nativeSwitching)$('native-xy-mode').value=nativeMode;$('native-xy-note').textContent=nativeMode==='latest'?'No coordinate smoothing':'Speed-sensitive smoothing';
$('game-session').textContent=s.game_session_active?'Registered game active':(s.profile_source==='Dashboard'?'Manual profile':'No registered game');$('game-session').className='label '+(s.game_session_active?'good':'');
$('camera').style.display=idle||starting?'none':'block';$('camera-idle').style.display=idle||starting?'flex':'none';$('camera-idle').textContent=starting?startup:'POWER GLOVE VISION — Gestures are paused. Select a profile to resume.';if(idle||starting){$('camera').removeAttribute('src')}else if(!$('camera').getAttribute('src')){$('camera').src=$('camera').dataset.src+'?t='+Date.now()}updateCalibration(s);
$('receiver').textContent=!s.connection_configured?'Set up Connection':s.controller_request_pending?'Waiting for tracker':s.controller_enabled?(!s.controller_context_active?'Armed — waiting for game':starting?'Waiting for vision':idle?'Ready when gestures resume':(s.launch_guard_active?'Launch delay':(s.receiver_available===true?'Sending controls':'Waiting for console'))):'Stopped'; $('receiver').className='value '+(s.receiver_available===true||idle||s.controller_enabled&&!s.controller_context_active?'good':'warn');
buttonText($('controller-toggle'),controllerBusy?'Please wait…':s.controller_enabled?'Stop controller':'Start controller'); $('controller-toggle').className=s.controller_enabled?'danger':''; $('controller-toggle').dataset.enabled=s.controller_enabled?'true':'false'; $('controller-toggle').disabled=controllerBusy||!s.connection_configured; $('controller-toggle').title=s.connection_configured?'':'Configure your RetroPie destination in Connection first';
const player=s.player||{},selected=(player.players||[]).find(p=>p.id===player.active);$('center-guidance').textContent=player.needs_center?`Center your hand for ${selected?selected.name:'the selected player'} before starting controls. Hold a relaxed open hand at your normal playing position and select the centering button.`:'';
$('tracking').textContent=starting?'Starting…':idle?'Paused':(s.calibrating?'Centering — hold still':(s.detected?`${Math.round((s.confidence||0)*100)}% confidence`:'Show your hand')); $('confidence').style.width=`${Math.round((s.confidence||0)*100)}%`;
bits('dpad',s.dpad);bits('buttons',s.buttons);bars('axes',s.axes);bars('fingers',s.fingers,2);$('performance').innerHTML=performance(s);
for(const event of (s.events||[])) seen.unshift(`${new Date().toLocaleTimeString()}  ${event}`);seen=seen.slice(0,30);if(seen.length)$('events').innerHTML=seen.map(x=>`<div>${x}</div>`).join('');
}catch(e){$('system').textContent='Dashboard disconnected';$('system').className='value bad'}}
fetch('/api/practice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:false,reset:true})}).finally(update);setInterval(update,250);
$('center').onclick=calibrate;
$('profile-selector').onchange=async()=>{const p=$('profile-selector'),notice=$('dashboard-notice');desiredProfile=p.value;switching=true;p.disabled=true;notice.textContent='Switching profile…';try{const r=await fetch('/api/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:desiredProfile})}),x=await r.json();if(!r.ok)throw new Error(x.error||'Could not change profile.');notice.textContent=desiredProfile==='off'?'Gestures paused. Camera capture is stopping.':'Profile selected.';}catch(e){switching=false;p.disabled=false;notice.textContent=e.message;update()}};
$('native-xy-mode').onchange=async()=>{if(nativeSwitching)return;const p=$('native-xy-mode'),notice=$('dashboard-notice');nativeSwitching=true;p.disabled=true;notice.textContent='Changing Super Glove Ball movement and restarting tracking…';try{const r=await fetch('/api/native-xy',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'native-xy'},body:JSON.stringify({mode:p.value})}),x=await r.json();if(!r.ok)throw Error(x.error||'Could not change movement mode.');notice.textContent='Movement mode saved. Tracking is restarting.';}catch(e){nativeSwitching=false;p.disabled=false;notice.textContent=e.message;update()}};
$('controller-toggle').onclick=async()=>{if(controllerBusy)return;controllerBusy=true;const b=$('controller-toggle'),enabled=b.dataset.enabled!=='true';b.disabled=true;try{const r=await fetch('/api/controller',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled})}),x=await r.json();if(!r.ok)throw Error(x.error||'Could not change controller state.');$('dashboard-notice').textContent=x.pending?'Request saved. Waiting for the tracker; the Controller will retry.':enabled?'Controller armed.':'Stop request delivered to tracking.';}catch(e){$('dashboard-notice').textContent=e.message;}finally{controllerBusy=false;b.disabled=false;update();}};
$('shutdown-system').onclick=()=>shutdownSystem($('shutdown-system'));
async function shutdownSystem(button){if(!confirm('Request a system halt? Controller input will stop. Some UNO Q boards restart automatically after shutdown. A disconnected website does not confirm it is safe to remove power.'))return;button.disabled=true;button.textContent='Shutting down…';try{const r=await fetch('/api/system/shutdown',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'shutdown'},body:JSON.stringify({confirm:'SHUTDOWN'})}),x=await r.json();if(!r.ok)throw new Error(x.error||'Shutdown request failed.');$('system').textContent='Shutting down safely';$('system').className='value warn';}catch(e){button.disabled=false;button.textContent='Shutdown';alert(e.message);}}""",
)


from .player_web import PLAYER_SCRIPT

DASHBOARD = DASHBOARD.replace(b"</body>", b"<script>" + PLAYER_SCRIPT.encode() + b"</script></body>")
