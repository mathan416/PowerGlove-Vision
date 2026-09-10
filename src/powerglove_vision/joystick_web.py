# Project: PowerGlove Vision
# File: src/powerglove_vision/joystick_web.py
# Purpose: Render per-player digital joystick dead-zone controls and status.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-06 - Added Setup dead-zone controls with per-player persistence.
# Full history: docs/CHANGELOG.md and Git history.
"""Per-player Setup controls for the nine-region digital joystick layout."""

JOYSTICK_CONTENT = """<section class=card id=joystick-settings style="margin-top:14px" aria-labelledby=joystick-title>
<h2 id=joystick-title>Joystick dead zone</h2>
<p id=joystick-player>Loading player…</p>
<form id=joystick-form><label for=joystick-size>Center box size: Small ↔ Large</label>
<input id=joystick-size type=range min=0.14 max=1 step=0.01 value=0.28 disabled aria-describedby=joystick-value>
<p id=joystick-value></p><div class=controls><button id=joystick-save type=submit disabled>Save dead zone</button><button id=joystick-default type=button disabled>Use standard size</button></div></form>
<div id=joystick-directions class=controls aria-label="Live direction states"><span class=bit data-direction=left>Left: off</span><span class=bit data-direction=up>Up: off</span><span class=bit data-direction=down>Down: off</span><span class=bit data-direction=right>Right: off</span></div>
<p id=joystick-live>Waiting for tracking…</p><p id=joystick-notice role=status aria-live=polite></p>
<p>Choose the size of the resting box around your saved center. Smaller values require less hand travel; larger values give you more room to rest.</p><ul><li>Inside or exactly on the box: movement stops.</li><li>Outside a side: one direction. Outside a corner: a diagonal.</li><li>Native Super Glove Ball X/Y reach stays separate.</li></ul>
<p>PowerGlove Vision may safely enlarge the effective box when your saved neutral-hand jitter needs more resting room.</p></section>"""

JOYSTICK_SCRIPT = r"""(()=>{
const el=id=>document.getElementById(id), directions=['left','right','up','down'];
let player=null, dirty=false, busy=false, polling=false;
const notice=text=>el('joystick-notice').textContent=text;
async function api(payload){const r=await fetch('/api/players',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'players'},body:JSON.stringify(payload)});const s=await r.json();if(!r.ok)throw Error(s.error||'Player request failed.');return s}
function describe(state=null){const v=Number(el('joystick-size').value);let text=`Chosen size: ${Math.round(v*100)}% of calibrated palm size.`;
 if(state?.joystick?.jitter_protected)text+=` Effective size: ${Math.round(state.joystick.effective_deadzone*100)}% because neutral-hand movement needs a little more resting room.`;
 el('joystick-value').textContent=text}
function controls(){el('joystick-size').disabled=busy||!player;el('joystick-save').disabled=busy||!player||!dirty;el('joystick-default').disabled=busy||!player}
function apply(s){if(!s.joystick||!s.players)throw Error('Joystick settings unavailable. Reload after updating the Controller.');
 const changed=player&&(player.active!==s.active||player.generation!==s.generation);
 if(changed){if(dirty)notice('Player settings changed. Unsaved dead-zone edits were discarded.');dirty=false}
 player=s;el('joystick-player').textContent='Player: '+(s.players.find(p=>p.id===s.active)?.name||s.active);
 if(!dirty){const value=s.joystick.deadzone;
 el('joystick-size').value=Math.max(.14,Math.min(1,value));describe(s);
 }controls();}
el('joystick-size').oninput=()=>{dirty=true;describe();controls()};
el('joystick-default').onclick=()=>{el('joystick-size').value=.28;dirty=true;describe();controls();notice('Standard size selected. Save to apply.')};
el('joystick-form').onsubmit=async e=>{e.preventDefault();if(busy||!player||!dirty)return;busy=true;controls();notice('Saving…');
 const identity={player:player.active,generation:player.generation};
 try{const s=await api({action:'joystick_deadzone',...identity,value:Number(el('joystick-size').value)});dirty=false;apply(s);notice('Dead zone saved for this player. Center and reach are unchanged.')}
 catch(e){notice(e.message)}finally{busy=false;controls()}};
function feedback(s){const active=s.vision_state==='active'&&s.detected===true&&s.calibrated===true&&!s.calibrating;
 for(const d of directions){const node=el('joystick-directions').querySelector(`[data-direction=${d}]`),on=active&&s.dpad?.[d]===true;node.classList.toggle('on',on);node.textContent=d[0].toUpperCase()+d.slice(1)+(on?': pressed':': off')}
 el('joystick-live').textContent=active?'Live direction feedback using saved settings.':s.vision_state==='active'?'Keep a calibrated hand visible for direction feedback.':'Tracking is paused. Start the controller from Dashboard to see live directions.';}
async function poll(){if(polling||busy||document.hidden)return;polling=true;try{const settings=await api({action:'read'});if(busy)return;apply(settings);const r=await fetch('/status',{cache:'no-store'});if(!r.ok)throw Error('Status unavailable.');feedback(await r.json())}catch(e){feedback({});el('joystick-live').textContent='Live feedback unavailable.';notice(e.message)}finally{polling=false}}
describe();controls();poll();setInterval(poll,500);
})();"""
