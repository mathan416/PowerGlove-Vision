# Project: PowerGlove Vision
# File: src/powerglove_vision/setup_web.py
# Purpose: Present connection, pairing, and idle-display settings with recoverable browser actions.
# Author: Iain Bennett
# Copyright (c) 2026 Iain Bennett
# SPDX-License-Identifier: MIT
# Full history: docs/CHANGELOG.md and Git history.
# Change log:
#   2026-09-07 - Added advanced camera reader and exposure choices.
#   2026-09-06 - Implement approved player and connectivity refinements.
#   2026-09-06 - Organize Setup and keep failed requests and unsaved fields recoverable.

"""Setup content is separate from routing so its wording and behavior are reviewable."""

SETUP_CONTENT = """<style>main a{color:var(--cyan)}#players{margin-bottom:14px}#form p{margin:0}#notice:empty,#pair-notice:empty,#attract-notice:empty{display:none}#connection-fields details{margin-top:16px}#attract-form button{justify-self:start}.connection-indicators{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;list-style:none;padding:0;margin:0}.connection-indicators li{display:flex;gap:10px;align-items:flex-start;padding:12px;border:1px solid var(--line);border-radius:10px;min-width:0}.connection-indicators .check-dot{flex:0 0 12px;width:12px;height:12px;border-radius:50%;background:#8992a8;margin-top:5px}.connection-indicators [data-state=good] .check-dot{background:var(--green)}.connection-indicators [data-state=bad] .check-dot{background:#ff737c}.connection-indicators strong{display:block;font-size:14px;margin-top:4px}.connection-indicators .check-label{font-size:12px;color:var(--muted)}.setup-summary{display:flex;flex-wrap:wrap;gap:10px 24px;margin:16px 0 0}.setup-summary div{min-width:0}.setup-summary dt{font-size:12px;color:var(--muted)}.setup-summary dd{margin:2px 0 0;overflow-wrap:anywhere}.setup-status-note{color:var(--muted);font-size:12px;margin-bottom:0}@media(max-width:850px){.connection-indicators{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:360px){.connection-indicators{gap:8px}.connection-indicators li{padding:8px;gap:6px}}#pairing-section [hidden]{display:none!important}#pairing-section fieldset{border:0;padding:0;margin:12px 0}#pairing-section legend{font-weight:bold;margin-bottom:8px}.pair-choice{display:flex;align-items:flex-start;gap:12px;padding:14px;border:1px solid var(--line);border-radius:10px;margin-bottom:10px}.pair-choice input{width:auto;margin-top:5px}.pair-progress{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;padding-left:0;list-style-position:inside;color:var(--muted);font-size:13px}.pair-progress li{padding:8px 0;border-bottom:1px solid var(--line)}.pair-progress [aria-current=step]{color:var(--cyan);font-weight:bold}.pair-destination{overflow-wrap:anywhere}#pair-change{margin-left:12px}#pairing-section pre{white-space:pre-wrap;overflow-wrap:anywhere}#pair-timer{color:var(--cyan)}#pair-notice{padding:14px;border:1px solid var(--cyan);border-radius:10px}#pairing-section h3:focus,#pair-notice:focus{outline:2px solid var(--cyan);outline-offset:4px}</style><h1>Setup</h1><p>Connect your PowerGlove Vision Controller to RetroPie and choose how it starts. For hand calibration, players, and backups, open <a href=/learn>Glove Academy</a>.</p>
<section class=card style="margin-bottom:14px" aria-labelledby=connection-status-title><h2 id=connection-status-title>Controller status</h2><ul class=connection-indicators aria-label="Connection checks in matrix pixel order" aria-live=polite>
<li id=status-app data-state=unknown><span class=check-dot aria-hidden=true></span><div><span class=check-label>1 · Controller app</span><strong>Checking…</strong></div></li>
<li id=status-console data-state=unknown><span class=check-dot aria-hidden=true></span><div><span class=check-label>2 · Console service</span><strong>Checking…</strong></div></li>
<li id=status-auth data-state=unknown><span class=check-dot aria-hidden=true></span><div><span class=check-label>3 · Authenticated response</span><strong>Checking…</strong></div></li>
<li id=status-wifi data-state=unknown><span class=check-dot aria-hidden=true></span><div><span class=check-label>4 · Networking</span><strong id=wifi-status>Checking…</strong></div></li></ul>
<dl class=setup-summary><div><dt>Tracking</dt><dd id=status-tracking>Checking…</dd></div><div><dt>Controller output</dt><dd id=status-output>Checking…</dd></div><div><dt>Saved console</dt><dd id=status-destination>Loading…</dd></div></dl>
<p class=setup-status-note id=connection-status-note>These checks match the four Off-mode pixels. They do not confirm that a game received input.</p></section>
{{PLAYER_CONTENT}}
<section class=card style="margin-bottom:14px"><h2>Matrix attract mode</h2><form id=attract-form><label>Idle display<select id=matrix-attract><option value=on>On — full animation</option><option value=dim>Dim — gentle animation</option><option value=off>Off — connection pixels only</option></select></label><button type=submit>Save attract mode</button></form><p>Changes only the idle glove animation. Game displays, T, L, startup, errors, and pairing keep their normal brightness. Saves without restarting tracking.</p><details><summary>What the connection pixels mean</summary><p>In Off mode, four faint bottom-left pixels show: app running, console service reachable, authenticated RetroPie response, and a Wi-Fi or Ethernet link connected. The Networking pixel comes from the Controller’s physical network links, including Ethernet through a USB dock, independently of RetroPie. It does not confirm an IP address or Internet access. These indicators do not prove that a game received input.</p></details><p id=attract-notice role=status></p></section>
<section id=connection-section class=card style="margin-bottom:14px"><h2>Connection and startup</h2><p id=paired role=status>Loading saved settings…</p><form id=form><fieldset id=connection-fields disabled style='border:0;padding:0;margin:0;min-width:0'><div class=formgrid>
<label>RetroPie hostname or IP address<input id=receiver name=receiver placeholder=RETROPIE-NAME.local autocomplete=off></label>
<label>Startup game profile<select id=profile name=profile>{{PROFILE_OPTIONS}}</select></label>
<label>Hand or glove (diagnostic label)<select id=glove_color name=glove_color><option value=none>Bare hand</option><option value=white>White glove</option><option value=black>Black glove</option></select></label>
</div><details><summary>Advanced connection and camera settings</summary><div class=formgrid><label>Receiver UDP port<input id=port name=port type=number min=1 max=65535 required></label><label>Camera<input id=camera name=camera placeholder=auto></label><label>Camera frame rate<select id=camera_fps name=camera_fps><option value=auto>Automatic — prefer 30 fps</option><option value=30>30 fps</option><option value=60>60 fps</option></select></label><label>Camera reader<select id=camera_backend name=camera_backend><option value=opencv>Compatible — OpenCV</option><option value=direct-v4l2>Low latency — Direct V4L2</option></select></label><label>Exposure behavior<select id=camera_exposure name=camera_exposure><option value=auto>Automatic — no camera changes</option><option value=low-latency>Low latency — standard UVC</option><option value=kiyo-low-latency>Razer Kiyo Pro — tested low latency</option></select></label></div><p>Keep port 55355 and camera auto unless your installation needs different values. Direct V4L2 uses the newest Linux camera buffer and automatically falls back to OpenCV if the camera or format is unsupported. Low latency keeps automatic exposure but disables variable frame-rate exposure only when the camera advertises that standard control. The Kiyo Pro choice also requests the tested volatile HDR-off mode; repower the camera to restore its hardware defaults.</p><p class=setup-status-note id=camera-rate-status role=status>Actual camera behavior appears while tracking is active.</p><label class=check><input id=rotate_token type=checkbox> Replace the pairing key when saving</label><p>Replacing the key stops controller output. Pair with RetroPie again afterward.</p></details>
<div class=controls><button type=submit>Save settings</button><button class=secondary type=button id=test>Check console address</button></div></fieldset><p>Saving connection settings restarts tracking. Checking an address only confirms name resolution; it does not prove controller delivery.</p><p class=notice id=notice role=status aria-live=polite></p></form><button id=setup-retry type=button hidden>Reload saved settings</button></section>
<section id=pairing-section class=card style="margin-bottom:14px" aria-labelledby=pair-title><h2 id=pair-title>Pair with RetroPie</h2>
<p id=secure-note></p>
<div id=pair-wizard hidden>
<p class=pair-destination>Saved console: <strong id=pair-destination>Loading…</strong> <a id=pair-change href=#connection-section>Change</a></p>
<p id=pair-prerequisite role=status></p>
<ol class=pair-progress aria-label="Pairing steps"><li id=pair-progress-1>Choose a method</li><li id=pair-progress-2>Confirm your Controller</li><li id=pair-progress-3>Pair with RetroPie</li></ol>
<p id=pair-summary></p><p id=pair-timer role=timer aria-live=off hidden></p>
<div id=pair-step-1><h3 id=pair-heading-1 tabindex=-1>1. Choose a pairing method</h3>
<fieldset id=pair-methods><legend>How will you connect?</legend>
<label class=pair-choice><input type=radio name=pair-method value=code checked><span><strong>One-time code (recommended)</strong><br>Run a command on RetroPie and enter the code it displays.</span></label>
<label class=pair-choice><input type=radio name=pair-method value=ssh><span><strong>SSH password</strong><br>Use your RetroPie username and password. SSH password login must be enabled.</span></label></fieldset>
<button id=pair-begin type=button>Continue</button></div>
<div id=pair-step-2 hidden><h3 id=pair-heading-2 tabindex=-1>2. Confirm your Controller</h3>
<p id=pair-confirmation>Start confirmation to display the matrix ID and approval PIN.</p>
<details><summary>How to compare the certificate</summary><p>Open the browser’s connection or security details for this page, then view its certificate and find the SHA-256 fingerprint. Compare its beginning with the ID displayed on the Controller matrix. Ignore spaces, colons, and letter case. Use the physical matrix as your reference, not just the ID shown on this page.</p><p>In Safari, open the website’s connection details and choose Show Certificate. In Chrome or Edge, use the site controls beside the address, open connection information, then the certificate viewer. The labels vary by browser version.</p><p>If the values differ, stop pairing. Do not enter your PIN, RetroPie code, or password.</p></details>
<fieldset id=pair-confirm-fields disabled><label class=check><input id=verified type=checkbox> I compared the browser certificate fingerprint with the matrix ID and they match</label>
<label>Controller approval PIN<input id=device-code inputmode=numeric maxlength=6 pattern="[0-9]{6}" autocomplete=off placeholder="Six digits shown on the Controller matrix"></label></fieldset>
<div class=controls><button id=pair-confirm-next type=button disabled>Continue</button><button id=pair-restart type=button hidden>Start a new confirmation</button><button id=pair-method-back type=button class=secondary hidden>Change pairing method</button></div></div>
<div id=pair-step-3 hidden><h3 id=pair-heading-3 tabindex=-1>3. Pair with RetroPie</h3>
<fieldset id=pair-credentials disabled>
<div id=pair-code-fields><p>On RetroPie, open a terminal and run:</p><pre><code>sudo /opt/powerglove/bin/powerglove-pair</code></pre><label>RetroPie one-time code<input id=pair-code autocomplete=off placeholder=ABCDE-FGHIJ-23456-7ABCD></label><p>This code comes from RetroPie. It is different from the six-digit Controller approval PIN.</p></div>
<div id=pair-ssh-fields hidden><div class=formgrid><label>RetroPie username<input id=pair-user value=pi autocomplete=username></label><label>RetroPie SSH password<input id=pair-password type=password autocomplete=off disabled></label></div><p>Your password is used for this pairing request and is not saved by the Controller.</p></div>
</fieldset><div class=controls><button id=pair-submit type=button disabled>Pair with RetroPie</button><button id=pair-review type=button class=secondary>Review Controller confirmation</button></div></div>
<div id=pair-pending hidden><h3 id=pair-pending-heading tabindex=-1>Pairing in progress</h3><p>Sending the pairing request to RetroPie. Keep this page open while we wait for its response.</p><p>SSH pairing can take a few minutes. Pairing does not start controller output.</p></div>
<div id=pair-success hidden><h3 id=pair-success-heading tabindex=-1>Pairing complete</h3><p>The RetroPie receiver was restarted. The matrix resumes its normal display; when idle, it follows your attract setting. Open Dashboard to start controller output when you are ready. Pairing does not verify that a game received input.</p><a class=button href=/dashboard>Open Dashboard</a></div>
<p id=pair-notice role=status aria-live=polite aria-atomic=true tabindex=-1></p></div></section>"""

