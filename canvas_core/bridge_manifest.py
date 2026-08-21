"""SHIYIN-AI ↔ filmstoryboard 桥接 manifest 契约与安全校验。"""
from __future__ import annotations

import copy
import json
import re
from typing import Any, Mapping


BRIDGE_SCHEMA = "shiyin-film-bridge"
BRIDGE_SCHEMA_VERSION = 2
SUPPORTED_BRIDGE_VERSIONS = frozenset({1, 2})
SUPPORTED_DIRECTIONS = frozenset({"film-to-shiyin", "shiyin-to-film"})
SUPPORTED_VARIANTS = frozenset({"original", "expanded-16x9", "line-art", "replicated"})
MAX_BRIDGE_ID_LENGTH = 512
MAX_FRAME_COUNT = 10000
MAX_SHOT_COUNT = 10000
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,511}$")


class BridgeManifestError(ValueError):
    """桥接 manifest 不符合协议或安全约束。"""


def _text(value: Any, field: str, *, required: bool = False, max_length: int = 4096) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise BridgeManifestError(f"{field}不能为空。")
    if len(result) > max_length:
        raise BridgeManifestError(f"{field}过长。")
    return result


def safe_stable_id(value: Any, field: str = "stable_id") -> str:
    result = _text(value, field, required=True, max_length=MAX_BRIDGE_ID_LENGTH)
    if not _SAFE_ID_RE.fullmatch(result):
        raise BridgeManifestError(f"{field}包含不支持的字符。")
    return result


def safe_relative_path(value: Any, field: str = "relative_path") -> str:
    """只允许 zip 内部 POSIX 相对路径，拒绝盘符、绝对路径和穿越。"""
    result = _text(value, field, required=True, max_length=1024).replace("\\", "/")
    if result.startswith("/") or re.match(r"^[A-Za-z]:/", result):
        raise BridgeManifestError(f"{field}不能是绝对路径。")
    parts = result.split("/")
    if not parts or any(not part or part in {".", ".."} for part in parts):
        raise BridgeManifestError(f"{field}包含非法路径片段。")
    return "/".join(parts)


def frame_stable_id(source_id: str, frame_index: int, variant: str = "original") -> str:
    source = safe_stable_id(source_id, "source_id")
    try:
        index = int(frame_index)
    except (TypeError, ValueError) as exc:
        raise BridgeManifestError("frame_index 无效。") from exc
    if index < 0 or index >= MAX_FRAME_COUNT:
        raise BridgeManifestError("frame_index 超出范围。")
    selected_variant = _variant(variant)
    return f"frame:{source}:{index:04d}:{selected_variant}"


def shot_stable_id(bridge_id: str, shot_number: int) -> str:
    bridge = safe_stable_id(bridge_id, "bridge_id")
    try:
        number = int(shot_number)
    except (TypeError, ValueError) as exc:
        raise BridgeManifestError("shot_number 无效。") from exc
    if number < 1 or number > MAX_SHOT_COUNT:
        raise BridgeManifestError("shot_number 超出范围。")
    return f"shot:{bridge}:{number}"


def _variant(value: Any) -> str:
    result = _text(value, "variant", required=True, max_length=32)
    if result not in SUPPORTED_VARIANTS:
        raise BridgeManifestError(f"不支持的图片变体：{result}")
    return result


def _positive_int(value: Any, field: str, *, default: int = 0, maximum: int = 2_000_000) -> int:
    if value is None or value == "":
        return default
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise BridgeManifestError(f"{field} 必须是整数。") from exc
    if result < 0 or result > maximum:
        raise BridgeManifestError(f"{field} 超出范围。")
    return result


def _float(value: Any, field: str, *, default: float = 0.0) -> float:
    try:
        result = float(value if value is not None else default)
    except (TypeError, ValueError) as exc:
        raise BridgeManifestError(f"{field} 必须是数字。") from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise BridgeManifestError(f"{field} 必须是有限数字。")
    return result


