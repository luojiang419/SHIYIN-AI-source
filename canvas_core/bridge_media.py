"""将已校验的桥接包图片安全落盘为当前账户可访问的媒体资源。"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any, Mapping

from .bridge_manifest import BridgeManifestError, safe_stable_id
from .bridge_package import BridgePackage, BridgePackageError


ALLOWED_VARIANTS = frozenset({"original", "expanded-16x9", "line-art", "replicated"})


def _slug(value: str, *, prefix: str) -> str:
    """生成适合 Windows/Unix 文件系统的稳定目录名，不暴露原始 ID。"""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _selected_frames(manifest: Mapping[str, Any], selected_variant: str) -> tuple[str, list[dict[str, Any]]]:
    storyboard = manifest.get("storyboard") if isinstance(manifest.get("storyboard"), Mapping) else {}
    frames = storyboard.get("frames") if isinstance(storyboard.get("frames"), list) else []
    preferred = str(selected_variant or storyboard.get("selected_variant") or "original").strip()
    if preferred not in ALLOWED_VARIANTS:
        raise BridgePackageError(f"不支持的图片变体：{preferred}")
    chosen = [dict(frame) for frame in frames if str(frame.get("variant") or "original") == preferred]
    if not chosen and preferred != "original":
        preferred = "original"
        chosen = [dict(frame) for frame in frames if str(frame.get("variant") or "original") == preferred]
    if not chosen:
        raise BridgePackageError("桥接包中没有可导入的 storyboard 图片帧。")
    chosen.sort(key=lambda item: (int(item.get("slot_index") or 0), int(item.get("frame_index") or 0), str(item.get("stable_id") or "")))
    return preferred, chosen


def materialize_bridge_frames(
    package: BridgePackage,
    output_root: str | Path,
    canvas_id: str,
    *,
    selected_variant: str = "",
) -> list[dict[str, Any]]:
    """把包内帧复制到账户媒体目录，返回可直接创建画布节点的元数据。"""
    try:
        canvas = safe_stable_id(canvas_id, "canvas_id")
    except BridgeManifestError as exc:
        raise BridgePackageError(str(exc)) from exc
    bridge_id = str(package.manifest.get("bridge_id") or "").strip()
    if not bridge_id:
        raise BridgePackageError("桥接包缺少 bridge_id。")
    variant, frames = _selected_frames(package.manifest, selected_variant)
    root = Path(output_root).resolve()
    target = (root / "canvas-bridges" / canvas / _slug(bridge_id, prefix="bridge") / variant).resolve()
    try:
        if os.path.commonpath([str(root), str(target)]) != str(root):
            raise BridgePackageError("桥接媒体目录越界。")
    except ValueError as exc:
        raise BridgePackageError("桥接媒体目录跨越了不兼容的盘符。") from exc
    target.mkdir(parents=True, exist_ok=True)
    result: list[dict[str, Any]] = []
    for ordinal, frame in enumerate(frames):
        relative = str(frame.get("relative_path") or "").replace("\\", "/")
        source = package.files.get(relative)
        if source is None or not source.is_file():
            raise BridgePackageError(f"桥接图片缺失：{relative}")
        suffix = Path(relative).suffix.lower() or ".png"
        destination = target / f"frame_{ordinal + 1:04d}{suffix}"
        partial = destination.with_suffix(destination.suffix + ".partial")
        shutil.copyfile(source, partial)
        os.replace(partial, destination)
        result.append({
            **frame,
            "variant": variant,
            "local_path": str(destination),
            "ordinal": ordinal,
        })
    return result


__all__ = ["materialize_bridge_frames"]
