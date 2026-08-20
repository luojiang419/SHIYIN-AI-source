"""filmstoryboard → SHIYIN-AI 画布的幂等帧级增量同步。"""
from __future__ import annotations

import math
import uuid
from typing import Any, Callable, Iterable, Mapping


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def find_bridge_target(
    canvases: Iterable[Mapping[str, Any]],
    bridge_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """按传入顺序返回同一 film bridge 的未删除画布与源 GROUP。"""
    wanted = _text(bridge_id)
    if not wanted:
        return None, None
    for raw_canvas in canvases:
        if not isinstance(raw_canvas, Mapping) or raw_canvas.get("deleted_at"):
            continue
        canvas = raw_canvas if isinstance(raw_canvas, dict) else dict(raw_canvas)
        for node in canvas.get("nodes") or []:
            if (
                isinstance(node, dict)
                and node.get("type") == "group"
                and _text(node.get("bridgeId")) == wanted
                and _text(node.get("bridgeDirection")) == "film-to-shiyin"
            ):
                return canvas, node
    return None, None


def _frame_checksum(frame: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    relative_path = _text(frame.get("relative_path"))
    checksums = manifest.get("checksums") if isinstance(manifest.get("checksums"), Mapping) else {}
    # checksums.json 已由 bridge_package 做过真实文件校验，应作为内容指纹权威来源。
    return _text(checksums.get(relative_path) or frame.get("sha256")).lower()


def _frame_metadata(frame: Mapping[str, Any], bridge_id: str, checksum: str, index: int) -> dict[str, Any]:
    return {
        "name": frame.get("source_name") or f"film_frame_{index + 1:04d}",
        "mediaKind": "image",
        "natural_w": _integer(frame.get("width")),
        "natural_h": _integer(frame.get("height")),
        "bridgeSource": "filmstoryboard",
        "bridgeId": bridge_id,
        "bridgeFrameStableId": _text(frame.get("stable_id")),
        "bridgeVariant": _text(frame.get("variant")) or "original",
        "bridgeFrameIndex": _integer(frame.get("frame_index"), index),
        "bridgeSlotIndex": _integer(frame.get("slot_index"), index),
        "bridgeShotNumber": _integer(frame.get("shot_number")),
        "bridgeCaption": _text(frame.get("caption")),
        "bridgeSha256": checksum,
    }


def _metadata_changed(node: Mapping[str, Any], values: Mapping[str, Any]) -> bool:
    return any(node.get(key) != value for key, value in values.items())


def _prompt_key(shot: Mapping[str, Any]) -> str:
    stable_id = _text(shot.get("stable_id"))
    if stable_id:
        return f"stable:{stable_id}"
    shot_number = _integer(shot.get("shot_number"))
    return f"number:{shot_number}" if shot_number else ""


def _existing_prompt_key(node: Mapping[str, Any]) -> str:
    stable_id = _text(node.get("bridgeShotStableId"))
    if stable_id:
        return f"stable:{stable_id}"
    shot_number = _integer(node.get("bridgeShotNumber"))
    return f"number:{shot_number}" if shot_number else ""


def _prompt_text(shot: Mapping[str, Any]) -> str:
    return _text(shot.get("prompt") or shot.get("visual") or shot.get("content"))


def _invalidate_derived_nodes(
    nodes: list[dict[str, Any]],
    connections: list[dict[str, Any]],
    group_id: str,
    affected_frame_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    if not affected_frame_ids:
        return nodes, connections, 0
    remove_ids = {
        _text(node.get("id"))
        for node in nodes
        if _text(node.get("derivedFromGroupId")) == group_id
        and _text(node.get("bridgeSourceFrameStableId")) in affected_frame_ids
        and node.get("type") != "group"
    }
    remove_ids.discard("")
    invalidated_count = len(remove_ids)
    if not remove_ids:
        return nodes, connections, 0

    surviving_ids = {_text(node.get("id")) for node in nodes if _text(node.get("id")) not in remove_ids}
    for node in nodes:
        if node.get("type") != "group" or _text(node.get("derivedFromGroupId")) != group_id:
            continue
        items = [_text(item) for item in (node.get("items") or [])]
        kept = [item for item in items if item and item not in remove_ids and item in surviving_ids]
        node["items"] = kept
        node["frameCount"] = len(kept)
        if not kept:
            remove_ids.add(_text(node.get("id")))

    nodes = [node for node in nodes if _text(node.get("id")) not in remove_ids]
    connections = [
        connection
        for connection in connections
        if _text(connection.get("from")) not in remove_ids and _text(connection.get("to")) not in remove_ids
    ]
    return nodes, connections, invalidated_count


def sync_film_bridge_canvas(
    canvas: dict[str, Any],
    manifest: Mapping[str, Any],
    frames: list[Mapping[str, Any]],
    *,
    create_prompt_nodes: bool = True,
    id_factory: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """把已落盘且带 ``url`` 的帧增量合并到画布，并返回同步结果。"""
    bridge_id = _text(manifest.get("bridge_id"))
    if not bridge_id:
        raise ValueError("bridge_id 不能为空。")
    make_id = id_factory or (lambda prefix: f"{prefix}_{uuid.uuid4().hex[:16]}")
    storyboard = manifest.get("storyboard") if isinstance(manifest.get("storyboard"), Mapping) else {}
    source = manifest.get("source") if isinstance(manifest.get("source"), Mapping) else {}
    nodes = [dict(node) for node in (canvas.get("nodes") or []) if isinstance(node, Mapping)]
    connections = [dict(item) for item in (canvas.get("connections") or []) if isinstance(item, Mapping)]

    group = next((
        node for node in nodes
        if node.get("type") == "group"
        and _text(node.get("bridgeId")) == bridge_id
        and _text(node.get("bridgeDirection")) == "film-to-shiyin"
    ), None)
    is_new_group = group is None
    if group is None:
        right_edge = max((_number(node.get("x")) + _number(node.get("w"), 280) for node in nodes), default=0)
        base_x = right_edge + 120 if nodes else 120
        base_y = min((_number(node.get("y"), 120) for node in nodes), default=120)
        group = {"id": make_id("grp"), "type": "group", "x": base_x, "y": base_y, "items": []}
        nodes.append(group)
    base_x = _number(group.get("x"), 120)
    base_y = _number(group.get("y"), 120)
    group_id = _text(group.get("id"))

    old_item_ids = {_text(item) for item in (group.get("items") or [])}
    existing_frames: dict[str, dict[str, Any]] = {}
    duplicate_source_ids: set[str] = set()
    for node in nodes:
        stable_id = _text(node.get("bridgeFrameStableId"))
        if node.get("type") != "image" or _text(node.get("id")) not in old_item_ids or not stable_id:
            continue
        if stable_id in existing_frames:
            duplicate_source_ids.add(_text(node.get("id")))
        else:
            existing_frames[stable_id] = node

    cols = min(3, max(1, math.ceil(math.sqrt(len(frames)))))
    gap_x, gap_y = 290, 250
    image_nodes: list[dict[str, Any]] = []
    incoming_ids: set[str] = set()
    changed_frame_ids: set[str] = set()
    stats = {
        "created": 0,
        "updated": 0,
        "updated_metadata": 0,
        "unchanged": 0,
        "removed": 0,
        "prompt_created": 0,
        "prompt_updated": 0,
        "prompt_unchanged": 0,
        "prompt_removed": 0,
        "invalidated_derived": 0,
    }
    for index, raw_frame in enumerate(frames):
        frame = dict(raw_frame)
        stable_id = _text(frame.get("stable_id"))
        url = _text(frame.get("url"))
        if not stable_id or stable_id in incoming_ids:
            raise ValueError("桥接帧 stable_id 不能为空且不能重复。")
        if not url:
            raise ValueError(f"桥接帧缺少媒体 URL：{stable_id}")
        incoming_ids.add(stable_id)
        checksum = _frame_checksum(frame, manifest)
        metadata = _frame_metadata(frame, bridge_id, checksum, index)
        node = existing_frames.get(stable_id)
        if node is None:
            node = {
                "id": make_id("img"),
                "type": "image",
                "x": base_x + 28 + (index % cols) * gap_x,
                "y": base_y + 66 + (index // cols) * gap_y,
                "w": 260,
                "h": 220,
                "url": url,
                **metadata,
            }
            nodes.append(node)
            stats["created"] += 1
        else:
            old_checksum = _text(node.get("bridgeSha256")).lower()
            content_changed = not old_checksum or not checksum or old_checksum != checksum
            metadata_changed = _metadata_changed(node, metadata)
            if content_changed:
                node.update(metadata)
                node["url"] = url
                changed_frame_ids.add(stable_id)
                stats["updated"] += 1
            elif metadata_changed:
                node.update(metadata)
                stats["updated_metadata"] += 1
            else:
                stats["unchanged"] += 1
        image_nodes.append(node)

    removed_frame_ids = set(existing_frames) - incoming_ids
    remove_source_ids = {
        _text(existing_frames[stable_id].get("id")) for stable_id in removed_frame_ids
    } | duplicate_source_ids
    remove_source_ids.discard("")
    stats["removed"] = len(remove_source_ids)
    nodes = [node for node in nodes if _text(node.get("id")) not in remove_source_ids]
    connections = [
        item for item in connections
        if _text(item.get("from")) not in remove_source_ids and _text(item.get("to")) not in remove_source_ids
    ]

    affected_frame_ids = changed_frame_ids | removed_frame_ids
    nodes, connections, stats["invalidated_derived"] = _invalidate_derived_nodes(
        nodes, connections, group_id, affected_frame_ids
    )
    # 上一步可能重建了 list，但 group 字典对象仍为其中的同一对象；源 GROUP 不会被失效逻辑删除。

    prompt_nodes: list[dict[str, Any]] = []
    if create_prompt_nodes:
        old_prompt_ids = {_text(item) for item in (group.get("bridgePromptNodeIds") or [])}
        existing_prompts: dict[str, dict[str, Any]] = {}
        for node in nodes:
            if node.get("type") != "prompt" or _text(node.get("id")) not in old_prompt_ids:
                continue
            key = _existing_prompt_key(node)
            if key and key not in existing_prompts:
                existing_prompts[key] = node
        incoming_prompt_keys: set[str] = set()
        for index, raw_shot in enumerate(manifest.get("shots") or []):
            shot = dict(raw_shot)
            text = _prompt_text(shot)
            key = _prompt_key(shot)
            if not text or not key or key in incoming_prompt_keys:
                continue
            incoming_prompt_keys.add(key)
            frame_stable_id = _text(shot.get("frame_stable_id"))
            source_image = next((node for node in image_nodes if _text(node.get("bridgeFrameStableId")) == frame_stable_id), None)
            if source_image is None:
                source_image = next((node for node in image_nodes if _integer(node.get("bridgeShotNumber")) == _integer(shot.get("shot_number"))), None)
            values = {
                "text": text,
                "bridgeSource": "filmstoryboard",
                "bridgeId": bridge_id,
                "bridgeShotStableId": _text(shot.get("stable_id")),
                "bridgeFrameStableId": frame_stable_id,
                "bridgeShotNumber": _integer(shot.get("shot_number")),
                "bridgeSourceFrameNodeId": _text((source_image or {}).get("id")),
            }
            prompt = existing_prompts.get(key)
            if prompt is None:
                prompt = {
                    "id": make_id("prompt"),
                    "type": "prompt",
                    "x": base_x + 28 + cols * gap_x,
                    "y": base_y + 66 + index * 180,
                    **values,
                }
                nodes.append(prompt)
                stats["prompt_created"] += 1
            elif _metadata_changed(prompt, values):
                prompt.update(values)
                stats["prompt_updated"] += 1
            else:
                stats["prompt_unchanged"] += 1
            prompt_nodes.append(prompt)
        remove_prompt_ids = {
            _text(prompt.get("id"))
            for key, prompt in existing_prompts.items()
            if key not in incoming_prompt_keys
        }
        remove_prompt_ids.discard("")
        stats["prompt_removed"] = len(remove_prompt_ids)
        nodes = [node for node in nodes if _text(node.get("id")) not in remove_prompt_ids]
        connections = [
            item for item in connections
            if _text(item.get("from")) not in remove_prompt_ids and _text(item.get("to")) not in remove_prompt_ids
        ]
    else:
        prompt_by_id = {_text(node.get("id")): node for node in nodes if node.get("type") == "prompt"}
        prompt_nodes = [prompt_by_id[item] for item in (group.get("bridgePromptNodeIds") or []) if _text(item) in prompt_by_id]

    rows = max(1, math.ceil(len(image_nodes) / cols))
    computed_w = 28 + cols * gap_x + (340 if prompt_nodes else 0)
    computed_h = rows * gap_y + 100
    group.update({
        "items": [_text(node.get("id")) for node in image_nodes],
        "bridgeSource": "filmstoryboard",
        "bridgeId": bridge_id,
        "bridgeDirection": "film-to-shiyin",
        "bridgeBoardId": _text(source.get("board_id")),
        "bridgeBoardName": _text(storyboard.get("board_name")),
        "bridgeSelectedVariant": _text(storyboard.get("selected_variant")) or "original",
        "bridgeFrameCount": len(image_nodes),
        "bridgePromptNodeIds": [_text(node.get("id")) for node in prompt_nodes],
        "bridgeExportedAt": _text(manifest.get("exported_at")),
        "w": computed_w if is_new_group else max(_number(group.get("w")), computed_w),
        "h": computed_h if is_new_group else max(_number(group.get("h")), computed_h),
    })
    canvas["nodes"] = nodes
    canvas["connections"] = connections
    change_total = sum(value for key, value in stats.items() if key not in {"unchanged", "prompt_unchanged"})
    sync_mode = "created" if is_new_group else "updated" if change_total else "unchanged"
    return {
        "canvas": canvas,
        "group": group,
        "image_nodes": image_nodes,
        "prompt_nodes": prompt_nodes,
        "sync_mode": sync_mode,
        "stats": stats,
    }


__all__ = ["find_bridge_target", "sync_film_bridge_canvas"]
