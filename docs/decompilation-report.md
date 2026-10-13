# SmallTV-PRO V3.3.65EN — actual Ghidra decompilation

## Result and provenance

**Real headless Ghidra analysis completed. All 7,125 discovered functions have assembly and pseudocode exports. This is not recovered, recompilable source.** No device access, flash write, modified firmware, or GitHub change was performed.

Input: `../vendor/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin`, 2,106,432 bytes, SHA-256 `1aa9a0408e8a3bee568a45376eb2583fe35ba4daafc14880a8cf1531540066be`. It is the **vendor release application image, NOT a device flash dump**. The stock version string at `0x3f45c4d7` is `V3.3.65EN`. Bootloader, partition table, eFuses, actual filesystem contents, and device-specific configuration are not in this input.

Toolchain: Ghidra 12.1.4, native `Xtensa:LE:32:default`, default compiler spec, Temurin JDK 21.0.12.1+1; exact tool hashes in `toolchain.json`. Both the segment checksum and appended image digest independently validate in `image_manifest.json`.

## Correct image mapping

esptool's displayed offsets identify each **8-byte segment header**; payloads start eight bytes later. The official image format specifies address and length before segment data.[1]

| Block | Virtual address | Length | Segment-header file offset | Actual payload file offset |
|---|---:|---:|---:|---:|
| DROM | `0x3f400020` | `0xd5b14` | `0x18` | `0x20` |
| DRAM | `0x3ffbdb60` | `0x6620` | `0xd5b34` | `0xd5b3c` |
| IRAM_0 | `0x40080000` | `0x3eb4` | `0xdc15c` | `0xdc164` |
| IROM | `0x400d0020` | `0x10f150` | `0xe0018` | `0xe0020` |
| IRAM_1 | `0x40083eb4` | `0x132a0` | `0x1ef170` | `0x1ef178` |

Entry point: **`0x40083200`**, original file offset **`0xdf364`**, decoded as `entry a1,0x40`. Its 32 source bytes and all five mapped payload hashes match the vendor image. Ghidra `FileBytes` backing retains original file offsets. Two DRAM gaps are explicitly **uninitialized**, not invented zero contents or recovered BSS boundaries. ROM/MMIO references remain unsupplied.

## Verified coverage and limitations

- Discovered / unique inventoried / assembly exported / pseudocode exported: **7,125 / 7,125 / 7,125 / 7,125**.
- Decompiler failed attempts: **0**; analysis timeout: **false**.
- **991** successful pseudocode exports contain warnings. **11** contain bad-instruction/truncated-flow warnings; **13** function entries produced p-code-constructor errors in the log. These sets differ: a nonempty C result does not prove correct decoding or complete control flow.
- **420,405** exported instruction records; **1,114,847** unique function instruction bytes. All exported instruction bytes and reported source offsets were compared against the exact original file by tests.
- Those bytes are **92.5261% of 1,204,900 initialized executable-segment bytes**, **not 92.5261% proven code coverage**: executable segments also contain literal pools/data. There are 420,475 disassembled instructions globally; instructions outside discovered functions are not included in per-function assembly.
- Function discovery used 7,137 aligned `ENTRY a1` candidates with 16–8,192-byte frames, direct-flow analysis, and Ghidra analyzers. False positives, merged tails, and undiscovered indirect/call0 callbacks remain possible.
- **5,151** NUL-terminated printable string candidates retain source addresses, raw pointer locations, and direct/literal-mediated code xrefs. Numeric pointer matches are marked as evidence, not assumed types; printable strings in assets can be false positives.
- **12 tests pass**, including complete assembly-byte comparison, independent saved-project readback with the identical 7,125-entry function set, and verification of every file listed in the retained SHA-256 manifest.

## Address-linked handlers

All entries below have both `exports/functions/<entry>.c` and `.asm`; labels describe inferred roles, not recovered author symbols.

| Area | Actual function entries | Supporting evidence |
|---|---|---|
| Setup / built-in app registration | `400f34dc`, `400f4000`, `401d1b94` | Setup calls registration eight times; original 32-byte descriptors retained in `exports/app_descriptors.json`; capacity check rejects count above 11. |
| UI dispatch / app events | `400f42ec`, `400f4124`, `400f426c` | Calls descriptor offsets `+0xc` and `+0x10`; event delivery uses `+0x1c`. Dispatcher instructions at `400f438a` / `400f43a9` are indirect calls. |
| Monitor setup / outgoing request / rendering | `400d82ec`, `400d843c`, `400d84c0`, `400d8fdc`, `400d9568` | `/sse` at `3f45a2ae`; load at `400d8593` through literal `400d05ec`; metric tags load in `400d84c0`; fixed CPU/RAM labels format in `400d9568`. |
| HTTP route binding / `/set` | `400e4b20`, `400de644` | `400e4b20` binds `/set` to `400de644`; its monitor branch reads `ip` and `m_i`, writes monitor config, and sends stock Monitor events. |
| LittleFS / configuration | `4011a9c4`, `400e4ff4`, `400e5e38`, `400e6f64`, `400e63f4`, `400e8300` | Setup mounts `/littlefs` with partition label `spiffs`; `/.sys/monitor.json` at `3f46e979`; `/.sys/app.json` at `3f46e8de`; read/write helpers recover actual JSON fields. |
| Files / picture / upload | `400de1ac`, `400d9ac4`, `400d9bf0`, `400dbe5c` | `/doUpload` callback writes the requested directory/file; Picture enumerates `/image`; web fallback serves embedded stock gzip pages before its filesystem fallback. |
| OTA HTTP state machine | `400da7dc`, `400da670`, `400da994` | `/update` at `3f45cad0`; handler switches upload start/write/end/abort states, distinguishes `filesystem`, and reports authentication/update status. |
| OTA partition selection / updater | `4011ffa8`, `401322a0`, `40132144`, `401321b8` | Calls/assertion strings identify next/running/count partition helpers. Some SDK helper decompilations have p-code errors; do not treat those C results as complete implementations. |

