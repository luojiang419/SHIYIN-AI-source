"""为既有运行时更新自有 worker 模块，保留各 CUDA/CPU 包全部第三方字节码。"""
from pathlib import Path
import hashlib
import io
import json
import marshal
import struct
import tempfile
import zipfile
import zlib
import sys
import importlib.util

from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.archive.writers import CArchiveWriter

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def update_pyz(data: bytes) -> bytes:
    if data[:4] != b'PYZ\0':
        raise ValueError('未知 PYZ 格式')
    if data[4:8] != importlib.util.MAGIC_NUMBER:
        raise ValueError('构建 Python 与运行时字节码版本不一致')
    offset = struct.unpack('!i', data[8:12])[0]
    toc = dict(marshal.loads(data[offset:]))
    output = io.BytesIO()
    output.write(data[:16])
    updated = []
    for name, (kind, position, size) in toc.items():
        chunk = data[position:position + size]
        if name in {'worker.models', 'worker.depth_controls'}:
            path = ROOT / (name.replace('.', '/') + '.py')
            code = compile(path.read_text(encoding='utf-8'), name.replace('.', '/') + '.py', 'exec', optimize=1)
            chunk = zlib.compress(marshal.dumps(code), 6)
        updated.append((name, (kind, output.tell(), len(chunk))))
        output.write(chunk)
    toc_offset = output.tell()
    output.write(marshal.dumps(updated))
    output.seek(8)
    output.write(struct.pack('!i', toc_offset))
    return output.getvalue()


def build(source: Path, target: Path):
    archive = CArchiveReader(str(source))
    original = source.read_bytes()
    payload = io.BytesIO()
    toc = []
    for name, (_, _, _, compressed, kind) in archive.toc.items():
        data = archive.extract(name)
        if kind == 'z':
            data = update_pyz(data)
        elif name == 'main' and kind == 's':
            data = marshal.dumps(compile((ROOT / 'worker/main.py').read_text(encoding='utf-8'), 'worker/main.py', 'exec', optimize=1))
        raw_size = len(data)
        if compressed:
            data = zlib.compress(data, 9)
        toc.append((payload.tell(), len(data), raw_size, compressed, kind, name))
        payload.write(data)
    for option in archive.options:
        toc.append((payload.tell(), 0, 0, 0, 'o', option))
    toc_offset = payload.tell()
    toc_data = CArchiveWriter._serialize_toc(toc)
    payload.write(toc_data)
    old_cookie = original[-CArchiveWriter._COOKIE_LENGTH:]
    magic, _, _, _, version, pylib = struct.unpack(CArchiveWriter._COOKIE_FORMAT, old_cookie)
    if version != 312:
        raise ValueError('需要 Python 3.12 运行时')
    payload.write(struct.pack(CArchiveWriter._COOKIE_FORMAT, magic, payload.tell() + CArchiveWriter._COOKIE_LENGTH, toc_offset, len(toc_data), version, pylib))
    target.write_bytes(original[:archive._start_offset] + payload.getvalue())
    CArchiveReader(str(target))  # 验证目录结构可重新读取。


if __name__ == '__main__':
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('worker overlay 必须使用 Python 3.12 构建')
    output = ROOT / 'worker-overlays'
    output.mkdir(exist_ok=True)
    manifest = {}
    for variant in ['cpu', 'cuda126', 'cuda128']:
        archive = PROJECT / f'dist/video-depth-runtime/video-depth-runtime-1.0.0-windows-x86_64-{variant}.zip'
        with tempfile.TemporaryDirectory() as temp, zipfile.ZipFile(archive) as zip_file:
            exe = Path(temp) / 'video-depth-worker.exe'
            exe.write_bytes(zip_file.read('runtime/video-depth-worker/video-depth-worker.exe'))
            target = output / f'{variant}.exe'
            build(exe, target)
            manifest[variant] = {'file': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                                 'source_sha256': hashlib.sha256(exe.read_bytes()).hexdigest()}
            print(variant, target.stat().st_size)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
