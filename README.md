# SmallTV Pro Claude Monitor

Stock-preserving reverse engineering and a planned usage display for the GeekMagic SmallTV-PRO.

## Current status

**Research plus a working backend-hosted web configuration prototype—not an installable firmware release.** Settings persistence, connection checks, official native-client sign-in initiation and private terminal transport are implemented. Actual account authorization, real account telemetry, the stock embedded page integration, replacement renderer and device boot are not yet verified.

See [`docs/web-panel-prototype.md`](docs/web-panel-prototype.md) for the runnable panel and its exact limitations. The backend is deliberately loopback-only; no stock device has been changed.

The selected change is **Picture → usage display**. The other seven registered apps—BitCoin, Stock, Weather, Monitor, Clock, Idea and Settings—are to remain unchanged. Existing uploaded images are not to be deleted.

Screen configuration belongs in the **device web interface**: connect/sign in through a supported native-client/backend flow, connection status/testing, source selection, refresh/display options and disconnect/reconnect. Claude account passwords, browser cookies and subscription OAuth tokens do not belong on the ESP32. Only sanitized numeric snapshots and, if needed, a dedicated local relay-pairing credential should reach it. Missing, stale or expired data must not appear as a fresh 0% reading.

## What is already verified

- Exact vendor **V3.3.65EN** application: 2,106,432 bytes, SHA-256 `1aa9a0408e8a3bee568a45376eb2583fe35ba4daafc14880a8cf1531540066be`.
- Actual headless **Ghidra 12.1.4** analysis with native `Xtensa:LE:32:default`; all five payload segments mapped at their recorded addresses; entry `0x40083200`.
- **7,125 discovered functions**, each exported as pseudocode and assembly; zero failed exports, **991 warning-bearing results**. This is not recovered original or recompilable source.
- Original-byte verification and independent saved-project readback. Full assembly evidence additionally includes the 70 instructions outside discovered functions.
- Eight stock descriptors / 40 callback slots; a 12-slot registry; concrete branch/literal reach and startup-memory constraints.
- **19 local analysis/feasibility tests passed** in the retained external workspace. The pure repository tests below are a separate, portable check; they do not rerun Ghidra or prove device behavior.

The header declares 8 MB flash, DIO and 80 MHz; this is image metadata, not a physical JEDEC/partition-table measurement. The vendor update is an application image, **not a full device flash backup**.

## Repository contents

- [`docs/decompilation-report.md`](docs/decompilation-report.md): actual analysis, coverage and warnings.
- [`docs/native-screen-assessment.md`](docs/native-screen-assessment.md): verified native-screen hook constraints.
- [`docs/screen-web-config.md`](docs/screen-web-config.md): requested configuration/authentication boundary; implementation remains unverified.
- [`docs/claude-usage-sources.md`](docs/claude-usage-sources.md): native usage sources, privacy and missing-data semantics. Documentation examples are explicitly synthetic, never real account output.
- [`docs/ota-safety-review.md`](docs/ota-safety-review.md): installation/preservation risks and evidence gaps.
- `analysis/`: small derived address/hash/count metadata and the selected Picture target.
- `tools/`: authored image parser, instruction-reach checks and the actual Ghidra scripts used.
- `verification/`: recorded original test source; requires the external authenticated vendor/evidence layout, not just this checkout.
- `tests/`: portable parser, opcode and metadata checks.

Reports and recorded launch scripts retain source-workspace paths as provenance. Their adjacent raw-evidence files are intentionally absent here. See [`docs/reproduction.md`](docs/reproduction.md) before running a headless replay.

## Portable verification

Python 3.10+ and pytest run the backend/portable suite. Node is additionally used for the JavaScript state regression and syntax check (Node 26 was exercised); the Node regression is explicitly skipped when Node is absent.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

Parse an independently obtained image without touching a device:

```bash
python tools/esp_image.py /path/to/application.bin --output image-report.json
```

## Safety and exclusions

Stock binaries/assets, vendor/community checkouts, Ghidra databases, massive raw exports, private device backups, credentials and runtime data are **not committed**. Vendor firmware is not open-source and is not relicensed here. Original backups and full evidence remain outside Git.

No OTA installation may proceed until the exact candidate, actual application-slot capacity, filesystem preservation, boot/security compatibility and a recovery route are verified. No judge/reviewer agent was used for this publication; checks are programmatic tests, syntax/diff checks and credential/artifact scans.