`exports/handler_map.json` links **34 manually traced functions** to both export hashes. `exports/focus.json` / `FOCUSED_INDEX.md` include every function selected by relevant string xrefs: app/UI 8, monitor 7, filesystem/config 109, OTA 8 (overlapping groups). This automatic index is narrower than the manually traced callback/call-chain table above.

## Actual extension points and patching assessment

**A ninth native screen is technically plausible, but not yet a safe, practical installable patch.** A concrete internal hook was found, rather than guessed:

1. The stock controller registers **eight apps**: BitCoin, Stock, Weather, Picture, Monitor, Clock, Idea, Settings. `401d1b94` checks a **12-slot maximum**; `400f4000` stores descriptor pointers at controller `+0x10 + 4*index`, paired values at `+0x40 + 4*index`, and increments count at `+0x84`. Therefore a ninth registration is not blocked by the observed registry capacity.
2. Monitor's descriptor at **`0x3ffbdca0`**, file **`0xd5c7c`**, contains pointers to setup `400d82ec`, loop `400d843c`, cleanup `400d8298`, and event handler `400d8fdc`; its complete measured words are retained. This is an **internal binary-injection hook, not an external/plugin API**.
3. A new screen still requires real executable code and a descriptor, hooks/trampolines with the Xtensa windowed ABI, verified literal/address relocations and image-layout constraints, LVGL lifecycle/heap ownership, image integrity regeneration, and measured partition capacity. No code cave, spare flash region, recoverable source build, hardware recovery method, or successful patched boot was established. Vendor image checksum validity does not establish the device's secure-boot/eFuse state.

**Lower-risk stock mechanisms actually found:**

- **Existing Monitor network input.** `400d84c0` connects to the configured `ip`, optionally parses `host:port` (default 80), sends `GET /sse`, searches the stream for literal **LF LF**, then reads a **single line**. It is not a general JSON/SSE parser. It extracts `F_CPU:` up to `MHz`, `UP_CPU:`/`UP_RAM:`/`UP_DRIVE_C:` up to `%`, `T_CPU:` up to the UTF-8 `℃` character, `PW_CPU:` up to `W`, disk quantities up to `GB`, and `TIME:` up to `{`. Source bytes for terminators are verifiable at `3f45a327`, `3f4bafc8`, `3f45a342`, and `3f45a377`. Standard CRLF HTTP header termination alone does not contain LF LF; an adapter must account for this exact framing. This supplies existing widgets, not arbitrary new widget names/layout. No live protocol compatibility test was performed here.
- **Stock configuration controls.** `/set`'s `ip` + `m_i` path and `/.sys/monitor.json` fields `theme`, `m_i`, `ip` configure the existing input. Monitor setup clamps loaded interval to at least 1 second. `theme` in `/.sys/app.json` is a stock selection/configuration field, not executable screen code. Do not assume out-of-range values add apps.
- **Picture assets.** User-provided images/GIFs in `/image`, through the stock upload/Picture paths, can present a custom visual without changing firmware. This uses filesystem writes/flash wear, not a native plugin or unlimited streaming screen. Uploading HTML does not replace the LCD's native UI.

Recommendation: use these existing mechanisms for a first stock-compatible integration; reserve an additional native screen patch for a separate, recovery-backed engineering task. Nothing was flashed or configured by this analysis.

## Reproduction and retained artifacts

- `run_headless.sh`: exact import/map/analyze/export command and 768 MiB heap/2-core settings.
- `run_readback.sh`: independently reopens the saved Ghidra project read-only.
- `projects/smalltv_v3_3_65.gpr` and `.rep/`: retained editable analysis database.
- `exports/mapped_image.json`, `summary.json`, `verified_counts.json`, `project_readback.json`: machine-readable attestations.
- `exports/functions.jsonl`, `calls.jsonl`, `string_xrefs.jsonl`, `app_descriptors.json`, `warnings.json`: address-linked evidence.
- `exports/functions/`: **7,125 raw pseudocode files + 7,125 assembly files**.
- `scripts/` and `tests/`: mapper, exporter, image parser, xref selector, readback verifier, validation tests.
- `logs/`: commands, full headless/analyzer/script output, RED/GREEN test output, saved-project readback.
- `ARTIFACT_SHA256SUMS.txt` / `ARTIFACT_SCOPE.json`: retained-file hash manifest and exact scope, excluding itself, caches, failed-project/lock files, and the post-manifest validation log. Regenerate with `scripts/hash_artifacts.py`.

Warnings retained: the first attempt had a corrected `FileBytes` import/compilation error and was aborted; logs are preserved under `logs/attempt1-compile-failure/` and none of that raw-address analysis is counted. GNU demangler native execution was permission-denied during the successful analysis; other analyzers and the native decompiler completed. No original symbol/source recovery is claimed. Keep stock binary, assets, Ghidra databases, and massive raw exports **out of the publication repository**.

## Sources

[1] https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/firmware-image-format.html — Espressif ESP32 firmware image format
