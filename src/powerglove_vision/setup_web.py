# Project: PowerGlove Vision
# File: src/powerglove_vision/setup_web.py
# Purpose: Present connection, pairing, and idle-display settings with recoverable browser actions.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-06 - Organize Setup and keep failed requests and unsaved fields recoverable.

"""Setup content is separate from routing so its wording and behavior are reviewable."""

SETUP_CONTENT = """<style>main a{color:var(--cyan)}#form p{margin:0}#notice:empty,#pair-notice:empty,#controller-notice:empty,#attract-notice:empty{display:none}#pairing-fields{display:grid;gap:12px}#pairing-fields p{margin:0}#pairing-fields button{justify-self:start}#pairing-fields details{width:100%}#pairing-fields details button{margin-top:12px}#connection-fields details{margin-top:16px}#attract-form button{justify-self:start}</style><h1>Setup</h1><p>Connect your PowerGlove Vision Controller to RetroPie and choose how it starts. For hand calibration, players, and backups, open <a href=/learn>Glove Academy</a>.</p>
<section class=card style="margin-bottom:14px"><h2>Connection and startup</h2><p id=paired role=status>Loading saved settings…</p><form id=form><fieldset id=connection-fields disabled style='border:0;padding:0;margin:0;min-width:0'><div class=formgrid>
<label>RetroPie hostname or IP address<input id=receiver name=receiver placeholder=RETROPIE-NAME.local autocomplete=off></label>
<label>Startup game profile<select id=profile name=profile>{{PROFILE_OPTIONS}}</select></label>
<label>Hand or glove (diagnostic label)<select id=glove_color name=glove_color><option value=none>Bare hand</option><option value=white>White glove</option><option value=black>Black glove</option></select></label>
</div><details><summary>Advanced connection settings</summary><div class=formgrid><label>Receiver UDP port<input id=port name=port type=number min=1 max=65535 required></label><label>Camera<input id=camera name=camera placeholder=auto></label></div><p>Keep port 55355 and camera auto unless your installation needs different values. The hand or glove label records your setup; it does not change recognition.</p><label class=check><input id=rotate_token type=checkbox> Replace the pairing key when saving</label><p>Replacing the key stops controller output. Pair with RetroPie again afterward.</p></details>
<div class=controls><button type=submit>Save connection settings</button><button class=secondary type=button id=test>Check console address</button></div></fieldset><p>Saving connection settings restarts tracking. Checking an address only confirms name resolution; it does not prove controller delivery.</p><p class=notice id=notice role=status aria-live=polite></p></form><button id=setup-retry type=button hidden>Reload saved settings</button></section>
<section class=card style="margin-bottom:14px"><h2>Pair with RetroPie</h2><p id=secure-note></p><label>RetroPie hostname or IP address<input id=pair-host placeholder=RETROPIE-NAME.local autocomplete=off></label><p>Use the one-time code from RetroPie, or open password pairing below.</p>
<div id=pairing-fields><label>RetroPie one-time code<input id=pair-code placeholder=ABCDE-FGHIJ-23456-7ABCD autocomplete=off></label><p>On RetroPie, run <code>sudo /opt/powerglove/bin/powerglove-pair</code> to get a code.</p><button id=pair-code-button type=button>Prepare code pairing</button>
<details><summary>Pair using an SSH password</summary><div class=formgrid><label>RetroPie username<input id=pair-user value=pi autocomplete=username></label><label>RetroPie SSH password<input id=pair-password type=password autocomplete=current-password disabled></label></div><button id=pair-ssh type=button>Prepare password pairing</button></details>
<label class=check><input id=verified type=checkbox disabled> I compared the browser certificate fingerprint with the matrix ID</label><label>Controller approval PIN<input id=device-code inputmode=numeric maxlength=6 pattern='[0-9]{6}' placeholder='Six digits shown on the matrix' autocomplete=off disabled></label></div><p id=pair-notice role=status aria-live=polite></p></section>
<section class=card style="margin-bottom:14px"><h2>Matrix attract mode</h2><form id=attract-form><label>Idle display<select id=matrix-attract><option value=on>On — full animation</option><option value=dim>Dim — gentle animation</option><option value=off>Off — connection pixels only</option></select></label><button type=submit>Save attract mode</button></form><p>Changes only the idle glove animation. Game displays, T, L, startup, errors, and pairing keep their normal brightness. Saves without restarting tracking.</p><details><summary>What the connection pixels mean</summary><p>In Off mode, three faint bottom-left pixels show: app running, console service reachable, and authenticated RetroPie response. They do not confirm Wi-Fi independently or prove that a game received input.</p></details><p id=attract-notice role=status></p></section>
<section class=card style="margin-bottom:14px"><h2>Controller and power</h2><p>Start arms controller output for a selected game. You can also control delivery from <a href=/dashboard>Dashboard</a>.</p><div class=controls><button type=button id=controller-toggle disabled>Start controller</button><button class=danger type=button id=shutdown-system>Shut down Controller</button></div><p id=controller-notice role=status aria-live=polite></p></section>"""

