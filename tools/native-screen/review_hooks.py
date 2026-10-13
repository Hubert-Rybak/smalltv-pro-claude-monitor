#!/usr/bin/env python3
"""Verify actual stock hook bytes and branch/literal reach; never generate patched firmware."""
from pathlib import Path
import hashlib
import json
import re
import struct
from xtensa_reach import decode_call8, decode_l32r, call8_reachable, l32r_reachable

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT.parent / 'decompilation'
OUT = ROOT / 'exports'
mapinfo = json.loads((ORIGINAL / 'image_manifest.json').read_text())
vendor = Path(mapinfo['source_path']).read_bytes()
assert hashlib.sha256(vendor).hexdigest() == mapinfo['sha256']
inventory = {r['entry']: r for r in [json.loads(x) for x in (ORIGINAL / 'exports/functions.jsonl').read_text().splitlines()]}
descriptors = json.loads((ORIGINAL / 'exports/app_descriptors.json').read_text())['descriptors']
checked_call8 = 0
checked_l32r = 0
mismatches = []
for entry, row in inventory.items():
    for line in (ORIGINAL / 'exports' / row['assembly_path']).read_text().splitlines():
        if line.startswith(';') or not line:
            continue
        address, bytes_hex, assembly = line.split('  ', 2)
        pc = int(address, 16)
        raw = bytes.fromhex(bytes_hex)
        call = re.match(r'call8 0x([0-9a-f]+)(?:\s|$)', assembly)
        literal = re.match(r'l32r [a-z0-9]+,0x([0-9a-f]+)(?:\s|$)', assembly)
        if call:
            checked_call8 += 1
            target = int(call.group(1), 16)
            actual = decode_call8(pc, raw)
            if actual != target or not call8_reachable(pc, target):
                mismatches.append({'address': address, 'kind': 'CALL8', 'assembly_target': f'{target:08x}', 'decoded_target': f'{actual:08x}'})
        if literal:
            checked_l32r += 1
            target = int(literal.group(1), 16)
            actual = decode_l32r(pc, raw)
            if actual != target or not l32r_reachable(pc, target):
                mismatches.append({'address': address, 'kind': 'L32R', 'assembly_target': f'{target:08x}', 'decoded_target': f'{actual:08x}'})
validation = {'basis': 'Pinned Ghidra xtensaArch.sinc and xtensaMain.sinc encoding rules; compared against original-byte assembly exports, not guessed source', 'call8_checked': checked_call8, 'l32r_checked': checked_l32r, 'mismatches': mismatches}
(OUT / 'encoding_validation.json').write_text(json.dumps(validation, indent=2) + '\n')
assert not mismatches, f'encoding validation found {len(mismatches)} mismatches'
irom = next(s for s in mapinfo['segments'] if s['address'] == 0x400d0020)
append = irom['address'] + irom['length']
hooks = []
for item in descriptors:
    pc = int(item['registration_call_address'], 16)
    offset = irom['data_offset'] + pc - irom['address']
    raw = vendor[offset:offset + 3]
    actual = decode_call8(pc, raw)
    assert actual == 0x400f4000
    hooks.append({'app': item['name'], 'call_address': f'{pc:08x}', 'source_file_offset': offset, 'raw_call_bytes_hex': raw.hex(), 'decoded_target': f'{actual:08x}', 'append_code_reachable_by_direct_call8': call8_reachable(pc, append), 'append_code_delta_from_call_base': append - ((pc & ~3) + 4), 'maximum_positive_call8_delta': ((1 << 17) - 1) * 4})
validator = (ORIGINAL / 'exports/functions/401d1b94.asm').read_text()
assert 'movi.n a10,0xb' in validator and 'bgeu a10,a9,' in validator
last = hooks[-1]
assert last['app'] == 'Settings'
hook_start = int(last['call_address'], 16) - 3
start_offset = irom['data_offset'] + hook_start - irom['address']
window = vendor[start_offset:start_offset + 6]
assert window[:3] == bytes.fromhex('101120')
assert decode_call8(hook_start + 3, window[3:]) == 0x400f4000
irams = [s for s in mapinfo['segments'] if s['address'] >= 0x40080000 and s['address'] < 0x400d0000]
startup_literals = []
for address in [0x40080698, 0x40080694]:
    segment = next(s for s in irams if s['address'] <= address < s['address'] + s['length'])
    offset = segment['data_offset'] + address - segment['address']
    startup_literals.append({'address': f'{address:08x}', 'source_file_offset': offset, 'value': struct.unpack_from('<I', vendor, offset)[0], 'raw_bytes_hex': vendor[offset:offset + 4].hex()})
