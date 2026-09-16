"""重建软件基线前清理软件发布；默认仅预览，保留所有模型与共享 blob。"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.request

SOFTWARE_KINDS = ('hot', 'hot-bootstrap', 'hot-updater', 'full')


def hashes(value):
    result = set()
    if isinstance(value, dict):
        sha = value.get('sha256')
        if isinstance(sha, str) and len(sha) == 64 and all(c in '0123456789abcdef' for c in sha):
            result.add(sha)
        for child in value.values():
            result.update(hashes(child))
    elif isinstance(value, list):
        for child in value:
            result.update(hashes(child))
    return result


def reset(data, backup, apply=False):
    data = Path(data).resolve(strict=True)
    database = data / 'index.db'
    if not database.is_file():
        raise ValueError('未找到分发中心index.db')
    with sqlite3.connect(database) as db:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute('SELECT id,kind,manifest FROM releases').fetchall()
        removed, kept, ids = set(), set(), []
        for release_id, kind, raw in rows:
            refs = hashes(json.loads(json.loads(raw)['payload']))
            if kind in SOFTWARE_KINDS:
                removed.update(refs)
                ids.append(release_id)
            else:
                kept.update(refs)
        paths = []
        blob_root = (data / 'blobs').resolve(strict=True)
        if not blob_root.is_relative_to(data):
            raise ValueError('blobs目录超出分发数据目录')
        for sha in sorted(removed - kept):
            path = blob_root / sha
            if path.exists():
                if path.is_symlink() or path.resolve().parent != blob_root or not path.is_file():
                    raise ValueError('拒绝删除异常blob路径')
                paths.append(path)
        bootstrap = data / 'bootstrap/SHIYIN-Hot-Update.exe'
        if bootstrap.exists():
            if bootstrap.is_symlink() or not bootstrap.resolve().is_relative_to(data):
                raise ValueError('旧迁移工具路径超出数据目录')
            paths.append(bootstrap)
        report = {'release_ids': ids, 'delete_files': len(paths),
                  'delete_bytes': sum(p.stat().st_size for p in paths),
                  'preserved_releases': [r[0] for r in rows if r[1] not in SOFTWARE_KINDS],
                  'shared_blobs_preserved': len(removed & kept), 'applied': apply}
        fixed = data / 'fixed-models.json'
        before = hashlib.sha256(fixed.read_bytes()).hexdigest() if fixed.exists() else None
        if apply:
            backup = Path(backup).resolve()
            if backup.exists() or backup == database:
                raise ValueError('备份文件已存在或指向正式数据库')
            backup.parent.mkdir(parents=True, exist_ok=True)
            # 独立只读连接备份已提交的数据库；当前连接持写锁阻止并发发布。
            with sqlite3.connect(database.as_uri()+'?mode=ro', uri=True) as source, sqlite3.connect(backup) as target:
                source.backup(target)
            db.executemany('DELETE FROM releases WHERE id=?', [(release_id,) for release_id in ids])
            db.commit()
            for path in paths:
                path.unlink()
            if before is not None:
                assert hashlib.sha256(fixed.read_bytes()).hexdigest() == before
            report['database_backup'] = str(backup)
        return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default='D:/SHIYIN-Distribution')
    parser.add_argument('--backup', required=True)
    parser.add_argument('--admin-port', type=int, default=3013)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply:
        token = (Path(args.data) / 'admin-token').read_text('ascii')
        request = urllib.request.Request(f'http://127.0.0.1:{args.admin_port}/api/status', headers={'Authorization': 'Bearer '+token})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=10) as response:
            status = json.load(response)
        if status['running'] or status['job']['running'] or status.get('traffic', {}).get('active_count', 0):
            raise SystemExit('请先暂停公开分发，并等待导入和下载结束')
    print(json.dumps(reset(args.data, args.backup, args.apply), ensure_ascii=False, indent=2))
