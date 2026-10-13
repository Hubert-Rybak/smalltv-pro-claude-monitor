# Reproduction and publication scope

This is a curated snapshot of authored tools, reports and small derived metadata. The source workspace is `/opt/data/smalltv-pro-recon`. The full vendor update, Ghidra project, analyzer logs, pseudocode/assembly exports and private device backups remain there, outside Git.

## Portable tests versus full evidence checks

`python -m pytest` runs only `tests/`, as configured in `pytest.ini`. These tests exercise the published parser's malformed-input rejection, the original opcode/reach checker against four actual instruction records, and consistency of committed metadata. They do **not** rerun Ghidra, verify all 7,125 function files or execute ESP32 firmware.

The four opcode records contain only 12 instruction bytes with their original addresses/source offsets. They are neither a firmware image nor recovered source. A vendor image is not bundled or downloaded by the tests.

`verification/recorded-analysis-tests/` and `verification/recorded-native-tests/` retain the original integration-test source unchanged. Their original parent-directory assumptions and authenticated vendor/raw-evidence inputs require the external source-workspace layout. They are deliberately excluded from portable pytest discovery, not silently counted as passing.

## Exact recorded environment

The analysis used Ghidra `12.1.4`, `Xtensa:LE:32:default`, JDK `/opt/data/tools/jdk-21.0.12.1+1`, a 768 MiB headless heap and two CPUs. Toolchain hashes and image mapping are retained in `analysis/`. Image and Ghidra source addresses have not been renumbered.

The launch scripts are preserved as **host-specific recorded commands**, not one-click portable installation scripts. Read them before execution. They retain `/opt/data/...` paths, require the original workspace/tool layout and write analysis outputs/logs there. The first import must use a fresh project/output location; do not accidentally replace sealed original evidence.

For a new isolated replay:

1. Obtain the exact vendor image independently and verify size 2,106,432 and SHA-256 `1aa9a0408e8a3bee568a45376eb2583fe35ba4daafc14880a8cf1531540066be`.
2. Prepare the pinned Ghidra/JDK environment and a **new** analysis workspace. Preserve the original recorded workspace.
3. Put `MapEsp32Image.java`, `ExportEsp32Analysis.java` and the parser under the replay workspace's `scripts/`; set the recorded runner's root, vendor and tool paths explicitly for that workspace.
4. Run `analyzeHeadless` with the recorded `BinaryLoader`, Xtensa processor, mapper pre-script and exporter post-script. Inspect script/analyzer logs and mapping/export artifacts, not just the process exit code.
5. Reopen read-only using `VerifyEsp32Readback.java`. Run the original vendor-byte/export tests with the authenticated replay layout.
6. Run `AuditNativeScreen.java` against the saved project read-only; compare every CALL8/L32R record with `xtensa_reach.py` and retain mismatches/warnings.

These are analysis operations, not flashing instructions. No device access, replacement firmware, account login or quota fetch is implemented by this repository.

## Publication checks

The private GitHub repository was confirmed empty before preparation. Only curated text/code/small derived metadata are staged; no vendor/community tree, raw function exports, Ghidra databases, downloaded official-documentation caches, private backups, credentials or runtime data are included.

The source `native-screen-feasibility/tests/test_followup.py` was found absent during preparation and recovered from the independently checksum-verified retained `followup-evidence.tar.gz`. The recovered file matched SHA-256 `13c35808c1af08027b6c5e0aecb3d421a7ba844ac90c66ba55b8192bb31b572b`; the archive matched `f622580ffc3243ebfb498313bc56e6b87a0693ff6e93ab00fa355dc42ff5c14c`. The cause of its removal remains unknown; no baseline manifest was regenerated to conceal it.

No judge/reviewer agent is used. Programmatic tests, syntax checks, secret/artifact exclusion scans and remote ref/blob verification are distinct from independent human/LLM review or hardware testing.
