"""从已发布后端生成仅替换深度视频模块的候选，保留其他冻结代码与依赖。"""
import argparse
import hashlib
import importlib.util
import io
import json
import marshal
from pathlib import Path
import shutil
import struct
import sys
import zlib

from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.archive.writers import CArchiveWriter

MODULES = ('canvas_core.video_depth', 'canvas_core.video_depth_overlay', 'canvas_core.video_depth_runtime',
           'canvas_core.component_profiles', 'canvas_core.person_depth_components', 'canvas_core.storage_bootstrap')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def patch_pyz(data, source):
    if data[:4] != b'PYZ\0' or data[4:8] != importlib.util.MAGIC_NUMBER:
        raise ValueError('构建 Python 与已发布后端字节码版本不一致')
    toc = dict(marshal.loads(data[struct.unpack('!i', data[8:12])[0]:]))
    output = io.BytesIO(data[:16])
    output.seek(16)
    updated = []
    for name in [*toc, *(name for name in MODULES if name not in toc)]:
        kind, position, size = toc.get(name, (0, 0, 0))
        chunk = data[position:position + size]
        if name in MODULES:
            filename = name.replace('.', '/') + '.py'
            code = compile((source / filename).read_text(encoding='utf-8'), filename, 'exec', optimize=1)
            chunk = zlib.compress(marshal.dumps(code), 6)
        updated.append((name, (kind, output.tell(), len(chunk))))
        output.write(chunk)
    offset = output.tell()
    output.write(marshal.dumps(updated))
    output.seek(8)
    output.write(struct.pack('!i', offset))
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-snapshot', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--overlays', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        raise ValueError('需要 Python 3.12')
    manifest = json.loads((args.base_snapshot / 'manifest.json').read_text(encoding='utf-8'))
    prefix = 'app/backend/canvas-backend/'
    files = [item for item in manifest['files'] if item['path'].startswith(prefix)]
    if not files:
        raise ValueError('底包不含后端')
    for item in files:
        path = args.base_snapshot / 'files' / item['path']
        if path.stat().st_size != item['size'] or digest(path) != item['sha256']:
            raise ValueError(f'底包校验失败：{item["path"]}')
    shutil.copytree(args.base_snapshot / 'files/app/backend/canvas-backend', args.output)
    target = args.output / 'canvas-backend.exe'
    archive = CArchiveReader(str(target))
    original = target.read_bytes()
    payload = io.BytesIO()
    toc = []
    for name, (_, _, _, compressed, kind) in archive.toc.items():
        data = archive.extract(name)
        if kind == 'z':
            data = patch_pyz(data, args.source)
        raw_size = len(data)
        if compressed:
            data = zlib.compress(data, 9)
        toc.append((payload.tell(), len(data), raw_size, compressed, kind, name))
        payload.write(data)
    for option in archive.options:
        toc.append((payload.tell(), 0, 0, 0, 'o', option))
    offset = payload.tell()
    serialized = CArchiveWriter._serialize_toc(toc)
    payload.write(serialized)
    magic, _, _, _, version, library = struct.unpack(CArchiveWriter._COOKIE_FORMAT, original[-CArchiveWriter._COOKIE_LENGTH:])
    if version != 312:
        raise ValueError('底包不是 Python 3.12')
    payload.write(struct.pack(CArchiveWriter._COOKIE_FORMAT, magic, payload.tell()+CArchiveWriter._COOKIE_LENGTH,
                              offset, len(serialized), version, library))
    target.write_bytes(original[:archive._start_offset] + payload.getvalue())
    before = CArchiveReader(str(args.base_snapshot / 'files/app/backend/canvas-backend/canvas-backend.exe')).open_embedded_archive('PYZ.pyz')
    after = CArchiveReader(str(target)).open_embedded_archive('PYZ.pyz')
    changed = {name for name in before.toc if before.extract(name, raw=True) != after.extract(name, raw=True)}
    added = set(after.toc) - set(before.toc)
    if changed | added != set(MODULES):
        raise ValueError(f'意外的后端模块差异：{changed | added}')
    overlays = json.loads((args.overlays / 'manifest.json').read_text(encoding='utf-8'))
    for item in overlays.values():
        if digest(args.overlays / item['file']) != item['sha256']:
            raise ValueError('worker 补丁摘要不符')
    shutil.copytree(args.overlays, args.output / '_internal/canvas_core/video_depth_workers')
    report = {'baseVersion': manifest['version'], 'changedModules': sorted(changed), 'addedModules': sorted(added),
              'sourceHashes': {name: digest(args.source / (name.replace('.', '/') + '.py')) for name in MODULES},
              'backendSha256': digest(target), 'otherModulesUnchanged': True}
    (args.output.parent / 'backend-provenance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