SETUP_SCRIPT = r"""(()=>{
const $=id=>document.getElementById(id), secure=location.protocol==='https:';
let prepared=null, connectionConfigured=false;
async function api(path,payload){
  const options=payload===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)};
  if(path==='/api/attract')options.headers['X-PowerGlove-Action']='attract';
  if(path==='/api/system/shutdown')options.headers['X-PowerGlove-Action']='shutdown';
  const response=await fetch(path,options);let result;
  try{result=await response.json()}catch(e){throw Error('The Controller returned an unreadable response. Try again.')}
  if(!response.ok)throw Error(result.error||'The request could not be completed.');
  return result;
}
async function action(button,notice,work){
  button.disabled=true;$(notice).textContent='Working…';
  try{await work()}catch(e){$(notice).textContent=e.message||'Connection lost. Try again.'}finally{button.disabled=button.id==='controller-toggle'&&!connectionConfigured}
}
async function load(updateFields=false){
  const c=await api('/api/config');
  if(updateFields){for(const k of ['receiver','port','profile','glove_color','camera'])$(k).value=c[k];$('matrix-attract').value=c.matrix_attract||'on';$('connection-fields').disabled=false;}
  if(!$('pair-host').value)$('pair-host').value=c.receiver;
  $('paired').textContent=c.connection_configured?'Connection and pairing key saved. Use pairing below if RetroPie has not received this key.':'Enter your console address and pair with RetroPie. Local play and Glove Academy work without pairing.';
  connectionConfigured=c.connection_configured;
  $('controller-toggle').disabled=!connectionConfigured;
  $('controller-toggle').textContent=c.controller_enabled?'Stop controller':'Start controller';
  $('controller-toggle').dataset.enabled=String(c.controller_enabled);
  $('controller-toggle').className=c.controller_enabled?'danger':'';
  $('setup-retry').hidden=true;
}
async function initialLoad(){$('notice').textContent='Loading saved settings…';try{await load(true);$('notice').textContent=''}catch(e){$('notice').textContent='Could not load saved settings. '+e.message;$('setup-retry').hidden=false}}
$('setup-retry').onclick=initialLoad;initialLoad();
$('secure-note').textContent=secure?'Before pairing, compare the certificate SHA-256 fingerprint in your browser with the ID on the Controller matrix. Then enter its one-time approval PIN.':'Pairing requires the secure Setup page. ';
if(!secure){const a=document.createElement('a');a.href='https://'+location.hostname+':8443/setup';a.textContent='Open secure Setup';$('secure-note').append(a)}
for(const id of ['pair-host','pair-user','pair-code','pair-ssh','pair-code-button'])$(id).disabled=!secure;
function resetPairing(){prepared=null;$('verified').checked=false;$('verified').disabled=true;$('pair-password').value='';$('pair-password').disabled=true;$('device-code').value='';$('device-code').disabled=true;$('pair-ssh').textContent='Prepare password pairing';$('pair-code-button').textContent='Prepare code pairing'}
$('pair-host').oninput=resetPairing;
$('verified').onchange=()=>{$('pair-password').disabled=!(prepared?.method==='ssh'&&$('verified').checked);if($('verified').checked)$('device-code').focus()};
$('form').onsubmit=e=>{e.preventDefault();if($('rotate_token').checked&&!confirm('Replace the pairing key and stop controller output? You must pair with RetroPie again.'))return;action(e.submitter,'notice',async()=>{
  const payload={receiver:$('receiver').value.trim(),port:Number($('port').value),profile:$('profile').value,glove_color:$('glove_color').value,camera:$('camera').value.trim(),rotate_token:$('rotate_token').checked};
  await api('/api/config',payload);$('rotate_token').checked=false;$('notice').textContent='Settings saved. Tracking is restarting.';await load(true);
})};
$('test').onclick=()=>action($('test'),'notice',async()=>{const x=await api('/api/test-connection',{receiver:$('receiver').value.trim()});$('notice').textContent=`Address resolved: ${x.receiver} → ${x.address}. Pairing and controller delivery have not been tested.`});
$('attract-form').onsubmit=e=>{e.preventDefault();action(e.submitter,'attract-notice',async()=>{await api('/api/attract',{mode:$('matrix-attract').value});$('attract-notice').textContent='Attract mode saved. Tracking was not restarted.'})};
$('controller-toggle').onclick=()=>action($('controller-toggle'),'controller-notice',async()=>{
 const enabled=$('controller-toggle').dataset.enabled!=='true',x=await api('/api/controller',{enabled});
 $('controller-notice').textContent=x.pending?'Request saved. Waiting for the tracker; the Controller will retry.':enabled?'Controller armed. Delivery begins when a game is active and tracking is ready.':'Stop request delivered to tracking.';
 await load(false);
});
$('shutdown-system').onclick=()=>{if(!confirm('Request a system halt? Controller input stops. The board may restart automatically; a disconnected website does not prove it is safe to remove power.'))return;action($('shutdown-system'),'controller-notice',async()=>{await api('/api/system/shutdown',{confirm:'SHUTDOWN'});$('controller-notice').textContent='System halt requested. The board may restart automatically; loss of this page does not confirm it is safe to remove power.'})};
async function pairing(method,button){await action(button,'pair-notice',async()=>{
 const host=$('pair-host').value.trim();
 if(!prepared||prepared.method!==method||prepared.host!==host){resetPairing();const x=await api('/api/pair/begin',{host,method});prepared={host,method};$('device-code').disabled=false;$('verified').disabled=false;button.textContent='Complete pairing';$('pair-notice').textContent=`Matrix: ID ${x.certificate_id}, then PIN. Confirm that the browser certificate SHA-256 begins ${x.certificate_id}, check the confirmation, and enter the PIN.`;return;}
 if(!$('verified').checked)throw Error('Compare the browser certificate fingerprint with the matrix ID first.');
 const payload={host,device_code:$('device-code').value};
 if(method==='ssh'){payload.username=$('pair-user').value.trim();payload.password=$('pair-password').value}else payload.code=$('pair-code').value.trim();
 try{await api('/api/pair/'+method,payload);$('pair-notice').textContent='Pairing completed. The RetroPie receiver was restarted.';if($('receiver').value.trim()!==host){$('receiver').value=host;$('pair-notice').textContent+=' Save connection settings above to use this console.';}await load(false);}finally{resetPairing();}
})}
$('pair-ssh').onclick=()=>pairing('ssh',$('pair-ssh'));
$('pair-code-button').onclick=()=>pairing('code',$('pair-code-button'));
})();"""
