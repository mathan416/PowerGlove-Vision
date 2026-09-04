# Project: PowerGlove Vision
# File: src/powerglove_vision/web_features.py
# Purpose: Provide the game JSON editor and guided Learn tuning interface.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Change log:
#   2026-09-04 - Added Games and guided gesture tuning views.
# Full history: docs/CHANGELOG.md and Git history.

"""Browser interfaces for paired game mappings and personal gesture thresholds."""

GAMES_CONTENT = """<section id=games-section style="margin-top:28px;scroll-margin-top:20px"><h2>Games</h2>
<p class=lead>Edit the game mappings installed on your RetroPie. Saving affects the next game launch.</p>
<section class=card><p>Use the exact ROM filename, including its extension: <code>Joust (USA).7z</code> and <code>Joust (USA).nes</code> need separate entries. Matching ignores letter case. Only NES and Famicom launches use these mappings.</p>
<details><summary>Available profile identifiers</summary><p id=game-profiles></p><p>Example: <code>{"games": {"Joust (USA).7z": "program_b"}}</code>. Remove a mapping to leave that game off.</p></details>
<label for=game-json>Game mappings JSON</label><textarea id=game-json spellcheck=false rows=22 style="width:100%;font:14px/1.5 monospace;tab-size:2;background:#090b11;color:#f7f8ff;border:1px solid #303748;border-radius:8px;padding:12px" aria-describedby=games-notice></textarea>
<div class=controls><button id=games-validate>Validate</button><button id=games-format>Format</button><button id=games-save>Save</button><button id=games-reload>Reload</button><button id=games-backup>Download backup</button><button id=games-restore>Restore previous save</button></div>
<p id=games-notice role=status aria-live=polite>Loading the installed RetroPie registry…</p></section></section>"""

GAMES_SCRIPT = r"""(()=>{
const editor=document.getElementById('game-json'),notice=document.getElementById('games-notice');
let revision=null,loaded='',backup=false,busy=false;
const buttons=[...document.querySelectorAll('#games-section button')];
function controls(){buttons.forEach(b=>b.disabled=busy||(b.id!=='games-reload'&&!revision)||(b.id==='games-restore'&&!backup))}
async function api(action){const r=await fetch('/api/games',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'games'},body:JSON.stringify({action,document:editor.value,revision})});const x=await r.json();if(!r.ok)throw Error(x.error||'Games request failed');return x}
async function run(action){if(busy)return;if(action==='read'&&editor.value!==loaded&&!confirm('Discard your unsaved edits and reload?'))return;if(action==='restore'&&!confirm('Replace the current mappings with the previous save?'))return;busy=true;controls();try{const x=await api(action);if(['read','save','restore'].includes(action)){editor.value=x.document;loaded=x.document;revision=x.revision;backup=x.has_backup;document.getElementById('game-profiles').textContent=x.profiles.join(' · ')}if(action==='format')editor.value=x.document;notice.textContent=action==='save'?'Saved on RetroPie and verified. The next game launch uses these mappings.':action==='restore'?'Previous save restored on RetroPie.':action==='validate'?'Valid JSON and game mappings.':action==='format'?'Formatted. Select Save to apply.':'Installed mappings loaded.'}catch(e){notice.textContent=e.message+' Your draft has been kept.'}finally{busy=false;controls()}}
for(const [id,action] of Object.entries({'games-validate':'validate','games-format':'format','games-save':'save','games-reload':'read','games-restore':'restore'}))document.getElementById(id).onclick=()=>run(action);
document.getElementById('games-backup').onclick=()=>{const url=URL.createObjectURL(new Blob([loaded],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='powerglove-games-backup.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notice.textContent='Downloaded the last verified installed registry.'};
window.addEventListener('beforeunload',e=>{if(editor.value!==loaded){e.preventDefault();e.returnValue=''}});controls();run('read');})();"""