clear_start = startup_literals[0]['value']
clear_end = startup_literals[1]['value']
dram = next(s for s in mapinfo['segments'] if s['address'] == 0x3ffbdb60)
dram_end = dram['address'] + dram['length']
startup_asm = (ORIGINAL / 'exports/functions/40083200.asm').read_text()
assert '40083226  a0ccc0  sub a12,a12,a10' in startup_asm
assert '40083229  654208  call8 0x4008b650' in startup_asm
monitor = next(d for d in descriptors if d['name'] == 'Monitor')
loop_pointer_address = int(monitor['descriptor_address'], 16) + 0x10
loop_pointer_offset = monitor['descriptor_file_offset'] + 0x10
assert struct.unpack_from('<I', vendor, loop_pointer_offset)[0] == 0x400d843c
review = {
    'vendor_sha256': mapinfo['sha256'],
    'registry_capacity': 12,
    'stock_registration_count': len(descriptors),
    'registry_capacity_evidence': '401d1b94.asm at 401d1b9e loads 0xb; 401d1ba2 permits unsigned count <=11 before the next registration',
    'controller_pointer_array_offset': 0x10,
    'controller_paired_value_array_offset': 0x40,
    'controller_count_offset': 0x84,
    'append_code_start': f'{append:08x}',
    'append_is_code_placement_candidate_only': True,
    'append_fit_in_device_partition_established': False,
    'stock_registration_calls': hooks,
    'last_registration_window': {'start': f'{hook_start:08x}', 'source_file_offset': start_offset, 'bytes_hex': window.hex(), 'stock_instructions': ['mov a1,a1', 'call8 0x400f4000'], 'candidate_replacement_size_bytes': 6, 'indirect_call_plan': 'L32R a8 from a separately verified nearby literal, then CALLX8 a8; no such patch was generated', 'literal_location_established': False, 'l32r_can_load_literal_at_append_address': l32r_reachable(hook_start, append), 'l32r_lowest_reachable_literal': f'{(((hook_start + 3) & ~3) - (1 << 18)):08x}', 'l32r_highest_reachable_literal': f'{(((hook_start + 3) & ~3) - 4):08x}'},
    'startup_dram_clear': {'start': f'{clear_start:08x}', 'end_exclusive': f'{clear_end:08x}', 'length': clear_end - clear_start, 'startup_call_address': '40083229', 'boundary_literals': startup_literals, 'original_initialized_dram_end': f'{dram_end:08x}', 'naive_descriptor_at_original_dram_end_would_be_cleared': clear_start <= dram_end < clear_end, 'warning': 'Do not grow the initialized DRAM segment into existing BSS globals; startup explicitly clears this range'},
    'existing_screen_callback_data_hook': {'app': 'Monitor', 'descriptor_slot_offset': 0x10, 'address': f'{loop_pointer_address:08x}', 'source_file_offset': loop_pointer_offset, 'raw_bytes_hex': vendor[loop_pointer_offset:loop_pointer_offset + 4].hex(), 'stock_target': '400d843c', 'dispatcher_indirect_call': '400f43a9', 'adds_ninth_app': False, 'runtime_safety_established': False, 'warning': 'Changing this pointer would replace existing Monitor loop behavior, not register an additional screen. Callback/UI lifecycle compatibility is untested.'},
    'image_file_alignment': {'irom_payload_offset_mod_64k': irom['data_offset'] % 65536, 'irom_virtual_address_mod_64k': irom['address'] % 65536},
    'modified_firmware_generated': False,
    'warning': 'Static instruction/layout compatibility only. No runtime callback ABI, literal-slot reuse, UI lifecycle, partition capacity or secure-boot validation was performed.',
}
(OUT / 'hook_review.json').write_text(json.dumps(review, indent=2) + '\n')
source_root = Path('/opt/data/tools/ghidra_12.1.4_PUBLIC/Ghidra/Processors/Xtensa/data/languages')
source_evidence = []
for name, ranges in [('xtensaMain.sinc', [(195, 203)]), ('xtensaInstructions.sinc', [(332, 339), (368, 376), (639, 642)]), ('xtensaArch.sinc', [(200, 214)])]:
    path = source_root / name
    data = path.read_bytes()
    lines = data.decode().splitlines()
    source_evidence.append({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'excerpts': [{'first_line': start, 'last_line': end, 'text': '\n'.join(lines[start - 1:end])} for start, end in ranges]})
(OUT / 'encoding_source_evidence.json').write_text(json.dumps(source_evidence, indent=2) + '\n')
print(json.dumps({'encoding_validation': validation, 'stock_registrations': len(hooks), 'append_code_start': f'{append:08x}', 'last_call_append_delta': last['append_code_delta_from_call_base'], 'last_call_max_positive_delta': last['maximum_positive_call8_delta'], 'candidate_six_byte_hook': review['last_registration_window']}, indent=2))
