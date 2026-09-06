# Project: PowerGlove Vision
# File: src/powerglove_vision/player_web.py
# Purpose: Provide player selection, persistent Academy progress, and hand-setting backups.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-06 - Add complete hand-setup backups and explicit calibration restoration.
#   2026-09-06 - Add player controls and bounded backup import/export.

"""Browser controls share the Academy's session state without exposing credentials."""

PLAYER_CONTENT = """<style>.player-card .check{display:flex;align-items:center;gap:12px;min-height:44px}.player-card .check input{flex:0 0 20px;width:20px;height:20px;margin:0}</style><section class="card player-card" aria-labelledby=player-heading>
<h2 id=player-heading>Your player</h2><div class=player-row><label>Active player<select id=player-select disabled></select></label><button id=player-use type=button>Use player</button><button id=player-center type=button>Set this as my center</button></div>
<p id=player-notice role=status aria-live=polite>Loading saved progress…</p>
<details><summary>Players and hand-setup backups</summary><p>New players start with the current sensitivity and their own lesson progress. Switching players pauses controls until you set your center again.</p>
<label>Player name<input id=player-name maxlength=32 autocomplete=off placeholder="Player name"></label>
<div class=controls><button id=player-create type=button>Add player</button><button id=player-rename type=button>Rename current</button><button id=player-delete type=button>Delete current</button></div>
<p>Backups include your name, saved sensitivity adjustments, and current calibration. Unchanged sensitivity uses the supplied defaults. Pairing credentials, Wi-Fi settings, and lesson progress are excluded. Reuse calibration only with the same camera position and playing position; otherwise set a fresh center.</p>
<div class=controls><button id=player-export type=button>Back up hand setup</button><label class=button for=player-import>Restore hand setup</label><input id=player-import type=file accept=".json,application/json" hidden></div><div id=restore-review hidden><p id=restore-description></p><label class=check><input id=restore-reuse type=checkbox> My camera position and playing position match this backup; reuse its calibration.</label><p>Leave unchecked to restore sensitivity and set a fresh center. The current player's Academy progress is kept. Controller output stays paused until you explicitly start it.</p><div class=controls><button id=restore-confirm type=button>Restore this setup</button><button id=restore-cancel type=button>Cancel</button></div></div></details></section>"""

PLAYER_SCRIPT = r"""(()=>{
let context=null,busy=false,loading=false,pending=null,saving=null,listKey='',importBackup=null,importIdentity=null;
const el=id=>document.getElementById(id);
const notice=text=>{el('player-notice').textContent=text};
async function api(action,extra={}){const r=await fetch('/api/players',{method:'POST',headers:{'Content-Type':'application/json','X-PowerGlove-Action':'players'},body:JSON.stringify({action,player:context?.active,generation:context?.generation,...extra}),keepalive:action==='progress'});const s=await r.json();if(!r.ok)throw Error(s.error||'Player request failed.');return s}
function apply(s,restore=false){if(!s||!Array.isArray(s.players)||!s.progress)throw Error('Player settings are unavailable.');const changed=!context||s.active!==context.active||s.generation!==context.generation;context=s;const key=JSON.stringify(s.players);if(key!==listKey){el('player-select').replaceChildren(...s.players.map(p=>new Option(p.name,p.id)));listKey=key;el('player-select').value=s.active}if(changed||restore)el('player-select').value=s.active;el('player-select').disabled=false;if(changed||restore){beginTransition();completed=new Set(s.progress.completed);index=s.progress.lesson;trainingComplete=completed.size===lessons.length;pending=null;draw()}else{for(const n of s.progress.completed)completed.add(n);if(completed.size===lessons.length&&!trainingComplete){beginTransition();trainingComplete=true;draw()}}playerReady=!s.error;el('player-center').hidden=!s.needs_center||s.restoring_calibration;notice(s.error||(s.restoring_calibration?'Applying restored calibration; controller output is paused.':s.needs_center?'Player ready. Set your center before starting controller output.':trainingComplete?'Glove Master saved. Your award will be here when you return.':'Progress saves automatically on this Controller.'));}
async function load(){if(loading||busy||saving)return;loading=true;try{apply(await api('read'))}catch(e){playerReady=false;notice(e.message+' Retrying…')}finally{loading=false}}
function save(){if(!context||!playerReady||busy)return;pending={course:1,completed:[...completed],lesson:index};flush()}
function flush(){if(saving||!pending)return saving;const value=pending;pending=null;saving=api('progress',{progress:value}).then(s=>{if(context&&s.active===context.active&&s.generation===context.generation)context=s}).catch(e=>{playerReady=false;notice('Progress could not be saved. '+e.message)}).finally(()=>{saving=null;if(pending&&playerReady)flush()});return saving}
window.saveAcademyProgress=save;
window.playerIdentity=()=>context?{player:context.active,generation:context.generation}:{};
async function command(action,extra={}){if(busy)return;busy=true;playerReady=false;try{while(saving)await saving;pending=null;apply(await api(action,extra),true);return true}catch(e){notice(e.message);playerReady=!!context&&!context.error;return false}finally{busy=false}}
window.resetAcademyProgress=()=>command('reset_progress');
el('player-use').onclick=()=>command('select',{id:el('player-select').value});
el('player-create').onclick=()=>command('create',{name:el('player-name').value});
el('player-rename').onclick=()=>command('rename',{name:el('player-name').value});
el('player-delete').onclick=()=>{if(confirm('Delete this player, their sensitivity settings, and Academy progress?'))command('delete')};
el('player-center').onclick=calibrate;
el('player-export').onclick=async()=>{try{const s=await api('export');const blob=new Blob([JSON.stringify(s.backup,null,2)+'\n'],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='powerglove-hand-setup.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){notice(e.message)}};
el('player-import').onchange=async()=>{const file=el('player-import').files?.[0];if(!file)return;try{if(file.size>8192)throw Error('Choose a hand-setup JSON file smaller than 8 KB.');const backup=JSON.parse(await file.text());if(!backup||typeof backup!=='object')throw Error('Choose a hand-setup backup.');importBackup=backup;importIdentity={player:context?.active,generation:context?.generation};const complete=backup.format==='powerglove-hand-setup'&&backup.version===2,hasCalibration=complete&&backup.calibration!=null;el('restore-description').textContent='Restore '+(typeof backup.name==='string'?backup.name:'this backup')+' to the current player: replace sensitivity'+(complete?' and player name':'')+'. '+(hasCalibration?'A saved calibration is available.':'No saved calibration is included; set a fresh center.');el('restore-reuse').checked=false;el('restore-reuse').disabled=!hasCalibration;el('restore-review').hidden=false}catch(e){notice(e.message)}finally{el('player-import').value=''}};
el('restore-confirm').onclick=async()=>{if(!importBackup)return;const ok=await command('restore',{backup:importBackup,...importIdentity,reuse_calibration:el('restore-reuse').checked});if(ok){importBackup=null;el('restore-review').hidden=true}};
el('restore-cancel').onclick=()=>{importBackup=null;el('restore-review').hidden=true};
window.addEventListener('pagehide',()=>{if(pending&&!saving)flush()});
load();setInterval(load,2000);
})();"""
