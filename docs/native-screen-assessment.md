# Native-screen extension — verified static follow-up

**No firmware was modified or flashed.** The original Ghidra project was reopened **read-only**, with analysis disabled. The vendor application remains SHA-256 `1aa9a0408e8a3bee568a45376eb2583fe35ba4daafc14880a8cf1531540066be`.

## New findings

### 1. Registry capacity is sufficient, but a direct append-and-call is not

All **eight descriptors and 40 callback slots** were checked against actual saved-project functions and original bytes. The registration guard at `0x401d1b94` permits counts through 11; the controller therefore supports **12 slots**. This confirms space for a ninth app without growing its pointer arrays.

The last unconditional stock registration is Settings, `CALL8` at **`0x400f38e3`** to `0x400f4000`. Appending code immediately after the existing IROM segment would start at **`0x401df170`**. That is **964,748 bytes from this call's aligned PC base**, but `CALL8` permits at most **524,284 bytes forward**. **Simply retargeting this three-byte call to appended code cannot work.**

Encoding checks compared **24,449 stock CALL8 instructions and 32,109 L32R instructions** with the pinned Ghidra SLEIGH definitions and raw vendor-byte assembly exports: **zero mismatches**. This is static verification, not Xtensa CPU emulation.

A concrete six-byte hook window exists at **`0x400f38e0`**, file offset **`0x1038e0`**:

```text
101120 e57100   mov a1,a1 ; call8 0x400f4000
```

A proposed `L32R` / `CALLX8` sequence could fit that size, but would need a separately verified literal word between **`0x400b38e0` and `0x400f38dc`**. No safe reusable literal slot or working trampoline was established. The existing Settings descriptor literal is live; overwriting it would corrupt the registration argument. A wrapper would also have to preserve the original Settings registration, the caller's windowed ABI, and runtime lifetime rules.

### 2. The observed zero-filled areas are not established safe code caves

Scanning all initialized executable segments found **15 runs of at least 16 identical zero/0xff bytes**:

- **14 zero runs** fall in `0x40080000`–`0x40080400`. Startup passes `0x40080000` to `0x40092fd8`, whose instruction at `0x40092fdb` writes **VECBASE**. These lie in the vector area, not an established free extension region. Lack of normal Ghidra xrefs does not establish safety for hardware-entered vectors.
- The only IROM run is **18 zero bytes beginning at `0x401dda32`**. It overlaps a discovered function's `ENTRY` operand and `ILL` instruction (`0x401dda30` / `0x401dda33`). Its remaining padding is not proven reusable and is also beyond the registration call's direct reach.

This survey does **not** prove that smaller reusable spaces do not exist. It establishes **zero safe caves from the tested fill-run candidates**.

### 3. Appending an initialized descriptor at the DRAM tail would be wrong

The original initialized DRAM ends at **`0x3ffc4180`**. Startup's call at **`0x40083229`** clears **`[0x3ffc4180, 0x3ffd4818)`**, length **`0x10698`**, using boundaries stored at literal addresses `0x40080698` and `0x40080694`.

A descriptor naively appended at that tail would overlap existing BSS globals and be cleared during boot. It needs an independently justified storage/lifetime strategy; growing the segment alone is not sufficient.

### 4. Replacing an existing screen has a simpler hook, but is a different outcome

Monitor's loop callback is an initialized four-byte pointer at **`0x3ffbdcb0`**, file offset **`0xd5c8c`**, containing **`3c840d40`** → `0x400d843c`. The dispatcher calls it indirectly at `0x400f43a9`.

Changing such a pointer avoids the registration site's direct-call distance constraint. However, that would **replace existing Monitor behavior, not add a ninth app**, and would still require validated callback/UI cleanup, allocation, and ABI behavior. No pointer was changed and no new implementation was fabricated.

## Coverage completion and verification

The saved project still contains **7,125 functions**. The follow-up additionally exports **all 70 instructions / 180 bytes outside those functions** as address-linked JSONL and assembly. Most are exception/window/context restoration sequences, with a small spin-wait/return tail. They were not assigned invented function boundaries or pseudocode.

Combined with the initial per-function exports, assembly evidence now covers **all 420,475 instructions already disassembled in the saved project**. This is not a claim that all firmware code has been discovered.

Validation: **7 follow-up tests plus the original 12 tests**, including original-byte comparisons, decoding/reach checks, descriptor checks and startup RAM clearance. The original **14,312-file** hash manifest is checked independently after the read-only audit.

One previously hashed validation test was found missing. Its exact contents were restored only after matching the original retained SHA-256; the initial failed check and restoration are logged. Its removal cause was not established. Vendor bytes, pseudocode exports and the analysis database were not changed by this recovery.

## Assessment

**Adding a ninth screen is a bounded binary-engineering task, not yet a safe deployable modification.** The internal registration mechanism is real and has spare capacity. The blockers are now specific: a long-range hook with an owned literal/trampoline, correct descriptor lifetime, UI callback lifecycle, actual OTA partition capacity, image-layout/integrity handling, and recovery-backed device testing.

No partition table or device eFuse/secure-boot state is available from this vendor update archive. Keep using stock Monitor input or Picture assets when the goal can be met without native binary injection.

## Retained artifacts

Root: `/opt/data/smalltv-pro-recon/native-screen-feasibility/`

- `exports/audit_summary.json`, `descriptor_audit.json`, `fill_runs.json`
- `exports/orphan_instructions.jsonl` and `.asm`
- `exports/hook_review.json`, `encoding_validation.json`, `encoding_source_evidence.json`
- `scripts/AuditNativeScreen.java`, `xtensa_reach.py`, `review_hooks.py`
- `run_audit.sh`, `run_followup.sh`, `tests/`, `logs/`
- `ARTIFACT_SHA256SUMS.txt`: follow-up evidence hashes (verification logs and caches excluded as recorded in the manifest scope).

Original complete decompilation: `../decompilation/DECOMPILATION_REPORT.md` and its retained project/exports. Pinning and source-address references are in the JSON artifacts; no claim of recovered original source or a successful modified boot is made.
