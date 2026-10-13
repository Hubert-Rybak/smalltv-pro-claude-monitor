# Claude Code usage data sources for SmallTV-PRO

**Research date:** October 13, 2026. **Scope:** public-source research and data-source design only; no service implementation, login, inference request, firmware change, or remote-system write. All JSON below is **documentation/example with invented values**, never real account output.

## Outcome

Use an **unmodified, user-authenticated Claude Code instance → documented status-line JSON → local sanitized relay → SmallTV-PRO**.
Exact *reported* 5-hour/weekly utilization percentages and reset timestamps are now documented status-line fields; reading OAuth credentials is unnecessary.[1][3]
Add optional local OpenTelemetry (OTel) collection for cumulative session token totals, not for subscription quotas.[2]
Do not convert token counts or dollar estimates into subscription percentages: product surfaces share plan usage, and allowances depend on more than tokens alone.[7]

The official npm `latest` package and the top of Anthropic's changelog both identify **2.1.296** at retrieval.[15][9] Relevant compatibility boundaries:

| Version | Documented release change |
|---|---|
| 2.1.80 | Adds status-line `rate_limits` with 5-hour/7-day percentages and reset times.[9] |
| 2.1.97 | Adds `statusLine.refreshInterval`.[9] |
| 2.1.132 | Fixes status-line context token counts incorrectly reflecting cumulative session totals.[9] |
| 2.1.243 | Fixes expired rate-limit windows remaining visible after reset during idle sessions.[9] |

**Recommendation:** use the current supported client, rather than merely the minimum 2.1.80, and record its `version` alongside each local snapshot.

## 1. Supported interfaces and their boundaries

| Interface | What it supplies | What it does not supply / caution |
|---|---|---|
| Status line (`statusLine.type: "command"`; JSON on stdin) | `rate_limits.five_hour` / `seven_day`: `used_percentage` (0–100), `resets_at` (Unix seconds); context snapshot; estimated session cost; session identifier; client version.[1] | No documented absolute subscription-token allowance, cumulative session input/output totals, model-specific weekly caps, or upstream-fetch timestamp in these fields. Treat it as a native-client snapshot, not an independently polled subscription API.[1] |
| Interactive `/usage` | Session cost/token breakdown, plan limits, activity; `/cost` and `/stats` are aliases (the latter opens Stats).[13][4] | Human UI, not a documented quota JSON endpoint. On failed plan-usage requests it can show a last-known snapshot from the past 60 minutes with a stale-data note.[4] |
| `/context` | Human context inspection.[13] | It can include estimates for messages added since the last response and therefore differ from the status-line snapshot.[1] |
| OTel metrics | `claude_code.token.usage` by `type` = `input`, `output`, `cacheRead`, `cacheCreation`, plus `claude_code.cost.usage`; session/model/request-category attribution.[2] | The documented metric inventory contains no 5-hour/7-day quota-percentage/reset metric. It covers instrumented Claude Code activity, not unobserved use elsewhere.[2] |
| Console Usage & Cost Admin API | Organization API token/cost history: `GET https://api.anthropic.com/v1/organizations/usage_report/messages` and `GET https://api.anthropic.com/v1/organizations/cost_report`.[11] | Not consumer Pro/Max rolling quotas; unavailable for individual accounts. Requires an authorized Admin API credential; current docs allow an Admin API key, suitable `org:admin` OAuth, or qualifying non-workspace personal/service key. This is not permission to reuse a consumer session token.[11][3] |
| Claude Enterprise Analytics API | Enterprise organization cost/usage reporting with an Analytics API key, distinct from Console Admin credentials.[11] | Not a replacement for a consumer plan's exact five-hour/weekly bars. Only pursue if the user actually needs an authorized enterprise analytics integration.[11] |

**Availability:** status-line subscription windows are documented for **claude.ai Pro/Max**, after the first API response.[1]
Each window may be independently absent and is dropped after its reset time.[1]
Gateway `rate_limits.spend_limit` is a different spend-limit object, not a five-hour/weekly subscription window; do not map it into those bars.[1]
Do not assume Team/Enterprise/native GUI/headless sessions expose the same status-line windows without verifying the actual supported client behavior.

### Documentation/example: selected status-line fields, synthetic values

This is a reduced example using documented field names, not the full schema and not captured output.[1]

