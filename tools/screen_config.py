#!/usr/bin/env python3
"""Loopback-only usage-screen configuration prototype. No firmware or model requests.

Native authentication runs only in the unmodified official CLI. Terminal input is
opaque, transient stdin transport; it is never a device setting or telemetry field.
"""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = dict(enabled=False, source='account_quota', refresh_seconds=30,
                stale_seconds=180, show_reset_countdown=True, show_context=False)
MAX_BODY = 16384


def validate_config(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULTS):
        raise ValueError('Only documented display settings are accepted')
    for key in ['enabled', 'show_reset_countdown', 'show_context']:
        if type(value[key]) is not bool:
            raise ValueError('Display switches must be booleans')
    if value['source'] not in ['account_quota', 'session', 'both']:
        raise ValueError('Unsupported data source')
    for key, minimum, maximum in [('refresh_seconds', 5, 3600), ('stale_seconds', 5, 86400)]:
        if type(value[key]) is not int or not minimum <= value[key] <= maximum:
            raise ValueError('Refresh/stale interval outside supported bounds')
    if value['stale_seconds'] < value['refresh_seconds']:
        raise ValueError('Stale threshold must be at least the refresh interval')
    return dict(value)


def atomic_json(path, value):
    if path.is_symlink():
        raise ValueError('Refusing symbolic-link state file')
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        if hasattr(os, 'fchmod'):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, allow_nan=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def percentage(value):
    if type(value) not in [int, float] or not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError('Native percentage must be a finite number from 0 to 100')
    return value


def sanitize_snapshot(value, received_at):
    if not isinstance(value, dict) or type(received_at) not in [int, float] or not math.isfinite(received_at):
        raise ValueError('Invalid native snapshot')
    limits = value.get('rate_limits') or {}
    context = value.get('context_window') or {}
    if not isinstance(limits, dict) or not isinstance(context, dict):
        raise ValueError('Invalid native snapshot sections')
    clean = {'received_at': received_at, 'source': 'native_statusline_input', 'five_hour': None, 'seven_day': None, 'context_percentage': None}
    for key in ['five_hour', 'seven_day']:
        window = limits.get(key)
        if window is not None:
            if not isinstance(window, dict) or 'used_percentage' not in window:
                raise ValueError('Native quota window lacks a measured percentage')
            reset = window.get('resets_at')
            if reset is not None and (type(reset) is not int or reset <= 0):
                raise ValueError('Invalid reset timestamp')
            clean[key] = {'used_percentage': percentage(window['used_percentage']), 'resets_at': reset}
    if context.get('used_percentage') is not None:
        clean['context_percentage'] = percentage(context['used_percentage'])
    return clean


def sanitize_native_status(value):
    if not isinstance(value, dict) or type(value.get('loggedIn')) is not bool:
        raise ValueError('Unsupported native status response')
    method = value.get('authMethod', 'none')
    if method not in ['none', 'claude.ai', 'api_key', 'api_key_helper', 'bedrock', 'vertex', 'foundry', 'oauth_token']:
        method = 'other'
    return {'available': True, 'logged_in': value['loggedIn'], 'method': method}


def authorization_url(output):
    for link in re.findall(r'https://[^\s\x1b]+', output):
        try:
            parsed = urllib.parse.urlsplit(link)
            port = parsed.port
        except ValueError:
            continue
        allowed = {
            ('claude.com', '/cai/oauth/authorize'),
            ('claude.ai', '/oauth/authorize'),
            ('platform.claude.com', '/oauth/authorize'),
            ('console.anthropic.com', '/oauth/authorize'),
        }
        if (parsed.hostname, parsed.path) in allowed and parsed.username is None and parsed.password is None and port in [None, 443]:
            return link
    return None


