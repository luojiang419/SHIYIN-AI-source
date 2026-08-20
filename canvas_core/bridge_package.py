"""桥接 zip 包的原子写入、受限解压和校验。"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .bridge_manifest import BridgeManifestError, safe_relative_path, validate_manifest


class BridgePackageError(ValueError):
    """桥接包不安全、损坏或无法读写。"""


DEFAULT_MAX_ENTRIES = 10_500
DEFAULT_MAX_FILE_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
ALLOWED_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_name(value: str) -> str:
    try:
        return safe_relative_path(value, "zip entry")
    except BridgeManifestError as exc:
        raise BridgePackageError(str(exc)) from exc


def _ensure_inside(root: Path, target: Path) -> None:
    try:
        if os.path.commonpath([str(root), str(target)]) != str(root):
            raise BridgePackageError("桥接包路径超出目标目录。")
    except ValueError as exc:
        raise BridgePackageError("桥接包路径跨越了不兼容的盘符。") from exc


@dataclass
class BridgePackage:
    manifest: dict[str, Any]
    root: Path
    files: dict[str, Path]

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def write_bridge_package(
    manifest: Mapping[str, Any],
    files: Mapping[str, str | Path],
    output_path: str | Path,
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> dict[str, Any]:
    """将 manifest 和文件原子写入 zip，返回包路径、大小和校验摘要。"""
    try:
        normalized = validate_manifest(manifest)
    except BridgeManifestError as exc:
        raise BridgePackageError(str(exc)) from exc
    normalized_files: dict[str, Path] = {}
    total = 0
    for raw_name, raw_path in files.items():
        name = _zip_name(str(raw_name))
        if name in {"manifest.json", "checksums.json"}:
            raise BridgePackageError(f"不能覆盖保留的桥接包文件：{name}")
        source = Path(raw_path).resolve()
        if not source.is_file():
            raise BridgePackageError(f"桥接资源不存在：{source}")
        if source.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES and not name.startswith("preview/"):
            raise BridgePackageError(f"不支持的桥接资源格式：{name}")
        size = source.stat().st_size
        if size > max_file_bytes:
            raise BridgePackageError(f"桥接资源超过单文件大小限制：{name}")
        total += size
        if total > max_total_bytes:
            raise BridgePackageError("桥接资源总大小超过限制。")
        if name in normalized_files:
            raise BridgePackageError(f"桥接包内路径重复：{name}")
        normalized_files[name] = source
    checksums = {name: _sha256(path) for name, path in normalized_files.items()}
    normalized["checksums"] = checksums
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(f".{output.name}.{uuid.uuid4().hex}.partial")
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("manifest.json", json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            archive.writestr("checksums.json", json.dumps(checksums, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            for name, source in normalized_files.items():
                archive.write(source, name)
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)
    return {
        "path": str(output),
        "size": output.stat().st_size,
        "file_count": len(normalized_files),
        "checksums": checksums,
    }


def read_bridge_package(
    package_path: str | Path,
    extraction_root: str | Path,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> BridgePackage:
    """安全解压并验证桥接包；调用方负责在成功使用后 cleanup。"""
    package = Path(package_path).resolve()
    if not package.is_file() or package.suffix.lower() not in {".zip", ".filmbridge", ".shiyinbridge"}:
        raise BridgePackageError("桥接包文件不存在或扩展名不受支持。")
    root_parent = Path(extraction_root).resolve()
    root_parent.mkdir(parents=True, exist_ok=True)
    target = (root_parent / f"bridge_{uuid.uuid4().hex}").resolve()
    _ensure_inside(root_parent, target)
    total = 0
    try:
        with zipfile.ZipFile(package, "r") as archive:
            entries = archive.infolist()
            if len(entries) > max_entries:
                raise BridgePackageError("桥接包文件数量超过限制。")
            names = set()
            for info in entries:
                name = _zip_name(info.filename)
                if name in names:
                    raise BridgePackageError(f"桥接包内路径重复：{name}")
                names.add(name)
                if info.is_dir():
                    continue
                if info.file_size > max_file_bytes:
                    raise BridgePackageError(f"桥接包单文件超过限制：{name}")
                total += info.file_size
                if total > max_total_bytes:
                    raise BridgePackageError("桥接包解压总大小超过限制。")
                # Unix symlink 的高位类型标记；Windows 创建的普通文件不会命中。
                if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                    raise BridgePackageError(f"桥接包不允许符号链接：{name}")
            if "manifest.json" not in names:
                raise BridgePackageError("桥接包缺少 manifest.json。")
            target.mkdir(parents=True, exist_ok=False)
            files: dict[str, Path] = {}
            for info in entries:
                name = _zip_name(info.filename)
                if info.is_dir():
                    continue
                destination = (target / name).resolve()
                _ensure_inside(target, destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                files[name] = destination
        try:
            manifest = json.loads(files["manifest.json"].read_text(encoding="utf-8"))
            normalized = validate_manifest(manifest)
        except (OSError, UnicodeError, json.JSONDecodeError, BridgeManifestError) as exc:
            raise BridgePackageError(f"manifest.json 无法解析：{exc}") from exc
        checksums = normalized.get("checksums") if isinstance(normalized.get("checksums"), Mapping) else {}
        checksum_file = files.get("checksums.json")
        if checksum_file:
            try:
                package_checksums = json.loads(checksum_file.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise BridgePackageError(f"checksums.json 无法解析：{exc}") from exc
            if package_checksums != checksums:
                raise BridgePackageError("manifest 与 checksums.json 不一致。")
        for name, expected in checksums.items():
            safe_name = _zip_name(name)
            path = files.get(safe_name)
            if path is None or _sha256(path).lower() != str(expected).lower():
                raise BridgePackageError(f"桥接资源校验失败：{safe_name}")
        return BridgePackage(manifest=normalized, root=target, files=files)
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


__all__ = [
    "BridgePackage",
    "BridgePackageError",
    "read_bridge_package",
    "write_bridge_package",
]
