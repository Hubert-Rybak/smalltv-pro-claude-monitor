#!/usr/bin/env python3
"""Authenticate and describe an ESP32 application image; never talks to a device."""
from pathlib import Path
import argparse
import hashlib
import json
import struct


def parse_image(data: bytes) -> dict:
    if len(data) < 24:
        raise ValueError('truncated ESP32 header')
    if data[0] != 0xe9:
        raise ValueError('invalid ESP image magic')
    count = data[1]
    entry = struct.unpack_from('<I', data, 4)[0]
    segments = []
    cursor = 24
    checksum = 0xef
    entry_offset = None
    for index in range(count):
        if cursor + 8 > len(data):
            raise ValueError('truncated segment header')
        address, length = struct.unpack_from('<II', data, cursor)
        start = cursor + 8
        end = start + length
        if end > len(data):
            raise ValueError('truncated segment data')
        payload = data[start:end]
        for value in payload:
            checksum ^= value
        segments.append(dict(index=index, address=address, length=length,
                             header_offset=cursor, data_offset=start,
                             sha256=hashlib.sha256(payload).hexdigest(),
                             executable=address >= 0x40000000))
        if address <= entry < address + length:
            entry_offset = start + entry - address
        cursor = end
    checksum_offset = ((cursor + 16) // 16) * 16 - 1
    if checksum_offset >= len(data):
        raise ValueError('truncated checksum')
    if data[checksum_offset] != checksum:
        raise ValueError('invalid segment checksum')
    digest_valid = None
    if data[23] == 1:
        digest = data[checksum_offset + 1:checksum_offset + 33]
        if len(digest) != 32:
            raise ValueError('truncated image digest')
        digest_valid = hashlib.sha256(data[:checksum_offset + 1]).digest() == digest
        if not digest_valid:
            raise ValueError('invalid image digest')
    if entry_offset is None:
        raise ValueError('entry point outside image segments')
    return dict(size=len(data), sha256=hashlib.sha256(data).hexdigest(),
                chip_id=struct.unpack_from('<H', data, 12)[0],
                segment_count=count, segments=segments, entry_address=entry,
                entry_file_offset=entry_offset,
                entry_bytes_hex=data[entry_offset:entry_offset + 32].hex(),
                checksum_offset=checksum_offset, checksum=checksum,
                checksum_valid=True, image_digest_valid=digest_valid,
                provenance='vendor release application image; NOT device flash dump')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = parse_image(args.image.read_bytes())
    result['source_path'] = str(args.image.resolve())
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
