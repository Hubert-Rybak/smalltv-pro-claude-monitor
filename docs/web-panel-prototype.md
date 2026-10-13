# Backend-hosted usage-screen configuration prototype

## Implemented milestone, not the full device goal

A real browser panel and Python HTTP backend now implement the screen-management contract. The panel is currently hosted by the backend, **not by the ESP32 stock firmware**. It is explicitly marked “Not installed on the device”. No firmware, app callback, uploaded image, Wi-Fi setting or OTA state was changed.

Implemented:

- Persistent display-only configuration: source selection, refresh/stale intervals, reset countdowns and optional context display.
- Connect/sign in, bounded read-only connection checks, and display-only disconnect.
- Native-client availability/authentication summary separate from data availability.
- Private native sign-in terminal and official authorization link. Input is opaque, transient stdin to the unmodified client; there is no app password, browser-cookie or OAuth/session-token field.
- A bounded native job lifetime, cancellation that cannot revive stale terminal output, and no terminal transcript/input persistence by the controller.
- Allowlisted local native-statusline ingestion. Unknown account, transcript and credential fields are discarded; cached data is revalidated before return.
- Missing/expired/failed-source values are unavailable, never fresh 0%. A supplied numeric 0% is preserved as a valid observation.
- Same-origin/CSRF checks, strict Host checks against DNS rebinding, bounded request/input sizes, private local state, no path-based file serving and no arbitrary command selection.

## Run

Python 3.10+ runs the backend without application packages:

```bash
python tools/screen_config.py --port 8765
```

An official native client on PATH is detected. If it is installed in an isolated location:

```bash
python tools/screen_config.py --port 8765 --claude-path /path/to/official/claude
```

Open the loopback URL printed by the server on the backend machine. Configuration defaults to `runtime/web-screen/config.json` (ignored by Git, mode 0600 on the tested Linux host). Its native client profile is under `runtime/web-screen/native-client`; the **native client** owns any credentials it later creates. This dedicated profile is not automatic discovery of a Claude Code/VS Code/Desktop session on another computer.

The UI does not ask which computer OS the user has. Installing the native executable on the chosen backend is a separate operational prerequisite. Linux and Chromium were actually exercised; other backend operating systems and browsers are not claimed tested.

## Native authentication boundary

The official CLI exposes `auth login`, `auth status`, subscription/Console selection and SSO options.[1] Its published authentication documentation includes the native terminal fallback when an official browser callback returns a one-time code, particularly for SSH/containers.[2]

The controller launches only fixed native authentication subcommands. It does not implement OAuth exchanges, inspect credential files, mint subscription tokens, launch model inference or route model requests. The native executable remains unchanged. Official guidance distinguishes hosting the unmodified native client from third-party reuse of subscription credentials.[3]

Click **Connect / sign in**, then open the official authorization link when the native client supplies it. If the official site returns an authorization code, use only the displayed native terminal while its own prompt requests input. That input is forwarded to the running native process; it is not interpreted as an app credential, written to display settings, retained in a controller transcript, or sent to the numeric telemetry relay. Do not enter an account password, API key or OAuth/session token into this terminal or into chat.

The controller strips ambient provider credentials for its dedicated discovery/login profile, so unrelated API keys in the agent's environment do not silently select a different authentication source. The native binary's supported authentication mechanisms are not modified; operators can use the official client directly for other methods.

Successful initiation is **not successful account authorization**. The current real client was observed unauthenticated; the official link and native prompt were observed and then cancelled. No real authorization code, login password or account credential was entered. Terminal byte-forwarding tests use explicitly synthetic subprocess fixtures, not a fabricated successful account response.

The isolated real executable used for verification was official `@anthropic-ai/claude-code-linux-x64` version `2.1.296`, resolved from the registry metadata.[4] The downloaded package matched its published SHA-512 integrity, and the extracted executable SHA-256 was `24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de`. The binary/package remains outside Git.

## Native snapshot hook

A native status-line hook can invoke:

```bash
python /absolute/path/to/tools/screen_config.py --state-dir /absolute/path/to/runtime/web-screen --ingest
```

It reads one bounded JSON object from stdin and stores only allowed numeric quota/context fields plus local receipt time. No model request or direct account-quota API call is made. Wiring this hook to a real authenticated native session, and receipt of real account data, remain unverified. Synthetic unit/browser fixtures are never a runtime fallback.

The configured refresh interval is a saved **target-display setting**. The management page polls local status separately; neither timer proves an upstream quota snapshot was refreshed. No renderer is installed on the device to consume that interval yet.

## HTTP action contract

- `GET /`: actual static panel; `/app.js` and `/style.css` are served from the checked-in bundle.
- `GET /api/session`: ephemeral local CSRF capability; it is not a provider/account credential.
- `GET /api/config`: validated display-only settings.
- `GET /api/status`: backend state plus the private native terminal's transient state. **This is not a device-public telemetry endpoint.**
- `POST /api/config`: validated partial display settings, atomic private-file replacement.
- `POST /api/test-connection`: empty JSON, native status/local metadata only.
- `POST /api/disconnect`: empty JSON, disable this display and discard its snapshot; do not run native logout.
- `POST /api/auth/start`: only native `method` and boolean `sso`; fixed argv, no shell.
- `POST /api/auth/input`: only bounded opaque text `data`, forwarded to the active native process. Never part of telemetry/config.
- `POST /api/auth/cancel`: terminate only this controller's job and clear transient output/link.

POST actions require matching Origin, Host and the local CSRF capability. Configuration and state routes return `Cache-Control: no-store`. Native authentication URLs are allowlisted, unmodified and not logged in the retained verification output.

## Verification and remaining gates

The local test suite and real HTTP/browser evidence are enumerated in `verification/web-panel-checks.json`. Real browser checks exercised settings save/readback, native sign-in initialization/cancellation, desktop layout, a 390-pixel mobile viewport, and runtime errors. Separate **synthetic-only** browser tests exercised a supplied 0%, absent values and a backend failure, without creating real account data.

Still open:

1. User completion of official native authorization, then real source telemetry and expiration behavior.
2. Authenticated HTTPS/LAN management and pairing with a numeric-only device endpoint. The prototype refuses non-loopback binding rather than exposing native authentication to the LAN.
3. Integration of this frontend/handler contract into stock embedded web assets/routes.
4. Safe native Picture replacement code/data placement, lifecycle/ABI verification, actual app-slot capacity, image/security checks and recovery.
5. A verified device boot and preservation of the seven other apps and existing images.

A working backend panel does not close these gates. No judge is used and no device deployment is claimed.

## Sources

[1] https://code.claude.com/docs/en/cli-reference
[2] https://code.claude.com/docs/en/authentication
[3] https://code.claude.com/docs/en/legal-and-compliance?full=1
[4] https://registry.npmjs.org/@anthropic-ai/claude-code/latest