def _frame(frame: Mapping[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(frame, Mapping):
        raise BridgeManifestError(f"storyboard.frames[{index}] 必须是对象。")
    variant = _variant(frame.get("variant") or "original")
    stable_id = safe_stable_id(frame.get("stable_id"), f"frames[{index}].stable_id")
    relative_path = safe_relative_path(frame.get("relative_path"), f"frames[{index}].relative_path")
    width = _positive_int(frame.get("width"), f"frames[{index}].width")
    height = _positive_int(frame.get("height"), f"frames[{index}].height")
    if width <= 0 or height <= 0:
        raise BridgeManifestError(f"frames[{index}] 缺少有效图片尺寸。")
    return {
        "stable_id": stable_id,
        "shot_stable_id": _text(frame.get("shot_stable_id"), "shot_stable_id", max_length=MAX_BRIDGE_ID_LENGTH),
        "slot_index": _positive_int(frame.get("slot_index"), f"frames[{index}].slot_index"),
        "shot_number": _positive_int(frame.get("shot_number"), f"frames[{index}].shot_number"),
        "frame_index": _positive_int(frame.get("frame_index"), f"frames[{index}].frame_index"),
        "timestamp_ms": _positive_int(frame.get("timestamp_ms"), f"frames[{index}].timestamp_ms", maximum=86_400_000),
        "source_name": _text(frame.get("source_name"), "source_name", max_length=512),
        "relative_path": relative_path,
        "width": width,
        "height": height,
        "variant": variant,
        "caption": _text(frame.get("caption"), "caption", max_length=8000),
        "sha256": _text(frame.get("sha256"), "sha256", max_length=128),
        "metadata": copy.deepcopy(frame.get("metadata") if isinstance(frame.get("metadata"), Mapping) else {}),
        "upload_name": safe_relative_path(frame.get("upload_name"), f"frames[{index}].upload_name") if frame.get("upload_name") else "",
    }


def _shot(shot: Mapping[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(shot, Mapping):
        raise BridgeManifestError(f"shots[{index}] 必须是对象。")
    result = {
        "stable_id": safe_stable_id(shot.get("stable_id"), f"shots[{index}].stable_id"),
        "shot_number": _positive_int(shot.get("shot_number"), f"shots[{index}].shot_number"),
        "frame_stable_id": _text(shot.get("frame_stable_id"), "frame_stable_id", max_length=MAX_BRIDGE_ID_LENGTH),
        "duration_seconds": _float(shot.get("duration_seconds"), "duration_seconds"),
    }
    for field in (
        "visual", "content", "free_creation_description", "shot_size", "camera_movement", "camera_notes",
        "composition", "camera_angle", "lighting_mood", "color_palette", "visual_focus", "transition_hint",
        "movement_trend", "action_stage", "dialogue", "sound", "prompt", "replication_instructions",
    ):
        result[field] = _text(shot.get(field), field, max_length=16000)
    result["continues_from_previous"] = bool(shot.get("continues_from_previous", False))
    result["continues_to_next"] = bool(shot.get("continues_to_next", False))
    return result


def validate_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    """校验并返回可安全序列化的规范化 manifest 副本。"""
    if not isinstance(value, Mapping):
        raise BridgeManifestError("manifest 必须是 JSON 对象。")
    schema = _text(value.get("schema"), "schema", required=True, max_length=80)
    if schema != BRIDGE_SCHEMA:
        raise BridgeManifestError(f"不支持的 bridge schema：{schema}")
    version = _positive_int(value.get("schema_version"), "schema_version")
    if version not in SUPPORTED_BRIDGE_VERSIONS:
        raise BridgeManifestError(f"不支持的 bridge schema_version：{version}")
    bridge_id = safe_stable_id(value.get("bridge_id"), "bridge_id")
    direction = _text(value.get("direction") or "film-to-shiyin", "direction", required=True, max_length=40)
    if direction not in SUPPORTED_DIRECTIONS:
        raise BridgeManifestError(f"不支持的桥接方向：{direction}")
    source = value.get("source") if isinstance(value.get("source"), Mapping) else {}
    storyboard = value.get("storyboard") if isinstance(value.get("storyboard"), Mapping) else {}
    frames_value = storyboard.get("frames") or []
    if not isinstance(frames_value, list) or len(frames_value) > MAX_FRAME_COUNT:
        raise BridgeManifestError("storyboard.frames 数量无效。")
    shots_value = value.get("shots") or value.get("script_seed", {}).get("shots", []) if isinstance(value.get("script_seed"), Mapping) else value.get("shots") or []
    if not isinstance(shots_value, list) or len(shots_value) > MAX_SHOT_COUNT:
        raise BridgeManifestError("shots 数量无效。")
    frames = [_frame(frame, index) for index, frame in enumerate(frames_value)]
    shots = [_shot(shot, index) for index, shot in enumerate(shots_value)]
    stable_ids = [item["stable_id"] for item in frames]
    if len(set(stable_ids)) != len(stable_ids):
        raise BridgeManifestError("frame stable_id 不能重复。")
    paths = [item["relative_path"] for item in frames]
    if len(set(paths)) != len(paths):
        raise BridgeManifestError("frame relative_path 不能重复。")
    selected_variant = _variant(storyboard.get("selected_variant") or "original")
    variants = storyboard.get("variants") or [selected_variant]
    if not isinstance(variants, list):
        raise BridgeManifestError("storyboard.variants 必须是数组。")
    normalized_variants = []
    for item in variants:
        variant = _variant(item)
        if variant not in normalized_variants:
            normalized_variants.append(variant)
    return {
        "schema": schema,
        "schema_version": version,
        "bridge_id": bridge_id,
        "direction": direction,
        "exported_at": _text(value.get("exported_at"), "exported_at", max_length=80),
        "source": copy.deepcopy(dict(source)),
        "canvas": copy.deepcopy(dict(value.get("canvas") if isinstance(value.get("canvas"), Mapping) else {})),
        "storyboard": {
            "board_name": _text(storyboard.get("board_name"), "storyboard.board_name", max_length=512),
            "selected_variant": selected_variant,
            "variants": normalized_variants,
            "frames": frames,
        },
        "shots": shots,
        "variants": copy.deepcopy(value.get("variants") if isinstance(value.get("variants"), list) else []),
        "checksums": copy.deepcopy(value.get("checksums") if isinstance(value.get("checksums"), Mapping) else {}),
    }


def manifest_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(validate_manifest(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


__all__ = [
    "BRIDGE_SCHEMA",
    "BRIDGE_SCHEMA_VERSION",
    "BridgeManifestError",
    "SUPPORTED_VARIANTS",
    "frame_stable_id",
    "manifest_json",
    "safe_relative_path",
    "safe_stable_id",
    "shot_stable_id",
    "validate_manifest",
]