```json
{
  "version": "2.1.296",
  "session_id": "example-session",
  "rate_limits": {
    "five_hour": { "used_percentage": 23.5, "resets_at": 1791918000 },
    "seven_day": { "used_percentage": 41.2, "resets_at": 1792504800 }
  },
  "context_window": {
    "context_window_size": 200000,
    "used_percentage": 5,
    "remaining_percentage": 95,
    "total_input_tokens": 10000,
    "total_output_tokens": 500,
    "current_usage": {
      "input_tokens": 4000,
      "output_tokens": 500,
      "cache_creation_input_tokens": 1000,
      "cache_read_input_tokens": 5000
    }
  },
  "cost": { "total_cost_usd": 0.12, "total_duration_ms": 600000 }
}
```

**Critical semantic distinction:** despite their names, current `context_window.total_input_tokens` / `total_output_tokens` are **the latest context/request snapshot, not cumulative session consumption**.[1][9]
Input includes fresh input plus cache creation and reads; output is from the most recent response.[1]
`used_percentage` uses **input only**, excluding output.[1]
Use the supplied percentage; never sum these snapshots across status-line invocations.
`current_usage` is null before the first response and immediately after compaction until a subsequent response; percentages can also be null.[1]

`cost.total_cost_usd` is locally estimated session cost, normally list-price based or adjusted by managed `modelPricing`, **not the subscriber's bill or remaining allowance**.[4]
Label the screen “estimated session cost,” not “spent from subscription.”
`/clear` starts new session totals in current versions.[4]

## 2. Undocumented OAuth routes: exclude from the implementation

**Undocumented/private implementation route:** `GET https://api.anthropic.com/api/oauth/usage`.

The route literal `/api/oauth/usage` and the API host were verified by static inspection of Anthropic's publicly published **historical 2.1.80** `package/cli.js`.[27]
This establishes implementation history, **not a present public API contract, response schema, permission grant, or availability guarantee**.
No authenticated request was made, and no current response schema is asserted here.

Anthropic's current published rules reserve subscription OAuth for ordinary use of native Anthropic applications, forbid third-party claude.ai sign-in offerings/routing through users' Free/Pro/Max credentials, and prohibit third-party developers collecting, storing, or intermediating claude.ai credentials/session tokens.[3]
The cited rules do **not** document a blanket read-only telemetry exception.[3]
Consequently, do not extract tokens from credential files/keychains, copy browser cookies, refresh native OAuth tokens in a daemon, imitate native clients, or poll authenticated web-app/private OAuth usage routes.
An authorized user logging into the **unmodified native client** and exporting its documented numeric status-line/OTel data is the recommended separation.[1][2][3]

For a different credential-bearing third-party reader, obtain explicit clarification/authorization from Anthropic; user consent alone does not establish a supported API. API-key model inference, ordinary API rate limits, and organization usage reports are separate products—not fallback mechanisms for reconstructing exact consumer-plan quotas.[3][11]

## 3. Credential-safe implementable design (proposal, not Anthropic API)

### A. Capture on the real Claude Code host

1. The user signs in through Claude Code's own login flow. The relay never handles Anthropic authentication.[12][3]
2. A fast status-line wrapper parses stdin and **allowlists** only the fields needed above. Never persist the entire payload, environment, account data, `transcript_path`, workspace paths, session titles, prompts, or credentials. Convert the internal session identifier to a local display alias before sending to the device.
3. Write a sanitized, per-session snapshot atomically into a user-only directory **outside every repository** (directory 0700, files 0600). Do not use untrusted session strings as filesystem paths. The wrapper performs no remote quota fetches and no synchronous LAN call; failure must not disrupt Claude Code's UI. Preserve any existing status-line renderer rather than silently replacing it.
4. An independent local relay reads these snapshots and exposes a **custom** read-only LAN endpoint, for example `GET /v1/smalltv/claude-usage`. This endpoint is ours, not an Anthropic endpoint. If capture and relay are on different hosts, authenticate their sanitized transfer with a dedicated local credential, not Anthropic credentials.
5. SmallTV-PRO at `192.168.1.117` receives only this sanitized data. Prefer pinned/verified HTTPS and LAN firewall rules; if using isolated-LAN HTTP, disclose its metadata exposure. A per-device credential may protect the relay, but **no Anthropic token, API key, cookie, or OAuth refresh capability belongs on the ESP32**.

### Documentation/example: proposed settings fragment (not installed)

`refreshInterval` is in seconds and has a documented minimum of 1; it reruns the script, not a guaranteed fresh upstream quota lookup.[1]