class NativeClient:
    """An argv-fixed CLI adapter. Never reads credential files or exchanges OAuth tokens."""
    def __init__(self, binary, profile, login_timeout=180):
        if type(login_timeout) not in [int, float] or not math.isfinite(login_timeout) or not 0 < login_timeout <= 180:
            raise ValueError('Native login lifetime must be positive and at most 180 seconds')
        self.login_timeout = login_timeout
        self._timer = None
        self.binary = Path(binary) if binary else None
        self.profile = Path(profile)
        if self.profile.is_symlink():
            raise ValueError('Refusing symbolic-link native profile')
        self.profile.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.profile.chmod(0o700)
        self._lock = threading.RLock()
        self._process = None
        self._output = ''
        self._login_state = 'idle'
        self._started = 0
        self._cached = None
        self._checked = 0

    def _environment(self):
        environment = {k: v for k, v in os.environ.items() if not k.startswith(('ANTHROPIC_', 'CLAUDE_')) and k not in ['DEBUG', 'GITHUB_TOKEN', 'GH_TOKEN']}
        environment.update(CLAUDE_CONFIG_DIR=str(self.profile), DISABLE_AUTOUPDATER='1', DISABLE_TELEMETRY='1', DISABLE_ERROR_REPORTING='1', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1', BROWSER='false')
        return environment

    def status(self):
        if not self.binary or not self.binary.is_file():
            return {'available': False, 'logged_in': False, 'method': 'none'}
        with self._lock:
            if self._cached is not None and time.monotonic() - self._checked < 2:
                return dict(self._cached)
        try:
            result = subprocess.run([str(self.binary), 'auth', 'status'], env=self._environment(), cwd=self.profile,
                                    capture_output=True, text=True, timeout=8)
            if result.returncode not in [0, 1] or len(result.stdout) > 32768:
                raise ValueError('Native status unavailable')
            summary = sanitize_native_status(json.loads(result.stdout))
            if summary['logged_in'] and result.returncode != 0:
                raise ValueError('Inconsistent native status')
        except (OSError, ValueError, subprocess.TimeoutExpired):
            summary = {'available': True, 'logged_in': False, 'method': 'none', 'error': 'native_status_unavailable'}
        with self._lock:
            self._cached, self._checked = summary, time.monotonic()
        return dict(summary)

    def start_login(self, method, sso=False):
        if method not in ['default', 'subscription', 'console'] or type(sso) is not bool:
            raise ValueError('Unsupported native authentication choice')
        if not self.binary or not self.binary.is_file():
            raise ValueError('Official native client is not installed on this backend')
        with self._lock:
            if self._process and self._process.poll() is None:
                raise ValueError('A native sign-in is already active')
            args = [str(self.binary), 'auth', 'login']
            if method == 'subscription':
                args.append('--claudeai')
            if method == 'console':
                args.append('--console')
            if sso:
                args.append('--sso')
            try:
                self._process = subprocess.Popen(args, cwd=self.profile, env=self._environment(), stdin=subprocess.PIPE,
                                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
            except OSError:
                raise ValueError('Could not start the official native client') from None
            self._output, self._login_state, self._started = '', 'starting', time.monotonic()
            threading.Thread(target=self._read_terminal, args=(self._process,), daemon=True).start()
            self._timer = threading.Timer(self.login_timeout, self._expire, args=(self._process,))
            self._timer.daemon = True
            self._timer.start()
        return self.login_status()

    def _expire(self, process):
        with self._lock:
            if process is not self._process or process.poll() is not None:
                return
            self.cancel_login()
            self._login_state = 'timed_out'

    def _read_terminal(self, process):
        try:
            while True:
                chunk = process.stdout.read(1024)
                if not chunk:
                    break
                text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', chunk.decode('utf-8', 'replace'))
                with self._lock:
                    if process is not self._process:
                        break
                    self._output = (self._output + text)[-32768:]
                    self._login_state = 'awaiting_native_input' if authorization_url(self._output) else 'starting'
            code = process.wait()
            with self._lock:
                if process is self._process and self._login_state != 'cancelled':
                    self._login_state = 'completed' if code == 0 else 'failed'
                    self._cached = None
                    if code == 0:
                        self._output = ''
        finally:
            process.stdout.close()

    def login_status(self):
        with self._lock:
            process = self._process
            expired = process and process.poll() is None and time.monotonic() - self._started > self.login_timeout
        if expired:
            self._expire(process)
        with self._lock:
            return {'state': self._login_state, 'output': self._output, 'authorization_url': authorization_url(self._output)}

    def send_input(self, data):
        if not isinstance(data, str) or not data or len(data.encode('utf-8')) > 4096:
            raise ValueError('Native terminal input must be bounded UTF-8 text')
        with self._lock:
            if not self._process or self._process.poll() is not None:
                raise ValueError('No native sign-in terminal is active')
            stream = self._process.stdin
            if stream is None:
                raise ValueError('Native terminal has no input transport')
            try:
                stream.write(data.encode('utf-8'))
                stream.flush()
            except (OSError, ValueError):
                raise ValueError('Native terminal is no longer available') from None

    def cancel_login(self):
        with self._lock:
            process = self._process
            self._process = None  # Detach before termination; late reader output cannot revive this job.
            self._cached = None
            if self._timer is not None:
                self._timer.cancel()
            self._login_state, self._output = 'cancelled', ''
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if process and process.stdin and not process.stdin.closed:
            process.stdin.close()


class ScreenState:
    def __init__(self, directory, native):
        self.root = Path(directory)
        if self.root.is_symlink():
            raise ValueError('Refusing symbolic-link state directory')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.native, self._lock = native, threading.RLock()
        self.config_path, self.snapshot_path = self.root / 'config.json', self.root / 'snapshot.json'
        if not self.config_path.exists():
            atomic_json(self.config_path, DEFAULTS)
        self.read_config()

    def read_config(self):
        with self._lock:
            if self.config_path.is_symlink():
                raise ValueError('Unsafe configuration file')
            return validate_config(json.loads(self.config_path.read_text()))

    def save_config(self, changes):
        if not isinstance(changes, dict) or set(changes) - set(DEFAULTS):
            raise ValueError('Only display settings can be saved; credentials and OS are not accepted')
        with self._lock:
            merged = self.read_config()
            merged.update(changes)
            merged = validate_config(merged)
            atomic_json(self.config_path, merged)
            return merged

    def ingest_snapshot(self, value, received_at=None):
        snapshot = sanitize_snapshot(value, time.time() if received_at is None else received_at)
        with self._lock:
            atomic_json(self.snapshot_path, snapshot)

    def disconnect(self):
        self.save_config({'enabled': False})
        self.native.cancel_login()
        with self._lock:
            if self.snapshot_path.exists() or self.snapshot_path.is_symlink():
                self.snapshot_path.unlink()

    def status(self, now=None):
        now = time.time() if now is None else now
        config, native = self.read_config(), self.native.status()
        result = {'state': 'disconnected', 'native': native, 'metrics': None, 'received_at': None,
                  'backend_only_prototype': True, 'firmware_integrated': False}
        if not config['enabled']:
            return result
        if not native['available']:
            result['state'] = 'client_unavailable'
            return result
        if native.get('error'):
            result['state'] = 'error'
            return result
        if not native['logged_in']:
            result['state'] = 'login_required'
            return result
        result['state'] = 'waiting_for_data'
        if not self.snapshot_path.exists():
            return result
        with self._lock:
            if self.snapshot_path.is_symlink() or self.snapshot_path.stat().st_size > MAX_BODY:
                raise ValueError('Unsafe native snapshot file')
            data = json.loads(self.snapshot_path.read_text())
        received = data.get('received_at')
        if type(received) not in [int, float] or not math.isfinite(received):
            raise ValueError('Invalid snapshot timestamp')
        data = sanitize_snapshot({'rate_limits': {'five_hour': data.get('five_hour'), 'seven_day': data.get('seven_day')},
                                  'context_window': {'used_percentage': data.get('context_percentage')}}, received)
        result['received_at'] = received
        age = now - received
        if age < 0 or age > config['stale_seconds']:
            result['state'] = 'stale'
            return result
        metrics = {'five_hour': None, 'seven_day': None, 'context_percentage': None}
        if config['source'] in ['account_quota', 'both']:
            metrics['five_hour'], metrics['seven_day'] = data.get('five_hour'), data.get('seven_day')
        if config['source'] in ['session', 'both'] or config['show_context']:
            metrics['context_percentage'] = data.get('context_percentage')
        if any(value is not None for value in metrics.values()):
            result['state'], result['metrics'] = 'connected', metrics
        return result


class PanelServer(ThreadingHTTPServer):
    state: ScreenState
    csrf_token: str
    daemon_threads = True
    def server_close(self):
        self.state.native.cancel_login()
        super().server_close()


class PanelHandler(BaseHTTPRequestHandler):
    @property
    def panel(self) -> PanelServer:
        return cast(PanelServer, self.server)
    def log_message(self, format, *args):
        pass  # Never log paths, request bodies, terminal input or native output.

    def _host_allowed(self):
        hosts = self.headers.get_all('Host', [])
        return len(hosts) == 1 and hosts[0] in [f'127.0.0.1:{self.panel.server_port}', f'localhost:{self.panel.server_port}']

    def _respond(self, code, value, content_type='application/json'):
        raw = json.dumps(value, allow_nan=False).encode() if content_type == 'application/json' else value
        self.send_response(code)
        for key, item in {'Content-Type': content_type, 'Content-Length': str(len(raw)), 'Cache-Control': 'no-store',
                          'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Connection': 'close',
                          'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():
            self.send_header(key, item)
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def do_GET(self):
        if not self._host_allowed():
            return self._respond(403, {'ok': False, 'error': 'Untrusted Host'})
        path = urllib.parse.urlsplit(self.path).path
        state = self.panel.state
        if path == '/api/session':
            return self._respond(200, {'csrf_token': self.panel.csrf_token})
        if path == '/api/config':
            return self._respond(200, {'ok': True, 'config': state.read_config()})
        if path == '/api/status':
            try:
                return self._respond(200, {'ok': True, 'status': state.status(), 'login': state.native.login_status()})
            except ValueError:
                return self._respond(503, {'ok': False, 'error': 'Local state could not be validated'})
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if path in files:
            name, kind = files[path]
            file = ROOT / 'web/usage-config' / name
            if file.is_file():
                return self._respond(200, file.read_bytes(), kind)
        return self._respond(404, {'ok': False, 'error': 'Route not found'})

    def do_POST(self):
        if not self._host_allowed():
            return self._respond(403, {'ok': False, 'error': 'Untrusted Host'})
        expected_origin = 'http://' + self.headers['Host']
        origins = self.headers.get_all('Origin', [])
        tokens = self.headers.get_all('X-CSRF-Token', [])
        if origins != [expected_origin] or len(tokens) != 1 or not tokens[0].isascii() or not secrets.compare_digest(tokens[0], self.panel.csrf_token):
            return self._respond(403, {'ok': False, 'error': 'Same-origin request and CSRF token required'})
        try:
            if self.headers.get_content_type() != 'application/json' or self.headers.get('Transfer-Encoding') is not None:
                raise ValueError('JSON with an explicit body length is required')
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= MAX_BODY:
                raise ValueError('Request body is missing or too large')
            self.connection.settimeout(3)
            raw = self.rfile.read(int(lengths[0]))
            if len(raw) != int(lengths[0]):
                raise ValueError('Incomplete request body')
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError('Request body must be a JSON object')
            path, state = urllib.parse.urlsplit(self.path).path, self.panel.state
            if path == '/api/config':
                return self._respond(200, {'ok': True, 'config': state.save_config(body)})
            if path == '/api/test-connection' and body == {}:
                return self._respond(200, {'ok': True, 'status': state.status()})
            if path == '/api/disconnect' and body == {}:
                state.disconnect()
                return self._respond(200, {'ok': True, 'status': state.status()})
            if path == '/api/auth/start':
                if set(body) - {'method', 'sso'}:
                    raise ValueError('Only native method and SSO selection are accepted')
                method, sso = body.get('method', 'default'), body.get('sso', False)
                if method not in ['default', 'subscription', 'console'] or type(sso) is not bool:
                    raise ValueError('Unsupported native authentication choice')
                return self._respond(200, {'ok': True, 'login': state.native.start_login(method, sso=sso)})
            if path == '/api/auth/input':
                if set(body) != {'data'} or not isinstance(body['data'], str) or not body['data'] or len(body['data'].encode('utf-8')) > 4096:
                    raise ValueError('Only bounded native terminal input is accepted')
                state.native.send_input(body['data'])
                return self._respond(200, {'ok': True})
            if path == '/api/auth/cancel' and body == {}:
                state.native.cancel_login()
                return self._respond(200, {'ok': True})
            return self._respond(404, {'ok': False, 'error': 'Route not found'})
        except (ValueError, UnicodeError):
            return self._respond(400, {'ok': False, 'error': 'Request or display settings are invalid; no changes applied'})
        except (OSError, TimeoutError):
            return self._respond(503, {'ok': False, 'error': 'Local operation unavailable'})


def make_server(address, state):
    if address[0] not in ['127.0.0.1', 'localhost']:
        raise ValueError('Prototype is loopback-only; authenticated HTTPS LAN deployment is not implemented')
    server = PanelServer(address, PanelHandler)
    server.state, server.csrf_token = state, secrets.token_urlsafe(32)
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=ROOT / 'runtime/web-screen')
    parser.add_argument('--claude-path', type=Path)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--ingest', action='store_true', help='Sanitize one native status-line JSON object from stdin, no network/model request')
    args = parser.parse_args()
    binary = args.claude_path or shutil.which('claude')
    native = NativeClient(binary, args.state_dir / 'native-client')
    state = ScreenState(args.state_dir, native)
    if args.ingest:
        import sys
        raw = sys.stdin.buffer.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise SystemExit('Native input exceeds the bounded snapshot size')
        try:
            state.ingest_snapshot(json.loads(raw))
        except (ValueError, UnicodeError):
            raise SystemExit('Native snapshot rejected; raw input was not retained') from None
        print('Allowlisted native snapshot saved; no account credentials or transcript data retained')
        return
    server = make_server(('127.0.0.1', args.port), state)
    print(f'Backend-only prototype ready at http://127.0.0.1:{server.server_port}; not installed on device', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
