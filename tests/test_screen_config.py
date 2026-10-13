"""Tests first for the backend-hosted panel; all account/usage fixtures are synthetic."""
from pathlib import Path
import importlib.util
import json
import os
import stat
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]


def implementation():
    path = ROOT / 'tools/screen_config.py'
    assert path.is_file(), 'Working web configuration backend is not implemented'
    spec = importlib.util.spec_from_file_location('screen_config_impl', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestNativeClient:
    """Explicit test-only fake; production must never substitute this for a real login."""
    __test__ = False

    def __init__(self, logged_in=False, available=True):
        self.logged_in = logged_in
        self.available = available
        self.inputs = []
        self.started = []
        self.cancelled = False

    def status(self):
        return {'available': self.available, 'logged_in': self.logged_in, 'method': 'claude.ai' if self.logged_in else 'none'}

    def login_status(self):
        return {'state': 'idle', 'output': '', 'authorization_url': None}

    def start_login(self, method, sso=False):
        self.started.append((method, sso))
        return {'state': 'awaiting_native_input', 'output': 'SYNTHETIC TEST TERMINAL', 'authorization_url': None}

    def send_input(self, data):
        self.inputs.append(data)

    def cancel_login(self):
        self.cancelled = True


def test_defaults_are_browser_configured_and_have_no_account_secrets(tmp_path):
    module = implementation()
    state = module.ScreenState(tmp_path / 'state', native=TestNativeClient())
    config = state.read_config()
    assert config['source'] == 'account_quota'
    assert config['refresh_seconds'] >= 5
    assert 'password' not in config and 'oauth_token' not in config and 'host_os' not in config
    assert state.status()['state'] == 'disconnected'


def test_configuration_persists_privately_across_restart(tmp_path):
    module = implementation()
    directory = tmp_path / 'state'
    state = module.ScreenState(directory, native=TestNativeClient())
    saved = state.save_config({'enabled': True, 'source': 'both', 'refresh_seconds': 45, 'stale_seconds': 180, 'show_reset_countdown': True, 'show_context': True})
    assert module.ScreenState(directory, native=TestNativeClient()).read_config() == saved
    assert stat.S_IMODE((directory / 'config.json').stat().st_mode) == 0o600


@pytest.mark.parametrize('bad', [
    {'password': 'unit'}, {'oauth_token': 'unit'}, {'source': 'unsupported'},
    {'refresh_seconds': True}, {'refresh_seconds': 0}, {'refresh_seconds': 99999},
    {'show_context': 'yes'}, {'stale_seconds': -1}, {'state_dir': '/elsewhere'},
])
def test_invalid_config_is_rejected_without_overwriting(tmp_path, bad):
    module = implementation()
    state = module.ScreenState(tmp_path / 'state', native=TestNativeClient())
    before = state.read_config()
    with pytest.raises(ValueError):
        state.save_config(bad)
    assert state.read_config() == before


def test_authentication_and_telemetry_are_separate_states(tmp_path):
    module = implementation()
    client = TestNativeClient()
    state = module.ScreenState(tmp_path / 'state', native=client)
    state.save_config({'enabled': True})
    assert state.status()['state'] == 'login_required'
    client.logged_in = True
    assert state.status()['state'] == 'waiting_for_data'
    assert state.status()['metrics'] is None
    client.available = False
    assert state.status()['state'] == 'client_unavailable'


def test_native_snapshot_is_allowlisted_not_raw_account_or_transcript_data(tmp_path):
    module = implementation()
    state = module.ScreenState(tmp_path / 'state', native=TestNativeClient(logged_in=True))
    state.save_config({'enabled': True, 'show_context': True})
    state.ingest_snapshot({
        'rate_limits': {'five_hour': {'used_percentage': 0, 'resets_at': 1900000000}, 'seven_day': {'used_percentage': 42.5, 'resets_at': 1900100000}},
        'context_window': {'used_percentage': 27},
        'transcript_path': '/SYNTHETIC/private/transcript', 'access_token': 'unit', 'email': 'fake@example.invalid',
    }, received_at=1000)
    result = state.status(now=1001)
    assert result['state'] == 'connected'
    assert result['metrics']['five_hour']['used_percentage'] == 0
    stored = (tmp_path / 'state' / 'snapshot.json').read_text()
    assert 'transcript' not in stored and 'access_token' not in stored and 'fake@example.invalid' not in stored
    assert 'private/transcript' not in json.dumps(result)


def test_stale_data_is_not_reported_as_fresh_zero_usage(tmp_path):
    module = implementation()
    state = module.ScreenState(tmp_path / 'state', native=TestNativeClient(logged_in=True))
    state.save_config({'enabled': True, 'stale_seconds': 120})
    state.ingest_snapshot({'rate_limits': {'five_hour': {'used_percentage': 7, 'resets_at': 1900000000}}}, received_at=1000)
    result = state.status(now=1201)
    assert result['state'] == 'stale'
    assert result['metrics'] is None


@pytest.mark.parametrize('bad', [True, '0', -1, 101, float('nan'), float('inf')])
def test_bad_usage_numbers_do_not_become_zero(tmp_path, bad):
    module = implementation()
    state = module.ScreenState(tmp_path / 'state', native=TestNativeClient(logged_in=True))
    with pytest.raises(ValueError):
        state.ingest_snapshot({'rate_limits': {'five_hour': {'used_percentage': bad}}})


def test_disconnect_affects_display_only_not_native_account(tmp_path):
    module = implementation()
    client = TestNativeClient(logged_in=True)
    state = module.ScreenState(tmp_path / 'state', native=client)
    state.save_config({'enabled': True})
    state.disconnect()
    assert state.status()['state'] == 'disconnected'
    assert client.logged_in is True


def test_client_status_is_allowlisted_and_fail_closed(tmp_path):
    module = implementation()
    summary = module.sanitize_native_status({'loggedIn': True, 'authMethod': 'claude.ai', 'email': 'fake@example.invalid', 'accessToken': 'unit'})
    assert summary == {'available': True, 'logged_in': True, 'method': 'claude.ai'}
    with pytest.raises(ValueError):
        module.sanitize_native_status({'loggedIn': 'true', 'authMethod': 'claude.ai'})


def test_missing_native_client_is_reported_honestly(tmp_path):
    module = implementation()
    client = module.NativeClient(tmp_path / 'does-not-exist', tmp_path / 'native')
    assert client.status()['available'] is False
    with pytest.raises(ValueError):
        client.start_login('subscription')


@pytest.fixture
def live_server(tmp_path):
    module = implementation()
    native = TestNativeClient()
    state = module.ScreenState(tmp_path / 'state', native=native)
    server = module.make_server(('127.0.0.1', 0), state)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        yield url, state, native
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def request(url, path, data=None, csrf=None, origin=None, headers=None):
    h = dict(headers or {})
    payload = None
    if data is not None:
        payload = json.dumps(data).encode()
        h['Content-Type'] = 'application/json'
        h['Origin'] = url if origin is None else origin
        if csrf:
            h['X-CSRF-Token'] = csrf
    req = urllib.request.Request(url + path, data=payload, headers=h)
    try:
        response = urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read()
        parsed = json.loads(raw) if response.headers.get('Content-Type', '').startswith('application/json') else raw.decode()
        return response.status, parsed, dict(response.headers)


def test_real_http_serves_panel_and_persists_configuration(live_server):
    url, state, _ = live_server
    code, html, headers = request(url, '/')
    assert code == 200 and 'Usage screen configuration' in html
    assert 'Not installed on the device' in html
    assert headers['Cache-Control'] == 'no-store'
    assert 'default-src' in headers['Content-Security-Policy']
    _, session, _ = request(url, '/api/session')
    code, result, _ = request(url, '/api/config', {'refresh_seconds': 45}, csrf=session['csrf_token'])
    assert code == 200 and result['ok'] and state.read_config()['refresh_seconds'] == 45


def test_http_blocks_missing_csrf_and_cross_origin(live_server):
    url, state, _ = live_server
    assert request(url, '/api/config', {'enabled': True})[0] == 403
    _, session, _ = request(url, '/api/session')
    assert request(url, '/api/config', {'enabled': True}, csrf=session['csrf_token'], origin='https://example.invalid')[0] == 403
    assert state.read_config()['enabled'] is False


def test_http_rejects_secret_fields_and_unknown_routes(live_server):
    url, _, _ = live_server
    _, session, _ = request(url, '/api/session')
    assert request(url, '/api/config', {'oauth_token': 'unit'}, csrf=session['csrf_token'])[0] == 400
    assert request(url, '/private/config.json')[0] == 404
    assert request(url, '/../.env')[0] == 404


def test_host_header_rebinding_is_rejected(live_server):
    url, _, _ = live_server
    assert request(url, '/api/session', headers={'Host': 'example.invalid'})[0] == 403


def test_native_terminal_input_is_forwarded_opaque_and_never_in_config(live_server):
    url, state, native = live_server
    _, session, _ = request(url, '/api/session')
    token = session['csrf_token']
    assert request(url, '/api/auth/start', {'method': 'subscription', 'sso': False}, csrf=token)[0] == 200
    # Synthetic transport bytes, not any real authorization or verification code.
    text = 'opaque-test-input\n'
    assert request(url, '/api/auth/input', {'data': text}, csrf=token)[0] == 200
    assert native.inputs == [text]
    assert text not in (state.root / 'config.json').read_text()
    assert request(url, '/api/auth/cancel', {}, csrf=token)[0] == 200
    assert native.cancelled


def test_auth_input_cannot_change_command_or_persist_credentials(live_server):
    url, _, _ = live_server
    _, session, _ = request(url, '/api/session')
    token = session['csrf_token']
    assert request(url, '/api/auth/start', {'method': 'arbitrary-shell-command'}, csrf=token)[0] == 400
    assert request(url, '/api/auth/input', {'data': 'unit', 'command': 'anything'}, csrf=token)[0] == 400


def test_unreadable_native_status_is_not_misreported_as_logged_out(tmp_path):
    module = implementation()
    native = TestNativeClient()
    native.status = lambda: {'available': True, 'logged_in': False, 'method': 'none', 'error': 'native_status_unavailable'}
    state = module.ScreenState(tmp_path / 'state', native=native)
    state.save_config({'enabled': True})
    assert state.status()['state'] == 'error'


def test_reloaded_snapshot_is_revalidated_and_allowlisted(tmp_path):
    module = implementation()
    state = module.ScreenState(tmp_path / 'state', native=TestNativeClient(logged_in=True))
    state.save_config({'enabled': True})
    state.ingest_snapshot({'rate_limits': {'five_hour': {'used_percentage': 12, 'resets_at': 1900000000}}}, received_at=1000)
    file = state.root / 'snapshot.json'
    data = json.loads(file.read_text())
    data['five_hour']['access_token'] = 'unit'
    file.write_text(json.dumps(data))
    assert 'access_token' not in json.dumps(state.status(now=1001))
    data['five_hour']['used_percentage'] = 'not-a-number'
    file.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        state.status(now=1001)


def test_state_and_native_profile_directories_are_private(tmp_path):
    module = implementation()
    directory = tmp_path / 'state'
    directory.mkdir(mode=0o755)
    native = module.NativeClient(None, directory / 'native-client')
    module.ScreenState(directory, native=native)
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / 'native-client').stat().st_mode) == 0o700