```json
{
  "statusLine": {
    "type": "command",
    "command": "/absolute/user-owned/path/smalltv-statusline-wrapper",
    "refreshInterval": 30
  }
}
```

The command path above is deliberately an example; no wrapper exists as a result of this research.

### B. Optional cumulative local-session counters

Use a local OTLP Collector/receiver that understands the standard protocol, then an allowlisted numeric reducer.
Claude Code documents a default **delta** metrics temporality and an explicit cumulative option; the sum's temporality and observation/start timestamps determine correct aggregation.[2][26]

**Design rules:** key full metric streams by source instance, session, model, token type, and other contributing dimensions. For delta sums, add each unique interval once and flag gaps. For cumulative sums, retain the newest value per stream/start epoch; do not add every repeated export. Handle process restarts/resumes and reset boundaries explicitly. Preserve stream identity internally before stripping labels; otherwise main/subagent/auxiliary streams can collide. Roll up main + subagent + auxiliary only when the screen explicitly says “observed session total.” These are recommendations based on the OTel model, not a claim of a lossless historical billing ledger.[2][26]

Prefer cumulative export for a small local relay to reduce sensitivity to missed intermediate exports, while marking totals **partial/from monitoring start** unless capture began with the session and continuity is proven. Never backfill by summing repeated context snapshots or parsing private transcript JSONL: Anthropic explicitly calls transcript-entry format internal and version-changing.[2]

### Documentation/example: optional metrics-only environment (not applied)

Set on the user's actual Claude Code host via shell/user settings, not repository settings; the current client ignores repository settings that would enable or redirect these exporters.[2]

```text
CLAUDE_CODE_ENABLE_TELEMETRY=1
OTEL_METRICS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_PROTOCOL=http/json
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=http://127.0.0.1:4318/v1/metrics
OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE=cumulative
OTEL_METRIC_EXPORT_INTERVAL=60000
OTEL_METRICS_INCLUDE_SESSION_ID=true
OTEL_METRICS_INCLUDE_ACCOUNT_UUID=false
OTEL_METRICS_INCLUDE_REPOSITORY=false
OTEL_LOGS_EXPORTER=none
OTEL_TRACES_EXPORTER=none
OTEL_LOG_USER_PROMPTS=0
OTEL_LOG_ASSISTANT_RESPONSES=0
OTEL_LOG_TOOL_DETAILS=0
OTEL_LOG_TOOL_CONTENT=0
```

Keep raw-API-body and enhanced/beta tracing options **unset**.
Metrics can still include `user.email`, `user.id`, and organization identity; the account-UUID option does not remove everything.[2]
Delete these locally before storage/forwarding and retain only explicit numeric fields and local aliases.
No external collector credentials are needed for a loopback-only collector.

## 4. Device contract and truthful missing/offline states

### Documentation/example: proposed sanitized relay schema, synthetic values

This is a **new local contract**, not an Anthropic response. Here the invented receipt time is October 13, 2026 at 14:00 UTC; example resets are October 13 at 19:00 UTC and October 20 at 14:00 UTC. `source_fetched_at` is null because status-line data does not document that upstream timestamp.[1]

```json
{
  "schema_version": 1,
  "collector_state": "online",
  "session_alias": "selected-session",
  "source": {
    "kind": "claude_code_statusline",
    "client_version": "2.1.296",
    "received_at": 1791900000,
    "source_fetched_at": null
  },
  "limits": {
    "five_hour": { "state": "snapshot", "used_percentage": 23.5, "resets_at": 1791918000 },
    "seven_day": { "state": "snapshot", "used_percentage": 41.2, "resets_at": 1792504800 }
  },
  "context": { "state": "ready", "used_percentage": 5, "capacity_tokens": 200000, "input_tokens": 10000, "latest_output_tokens": 500 },
  "session_cost": { "state": "estimated", "usd": 0.12 },
  "session_tokens": {
    "state": "unavailable",
    "reason": "otel_not_configured",
    "coverage": null,
    "input": null, "output": null, "cache_read": null, "cache_creation": null
  }
}
```

Contract rules (implementation recommendations):

