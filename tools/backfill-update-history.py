"""从指定分发数据库和构建清单补齐历史；仅提取公开日志字段。"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.update_history import TZ, read_history, merge_history, write_history


def manifest_record(manifest, kind='hot', status='built', created=None):
    version = str(manifest.get('version') or '')
    if not version:
        raise ValueError('清单缺少版本')
    if kind == 'full':
        display_kind, identity = 'baseline', 'release:' + version
    elif kind.startswith('hot'):
        display_kind = 'web' if kind == 'hot' and manifest.get('prune_roots') == ['app/web'] else kind
        identity = 'hot:' + version
    else:
        display_kind, identity = 'component', kind + ':' + version
    when = datetime.fromtimestamp(created, TZ).isoformat() if created else (
        datetime.strptime(version, '%Y%m%d%H%M%S').replace(tzinfo=TZ).isoformat() if re.fullmatch(r'\d{14}', version) else '')
    notes = str(manifest.get('notes') or '').strip()
    return {'id': identity, 'version': version, 'kind': display_kind, 'component': kind if display_kind == 'component' else '',
            'record_status': status, 'updated_at': when, 'min_desktop_version': manifest.get('min_desktop_version', ''),
            'items': [{'type': 'update', 'text': notes}] if notes else []}


def database_records(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute('SELECT kind, version, state, created, manifest FROM releases'):
            if row['state'] not in ('published', 'archived'):
                continue
            envelope = json.loads(row['manifest'])
            manifest = json.loads(envelope['payload'])
            manifest['version'] = row['version']
            yield manifest_record(manifest, row['kind'], 'published', row['created'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, action='append', default=[])
    parser.add_argument('--snapshots', type=Path)
    parser.add_argument('--output', type=Path, default=ROOT / 'static/update-history.json')
    args = parser.parse_args()
    data = read_history(args.output)
    records = []
    if args.snapshots:
        for path in sorted(args.snapshots.glob('*/manifest.json')):
            record = manifest_record(json.loads(path.read_text('utf-8-sig')))
            record['source'] = '本地构建清单'
            records.append(record)
    for path in args.database:
        for record in database_records(path):
            record['source'] = '分发数据库发布记录'
            records.append(record)
    write_history(args.output, merge_history(data, records))
    print(json.dumps({'records_read': len(records), 'total': len(read_history(args.output)['history'])}))


if __name__ == '__main__':
    main()
