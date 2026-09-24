"""应用携带自有 worker 更新，复用已校验的固定运行时依赖。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile


def worker_digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare_worker(worker: Path, overlays: Path) -> Path:
    manifest_path = overlays / 'manifest.json'
    if not manifest_path.is_file():
        raise RuntimeError('深度视频 worker 更新文件缺失，请重新应用包含后端的完整热更新')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    original_hash = worker_digest(worker)
    entry = next((item for item in manifest.values()
                  if item.get('source_sha256') == original_hash or item.get('sha256') == original_hash), None)
    if entry is None:
        raise RuntimeError('深度视频运行时版本无法识别，请重新安装受支持的深度视频运行时')
    expected = entry['sha256']
    if original_hash == expected:
        return worker
    source = (overlays / entry['file']).resolve()
    source.relative_to(overlays.resolve())
    if worker_digest(source) != expected:
        raise RuntimeError('深度视频 worker 更新文件校验失败，请重新应用热更新')
    target = worker.with_name(f'shiyin-video-depth-{expected[:16]}.exe')
    if target.is_file() and worker_digest(target) == expected:
        return target
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=worker.parent, suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(source.read_bytes())
        if worker_digest(temporary) != expected:
            raise RuntimeError('深度视频 worker 写入校验失败')
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target