- Validate finite numeric percentages and timestamps. Preserve decimals; missing is **null/absent**, not zero. Keep a value's presence separate from its freshness.
- Unknown window: `{"state":"unavailable","used_percentage":null,"resets_at":null}`. Reasons include `no_native_response_yet`, `unsupported_source`, `not_configured`, and `unknown`; do not guess which cause applies from absence alone.
- After reset: show `expired/awaiting native update`, never synthesize a fresh 0%. Compute countdowns locally only with a synchronized clock: `max(0, resets_at - now)`; keep exact Unix reset time in the relay schema.
- Disconnected collector: show `offline`; old numeric data may remain visible only as an explicitly stale last snapshot. Maintain separate collector-heartbeat and sample-receipt timestamps. Repeated timer invocations do **not** prove upstream quota freshness; label them snapshots, retain unknown upstream time, and apply a configurable stale-display policy.
- After compaction: context can be unavailable while plan-limit snapshots and session-cost estimates remain available; track states per metric, not one global boolean.[1]
- Multiple sessions: select one context/session-cost view or provide an explicit selector. Do not add percentages from two sessions using the same subscription. The account-level plan bar and a local session's context bar are different scopes.[7]
- Do not infer server rejection from a 100% bar: usage credits can permit continued work. Any warning colors or thresholds are **local display policy**, not native enforcement status.[4]

### Existing firmware compatibility (local source inspection only)

Read, not modified: `community/src/features/usage/UsageData.h` and `UsageClient.cpp`. The current legacy contract is `s`, `sr`, `w`, `wr`, `st`, `ok`; percentages are floats and resets are integer minutes. `UsageClient.cpp:37–44` rejects explicit `ok:false` but defaults missing weekly/reset fields to zero; `:100` preserves the previous snapshot on fetch failure. Thus it cannot faithfully represent independent unknown windows or richer context/token states unchanged.

A conservative temporary shim should emit legacy `ok:true` only when **both** windows are valid and usable; otherwise `ok:false`. That still requires the UI to mark retained data stale. A later implementation should add nullable/per-field states and exact reset timestamps for the new screens. Do not describe legacy `st` values as native status-line enforcement fields: the documented quota objects supply percentages/reset times, not that enum.[1]

## 5. Required user input / remaining verification

**Metadata-only local checks:** `claude` is not on PATH and `/opt/data/.claude` does not exist. No credential directory contents or secret files were read. Consequently, there is **no real local Claude session sample** to validate in this environment.

Before implementation, obtain:

1. **Actual Claude Code host and interface:** OS, terminal CLI versus native VS Code/Desktop/headless use, and whether a sanitized capture can run there. Start with the terminal CLI; do not promise a terminal status-line callback runs in every GUI/headless mode.
2. **Client version and plan/provider:** user-reported `claude --version`; Pro/Max/Team/Enterprise or Console/cloud/gateway authentication. `claude auth status` is a documented diagnostic, but request only the relevant nonsecret classification, not its complete JSON/account identifiers.[5]
3. **User-managed native login:** if needed, the user completes Anthropic's login locally. Request **no password, OAuth token, API key, session cookie, login code, or credential file**. A normal user-initiated response is required to populate the documented windows; do not run a model call just to test the display.[1][12]
4. **Consent/configuration:** whether to wrap an existing status line; whether optional local OTel counters are wanted; any managed-hook/telemetry policy requiring administrator approval.[1][2]
5. **Display scope:** which session/host to show, whether session totals mean main-only or all observed requests, local display aliases, time zone, and tolerance for snapshots/partial counters.
6. **Relay location/network:** an always-on host and LAN endpoint/port reachable from `192.168.1.117`, plus TLS/trust and firewall choices. No Anthropic credential is required for this relay.

Acceptance checks for the later implementation: capture a user-authorized **sanitized** native sample; verify independent absent windows, startup nulls, compaction, window expiry, relay outage, multiple-session selection, no fake zeros, token-counter temporality/retries, and absence of credentials/private text from every device payload, log, runtime artifact and repository. This research verified documentation, release boundaries, and example syntax—not live account values, firmware behavior, or end-to-end operation.

## Sources

[1] https://code.claude.com/docs/en/statusline
[2] https://code.claude.com/docs/en/monitoring-usage
[3] https://code.claude.com/docs/en/legal-and-compliance
[4] https://code.claude.com/docs/en/costs
[5] https://code.claude.com/docs/en/cli-reference
[7] https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work
[9] https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md
[11] https://platform.claude.com/docs/en/manage-claude/usage-cost-api
[12] https://code.claude.com/docs/en/authentication
[13] https://code.claude.com/docs/en/commands
[15] https://registry.npmjs.org/@anthropic-ai/claude-code/latest
[26] https://opentelemetry.io/docs/specs/otel/metrics/data-model
[27] https://registry.npmjs.org/@anthropic-ai/claude-code/-/claude-code-2.1.80.tgz
