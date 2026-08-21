"""从 SHIYIN-AI 画布 GROUP 构建回传 filmstoryboard 的桥接包数据。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from PIL import Image

from .bridge_manifest import frame_stable_id, shot_stable_id
from .bridge_package import BridgePackageError


OPERATION_VARIANTS = {
    "video-frame-extraction": "original",
    "expand-canvas": "expanded-16x9",
    "line-art": "line-art",
    "replicate": "replicated",
}


def _variant_for(node: Mapping[str, Any], group: Mapping[str, Any]) -> str:
    value = str(node.get("bridgeVariant") or "").strip()
    if value in {"original", "expanded-16x9", "line-art", "replicated"}:
        return value
    operation = str(node.get("derivedOperation") or group.get("derivedOperation") or "").strip()
    return OPERATION_VARIANTS.get(operation, str(group.get("bridgeSelectedVariant") or "original"))


def _dimensions(path: Path, node: Mapping[str, Any]) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            return int(image.width), int(image.height)
    except Exception:
        return max(1, int(node.get("natural_w") or node.get("width") or 1)), max(1, int(node.get("natural_h") or node.get("height") or 1))


def build_shiyin_bridge_payload(
    *,
    canvas: Mapping[str, Any],
    group: Mapping[str, Any],
    nodes: Iterable[Mapping[str, Any]],
    local_path_for_url,
    selected_variant: str = "",
    include_derived: bool = True,
) -> tuple[dict[str, Any], dict[str, Path]]:
    """返回 `(manifest, files)`，供 `write_bridge_package` 原子打包。"""
    group_id = str(group.get("id") or "").strip()
    canvas_id = str(canvas.get("id") or "").strip()
    if not group_id or not canvas_id:
        raise BridgePackageError("画布或 GROUP 缺少稳定 ID。")
    all_nodes = [dict(node) for node in nodes if isinstance(node, Mapping)]
    node_by_id = {str(node.get("id") or ""): node for node in all_nodes}
    groups = [dict(group)]
    if include_derived:
        groups.extend(node for node in all_nodes if node.get("type") == "group" and str(node.get("derivedFromGroupId") or "") == group_id)
    image_nodes: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen_nodes: set[str] = set()
    for source_group in groups:
        for item_id in source_group.get("items") or []:
            node = node_by_id.get(str(item_id))
            if not node or node.get("type") != "image" or not node.get("url"):
                continue
            node_id = str(node.get("id") or "")
            if not node_id or node_id in seen_nodes:
                continue
            seen_nodes.add(node_id)
            image_nodes.append((node, source_group))
    if not image_nodes:
        raise BridgePackageError("GROUP 中没有可回传的图片。")
    bridge_id = str(group.get("bridgeId") or f"shiyin:{canvas_id}:{group_id}").strip()
    frames: list[dict[str, Any]] = []
    files: dict[str, Path] = {}
    variants: list[str] = []
    for index, (node, source_group) in enumerate(image_nodes):
        variant = _variant_for(node, source_group)
        if variant not in variants:
            variants.append(variant)
        local_path = local_path_for_url(str(node.get("url") or ""))
        if not local_path:
            raise BridgePackageError(f"图片不是当前账户本地媒体：{node.get('name') or node.get('id')}")
        path = Path(local_path).resolve()
        if not path.is_file():
            raise BridgePackageError(f"图片文件不存在：{path}")
        width, height = _dimensions(path, node)
        suffix = path.suffix.lower() if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} else ".png"
        relative_path = f"images/{variant}/{index + 1:04d}{suffix}"
        frame_index = int(node.get("bridgeFrameIndex") if node.get("bridgeFrameIndex") is not None else node.get("frameIndex") or index)
        stable_id = frame_stable_id(bridge_id, max(0, frame_index), variant)
        frames.append({
            "stable_id": stable_id,
            "shot_stable_id": "",
            "slot_index": int(node.get("bridgeSlotIndex") if node.get("bridgeSlotIndex") is not None else index),
            "shot_number": int(node.get("bridgeShotNumber") or 0),
            "frame_index": frame_index,
            "timestamp_ms": int(node.get("timestampMs") or node.get("timestamp_ms") or 0),
            "source_name": str(node.get("name") or f"frame_{index + 1:04d}"),
            "relative_path": relative_path,
            "width": width,
            "height": height,
            "variant": variant,
            "source_frame_mode": str(node.get("bridgeSourceFrameMode") or node.get("sourceFrameMode") or ""),
            "derived_operation": str(node.get("derivedOperation") or ""),
            "caption": str(node.get("bridgeCaption") or ""),
            "metadata": {
                "source_node_id": str(node.get("id") or ""),
                "source_group_id": str(source_group.get("id") or ""),
                "source_frame_node_id": str(node.get("bridgeSourceFrameNodeId") or ""),
                "source_frame_stable_id": str(node.get("bridgeSourceFrameStableId") or ""),
                "source_frame_mode": str(node.get("bridgeSourceFrameMode") or node.get("sourceFrameMode") or ""),
                "derived_operation": str(node.get("derivedOperation") or ""),
            },
        })
        files[relative_path] = path
    frame_by_source = {str(node.get("id") or ""): frame for (node, _), frame in zip(image_nodes, frames)}
    prompt_nodes = []
    for prompt_id in group.get("bridgePromptNodeIds") or []:
        prompt = node_by_id.get(str(prompt_id))
        if prompt and prompt.get("type") == "prompt" and str(prompt.get("text") or "").strip():
            prompt_nodes.append(prompt)
    shots: list[dict[str, Any]] = []
    for index, prompt in enumerate(prompt_nodes):
        shot_number = int(prompt.get("bridgeShotNumber") or index + 1)
        source_frame = frame_by_source.get(str(prompt.get("bridgeSourceFrameNodeId") or ""))
        if source_frame is None:
            source_frame = next((frame for frame in frames if int(frame.get("shot_number") or 0) == shot_number), frames[min(index, len(frames) - 1)])
        shots.append({
            "stable_id": shot_stable_id(bridge_id, max(1, shot_number)),
            "shot_number": max(1, shot_number),
            "frame_stable_id": source_frame["stable_id"],
            "duration_seconds": 0,
            "prompt": str(prompt.get("text") or ""),
            "visual": str(prompt.get("text") or ""),
        })
    selected = str(selected_variant or group.get("bridgeSelectedVariant") or (variants[0] if variants else "original")).strip()
    if selected not in variants:
        selected = variants[0]
    manifest = {
        "schema": "shiyin-film-bridge",
        "schema_version": 2,
        "bridge_id": bridge_id,
        "direction": "shiyin-to-film",
        "exported_at": "",
        "source": {
            "app": "shiyin-ai",
            "canvas_id": canvas_id,
            "canvas_title": str(canvas.get("title") or ""),
            "group_id": group_id,
            "project_id": str(canvas.get("project") or ""),
            "board_id": str(group.get("bridgeBoardId") or ""),
        },
        "canvas": {"canvas_id": canvas_id, "canvas_title": str(canvas.get("title") or "")},
        "storyboard": {
            "board_name": str(group.get("bridgeBoardName") or canvas.get("title") or "SHIYIN 故事板"),
            "selected_variant": selected,
            "variants": variants,
            "frames": frames,
            "source_frame_mode": str(group.get("bridgeSourceFrameMode") or group.get("sourceFrameMode") or ""),
        },
        "shots": shots,
        "variants": [],
    }
    return manifest, files


__all__ = ["build_shiyin_bridge_payload"]
