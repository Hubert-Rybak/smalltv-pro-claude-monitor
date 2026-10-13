from pathlib import Path
import importlib.util
import hashlib
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT.parent / 'vendor/firmware/PRO_V3.3.65EN/FW_SmallTV-PRO_V3.3.65EN.bin'
EXPECTED_SHA256 = '1aa9a0408e8a3bee568a45376eb2583fe35ba4daafc14880a8cf1531540066be'
EXPECTED_SEGMENTS = [
    (0x3f400020, 0xd5b14, 0x18, 0x20),
    (0x3ffbdb60, 0x6620, 0xd5b34, 0xd5b3c),
    (0x40080000, 0x3eb4, 0xdc15c, 0xdc164),
    (0x400d0020, 0x10f150, 0xe0018, 0xe0020),
    (0x40083eb4, 0x132a0, 0x1ef170, 0x1ef178),
]


def load_parser():
    path = ROOT / 'scripts/esp_image.py'
    assert path.is_file(), 'ESP image parser not implemented'
    spec = importlib.util.spec_from_file_location('esp_image', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_exact_vendor_segment_mapping():
    mod = load_parser()
    data = VENDOR.read_bytes()
    result = mod.parse_image(data)
    assert result['sha256'] == EXPECTED_SHA256 == hashlib.sha256(data).hexdigest()
    assert result['size'] == 2106432
    assert result['entry_address'] == 0x40083200
    assert result['chip_id'] == 0
    assert result['entry_file_offset'] == 0xdf364
    assert result['entry_bytes_hex'] == data[0xdf364:0xdf384].hex()
    assert [(s['address'], s['length'], s['header_offset'], s['data_offset']) for s in result['segments']] == EXPECTED_SEGMENTS
    for seg in result['segments']:
        assert seg['sha256'] == hashlib.sha256(data[seg['data_offset']:seg['data_offset'] + seg['length']]).hexdigest()
    assert result['checksum_valid'] is True
    assert result['image_digest_valid'] is True


def test_reject_invalid_magic():
    mod = load_parser()
    data = bytearray(VENDOR.read_bytes()); data[0] = 0
    try:
        mod.parse_image(bytes(data))
    except ValueError as err:
        assert 'magic' in str(err)
    else:
        assert False, 'invalid magic must be rejected'


def test_reject_truncated_segment():
    mod = load_parser()
    try:
        mod.parse_image(VENDOR.read_bytes()[:100])
    except ValueError as err:
        assert 'truncated' in str(err)
    else:
        assert False, 'truncated image must be rejected'


def test_reject_changed_segment_checksum():
    mod = load_parser()
    data = bytearray(VENDOR.read_bytes()); data[0x300] ^= 1
    try:
        mod.parse_image(bytes(data))
    except ValueError as err:
        assert 'checksum' in str(err)
    else:
        assert False, 'changed segment data must be rejected'