TUNE_CONTENT = """<style>
#tune-switch{appearance:none;width:42px;height:24px;display:inline-block;vertical-align:middle;border-radius:14px;background:#303748;position:relative;margin:0 10px 0 0;cursor:pointer;padding:0}
#tune-switch::before{content:"";position:absolute;width:18px;height:18px;left:2px;top:2px;border-radius:50%;background:white;transition:transform .15s}
#tune-switch:checked{background:#3d75ff}#tune-switch:checked::before{transform:translateX(18px)}
.learn-camera{position:relative;align-self:start}#tune-panel .controls{gap:8px;display:grid;grid-template-columns:1fr 1fr}#tune-panel p{margin:10px 0}#tune-panel button{padding:10px 12px}#tune-panel #tune-instruction{font:600 17px/1.45 system-ui;padding:12px;border:1px solid var(--line);border-radius:8px;background:#090b11}#tune-components{font-size:12px;color:var(--muted)}
.tune-mode-bar{display:flex;align-items:center;gap:16px;margin:12px 0;padding:12px 16px}.tune-mode-bar>label{display:flex;align-items:center;flex-shrink:0;margin:0;font-size:15px}.tune-mode-bar>p{margin:0;font-size:13px;color:var(--muted)}
#tune-thresholds{margin-top:12px;padding:14px}#tune-thresholds h3{margin:0 0 8px}#tune-thresholds table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:13px}#tune-thresholds th,#tune-thresholds td{padding:5px 8px;text-align:left;border-bottom:1px solid var(--line)}#tune-thresholds input{width:100%;max-width:100px;margin:0;padding:6px;font-size:14px}#tune-live{font-size:13px;color:var(--cyan)}
@media(max-width:900px){.tune-mode-bar{flex-wrap:wrap}.learn-grid:has(#tune-panel:not([hidden])){display:flex;flex-direction:column}.learn-grid:has(#tune-panel:not([hidden]))>.learn-camera{order:2;width:100%}#tune-panel{order:1;width:100%}}
</style><section class="card tune-mode-bar"><label><input id=tune-switch type=checkbox role=switch> Tune gestures</label><p>Adjust gesture sensitivity across all profiles. Controller output stays paused.</p>
<div id=tune-panel hidden><p>Tuning is optional. Start with Set up my hand, or adjust only a control that feels difficult or triggers accidentally. Directions usually only need neutral calibration.</p><label for=tune-gesture>Gesture</label><select id=tune-gesture></select><button id=tune-hand-setup>Set up my hand</button><button id=tune-calibrate>Recalibrate neutral</button><p id=tune-components></p>
<p id=tune-instruction></p><button id=tune-record>Record open hand (3 seconds)</button><button id=tune-suggest>Analyze and preview</button>
<p id=tune-progress role=status aria-live=polite></p><p id=tune-fingers role=status aria-live=polite></p>
<div class=controls><button id=tune-preview>Preview adjustments</button><button id=tune-save>Save for all profiles</button><button id=tune-discard>Discard / record again</button><button id=tune-reset>Restore defaults</button></div>
<p id=tune-notice role=status aria-live=polite></p><details><summary>Preview and reset help</summary><p>Preview is temporary until saved. Reset restores only the selected components across all profiles.</p></details></div></section>"""

TUNE_THRESHOLDS = """<section class=card id=tune-thresholds hidden><h3>Gesture thresholds</h3><p id=tune-live></p><table><thead><tr><th scope=col>Gesture</th><th scope=col>Activation</th><th scope=col>Release</th></tr></thead><tbody id=tune-fields></tbody></table><p style="font-size:12px;color:var(--muted);margin-bottom:0">Activation starts the gesture. The lower release value stops it.</p></section>"""