SETUP_SCRIPT = r"""(()=>{
const $=id=>document.getElementById(id), secure=location.protocol==='https:';
let prepared=null, savedConfig=null, settingsBusy=false, pairingBusy=false;
let pairStep=1, lockedUntil=0, retryConfirmation=false;
const settingsFields=['receiver','port','profile','glove_color','camera','camera_fps','camera_backend','camera_exposure'];
async function api(path,payload,timeoutMs=0){
  const options=payload===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)};
  if(path==='/api/attract')options.headers['X-PowerGlove-Action']='attract';
  const controller=timeoutMs?new AbortController():null;
  const timer=controller?setTimeout(()=>controller.abort(),timeoutMs):null;
  if(controller)options.signal=controller.signal;
  try{const response=await fetch(path,options);let result;
  try{result=await response.json()}catch(e){throw Error('The Controller returned an unreadable response. Try again.')}
  if(!response.ok)throw Error(result.error||'The request could not be completed.');
  return result;}finally{if(timer!==null)clearTimeout(timer)}
}
async function action(button,notice,work){
  button.disabled=true;$(notice).textContent='Working…';
  try{await work()}catch(e){$(notice).textContent=e.message||'Connection lost. Try again.'}finally{button.disabled=false}
}
async function load(updateFields=false){
  const c=await api('/api/config');
  if(updateFields){for(const k of settingsFields)$(k).value=String(c[k]??'');$('matrix-attract').value=c.matrix_attract||'on';$('connection-fields').disabled=false;}
  $('paired').textContent=c.connection_configured?'Connection and pairing key saved. Use pairing below if RetroPie has not received this key.':'Enter your console address and pair with RetroPie. Local play and Glove Academy work without pairing.';
  $('status-destination').textContent=c.receiver||'Not configured';
  savedConfig=c;
  renderPairing();
  $('setup-retry').hidden=true;
}
async function initialLoad(){$('notice').textContent='Loading saved settings…';try{await load(true);$('notice').textContent=''}catch(e){$('notice').textContent='Could not load saved settings. '+e.message;$('setup-retry').hidden=false}}
$('setup-retry').onclick=initialLoad;initialLoad();
function indicator(id,state,label){const item=$(id);item.dataset.state=state;item.querySelector('strong').textContent=label}
async function refreshStatus(){
  if(document.hidden)return;
  const [connections,worker]=await Promise.allSettled([api('/api/connection-status',undefined,3500),api('/status',undefined,3500)]);
  if(connections.status==='fulfilled'){
    const c=connections.value,unknown=c.console_configured?'Checking…':'Not configured';
    indicator('status-app','good','Running');
    indicator('status-console',c.console_service===true?'good':c.console_service===false?'bad':'unknown',c.console_service===true?'Reachable':c.console_service===false?'Unreachable':unknown);
    indicator('status-auth',c.console_authenticated===true?'good':c.console_authenticated===false?'bad':'unknown',c.console_authenticated===true?'Confirmed':c.console_authenticated===false?'Not confirmed':unknown);
    indicator('status-wifi',c.networking==='connected'?'good':c.networking==='disconnected'?'bad':'unknown',({connected:'Connected',disconnected:'Disconnected',unavailable:'Unavailable'}[c.networking]||'Unavailable'));
    $('connection-status-note').textContent='Same order as the four Off-mode pixels. Green: confirmed; red: disconnected or not confirmed; grey: unknown. '+(c.checked_seconds_ago==null?'Console check pending. ':'Console checked '+Math.round(c.checked_seconds_ago)+' seconds ago. ')+'These checks do not confirm that a game received input.';
  }else{
    indicator('status-app',worker.status==='fulfilled'?'good':'bad',worker.status==='fulfilled'?'Running':'Check failed');
    for(const id of ['status-console','status-auth','status-wifi'])indicator(id,'unknown','Unavailable');
    $('connection-status-note').textContent='Could not refresh connection checks. Retrying automatically; no settings were changed.';
  }
  if(worker.status==='fulfilled'){
    const w=worker.value;
    $('status-tracking').textContent=({active:'Active',starting:'Starting',idle:'Idle',error:'Needs attention'}[w.vision_state]||(w.worker_running?'Starting':'Unavailable'));
    $('status-output').textContent=w.controller_request_pending?'Request pending':w.practice_mode?'Paused for practice':w.controller_enabled?'Armed':'Stopped';
    const actual=Number(w.camera_fps),requested=w.camera_fps_requested;
    const backend=w.capture_backend==='direct-v4l2'?'Direct V4L2':w.capture_backend==='opencv'?'OpenCV':'—',fallback=w.capture_backend_fallback?` Direct mode fell back safely: ${w.capture_backend_fallback}.`:'';
    const exposure=w.camera_exposure_mode==='auto'?'automatic exposure':w.camera_exposure_applied?'low-latency exposure applied':'low-latency exposure unavailable';
    $('camera-rate-status').textContent=(Number.isFinite(actual)&&actual>0?(requested!=='auto'&&Number(requested)!==actual?`Requested ${requested} fps; this camera is delivering ${actual} fps.`:`Camera is delivering ${actual} fps.`):'Camera rate is unavailable.')+` Reader: ${backend}; ${exposure}.`+fallback;
  }else{$('status-tracking').textContent='Unavailable';$('status-output').textContent='Unavailable'}
}
async function statusLoop(){try{await refreshStatus()}finally{setTimeout(statusLoop,5000)}}statusLoop();
function method(){return document.querySelector('input[name="pair-method"]:checked').value}
function methodLabel(){return method()==='ssh'?'SSH password':'One-time code'}
function dirtySettings(){return !savedConfig||settingsFields.some(k=>String($(k).value).trim()!==String(savedConfig[k]))||$('rotate_token').checked}
function windowActive(){return performance.now()<lockedUntil}
function validConfirmation(){return !!prepared&&windowActive()&&$('verified').checked&&/^[0-9]{6}$/.test($('device-code').value)}
function clearSecrets(){for(const id of ['device-code','pair-code','pair-password'])$(id).value='';$('verified').checked=false}
function focusPairing(id){$(id).focus();$(id).scrollIntoView({block:'center'})}
function pairNotice(message,focus=false){$('pair-notice').textContent=message;if(focus)focusPairing('pair-notice')}
function moveTo(step){pairStep=step;renderPairing();focusPairing(step===4?'pair-success-heading':'pair-heading-'+step)}
function renderPairing(){
 const active=windowActive(),blocked=!savedConfig?.connection_configured||dirtySettings()||settingsBusy;
 $('pair-destination').textContent=savedConfig?.receiver||'Not configured';
 $('pair-prerequisite').textContent=!savedConfig?'Load your saved settings before pairing.':!savedConfig.connection_configured?'Enter your console address above and select Save settings before pairing.':dirtySettings()?'You have unsaved changes. Select Save settings above before pairing.':'';
 $('pair-change').hidden=active||pairingBusy;
 $('connection-fields').disabled=!savedConfig||active||pairingBusy||settingsBusy;
 $('pair-methods').disabled=!secure||active||pairingBusy||blocked;
 for(let n=1;n<=3;n++){$('pair-step-'+n).hidden=pairStep!==n||(n===3&&pairingBusy);$('pair-progress-'+n).toggleAttribute('aria-current',pairStep===n);if(pairStep===n)$('pair-progress-'+n).setAttribute('aria-current','step')}
 $('pair-success').hidden=pairStep!==4;
 $('pair-pending').hidden=!(pairingBusy&&pairStep===3);
 $('pair-summary').textContent=pairStep>1?(savedConfig?.receiver||'Not configured')+' · '+methodLabel()+(pairStep>=3?' · Controller confirmation entered':''):'';
 $('pair-timer').hidden=!active||pairStep===4||pairingBusy;
 if(active)$('pair-timer').textContent='Confirmation window: '+Math.ceil((lockedUntil-performance.now())/1000)+' seconds remaining. Console and method are fixed until it ends.';
 $('pair-begin').disabled=!secure||blocked||pairingBusy;
 $('pair-confirm-fields').disabled=!prepared||!active||pairingBusy;
 $('pair-confirm-next').hidden=retryConfirmation;
 $('pair-confirm-next').disabled=!validConfirmation()||pairingBusy||blocked;
 $('pair-restart').hidden=!retryConfirmation;
 $('pair-restart').disabled=pairingBusy||blocked;
 $('pair-method-back').hidden=!retryConfirmation||active;
 $('pair-method-back').disabled=pairingBusy;
 $('pair-credentials').disabled=pairStep!==3||!validConfirmation()||pairingBusy;
 $('pair-password').disabled=method()!=='ssh'||pairStep!==3||!validConfirmation()||pairingBusy;
 $('pair-code-fields').hidden=method()!=='code';$('pair-ssh-fields').hidden=method()!=='ssh';
 $('pair-submit').disabled=pairStep!==3||!validConfirmation()||blocked||pairingBusy;
 const submitLabel=pairingBusy&&pairStep===3?'Pairing…':'Pair with RetroPie';
 if($('pair-submit').textContent!==submitLabel)$('pair-submit').textContent=submitLabel;
 $('pair-review').disabled=pairingBusy;
 // Keep the live status outside any aria-busy region so progress is announced immediately.
}
function expirePairing(){
 if(pairingBusy)return;
 if(prepared&&!windowActive()){
  prepared=null;clearSecrets();retryConfirmation=true;
  $('pair-notice').textContent='Controller confirmation expired. Start a new confirmation to try again.';moveTo(2);
 }else renderPairing();
}
async function beginPairing(){
 if(pairingBusy||settingsBusy||!secure||!savedConfig?.connection_configured||dirtySettings())return;
 pairingBusy=true;clearSecrets();prepared=null;renderPairing();$('pair-notice').textContent='Displaying the Controller ID and PIN…';
 const host=savedConfig.receiver,chosen=method();
 try{
  const started=performance.now(),x=await api('/api/pair/begin',{host,method:chosen});
  if(!Number.isFinite(x.expires_in)||x.expires_in<=0||!x.certificate_id)throw Error('Confirmation is unavailable. Try again.');
  lockedUntil=started+x.expires_in*1000;prepared={host,method:chosen};retryConfirmation=false;
  $('pair-confirmation').textContent='The Controller matrix shows ID '+x.certificate_id+', then a six-digit approval PIN. Compare the browser certificate with the physical matrix before entering that PIN.';
  $('pair-notice').textContent='';moveTo(2);
 }catch(e){retryConfirmation=pairStep===2;$('pair-notice').textContent=e.message||'Could not start confirmation. Try again.'}
 finally{pairingBusy=false;expirePairing()}
}
$('secure-note').textContent=secure?'Pair this Controller with your saved RetroPie console. Both methods use a physical confirmation on the Controller matrix.':'Pairing requires the secure Setup page.';
$('pair-wizard').hidden=!secure;
if(!secure){const a=document.createElement('a');a.href='https://'+location.hostname+':8443/setup';a.textContent='Open secure Setup';a.className='button';$('secure-note').append(' ',a)}
$('pair-change').onclick=()=>{$('receiver').focus()};
for(const id of settingsFields.concat('rotate_token'))$(id).addEventListener('input',()=>{if(pairStep===4){pairStep=1;clearSecrets()}renderPairing()});
for(const el of document.querySelectorAll('input[name="pair-method"]'))el.onchange=()=>{clearSecrets();renderPairing()};
$('pair-begin').onclick=beginPairing;$('pair-restart').onclick=beginPairing;
$('pair-method-back').onclick=()=>{if(!windowActive()&&!pairingBusy){retryConfirmation=false;clearSecrets();moveTo(1)}};
$('verified').onchange=()=>{if(!$('verified').checked)$('pair-password').value='';renderPairing();if($('verified').checked)$('device-code').focus()};
for(const id of ['device-code','pair-code','pair-user','pair-password'])$(id).oninput=()=>{if(pairStep===3)pairNotice('');renderPairing()};
$('pair-confirm-next').onclick=()=>{if(validConfirmation()){moveTo(3);$(method()==='ssh'?'pair-password':'pair-code').focus()}};
$('pair-review').onclick=()=>{if(!pairingBusy){$('pair-password').value='';moveTo(2)}};
$('pair-submit').onclick=async()=>{
 if($('pair-submit').disabled||pairingBusy||!validConfirmation()||dirtySettings())return;
 const chosen=prepared.method;
 if(chosen==='code'&&!$('pair-code').value.trim()){pairNotice('Enter the RetroPie one-time code from the command shown above, then select Pair with RetroPie.',true);return}
 if(chosen==='ssh'&&(!$('pair-user').value.trim()||!$('pair-password').value)){pairNotice('Enter your RetroPie username and SSH password, then select Pair with RetroPie.',true);return}
 const payload={host:prepared.host,device_code:$('device-code').value};
 if(chosen==='ssh'){payload.username=$('pair-user').value.trim();payload.password=$('pair-password').value}else payload.code=$('pair-code').value.trim();
 pairingBusy=true;renderPairing();pairNotice('Pairing in progress. Waiting for RetroPie…');focusPairing('pair-pending-heading');
 try{const result=await api('/api/pair/'+chosen,payload);if(result.paired!==true)throw Error('The Controller did not confirm pairing.');prepared=null;lockedUntil=0;clearSecrets();$('pair-notice').textContent='Pairing complete. The RetroPie receiver was restarted.';moveTo(4)}
 catch(e){prepared=null;clearSecrets();retryConfirmation=true;$('pair-notice').textContent=(e.message||'Connection lost. Pairing could not be confirmed.')+' Start a new Controller confirmation before retrying.';moveTo(2);focusPairing('pair-notice')}
 finally{payload.password='';payload.code='';payload.device_code='';pairingBusy=false;expirePairing()}
};
window.addEventListener('pagehide',()=>{clearSecrets();prepared=null;retryConfirmation=true;pairStep=2});
window.addEventListener('pageshow',()=>{expirePairing()});
setInterval(expirePairing,500);
$('form').onsubmit=e=>{e.preventDefault();if(settingsBusy||pairingBusy||windowActive())return;if($('rotate_token').checked&&!confirm('Replace the pairing key and stop controller output? You must pair with RetroPie again.'))return;settingsBusy=true;action(e.submitter,'notice',async()=>{
 try{const payload={receiver:$('receiver').value.trim(),port:Number($('port').value),profile:$('profile').value,glove_color:$('glove_color').value,camera:$('camera').value.trim(),camera_fps:$('camera_fps').value,camera_backend:$('camera_backend').value,camera_exposure:$('camera_exposure').value,rotate_token:$('rotate_token').checked};
 renderPairing();await api('/api/config',payload);$('rotate_token').checked=false;$('notice').textContent='Settings saved. Tracking is restarting.';await load(true);
 }finally{settingsBusy=false;renderPairing()}
})};
$('test').onclick=()=>action($('test'),'notice',async()=>{const x=await api('/api/test-connection',{receiver:$('receiver').value.trim()});$('notice').textContent=`Address resolved: ${x.receiver} → ${x.address}. Pairing and controller delivery have not been tested.`});
$('attract-form').onsubmit=e=>{e.preventDefault();action(e.submitter,'attract-notice',async()=>{await api('/api/attract',{mode:$('matrix-attract').value});$('attract-notice').textContent='Attract mode saved. Tracking was not restarted.'})};
renderPairing();
})();"""


from .player_web import PLAYER_CONTENT, PLAYER_SCRIPT

SETUP_CONTENT = SETUP_CONTENT.replace("{{PLAYER_CONTENT}}", PLAYER_CONTENT)
SETUP_SCRIPT += "\n" + PLAYER_SCRIPT

from .joystick_web import JOYSTICK_CONTENT, JOYSTICK_SCRIPT

SETUP_CONTENT += JOYSTICK_CONTENT
SETUP_SCRIPT += "\n" + JOYSTICK_SCRIPT
