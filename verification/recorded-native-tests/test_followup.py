from pathlib import Path
import json
import hashlib
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT.parent / 'decompilation'
OUT = ROOT / 'exports'
VENDOR = ROOT.parent / 'vendor/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin'


def read_json(path):
    assert path.is_file(), f'Follow-up artifact missing: {path}'
    return json.loads(path.read_text())


def test_actual_orphan_instructions_account_for_original_coverage_gap():
    audit = read_json(OUT / 'audit_summary.json')
    original = read_json(ORIGINAL / 'exports/summary.json')
    verified = read_json(ORIGINAL / 'exports/verified_counts.json')
    assert audit['discovered_functions'] == original['discovered_functions'] == 7125
    assert audit['orphan_instruction_count'] == original['all_disassembled_instruction_count'] - verified['exported_instruction_count']
    assert audit['orphan_instruction_bytes'] == original['all_disassembled_instruction_bytes'] - verified['unique_exported_instruction_bytes']
    path = OUT / 'orphan_instructions.jsonl'
    assert path.is_file()
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    data = VENDOR.read_bytes()
    assert len(rows) == audit['orphan_instruction_count']
    assert sum(len(bytes.fromhex(r['bytes_hex'])) for r in rows) == audit['orphan_instruction_bytes']
    for row in rows:
        raw = bytes.fromhex(row['bytes_hex'])
        offset = row['source_file_offset']
        assert raw == data[offset:offset + len(raw)]
        assert row['function'] is None


def test_fill_runs_not_assumed_safe_code_caves():
    audit = read_json(OUT / 'audit_summary.json')
    runs = read_json(OUT / 'fill_runs.json')
    data = VENDOR.read_bytes()
    assert len(runs) == audit['fill_run_count']
    assert runs
    for run in runs:
        assert run['length'] >= 16
        offset = run['source_file_offset']
        assert data[offset:offset + run['length']] == bytes([run['value']]) * run['length']
        assert run['safe_extension_point_established'] is False
        assert 'reference_count' in run
        assert 'defined_data_overlaps' in run
    assert audit['vendor_sha256'] == hashlib.sha256(data).hexdigest()


def test_descriptor_callbacks_and_registry_capacity_attested():
    rows = read_json(OUT / 'descriptor_audit.json')
    assert len(rows) == 8
    assert any(row['name'] == 'Monitor' for row in rows)
    for row in rows:
        assert row['descriptor_bytes_match_original'] is True
        assert len(row['callbacks']) == 5
        assert all(callback['function_discovered'] for callback in row['callbacks'])
    hooks = read_json(OUT / 'hook_review.json')
    assert hooks['registry_capacity'] == 12
    assert hooks['stock_registration_count'] == 8
    assert hooks['append_code_start'] == '401df170'
    assert hooks['modified_firmware_generated'] is False
    validation = read_json(OUT / 'encoding_validation.json')
    assert validation['call8_checked'] > 0
    assert validation['l32r_checked'] > 0
    assert validation['mismatches'] == []


def test_startup_clearance_blocks_naive_initialized_dram_tail():
    hooks = read_json(OUT / 'hook_review.json')
    assert 'startup_dram_clear' in hooks, 'Startup RAM boundary audit missing'
    clear = hooks['startup_dram_clear']
    assert clear['start'] == '3ffc4180'
    assert clear['end_exclusive'] == '3ffd4818'
    assert clear['length'] == 0x10698
    assert clear['naive_descriptor_at_original_dram_end_would_be_cleared'] is True
    assert clear['startup_call_address'] == '40083229'


def encoding():
    path = ROOT / 'scripts/xtensa_reach.py'
    assert path.is_file(), 'Xtensa encoding/reach checker not implemented'
    spec = importlib.util.spec_from_file_location('xtensa_reach', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_call8_decoder_matches_actual_stock_calls():
    module = encoding()
    data = VENDOR.read_bytes()
    for pc, target in [(0x400f3886, 0x400f4000), (0x400f38e3, 0x400f4000), (0x400f38ed, 0x400f4028)]:
        offset = pc - 0x400d0020 + 0xe0020
        assert module.decode_call8(pc, data[offset:offset + 3]) == target
    assert module.call8_reachable(0x400f38e3, 0x401df170) is False
    assert module.call8_reachable(0x400f38e3, 0x400f4000) is True


def test_l32r_decoder_matches_original_literal_load():
    module = encoding()
    data = VENDOR.read_bytes()
    pc = 0x400f38db
    offset = pc - 0x400d0020 + 0xe0020
    assert module.decode_l32r(pc, data[offset:offset + 3]) == 0x400d1548
    assert module.l32r_reachable(0x400f38e0, 0x401df170) is False
    assert module.l32r_reachable(0x400f38e0, 0x400d1548) is True


def test_decoders_fail_closed_for_wrong_opcodes_and_alignment():
    module = encoding()
    for fn in [module.decode_call8, module.decode_l32r]:
        try:
            fn(0x400f38e3, b'\x00\x00\x00')
        except ValueError:
            pass
        else:
            assert False, 'wrong opcode must be rejected'
    assert module.call8_reachable(0x400f38e3, 0x400f4001) is False
    assert module.l32r_reachable(0x400f38e0, 0x400d1549) is False