TUNE_SCRIPT = r"""(()=>{
const el=id=>document.getElementById(id);let enabled=false,busy=false,last=null,fieldsKey='',polling=false;
async function api(action,extra={}){const r=await fetch('/api/tuning',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'tuning'},body:JSON.stringify({action,session:practiceSession,...extra})});const x=await r.json();if(!r.ok)throw Error(x.error||'Tuning request failed');return x}
function pairs(){const values={};el('tune-fields').querySelectorAll('[data-channel]').forEach(row=>{const inputs=row.querySelectorAll('input');if(!row.dataset.changed&&!last?.preview?.[row.dataset.channel])return;values[row.dataset.channel]={on:Number(inputs[0].value),off:Number(inputs[1].value)}});return values}
const featured=['hand_setup','start','select','thumb','index','middle','ring','pinky','push','pull'];
const movements={left:'Move your open hand left without changing its distance from the camera.',right:'Move your open hand right without changing its distance from the camera.',up:'Move your open hand up without changing its distance from the camera.',down:'Move your open hand down without changing its distance from the camera.',push:'Push your open hand toward the camera, keeping your palm facing it.',pull:'Pull your open hand away from the camera, keeping your palm facing it.',roll_left:'Roll your wrist left while keeping your hand centered at the starting distance.',roll_right:'Roll your wrist right while keeping your hand centered at the starting distance.'};
function draw(s,force=false){last=s;if(!el('tune-gesture').options.length){for(const [label,keys] of [['Common adjustments',featured],['More adjustments',Object.keys(s.gestures).filter(k=>!featured.includes(k))]]){const group=document.createElement('optgroup');group.label=label;keys.filter(k=>s.gestures[k]).forEach(k=>group.append(new Option(s.gestures[k],k)));el('tune-gesture').append(group)}}el('tune-gesture').value=s.gesture;
el('tune-components').textContent='Adjusts: '+s.components.join(', ')+'. These components are shared across games and compound gestures.'+(['start','select'].includes(s.gesture)?' Extended fingers use your saved hand setup or existing thresholds. Set up my hand learns open and curled positions for all five fingers.':'');
const phase=s.completed_phases,performed=phase===1,movement=!!movements[s.gesture];
const neutral='Hold your open hand comfortably at your calibrated starting position and distance, with your wrist straight and palm facing the camera. Hold for three seconds.';
const open='Open your hand comfortably: fingers and thumb gently extended, wrist straight, hand centered at the same camera distance. Do not stretch or spread forcefully. Hold for three seconds.';
const perform=movement?movements[s.gesture]+' Hold comfortably for three seconds.':s.mode==='hand_setup'?'Make a gentle fist with your thumb curled outside your fingers. Hold comfortably for three seconds.':'Perform '+s.gestures[s.gesture]+' and hold it comfortably for three seconds.';
el('tune-instruction').textContent=phase>=s.total_phases?'Recording complete. Analyze the measurements, then try the preview.':performed?perform:movement?(phase===2?'Return to your starting position and distance. Opening your fingers alone does not release this movement. ':'')+neutral:open;
el('tune-record').textContent=s.recording?'Recording…':phase>=s.total_phases?'Recordings complete':performed?(s.mode==='hand_setup'?'Record gentle fist (3 seconds)':movement?'Record movement (3 seconds)':'Record gesture (3 seconds)'):movement?(phase===0?'Record starting position (3 seconds)':'Record return to start (3 seconds)'):phase===0?'Record open hand (3 seconds)':'Record open hand again (3 seconds)';
el('tune-progress').textContent=s.error||`${phase} of ${s.total_phases} recordings complete${s.recording?' · '+s.samples+' clear samples':''}`;
el('tune-fingers').hidden=movement;
el('tune-fingers').textContent=!s.ready?'Waiting for clear hand tracking.':'Selected pose: '+Object.entries(s.finger_feedback||{}).map(([finger,f])=>`${finger}: ${f.matches?f.expected+' ✓':'not yet '+f.expected}`).join(' · ');
el('tune-live').textContent=!s.ready?'Show your whole hand clearly and wait for tracking.':s.components.map(k=>`${k}: ${Number(s.measurements[k]??0).toFixed(3)}`).join(' · ');
el('tune-record').disabled=busy||s.recording||phase>=s.total_phases||!s.ready;el('tune-calibrate').disabled=busy||!s.ready;el('tune-suggest').disabled=busy||phase!==s.total_phases;el('tune-gesture').disabled=busy||s.recording;el('tune-hand-setup').disabled=busy||s.recording;
const key=s.gesture+'-'+s.revision+'-'+JSON.stringify(s.effective);if(force||key!==fieldsKey||!el('tune-fields').children.length){fieldsKey=key;el('tune-fields').replaceChildren();for(const channel of s.components){const pair=s.preview?.[channel]||s.effective[channel];if(!pair)continue;const row=document.createElement('tr');row.dataset.channel=channel;const title=document.createElement('th');title.scope='row';title.textContent=channel;row.append(title);for(const name of ['on','off']){const label=document.createElement('td');const input=document.createElement('input');input.type='number';input.min='0';input.step='.01';input.value=pair[name];input.style.width='100px';input.oninput=()=>{row.dataset.changed='yes'};input.setAttribute('aria-label',channel+' '+name);label.append(input);row.append(label)}el('tune-fields').append(row)}}
for(const id of ['tune-preview','tune-save'])el(id).disabled=busy||!el('tune-fields').children.length;
}
async function command(action,extra={}){if(busy)return;busy=true;try{draw(await api(action,extra),true);el('tune-notice').textContent=action==='save'?'Saved for every profile.':action==='suggest'||action==='preview'?'Preview active. Try the gesture; select Save to keep these thresholds.':action==='reset'?'Selected gesture components restored to their supplied defaults.':action==='discard'?'Unsaved adjustments discarded.':''}catch(e){el('tune-notice').textContent=e.message}finally{busy=false;if(last)draw(last)}}
el('tune-switch').onchange=async()=>{enabled=el('tune-switch').checked;try{const s=await api(enabled?'begin':'end');el('tune-panel').hidden=!enabled;el('tune-thresholds').hidden=!enabled;el('practice-lessons').hidden=enabled;if(enabled)draw(s,true)}catch(e){enabled=false;el('tune-switch').checked=false;el('tune-panel').hidden=false;el('tune-notice').textContent=e.message}};
el('tune-gesture').onchange=()=>command('select',{gesture:el('tune-gesture').value});
el('tune-hand-setup').onclick=()=>command('select',{gesture:'hand_setup'});
el('tune-calibrate').onclick=()=>calibrate();
el('tune-record').onclick=()=>command('record');el('tune-suggest').onclick=()=>command('suggest');el('tune-preview').onclick=()=>command('preview',{thresholds:pairs()});el('tune-save').onclick=()=>command('save',{thresholds:pairs()});el('tune-discard').onclick=()=>command('discard');el('tune-reset').onclick=()=>{if(confirm('Restore the selected gesture components to supplied defaults across all profiles?'))command('reset')};
setInterval(async()=>{if(!enabled||polling)return;polling=true;try{const s=await api('heartbeat');if(!busy)draw(s)}catch(e){el('tune-notice').textContent=e.message;enabled=false;el('tune-switch').checked=false}finally{polling=false}},1000);
window.addEventListener('pagehide',()=>{if(enabled)fetch('/api/tuning',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'tuning'},body:JSON.stringify({action:'end',session:practiceSession}),keepalive:true}).catch(()=>{})});})();"""
