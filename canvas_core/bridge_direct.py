"""filmstoryboard 直接 multipart 桥接帧的校验与落盘。"""
from __future__ import annotations

import hashlib
import os
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

from PIL import Image

from .bridge_manifest import BridgeManifestError, safe_stable_id, validate_manifest


class DirectBridgeError(ValueError):
    """直接桥接请求不符合协议或图片无法落盘。"""


def _slug(value: str, prefix: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]}"


def materialize_direct_bridge_frames(
    manifest: Mapping[str, Any],
    uploads: Mapping[str, bytes],
    output_root: str | Path,
    canvas_id: str,
    *,
    selected_variant: str = "",
) -> list[dict[str, Any]]:
    """校验 multipart 图片并以稳定路径落盘，返回可供 sync 使用的帧元数据。"""
    try:
        normalized = validate_manifest(manifest)
        canvas = safe_stable_id(canvas_id, "canvas_id")
    except BridgeManifestError as exc:
        raise DirectBridgeError(str(exc)) from exc
    bridge_id = str(normalized.get("bridge_id") or "").strip()
    if not bridge_id:
        raise DirectBridgeError("桥接 manifest 缺少 bridge_id。")
    storyboard = normalized.get("storyboard") or {}
    preferred = str(selected_variant or storyboard.get("selected_variant") or "original").strip()
    frames = [dict(frame) for frame in storyboard.get("frames") or [] if str(frame.get("variant") or "original") == preferred]
    if not frames and preferred != "original":
        preferred = "original"
        frames = [dict(frame) for frame in storyboard.get("frames") or [] if str(frame.get("variant") or "original") == preferred]
    if not frames:
        raise DirectBridgeError("直接桥接请求中没有可用的故事板图片。")
    frames.sort(key=lambda item: (int(item.get("slot_index") or 0), int(item.get("frame_index") or 0), str(item.get("stable_id") or "")))
    root = Path(output_root).resolve()
    target = (root / "canvas-bridges" / canvas / _slug(bridge_id, "bridge") / preferred).resolve()
    try:
        if os.path.commonpath([str(root), str(target)]) != str(root):
            raise DirectBridgeError("桥接媒体目录越界。")
    except ValueError as exc:
        raise DirectBridgeError("桥接媒体目录跨越了不兼容的盘符。") from exc
    target.mkdir(parents=True, exist_ok=True)
    checksums = normalized.get("checksums") if isinstance(normalized.get("checksums"), Mapping) else {}
    result: list[dict[str, Any]] = []
    desired_paths: set[str] = set()
    for ordinal, frame in enumerate(frames):
        upload_name = str(frame.get("upload_name") or "").replace("\\", "/")
        if not upload_name:
            raise DirectBridgeError(f"桥接帧缺少 upload_name：{frame.get('stable_id') or ordinal}")
        content = uploads.get(upload_name)
        if not content:
            raise DirectBridgeError(f"桥接图片缺失：{upload_name}")
        declared = str(checksums.get(frame.get("relative_path")) or frame.get("sha256") or "").strip().lower()
        checksum = hashlib.sha256(content).hexdigest()
        if declared and declared != checksum:
            raise DirectBridgeError(f"桥接图片摘要不匹配：{upload_name}")
        try:
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                image.verify()
        except Exception as exc:
            raise DirectBridgeError(f"桥接图片无法读取：{upload_name}") from exc
        if width <= 0 or height <= 0:
            raise DirectBridgeError(f"桥接图片尺寸无效：{upload_name}")
        suffix = Path(upload_name).suffix.lower() or ".png"
        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            suffix = ".png"
        destination = target / f"{_slug(str(frame.get('stable_id') or f'ordinal:{ordinal}'), 'frame')}_{checksum[:16]}{suffix}"
        partial = destination.with_suffix(destination.suffix + ".partial")
        partial.write_bytes(content)
        os.replace(partial, destination)
        desired_paths.add(str(destination.resolve()))
        result.append({
            **frame,
            "variant": preferred,
            "width": width,
            "height": height,
            "sha256": checksum,
            "local_path": str(destination),
            "ordinal": ordinal,
        })
    for stale in target.iterdir():
        if stale.is_file() and str(stale.resolve()) not in desired_paths and not stale.name.endswith(".partial"):
            try:
                stale.unlink()
            except OSError:
                pass
    return result


__all__ = ["DirectBridgeError", "materialize_direct_bridge_frames"]
