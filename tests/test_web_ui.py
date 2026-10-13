"""Fast UI regression using a test-only DOM/HTTP fixture, not real account data.

Actual Chromium desktop/mobile and native initiation checks are retained separately.
"""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_browser_script_preserves_zero_but_clears_values_on_backend_failure():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is not installed; real-browser checks remain separate')
    code = r'''
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const fields=new Map();
function field(id){if(!fields.has(id))fields.set(id,{textContent:'',value:'',checked:false,hidden:false,disabled:false,style:{},classList:{toggle(){},add(){},remove(){}},addEventListener(){},removeAttribute(){}});return fields.get(id);}
const config={enabled:true,source:'account_quota',refresh_seconds:30,stale_seconds:180,show_reset_countdown:true,show_context:false};
const status={status:{state:'waiting_for_data',native:{available:true,logged_in:true,method:'claude.ai'},metrics:null,received_at:null},login:{state:'idle',output:'',authorization_url:null}};
const fixture={document:{getElementById:field},window:{addEventListener(){}},setInterval(){return 1;},clearInterval(){},URL,Date,Number,JSON,Error,console,fetch:async path=>({ok:true,json:async()=>path==='/api/session'?{csrf_token:'synthetic-unit-fixture'}:path==='/api/config'?{ok:true,config}:status})};
vm.createContext(fixture);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),fixture);
(async()=>{
  await fixture.start();
  const synthetic={status:{state:'connected',native:{available:true,logged_in:true,method:'claude.ai'},metrics:{five_hour:{used_percentage:0,resets_at:1900000000},seven_day:{used_percentage:42.5,resets_at:1900100000},context_percentage:null},received_at:1000},login:{state:'idle',output:'',authorization_url:null}};
  fixture.render(synthetic);
  assert.equal(field('five-value').textContent,'0%');
  assert.equal(field('seven-value').textContent,'42.5%');
  fixture.fetch=async()=>({ok:false,json:async()=>({ok:false,error:'SYNTHETIC offline test'})});
  await fixture.refresh();
  assert.equal(field('five-value').textContent,'—');
  assert.equal(field('seven-value').textContent,'—');
  assert.equal(field('context-value').textContent,'—');
  assert.equal(field('native-input').value,'');
  assert.equal(field('official-sign-in').hidden,true);
  assert.equal(field('connect').disabled,true);
  assert.equal(field('connection-state').textContent,'Status unavailable');
  console.log('Synthetic-only UI regression passed; no native account or model request');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', code, str(ROOT / 'web/usage-config/app.js')], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
