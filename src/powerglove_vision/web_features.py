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
<div id=tune-panel hidden><label for=tune-gesture>Gesture</label><select id=tune-gesture></select><button id=tune-calibrate>Recalibrate neutral</button><p id=tune-components></p>
<p id=tune-instruction></p><button id=tune-record>Record baseline (3 seconds)</button><button id=tune-suggest>Analyze and preview</button>
<p id=tune-progress role=status aria-live=polite></p>
<div class=controls><button id=tune-preview>Preview adjustments</button><button id=tune-save>Save for all profiles</button><button id=tune-discard>Discard / record again</button><button id=tune-reset>Restore defaults</button></div>
<p id=tune-notice role=status aria-live=polite></p><details><summary>Preview and reset help</summary><p>Preview is temporary until saved. Reset restores only the selected components across all profiles.</p></details></div></section>"""

TUNE_THRESHOLDS = """<section class=card id=tune-thresholds hidden><h3>Gesture thresholds</h3><p id=tune-live></p><table><thead><tr><th scope=col>Gesture</th><th scope=col>Activation</th><th scope=col>Release</th></tr></thead><tbody id=tune-fields></tbody></table><p style="font-size:12px;color:var(--muted);margin-bottom:0">Activation starts the gesture. The lower release value stops it.</p></section>"""

TUNE_SCRIPT = r"""(()=>{
const el=id=>document.getElementById(id);let enabled=false,busy=false,last=null,fieldsKey='',polling=false;
async function api(action,extra={}){const r=await fetch('/api/tuning',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'tuning'},body:JSON.stringify({action,session:practiceSession,...extra})});const x=await r.json();if(!r.ok)throw Error(x.error||'Tuning request failed');return x}
function pairs(){const values={};el('tune-fields').querySelectorAll('[data-channel]').forEach(row=>{const inputs=row.querySelectorAll('input');if(!row.dataset.changed&&!last?.preview?.[row.dataset.channel])return;values[row.dataset.channel]={on:Number(inputs[0].value),off:Number(inputs[1].value)}});return values}
function draw(s,force=false){last=s;if(!el('tune-gesture').options.length)Object.entries(s.gestures).forEach(([key,label])=>el('tune-gesture').add(new Option(label,key)));el('tune-gesture').value=s.gesture;
el('tune-components').textContent='Adjusts: '+s.components.join(', ')+'. These components are shared across games and compound gestures.'+(['start','select'].includes(s.gesture)?' Extended fingers retain their current threshold unless adjusted manually.':'');
const phase=s.completed_phases,performed=phase%2===1;
el('tune-instruction').textContent=phase>=7?'Recording complete. Analyze the measurements, then try the preview.':performed?'Perform '+s.gestures[s.gesture]+' and hold it comfortably for three seconds.':'Return to your centered, relaxed hand position. Fully release the gesture and hold for three seconds.';
el('tune-record').textContent=s.recording?'Recording…':phase===0?'Record baseline (3 seconds)':performed?'Record gesture '+((phase+1)/2):'Record release '+(phase/2);
el('tune-progress').textContent=s.error||`${phase} of 7 recordings complete${s.recording?' · '+s.samples+' clear samples':''}`;
el('tune-live').textContent=!s.ready?'Show your whole hand clearly and wait for tracking.':s.components.map(k=>`${k}: ${Number(s.measurements[k]??0).toFixed(3)}`).join(' · ');
el('tune-record').disabled=busy||s.recording||phase>=7||!s.ready;el('tune-calibrate').disabled=busy||!s.ready;el('tune-suggest').disabled=busy||phase!==7;el('tune-gesture').disabled=busy||s.recording;
const key=s.gesture+'-'+s.revision+'-'+JSON.stringify(s.effective);if(force||key!==fieldsKey||!el('tune-fields').children.length){fieldsKey=key;el('tune-fields').replaceChildren();for(const channel of s.components){const pair=s.preview?.[channel]||s.effective[channel];if(!pair)continue;const row=document.createElement('tr');row.dataset.channel=channel;const title=document.createElement('th');title.scope='row';title.textContent=channel;row.append(title);for(const name of ['on','off']){const label=document.createElement('td');const input=document.createElement('input');input.type='number';input.min='0';input.step='.01';input.value=pair[name];input.style.width='100px';input.oninput=()=>{row.dataset.changed='yes'};input.setAttribute('aria-label',channel+' '+name);label.append(input);row.append(label)}el('tune-fields').append(row)}}
for(const id of ['tune-preview','tune-save'])el(id).disabled=busy||!el('tune-fields').children.length;
}
async function command(action,extra={}){if(busy)return;busy=true;try{draw(await api(action,extra),true);el('tune-notice').textContent=action==='save'?'Saved for every profile.':action==='suggest'||action==='preview'?'Preview active. Try the gesture; select Save to keep these thresholds.':action==='reset'?'Selected gesture components restored to their supplied defaults.':action==='discard'?'Unsaved adjustments discarded.':''}catch(e){el('tune-notice').textContent=e.message}finally{busy=false;if(last)draw(last)}}
el('tune-switch').onchange=async()=>{enabled=el('tune-switch').checked;try{const s=await api(enabled?'begin':'end');el('tune-panel').hidden=!enabled;el('tune-thresholds').hidden=!enabled;el('practice-lessons').hidden=enabled;if(enabled)draw(s,true)}catch(e){enabled=false;el('tune-switch').checked=false;el('tune-panel').hidden=false;el('tune-notice').textContent=e.message}};
el('tune-gesture').onchange=()=>command('select',{gesture:el('tune-gesture').value});
el('tune-calibrate').onclick=()=>calibrate();
el('tune-record').onclick=()=>command('record');el('tune-suggest').onclick=()=>command('suggest');el('tune-preview').onclick=()=>command('preview',{thresholds:pairs()});el('tune-save').onclick=()=>command('save',{thresholds:pairs()});el('tune-discard').onclick=()=>command('discard');el('tune-reset').onclick=()=>{if(confirm('Restore the selected gesture components to supplied defaults across all profiles?'))command('reset')};
setInterval(async()=>{if(!enabled||polling)return;polling=true;try{const s=await api('heartbeat');if(!busy)draw(s)}catch(e){el('tune-notice').textContent=e.message;enabled=false;el('tune-switch').checked=false}finally{polling=false}},1000);
window.addEventListener('pagehide',()=>{if(enabled)fetch('/api/tuning',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'tuning'},body:JSON.stringify({action:'end',session:practiceSession}),keepalive:true}).catch(()=>{})});})();"""
