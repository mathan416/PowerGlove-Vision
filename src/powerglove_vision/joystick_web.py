# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
"""Per-player Setup controls for the existing digital direction thresholds."""

JOYSTICK_CONTENT = """<section class=card id=joystick-settings style="margin-top:14px" aria-labelledby=joystick-title>
<h2 id=joystick-title>Joystick dead zone</h2>
<p id=joystick-player>Loading player…</p>
<p>Choose how far your hand moves from center before a direction presses. A larger dead zone gives you more room to rest. Applies to digital joystick directions; native Super Glove Ball and dot X/Y reach stay separate.</p>
<form id=joystick-form><label for=joystick-size>Small ↔ Large</label>
<input id=joystick-size type=range min=0.14 max=1 step=0.01 value=0.28 disabled aria-describedby=joystick-value>
<p id=joystick-value></p><div class=controls><button id=joystick-save type=submit disabled>Save dead zone</button><button id=joystick-default type=button disabled>Use standard size</button></div></form>
<p>Release is set automatically at half the activation distance. Centering jitter can raise either threshold to keep directions steady. Saving applies equally to all four directions and preserves your center and reach calibration.</p>
<div id=joystick-directions class=controls aria-label="Live direction states"><span class=bit data-direction=left>Left: off</span><span class=bit data-direction=up>Up: off</span><span class=bit data-direction=down>Down: off</span><span class=bit data-direction=right>Right: off</span></div>
<p id=joystick-live>Waiting for tracking…</p><p id=joystick-notice role=status aria-live=polite></p>
<details><summary>Advanced direction adjustments</summary><p>For separate left, right, up and down activation/release values, use <a href=/learn>Glove Academy → Tune gestures → Advanced thresholds and diagnostics</a>. This slider replaces those four directional pairs only when you save.</p></details></section>"""

JOYSTICK_SCRIPT = r"""(()=>{
const el=id=>document.getElementById(id), directions=['left','right','up','down'];
let player=null, dirty=false, busy=false, polling=false;
const notice=text=>el('joystick-notice').textContent=text;
async function api(payload){const r=await fetch('/api/players',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'players'},body:JSON.stringify(payload)});const s=await r.json();if(!r.ok)throw Error(s.error||'Player request failed.');return s}
function describe(){const v=Number(el('joystick-size').value);el('joystick-value').textContent=`Activation: ${Math.round(v*100)}% of calibrated palm size · Release: ${Math.round(v*50)}%.`}
function controls(){el('joystick-size').disabled=busy||!player;el('joystick-save').disabled=busy||!player||!dirty;el('joystick-default').disabled=busy||!player}
function apply(s){if(!s.joystick||!s.players)throw Error('Joystick settings unavailable. Reload after updating the Controller.');
 const changed=player&&(player.active!==s.active||player.generation!==s.generation);
 if(changed){if(dirty)notice('Player settings changed. Unsaved dead-zone edits were discarded.');dirty=false}
 player=s;el('joystick-player').textContent='Player: '+(s.players.find(p=>p.id===s.active)?.name||s.active);
 if(!dirty){const pairs=directions.map(d=>s.joystick[d]);const uniform=pairs.every(p=>p.on===pairs[0].on&&p.off===pairs[0].off);const value=pairs[0].on;
 el('joystick-size').value=Math.max(.14,Math.min(1,value));describe();
 if(!uniform||value<.14||value>1||pairs[0].off!==value/2)el('joystick-value').textContent='Custom directional settings are saved. Move the slider to choose one size for all four directions.';
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
