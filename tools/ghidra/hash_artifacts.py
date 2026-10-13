#!/usr/bin/env python3
"""Hash retained, completed static-analysis evidence, never the device."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_NAMES = {'ARTIFACT_SHA256SUMS.txt'}
EXCLUDED_VERIFICATION_LOG = 'logs/tests-artifact-verification.log'
paths = []
for path in ROOT.rglob('*'):
    if not path.is_file():
        continue
    relative = path.relative_to(ROOT).as_posix()
    if path.name in EXCLUDED_NAMES or relative == EXCLUDED_VERIFICATION_LOG:
        continue
    if '__pycache__' in path.parts or '.pytest_cache' in path.parts:
        continue
    if relative.startswith('projects/attempt1_incomplete') or path.name.endswith(('.lock', '.lock~')):
        continue
    paths.append(relative)
scope_name = 'ARTIFACT_SCOPE.json'
if scope_name not in paths:
    paths.append(scope_name)
paths.append('../vendor/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin')
paths = sorted(set(paths))
scope = {
    'scope': 'Completed static-analysis exports, saved Ghidra project, scripts/tests, references, report, retained command/analyzer/test logs, and exact vendor input',
    'hashed_files': len(paths),
    'exclusions': ['hash manifest itself', 'post-manifest validation log logs/tests-artifact-verification.log', '__pycache__', '.pytest_cache', 'failed attempt1 project files', 'project lock files'],
    'source_provenance': 'Vendor release application image; NOT device flash dump',
}
(ROOT / scope_name).write_text(json.dumps(scope, indent=2) + '\n')
lines = []
total_bytes = 0
for relative in paths:
    data = (ROOT / relative).read_bytes()
    total_bytes += len(data)
    lines.append(hashlib.sha256(data).hexdigest() + '  ' + relative)
(ROOT / 'ARTIFACT_SHA256SUMS.txt').write_text('\n'.join(lines) + '\n')
print(json.dumps({'manifest': str(ROOT / 'ARTIFACT_SHA256SUMS.txt'), 'files_hashed': len(lines), 'total_bytes_hashed': total_bytes}, indent=2))
