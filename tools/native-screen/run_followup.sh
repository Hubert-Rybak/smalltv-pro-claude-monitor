#!/usr/bin/env bash
# Reproduce actual static audits and tests; no modified binary or device operations.
set -euo pipefail
ROOT=/opt/data/smalltv-pro-recon/native-screen-feasibility
ORIGINAL=/opt/data/smalltv-pro-recon/decompilation
PY=/opt/data/smalltv-pro-recon/tooling-venv/bin/python
exec > "$ROOT/logs/followup-console.log" 2>&1
set -x
bash "$ROOT/run_audit.sh"
"$PY" "$ROOT/scripts/review_hooks.py" > "$ROOT/logs/hook-review.log" 2>&1
"$PY" -m pytest "$ORIGINAL/tests" "$ROOT/tests" -q > "$ROOT/logs/combined-tests-green.log" 2>&1
(cd "$ORIGINAL" && sha256sum -c ARTIFACT_SHA256SUMS.txt) > "$ROOT/logs/original-artifact-hash-verification-final.log" 2>&1
sha256sum /opt/data/smalltv-pro-recon/vendor/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin
