from pathlib import Path
import json
import hashlib

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports'
VENDOR = ROOT.parent / 'vendor/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin'
EXPECTED = [
    (0x3f400020, 0xd5b14, 0x20),
    (0x3ffbdb60, 0x6620, 0xd5b3c),
    (0x40080000, 0x3eb4, 0xdc164),
    (0x400d0020, 0x10f150, 0xe0020),
    (0x40083eb4, 0x132a0, 0x1ef178),
]


def read_json(path):
    assert path.is_file(), f'Real headless artifact missing: {path}'
    return json.loads(path.read_text())


def test_real_ghidra_image_mapping_and_entry():
    manifest = read_json(OUT / 'mapped_image.json')
    data = VENDOR.read_bytes()
    assert manifest['language'] == 'Xtensa:LE:32:default'
    assert manifest['vendor_sha256'] == hashlib.sha256(data).hexdigest()
    assert manifest['entry_address'] == '40083200'
    assert manifest['entry_bytes_hex'] == data[0xdf364:0xdf384].hex()
    assert len(manifest['segments']) == 5
    for seg, (addr, size, offset) in zip(manifest['segments'], EXPECTED):
        assert int(seg['address'], 16) == addr
        assert seg['length'] == size
        assert seg['data_offset'] == offset
        assert seg['ghidra_source_file_offset'] == offset
        assert seg['mapped_sha256'] == hashlib.sha256(data[offset:offset + size]).hexdigest()
    assert all(s['executable'] == (int(s['address'], 16) >= 0x40000000) for s in manifest['segments'])


def test_every_discovered_function_exported_and_counted():
    overview = read_json(OUT / 'summary.json')
    inventory_path = OUT / 'functions.jsonl'
    assert inventory_path.is_file()
    inventory = [json.loads(line) for line in inventory_path.read_text().splitlines()]
    addresses = [r['entry'] for r in inventory]
    assert addresses and len(addresses) == len(set(addresses))
    assert len(inventory) == overview['discovered_functions'] == overview['assembly_exported']
    successes = [r for r in inventory if r['decompile_ok']]
    failures = [r for r in inventory if not r['decompile_ok']]
    assert len(successes) == overview['pseudocode_exported']
    assert len(failures) == overview['decompile_failures']
    assert len(successes) > 0
    for row in inventory:
        asm = OUT / row['assembly_path']
        assert asm.is_file() and asm.stat().st_size > 0
        assert 'source_file_offset' in asm.read_text()
        if row['decompile_ok']:
            code = OUT / row['pseudocode_path']
            assert code.is_file() and code.stat().st_size > 0
        else:
            assert row['decompile_error']
    assert '40083200' in addresses


def test_string_reference_export_retained():
    summary = read_json(OUT / 'summary.json')
    path = OUT / 'string_xrefs.jsonl'
    assert path.is_file()
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == summary['string_count'] > 0
    assert any('monitor' in r['text'].lower() for r in rows)
    assert any(r['code_references'] for r in rows)


def test_every_assembly_instruction_matches_exact_vendor_bytes():
    summary = read_json(OUT / 'summary.json')
    manifest = read_json(OUT / 'mapped_image.json')
    data = VENDOR.read_bytes()
    inventory = [json.loads(line) for line in (OUT / 'functions.jsonl').read_text().splitlines()]
    byte_count = 0
    instruction_count = 0
    for row in inventory:
        lines = (OUT / row['assembly_path']).read_text().splitlines()
        local_count = 0
        for line in lines:
            if not line or line.startswith(';'):
                continue
            address_hex, bytes_hex, rest = line.split('  ', 2)
            address = int(address_hex, 16)
            values = bytes.fromhex(bytes_hex)
            segment = next(s for s in manifest['segments'] if int(s['address'], 16) <= address < int(s['address'], 16) + s['length'])
            offset = segment['data_offset'] + address - int(segment['address'], 16)
            assert offset == int(rest.split('source_file_offset=0x')[1].split()[0], 16)
            assert values == data[offset:offset + len(values)], f'assembly bytes differ at {address_hex}'
            byte_count += len(values)
            local_count += 1
        assert local_count == row['instruction_count']
        instruction_count += local_count
    assert byte_count == summary['summed_function_instruction_bytes_may_overlap']
    assert instruction_count > 0


def test_saved_project_readback_matches_final_export_inventory():
    summary = read_json(OUT / 'summary.json')
    readback = read_json(OUT / 'project_readback.json')
    assert readback['mapping_verified'] is True
    assert readback['same_entry_set'] is True
    assert readback['project_discovered_functions'] == readback['export_inventory_entries'] == summary['discovered_functions']
    assert readback['entry_point_registered'] is True

