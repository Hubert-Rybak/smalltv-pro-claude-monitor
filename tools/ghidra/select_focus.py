#!/usr/bin/env python3
"""Select actual stock-firmware function exports by measured string xrefs."""
from pathlib import Path
import argparse
import json

CATEGORIES = ('app_ui', 'monitor_http', 'filesystem_config', 'ota')


def classify_string(text: str) -> list[str]:
    lower = text.lower()
    categories = []
    if text in ('AppCtrl', 'Monitor', 'Picture', 'Settings', 'Weather', 'Stock', 'app', 'page', 'enter', 'theme', 'autoSwitch', 'switchInterval') or lower.startswith('/.sys/app.'):
        categories.append('app_ui')
    if 'monitor' in lower or text in ('/sse', 'F_CPU:', 'UP_CPU:', 'UP_RAM:', 'T_CPU:', 'PW_CPU:', 'UP_DRIVE_C:', 'FR_DRIVE_C:', 'U_DRIVE_C:', 'TIME:'):
        categories.append('monitor_http')
    if '/.sys/' in lower or 'littlefs' in lower or text in ('/filelist', '/delete', '/set', '/doUpload', '/space.json', '/image', 'filesystem'):
        categories.append('filesystem_config')
    if 'esp_ota' in lower or text == '/update' or lower.startswith(('update error:', 'update success:', 'update was aborted', 'update:', 'unauthenticated update')) or text == '/IDF/components/app_update/esp_ota_ops.c':
        categories.append('ota')
    return categories


def select(rows: list[dict]) -> dict:
    buckets = {name: {'strings': [], 'functions': set()} for name in CATEGORIES}
    for row in rows:
        for category in classify_string(row['text']):
            bucket = buckets[category]
            bucket['strings'].append(row)
            for ref in row.get('code_references', []):
                function = ref.get('function')
                if function:
                    bucket['functions'].add(function)
    for bucket in buckets.values():
        bucket['functions'] = sorted(bucket['functions'])
    return buckets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exports', type=Path)
    args = parser.parse_args()
    export = args.exports
    strings = [json.loads(line) for line in (export / 'string_xrefs.jsonl').read_text().splitlines()]
    inventory = {row['entry']: row for row in (json.loads(line) for line in (export / 'functions.jsonl').read_text().splitlines())}
    buckets = select(strings)
    (export / 'focus.json').write_text(json.dumps(buckets, indent=2) + '\n')
    lines = ['# Address-linked focused function index', '', 'Function labels and category assignments are analysis aids, not recovered source names.', 'All discovered functions have their own original-address assembly/pseudocode exports.', '']
    counts = {}
    for name, bucket in buckets.items():
        counts[name] = dict(strings=len(bucket['strings']), xref_functions=len(bucket['functions']))
        lines.extend(['## ' + name, '', '| Function entry | Name | C export | Instructions |', '|---|---|---:|---:|'])
        for entry in bucket['functions']:
            row = inventory.get(entry)
            if row:
                lines.append(f"| `{entry}` | `{row['name']}` | {row['decompile_ok']} | {row['instruction_count']} |")
            else:
                lines.append(f'| `{entry}` | not in exported inventory | no | - |')
        lines.append('')
    (export / 'FOCUSED_INDEX.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
