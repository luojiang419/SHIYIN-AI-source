"""从已发布后端制作人物深度显存释放热更新候选。"""

from __future__ import annotations

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
import types
import zlib

from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.archive.writers import CArchiveWriter


MODULE = "canvas_core.person_depth_client"
WORKER_NAME = "person-depth-worker-512.exe"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_worker(path: Path) -> None:
    code = marshal.loads(CArchiveReader(str(path)).extract("worker"))
    engine = next(
        item for item in code.co_consts
        if isinstance(item, types.CodeType) and item.co_name == "PersonDepthEngine"
    )
    methods = {
        item.co_name: item for item in engine.co_consts if isinstance(item, types.CodeType)
    }
    if not {"_release_gpu_and_schedule_unload", "_unload_if_idle", "estimate"} <= methods.keys():
        raise ValueError("冻结 worker 缺少显存释放方法")
    if "_release_gpu_and_schedule_unload" not in methods["estimate"].co_names:
        raise ValueError("冻结 worker 推理结束未调用显存释放方法")
    if "empty_cache" not in methods["_release_gpu_and_schedule_unload"].co_names:
        raise ValueError("冻结 worker 未清理 CUDA 缓存")


def patch_pyz(data: bytes, source: Path) -> bytes:
    if data[:4] != b"PYZ\0" or data[4:8] != importlib.util.MAGIC_NUMBER:
        raise ValueError("构建 Python 与已发布后端字节码版本不一致")
    toc = dict(marshal.loads(data[struct.unpack("!i", data[8:12])[0]:]))
    if MODULE not in toc:
        raise ValueError(f"冻结后端缺少 {MODULE}")
    output = io.BytesIO(data[:16])
    output.seek(16)
    updated = []
    for name, (kind, position, size) in toc.items():
        chunk = data[position:position + size]
        if name == MODULE:
            original = marshal.loads(zlib.decompress(chunk))
            if original.co_filename.replace("\\", "/") != "canvas_core/person_depth_client.py":
                raise ValueError("目标模块来源与预期不符")
            compiled = compile(source.read_text(encoding="utf-8"),
                               "canvas_core/person_depth_client.py", "exec", optimize=1)
            chunk = zlib.compress(marshal.dumps(compiled), 6)
        updated.append((name, (kind, output.tell(), len(chunk))))
        output.write(chunk)
    offset = output.tell()
    output.write(marshal.dumps(updated))
    output.seek(8)
    output.write(struct.pack("!i", offset))
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-snapshot", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--worker", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        raise ValueError("此已发布后端需要 Python 3.12")
    base = args.base_snapshot.resolve(strict=True)
    source = args.source.resolve(strict=True)
    worker = args.worker.resolve(strict=True)
    worker_hash = digest(worker)
    if f'PERSON_DEPTH_WORKER_512_SHA256 = "{worker_hash}"' not in source.read_text(encoding="utf-8"):
        raise ValueError("后端源码与 worker 摘要不匹配")
    validate_worker(worker)
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    prefix = "app/backend/canvas-backend/"
    entries = [item for item in manifest["files"] if item["path"].startswith(prefix)]
    if not entries:
        raise ValueError("底包不含后端")
    for item in entries:
        path = base / "files" / item["path"]
        if path.stat().st_size != item["size"] or digest(path) != item["sha256"]:
            raise ValueError(f"底包校验失败：{item['path']}")
    target_dir = args.output.resolve()
    if target_dir.exists():
        raise FileExistsError(target_dir)
    shutil.copytree(base / "files/app/backend/canvas-backend", target_dir)
    target = target_dir / "canvas-backend.exe"
    archive = CArchiveReader(str(target))
    original = target.read_bytes()
    payload = io.BytesIO()
    toc = []
    for name, (_, _, _, compressed, kind) in archive.toc.items():
        data = archive.extract(name)
        if kind == "z":
            data = patch_pyz(data, source)
        raw_size = len(data)
        if compressed:
            data = zlib.compress(data, 9)
        toc.append((payload.tell(), len(data), raw_size, compressed, kind, name))
        payload.write(data)
    for option in archive.options:
        toc.append((payload.tell(), 0, 0, 0, "o", option))
    offset = payload.tell()
    serialized = CArchiveWriter._serialize_toc(toc)
    payload.write(serialized)
    magic, _, _, _, version, library = struct.unpack(
        CArchiveWriter._COOKIE_FORMAT, original[-CArchiveWriter._COOKIE_LENGTH:]
    )
    if version != 312:
        raise ValueError("底包不是 Python 3.12")
    payload.write(struct.pack(CArchiveWriter._COOKIE_FORMAT, magic,
                              payload.tell() + CArchiveWriter._COOKIE_LENGTH,
                              offset, len(serialized), version, library))
    target.write_bytes(original[:archive._start_offset] + payload.getvalue())
    before = CArchiveReader(str(base / "files/app/backend/canvas-backend/canvas-backend.exe")).open_embedded_archive("PYZ.pyz")
    after = CArchiveReader(str(target)).open_embedded_archive("PYZ.pyz")
    changed = {name for name in before.toc if before.extract(name, raw=True) != after.extract(name, raw=True)}
    if changed != {MODULE} or set(after.toc) != set(before.toc):
        raise ValueError(f"意外的冻结模块差异：{changed}")
    overlay = target_dir / "worker-overlays" / WORKER_NAME
    overlay.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(worker, overlay)
    if digest(overlay) != worker_hash:
        raise ValueError("复制后的 worker 摘要不匹配")
    unexpected = [item["path"] for item in entries if not item["path"].endswith(
        ("/canvas-backend.exe", "/worker-overlays/" + WORKER_NAME)
    ) and digest(target_dir / item["path"][len(prefix):]) != item["sha256"]]
    if unexpected:
        raise ValueError(f"后端附属文件发生意外变化：{unexpected[:3]}")
    print(json.dumps({"base_version": manifest["version"], "changed_modules": sorted(changed),
                      "worker_sha256": worker_hash, "backend_sha256": digest(target),
                      "other_files_unchanged": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