@pytest.mark.parametrize('bad', [
    'https://claude.com:invalid/cai/oauth/authorize?state=unit',
    'https://claude.com@other.invalid/cai/oauth/authorize?state=unit',
    'https://claude.com/not-an-auth-path',
])
def test_malformed_or_unapproved_login_links_fail_closed(bad):
    module = implementation()
    assert module.authorization_url(bad) is None


@pytest.fixture
def synthetic_native_executable(tmp_path):
    """Real subprocess transport with explicitly synthetic output; no provider request."""
    script = tmp_path / 'synthetic-native'
    script.write_text('#!' + sys.executable + '\n' + '''
import json, signal, sys, time
if sys.argv[1:3] == ['auth', 'status']:
    print(json.dumps({'loggedIn': False, 'authMethod': 'none', 'email': 'fake@example.invalid', 'accessToken': 'unit'}))
    raise SystemExit(1)
def cancelled(*_):
    print('https://claude.com/cai/oauth/authorize?state=synthetic-late-output', flush=True)
    raise SystemExit(1)
signal.signal(signal.SIGTERM, cancelled)
print('SYNTHETIC UNIT-TEST NATIVE TERMINAL', flush=True)
print('https://claude.com/cai/oauth/authorize?state=synthetic-unit-fixture', flush=True)
text = sys.stdin.buffer.readline()
print('TEST_BYTES_HEX:' + text.hex(), flush=True)
raise SystemExit(1)
''')
    script.chmod(0o700)
    return script


