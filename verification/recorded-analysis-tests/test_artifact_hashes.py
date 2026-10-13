from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]


def test_retained_artifact_hashes_cover_complete_function_exports():
    manifest = ROOT / 'ARTIFACT_SHA256SUMS.txt'
    assert manifest.is_file(), 'Artifact SHA256 manifest not yet generated'
    paths = set()
    count_c = 0
    count_asm = 0
    for line in manifest.read_text().splitlines():
        digest, relative = line.split('  ', 1)
        assert relative not in paths, f'duplicate manifest path: {relative}'
        paths.add(relative)
        path = ROOT / relative
        assert path.is_file(), f'hashed artifact missing: {relative}'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'changed artifact: {relative}'
        if relative.startswith('exports/functions/'):
            count_c += relative.endswith('.c')
            count_asm += relative.endswith('.asm')
    assert count_c == count_asm == 7125
    assert 'DECOMPILATION_REPORT.md' in paths
    assert 'exports/project_readback.json' in paths
    assert 'exports/handler_map.json' in paths
    assert 'scripts/MapEsp32Image.java' in paths
    assert 'scripts/ExportEsp32Analysis.java' in paths
    assert 'projects/smalltv_v3_3_65.gpr' in paths
    assert '../vendor/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin' in paths
