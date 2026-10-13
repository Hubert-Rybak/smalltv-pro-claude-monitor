"""Portable checks only: no device, network, vendor binary or raw Ghidra exports."""
from pathlib import Path
import importlib.util
import json

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHA256 = '1aa9a0408e8a3bee568a45376eb2583fe35ba4daafc14880a8cf1531540066be'


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(relative):
    return json.loads((ROOT / relative).read_text())


@pytest.mark.parametrize('data,message', [
    (b'', 'truncated ESP32 header'),
    (bytes(24), 'invalid ESP image magic'),
    (bytes([0xe9, 1]) + bytes(22), 'truncated segment header'),
])
def test_parser_rejects_malformed_input(data, message):
    with pytest.raises(ValueError, match=message):
        load_tool('esp_image').parse_image(data)


RECORDS = read_json('tests/fixtures/xtensa.json')['records']


@pytest.mark.parametrize('record', RECORDS)
def test_original_instruction_fixture_target(record):
    fixture = read_json('tests/fixtures/xtensa.json')
    assert fixture['vendor_sha256'] == SHA256
    decoder = getattr(load_tool('xtensa_reach'), 'decode_' + record['kind'])
    assert decoder(record['pc'], bytes.fromhex(record['instruction_hex'])) == record['target']


@pytest.mark.parametrize('name', ['decode_call8', 'decode_l32r'])
@pytest.mark.parametrize('raw', [b'', bytes(3)])
def test_opcode_checker_rejects_bad_length_or_opcode(name, raw):
    with pytest.raises(ValueError):
        getattr(load_tool('xtensa_reach'), name)(0x400f38e3, raw)


def test_reach_checks_reject_append_target_and_misalignment():
    module = load_tool('xtensa_reach')
    assert not module.call8_reachable(0x400f38e3, 0x401df170)
    assert module.call8_reachable(0x400f38e3, 0x400f4000)
    assert not module.call8_reachable(0x400f38e3, 0x400f4001)
    assert not module.l32r_reachable(0x400f38e0, 0x401df170)
    assert module.l32r_reachable(0x400f38e0, 0x400d1548)
    assert not module.l32r_reachable(0x400f38e0, 0x400d1549)


def test_committed_coverage_counts_agree_without_source_recovery_claim():
    summary = read_json('analysis/decompilation-summary.json')
    counts = read_json('analysis/verified-counts.json')
    audit = read_json('analysis/native-screen/audit-summary.json')
    assert summary['discovered_functions'] == counts['discovered'] == 7125
    assert counts['unique_entries'] == counts['assembly_files'] == counts['pseudocode_files'] == 7125
    assert summary['decompile_failures'] == counts['failures'] == 0
    assert summary['successful_functions_with_warnings'] == counts['warning_functions'] == 991
    assert summary['all_disassembled_instruction_count'] == counts['exported_instruction_count'] + audit['orphan_instruction_count']
    assert summary['all_disassembled_instruction_bytes'] == counts['unique_exported_instruction_bytes'] + audit['orphan_instruction_bytes']
    assert 'NOT complete binary/source coverage' in summary['coverage_warning']
    assert audit['read_only_audit'] and not audit['modified_firmware_generated']


def test_picture_target_preserves_other_apps_and_web_config_boundary():
    target = read_json('analysis/picture-target.json')
    config = target['configuration']
    assert target['vendor_sha256'] == SHA256
    assert target['stock_internal_name'] == 'Picture' and target['stock_slot'] == 3
    assert len(target['preserved_apps']) == len(set(target['preserved_apps'])) == 7
    assert len(target['callbacks']) == 5
    assert config['management_surface'] == 'Device web interface'
    assert not config['host_os_question_required_for_screen_configuration']
    assert not config['direct_esp32_consumer_login_api_verified']
    assert not config['web_login_implementation_verified']
    assert not target['firmware_modified'] and not target['device_modified'] and not target['judge_used']


def test_retained_snapshot_files_match_recorded_hashes():
    import hashlib
    manifest = read_json('analysis/source-snapshot.json')
    paths = [row['path'] for row in manifest['files']]
    assert len(paths) == len(set(paths))
    for row in manifest['files']:
        path = (ROOT / row['path']).resolve()
        assert path.is_relative_to(ROOT)
        assert path.stat().st_size == row['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
