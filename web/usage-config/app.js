'use strict';
const el = id => document.getElementById(id);
let csrf = null;
let config = null;
let busy = false;
let timer = null;
const names = {disconnected:'Disconnected', client_unavailable:'Client unavailable', login_required:'Login required', waiting_for_data:'Waiting for data', connected:'Connected', stale:'Stale / offline', error:'Status unavailable'};
const details = {disconnected:'Display disconnected. Your native account is not signed out.', client_unavailable:'Install the official native client on this backend before signing in. No fake connection is substituted.', login_required:'The native client does not report a signed-in account. Use the official sign-in flow below.', waiting_for_data:'Native client reports signed in, but no usable native telemetry has arrived.', connected:'A recent native snapshot is available. This is not a new direct account-quota API fetch.', stale:'The last native snapshot is too old. Missing data is not shown as zero usage.', error:'The native client or local state could not be checked. No account state is assumed.'};

function notice(message, bad=false) { el('notice').textContent=message; el('notice').classList.toggle('error',bad); el('notice').hidden=false; }
async function api(path, body) {
  const options={credentials:'same-origin',cache:'no-store'};
  if(body!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-CSRF-Token':csrf};options.body=JSON.stringify(body);}
  const response=await fetch(path,options);
  const data=await response.json();
  if(!response.ok || data.ok===false) throw new Error(data.error || 'Backend request failed');
  return data;
}
function fillSettings(value) { config=value;el('source').value=value.source;el('refresh').value=value.refresh_seconds;el('stale').value=value.stale_seconds;el('show-reset').checked=value.show_reset_countdown;el('show-context').checked=value.show_context;el('save').disabled=false; }
function resetText(window) {
  if(!window || !config?.show_reset_countdown || !window.resets_at) return window?'Reset time unavailable':'No native snapshot';
  const seconds=Math.max(0,Math.floor(window.resets_at-Date.now()/1000));
  return 'Reset in '+Math.floor(seconds/3600)+'h '+Math.floor((seconds%3600)/60)+'m';
}
function windowMetric(prefix, value) {
  const percent=value?.used_percentage;
  const present=typeof percent==='number' && Number.isFinite(percent);
  el(prefix+'-value').textContent=present?percent.toFixed(percent%1?1:0)+'%':'—';
  el(prefix+'-bar').style.width=present?Math.max(0,Math.min(100,percent))+'%':'0%';
  el(prefix+'-reset').textContent=resetText(value);
}
function render(payload) {
  const status=payload.status;
  const login=payload.login || {state:'idle',output:'',authorization_url:null};
  el('connection-state').textContent=names[status.state] || 'Unknown';
  el('connection-state').classList.toggle('good',status.state==='connected');
  el('connection-detail').textContent=details[status.state] || 'No verified source state';
  el('native-state').textContent=!status.native.available?'Not installed':status.native.error?'Check failed':status.native.logged_in?'Reports signed in':'Not signed in';
  el('connect').disabled=busy || !status.native.available;
  el('test').disabled=busy;
  el('disconnect').disabled=busy || status.state==='disconnected';
  el('preview-state').textContent=names[status.state] || 'Data unavailable';
  windowMetric('five',status.metrics?.five_hour);
  windowMetric('seven',status.metrics?.seven_day);
  const context=status.metrics?.context_percentage;
  el('context-value').textContent=typeof context==='number'?context.toFixed(context%1?1:0)+'%':'—';
  el('context-row').hidden=!(config?.show_context || config?.source==='both' || config?.source==='session');
  el('data-age').textContent=status.received_at?'Native snapshot received '+new Date(status.received_at*1000).toLocaleString()+'. Receipt is not proof of a fresh upstream quota fetch.':'No native snapshot received. Unavailable is not zero usage.';
  const active=['starting','awaiting_native_input'].includes(login.state);
  el('native-terminal').hidden=login.state==='idle' || login.state==='cancelled';
  el('terminal-output').textContent=login.output || (login.state==='completed'?'Native command finished; checking its actual authentication status.':login.state==='timed_out'?'Native sign-in timed out. Start again.':login.state==='failed'?'The native sign-in command did not complete.':'Waiting for the native client…');
  el('native-input').disabled=!active;
  el('send-native').disabled=!active || busy;
  el('cancel-login').disabled=!active || busy;
  const url=login.authorization_url;
  let allowed=false;
  if(url){try{const parsed=new URL(url);allowed=parsed.protocol==='https:' && ['claude.com','claude.ai','platform.claude.com','console.anthropic.com'].includes(parsed.hostname) && !parsed.username && !parsed.password;}catch(_){allowed=false;}}
  el('official-sign-in').hidden=!allowed;
  if(allowed)el('official-sign-in').href=url;else el('official-sign-in').removeAttribute('href');
}
async function refresh() {
  try{render(await api('/api/status'));}catch(error){
    el('connection-state').textContent='Status unavailable';
    el('connection-state').classList.remove('good');
    el('connection-detail').textContent='The backend could not be checked. No account or data state is assumed.';
    el('native-state').textContent='Check unavailable';
    windowMetric('five',null);windowMetric('seven',null);
    el('context-value').textContent='—';el('preview-state').textContent='Source unavailable';
    el('data-age').textContent='No verified recent snapshot. Previously displayed values are withheld.';
    el('connect').disabled=true;el('send-native').disabled=true;
    el('native-input').value='';el('native-terminal').hidden=true;
    el('official-sign-in').hidden=true;el('official-sign-in').removeAttribute('href');
    notice(error.message,true);
  }
}
async function action(operation) {
  if(busy)return;
  busy=true;
  for(const id of ['connect','test','disconnect','save','send-native','cancel-login'])el(id).disabled=true;
  try{await operation();}catch(error){notice(error.message,true);}finally{busy=false;el('save').disabled=false;await refresh();}
}
el('settings-form').addEventListener('submit',event=>{event.preventDefault();action(async()=>{
  const changes={source:el('source').value,refresh_seconds:Number(el('refresh').value),stale_seconds:Number(el('stale').value),show_reset_countdown:el('show-reset').checked,show_context:el('show-context').checked};
  const result=await api('/api/config',changes);fillSettings(result.config);notice('Display settings saved. No account credentials were included.');
});});
el('connect').addEventListener('click',()=>action(async()=>{
  fillSettings((await api('/api/config',{enabled:true})).config);
  const payload=await api('/api/status');
  if(!payload.status.native.logged_in){await api('/api/auth/start',{method:el('auth-method').value,sso:el('sso').checked});notice('Official native sign-in started. Open its authorization link when it appears.');}
  else notice('Native client reports signed in. Waiting for source telemetry if none is available.');
}));
el('test').addEventListener('click',()=>action(async()=>{const result=await api('/api/test-connection',{});notice('Read-only backend check: '+(names[result.status.state] || result.status.state)+'. No model request was made.');}));
el('disconnect').addEventListener('click',()=>action(async()=>{await api('/api/disconnect',{});fillSettings((await api('/api/config')).config);notice('Display disconnected; the native account was not signed out.');}));
el('cancel-login').addEventListener('click',()=>action(async()=>{await api('/api/auth/cancel',{});el('native-input').value='';notice('Native sign-in cancelled.');}));
el('native-input-form').addEventListener('submit',event=>{event.preventDefault();action(async()=>{
  const input=el('native-input').value;
  el('native-input').value='';
  if(!input)throw new Error('The native terminal has no input to send');
  await api('/api/auth/input',{data:input+'\n'});notice('Input forwarded only to the official native client. Not saved as a device setting.');
});});
async function start() {
  try{csrf=(await api('/api/session')).csrf_token;fillSettings((await api('/api/config')).config);await refresh();timer=setInterval(()=>{if(!busy)refresh();},2000);}catch(error){notice(error.message,true);}
}
window.addEventListener('pagehide',()=>{if(timer)clearInterval(timer);el('native-input').value='';});
start();
