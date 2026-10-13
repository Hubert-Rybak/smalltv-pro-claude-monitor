#!/usr/bin/env bash
# Local static analysis only: no serial, LAN, device write or GitHub operation.
set -euo pipefail
ROOT=/opt/data/smalltv-pro-recon/decompilation
VENDOR=/opt/data/smalltv-pro-recon/vendor/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin
export JAVA_HOME=/opt/data/tools/jdk-21.0.12.1+1
export PATH="$JAVA_HOME/bin:$PATH"
export GHIDRA_HEADLESS_MAXMEM=768M
export TMPDIR=/opt/data/cache/scratch
export GHIDRA_HEADLESS_JAVA_OPTIONS="-Djava.io.tmpdir=$TMPDIR"
GHIDRA=/opt/data/tools/ghidra_12.1.4_PUBLIC
mkdir -p "$ROOT/logs" "$ROOT/projects" "$ROOT/exports"
exec > "$ROOT/logs/headless-console.log" 2>&1
set -x
sha256sum "$VENDOR"
"$GHIDRA/support/analyzeHeadless" "$ROOT/projects" smalltv_v3_3_65 \
  -import "$VENDOR" -loader BinaryLoader \
  -processor Xtensa:LE:32:default -cspec default \
  -scriptPath "$ROOT/scripts" \
  -preScript MapEsp32Image.java "$VENDOR" "$ROOT/exports" \
  -postScript ExportEsp32Analysis.java "$ROOT/exports" \
  -analysisTimeoutPerFile 1800 -max-cpu 2 \
  -log "$ROOT/logs/ghidra-analysis.log" \
  -scriptlog "$ROOT/logs/ghidra-script.log"
sha256sum "$VENDOR"