def wait_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError('Bounded native transport operation did not complete')


def test_native_adapter_uses_actual_subprocess_and_redacts_status_fields(tmp_path, synthetic_native_executable):
    module = implementation()
    native = module.NativeClient(synthetic_native_executable, tmp_path / 'profile')
    assert native.status() == {'available': True, 'logged_in': False, 'method': 'none'}


def test_native_input_transport_preserves_exact_bytes(tmp_path, synthetic_native_executable):
    module = implementation()
    native = module.NativeClient(synthetic_native_executable, tmp_path / 'profile')
    try:
        native.start_login('subscription')
        wait_until(lambda: native.login_status()['authorization_url'] is not None)
        text = '  opaque-unit-fixture  \n'
        native.send_input(text)
        wait_until(lambda: native.login_status()['state'] == 'failed')
        assert 'TEST_BYTES_HEX:' + text.encode().hex() in native.login_status()['output']
        assert not list((tmp_path / 'profile').iterdir()), 'Native transport must not persist input or output'
    finally:
        native.cancel_login()


def test_cancel_drops_late_native_terminal_output(tmp_path, synthetic_native_executable):
    module = implementation()
    native = module.NativeClient(synthetic_native_executable, tmp_path / 'profile')
    native.start_login('default')
    wait_until(lambda: native.login_status()['authorization_url'] is not None)
    native.cancel_login()
    time.sleep(0.05)
    assert native.login_status() == {'state': 'cancelled', 'output': '', 'authorization_url': None}


def test_native_login_timeout_is_enforced_even_without_browser_polling(tmp_path, synthetic_native_executable):
    import inspect
    module = implementation()
    assert 'login_timeout' in inspect.signature(module.NativeClient).parameters, 'Native job lacks an independently enforced lifetime'
    native = module.NativeClient(synthetic_native_executable, tmp_path / 'profile', login_timeout=0.2)
    native.start_login('default')
    process = native._process
    wait_until(lambda: process.poll() is not None)
    assert native.login_status()['state'] == 'timed_out'
    assert native.login_status()['authorization_url'] is None


def test_backend_refuses_unsecured_lan_binding(tmp_path):
    module = implementation()
    state = module.ScreenState(tmp_path / 'state', native=TestNativeClient())
    with pytest.raises(ValueError):
        module.make_server(('0.0.0.0', 0), state)
