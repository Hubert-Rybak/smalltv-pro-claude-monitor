#!/usr/bin/env bash
# Read-only audit: no reanalysis, project mutation, firmware modification or device access.
set -euo pipefail
ROOT=/opt/data/smalltv-pro-recon/native-screen-feasibility
ORIGINAL=/opt/data/smalltv-pro-recon/decompilation
export JAVA_HOME=/opt/data/tools/jdk-21.0.12.1+1
export PATH="$JAVA_HOME/bin:$PATH"
export GHIDRA_HEADLESS_MAXMEM=768M
export TMPDIR=/opt/data/cache/scratch
export GHIDRA_HEADLESS_JAVA_OPTIONS="-Djava.io.tmpdir=$TMPDIR"
exec > "$ROOT/logs/headless-console.log" 2>&1
set -x
/opt/data/tools/ghidra_12.1.4_PUBLIC/support/analyzeHeadless "$ORIGINAL/projects" smalltv_v3_3_65 \
  -process FW_SmallTV-PRO_V3.3.65EN.bin -noanalysis -readOnly \
  -scriptPath "$ROOT/scripts" -postScript AuditNativeScreen.java "$ORIGINAL" "$ROOT/exports" \
  -max-cpu 2 -log "$ROOT/logs/ghidra-audit.log" -scriptlog "$ROOT/logs/ghidra-script.log"
