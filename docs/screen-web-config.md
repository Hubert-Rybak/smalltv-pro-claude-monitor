# Picture replacement — web configuration/authentication contract

## Product requirement

Replace the stock Picture app with a usage display while retaining the other seven apps and existing image files. Screen configuration belongs in the **device's web interface**, not a firmware image customized for a particular computer OS. This contract records the requirement; it is not a deployed web UI or tested login implementation.

### Required screen configuration panel

- **Connect / sign in:** initiate a supported backend connection and, where needed, the official native Claude Code sign-in flow.
- **Connection status:** disconnected, login required, connected, waiting for data, stale/offline, or error. Authenticated does not automatically mean usage data is available.
- **Test connection:** a bounded metadata/read-only check; no model inference just to populate a display.
- **Source selection:** account-level quota snapshot; selected native session's context/session data when exposed.
- **Display controls:** five-hour/weekly windows, reset countdowns, optional context/session estimate, refresh interval and stale threshold.
- **Disconnect/reconnect:** separate revocation of the device's relay pairing from native account logout, with explicit scope.

Missing, expired or inaccessible metrics must not become a fake 0% bar. Session-specific values and account-level rolling quotas must remain distinct.

## Verified authentication boundary

The current official CLI documents `claude auth login`, `claude auth status`, and `claude auth logout`.[3] Sign-in must complete through Anthropic's own flow; its published guidance allows an end user to sign into the unmodified native Claude Code binary, including where a platform hosts that binary.[1][4]

The custom web page must **not** implement its own Claude password form, copy browser cookies, collect native OAuth/session tokens, or promise a standalone consumer-usage OAuth API that has not been established.[1]

Therefore the intended implementation boundary is:

```text
Device web configuration
    -> supported backend connector / native client interface
    -> official native Claude Code authentication
    -> allowlisted numeric usage snapshots
    -> device display
```

A backend may run on an available always-on host; the screen UI should not require the user to identify an OS first. That does not mean the ESP32 can run the native client or that logging in discovers every session on another computer. Session-specific data still requires the selected native source to supply it.[2]

Only a dedicated **local device/relay pairing credential**, if needed, belongs in device configuration. Anthropic credentials remain controlled by the native client. The custom relay must never parse or persist raw authentication material, prompts, transcript paths or full account-status output.

## Verified data source

Official status-line JSON documents the five-hour/seven-day `used_percentage` and `resets_at` values, together with current context and session-cost snapshot fields.[2] These are native-client snapshots, not a newly verified device-direct account polling API.[2]

Native login can be successful before those data fields are available. The configuration panel must show that distinction rather than manufacture usage values. A refresh timer alone does not establish that an upstream quota snapshot is newly fetched.

## Implementation gates still open

1. Actual native-client/backend login integration and callback handling must be exercised, not replaced with a simulated successful account response.
2. The configuration page must be integrated with the stock embedded web asset/handler boundaries without altering other app configuration.
3. The replacement renderer/lifecycle and Picture event handling must be built and tested against the exact stock binary.
4. Firmware image/partition/recovery validation remains required before any flash.

The current work has verified source documentation and updated the target contract. No login was performed, credentials requested, backend deployed, firmware modified or device flashed.

## Sources

[1] https://code.claude.com/docs/en/legal-and-compliance.md — Claude Code legal and compliance, current official Markdown
[2] https://code.claude.com/docs/en/statusline.md — Claude Code documented status-line fields
[3] https://code.claude.com/docs/en/cli-reference.md — Claude Code documented auth commands
[4] https://code.claude.com/docs/en/authentication.md — Claude Code native authentication
