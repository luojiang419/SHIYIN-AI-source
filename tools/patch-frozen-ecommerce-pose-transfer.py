"""Repair missing pose-transfer role constants in a published frozen backend.

Only canvas_core.ecommerce changes; every other PYZ member is verified unchanged.
"""

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
import zlib

from PyInstaller.archive.readers import CArchiveReader
from PyInstaller.archive.writers import CArchiveWriter


MODULE = "canvas_core.ecommerce"
DETAIL_ROLE = "fabric_detail"
VIEW_ROLES = ("source_view_1", "source_view_2")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def patch_pyz(data: bytes) -> bytes:
    if data[:4] != b"PYZ\0" or data[4:8] != importlib.util.MAGIC_NUMBER:
        raise ValueError("发布后端与当前 Python 字节码版本不一致")
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
            if original.co_filename.replace("\\", "/") != "canvas_core/ecommerce.py":
                raise ValueError("目标模块来源与预期不符")
            source = (
                "import marshal as _m, zlib as _z\n"
                f"exec(_m.loads(_z.decompress({zlib.compress(marshal.dumps(original), 9)!r})))\n"
                f"POSE_TRANSFER_DETAIL_ROLE = {DETAIL_ROLE!r}\n"
                f"POSE_TRANSFER_VIEW_ROLES = {VIEW_ROLES!r}\n"
                "ALLOWED_INPUT_ROLES.update((*POSE_TRANSFER_VIEW_ROLES, POSE_TRANSFER_DETAIL_ROLE))\n"
                "_original_validate_input_roles = validate_input_roles\n"
                "def validate_input_roles(operation, inputs, options=None):\n"
                "    result = _original_validate_input_roles(operation, inputs, options)\n"
                "    if operation == 'pose_transfer':\n"
                "        order = {role: index for index, role in enumerate(('source', 'pose', *POSE_TRANSFER_VIEW_ROLES, POSE_TRANSFER_DETAIL_ROLE))}\n"
                "        result.sort(key=lambda item: order.get(item['role'], len(order)))\n"
                "    return result\n"
            )
            chunk = zlib.compress(marshal.dumps(compile(source, "canvas_core/ecommerce.py", "exec", optimize=1)), 6)
        updated.append((name, (kind, output.tell(), len(chunk))))
        output.write(chunk)
    offset = output.tell()
    output.write(marshal.dumps(updated))
    output.seek(8)
    output.write(struct.pack("!i", offset))
    return output.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_snapshot", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12):
        raise ValueError("此已发布后端需要 Python 3.12")
    base = args.base_snapshot.resolve(strict=True)
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    prefix = "app/backend/canvas-backend/"
    entries = [item for item in manifest["files"] if item["path"].startswith(prefix)]
    if not entries:
        raise ValueError("底包不含后端")
    for item in entries:
        path = base / "files" / item["path"]
        if path.stat().st_size != item["size"] or sha256(path) != item["sha256"]:
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
            data = patch_pyz(data)
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
    magic, _, _, _, version, library = struct.unpack(CArchiveWriter._COOKIE_FORMAT, original[-CArchiveWriter._COOKIE_LENGTH:])
    if version != 312:
        raise ValueError("底包不是 Python 3.12")
    payload.write(struct.pack(CArchiveWriter._COOKIE_FORMAT, magic, payload.tell() + CArchiveWriter._COOKIE_LENGTH,
                              offset, len(serialized), version, library))
    target.write_bytes(original[:archive._start_offset] + payload.getvalue())
    before = CArchiveReader(str(base / "files/app/backend/canvas-backend/canvas-backend.exe")).open_embedded_archive("PYZ.pyz")
    after = CArchiveReader(str(target)).open_embedded_archive("PYZ.pyz")
    changed = {name for name in before.toc if before.extract(name, raw=True) != after.extract(name, raw=True)}
    if changed != {MODULE} or set(after.toc) != set(before.toc):
        raise ValueError(f"意外的冻结模块差异：{changed}")
    report = {"base_version": manifest["version"], "changed_modules": sorted(changed),
              "backend_sha256": sha256(target), "other_files_unchanged": all(
                  sha256(target_dir / item["path"][len(prefix):]) == item["sha256"]
                  for item in entries if not item["path"].endswith("/canvas-backend.exe"))}
    if not report["other_files_unchanged"]:
        raise ValueError("后端附属文件发生意外变化")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
