from __future__ import annotations

import math
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from PIL import Image, ImageOps


POSE_CALIBRATION_VERSION = 1
POSE_CALIBRATION_MAX_REGIONS = 4
POSE_CALIBRATION_MIN_SIZE = 0.01
POSE_CALIBRATION_CONTEXT_RATIO = 0.15


def _number(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"标定区域的 {field} 必须是数字") from exc
    if not math.isfinite(result):
        raise ValueError(f"标定区域的 {field} 必须是有限数字")
    return result


def normalize_pose_calibration(value: Any, source_url: str) -> Dict[str, Any]:
    """校验并规范化动作迁移原图标定数据；空标定保持旧流程兼容。"""
    if not isinstance(value, dict):
        return {}
    raw_regions = value.get("regions")
    if raw_regions in (None, []):
        return {}
    if not isinstance(raw_regions, list):
        raise ValueError("动作迁移标定区域格式不正确")
    if len(raw_regions) > POSE_CALIBRATION_MAX_REGIONS:
        raise ValueError(f"动作迁移最多支持 {POSE_CALIBRATION_MAX_REGIONS} 个标定区域")
    bound_url = str(value.get("source_url") or "").strip()
    if not source_url or bound_url != source_url:
        raise ValueError("标定区域与当前保留款原图不匹配，请重新标定")

    regions: List[Dict[str, Any]] = []
    seen_ids = set()
    for index, raw in enumerate(raw_regions, 1):
        if not isinstance(raw, dict):
            raise ValueError("动作迁移标定区域格式不正确")
        region_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(raw.get("id") or index).strip())[:48] or str(index)
        if region_id in seen_ids:
            region_id = f"{region_id}-{index}"
        seen_ids.add(region_id)
        name = re.sub(r"[\r\n\t]+", " ", str(raw.get("name") or f"重点区域 {index}")).strip()[:32]
        name = name or f"重点区域 {index}"
        x = _number(raw.get("x"), "x")
        y = _number(raw.get("y"), "y")
        width = _number(raw.get("w"), "w")
        height = _number(raw.get("h"), "h")
        if x < 0 or y < 0 or width < POSE_CALIBRATION_MIN_SIZE or height < POSE_CALIBRATION_MIN_SIZE:
            raise ValueError("标定区域必须位于原图内，且宽高不能小于原图的 1%")
        if x + width > 1.000001 or y + height > 1.000001:
            raise ValueError("标定区域超出保留款原图范围")
        regions.append({
            "id": region_id,
            "name": name,
            "x": round(x, 6),
            "y": round(y, 6),
            "w": round(width, 6),
            "h": round(height, 6),
        })
    return {
        "version": POSE_CALIBRATION_VERSION,
        "source_url": source_url,
        "regions": regions,
    }


def _pixel_box(region: Dict[str, Any], width: int, height: int) -> Tuple[int, int, int, int]:
    left = max(0, min(width - 1, round(float(region["x"]) * width)))
    top = max(0, min(height - 1, round(float(region["y"]) * height)))
    right = max(left + 1, min(width, round((float(region["x"]) + float(region["w"])) * width)))
    bottom = max(top + 1, min(height, round((float(region["y"]) + float(region["h"])) * height)))
    return left, top, right, bottom


def create_pose_calibration_references(
    source_path: str | Path,
    calibration: Dict[str, Any],
    output_dir: str | Path,
    url_for_path: Callable[[str], str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """从保留款原图生成带上下文的无损选区证据，供真实生图请求使用。"""
    regions = list(calibration.get("regions") or [])
    if not regions:
        return [], {"status": "not_required", "regions": []}
    destination_root = Path(output_dir)
    destination_root.mkdir(parents=True, exist_ok=True)
    references: List[Dict[str, Any]] = []
    audit_regions: List[Dict[str, Any]] = []
    with Image.open(source_path) as opened:
        source = ImageOps.exif_transpose(opened).convert("RGB")
        source_width, source_height = source.size
        for index, region in enumerate(regions, 1):
            left, top, right, bottom = _pixel_box(region, source_width, source_height)
            selection_width = right - left
            selection_height = bottom - top
            margin_x = max(8, round(selection_width * POSE_CALIBRATION_CONTEXT_RATIO))
            margin_y = max(8, round(selection_height * POSE_CALIBRATION_CONTEXT_RATIO))
            crop_box = (
                max(0, left - margin_x),
                max(0, top - margin_y),
                min(source_width, right + margin_x),
                min(source_height, bottom + margin_y),
            )
            crop = source.crop(crop_box)
            destination = destination_root / f"pose_calibration_{uuid.uuid4().hex}.png"
            crop.save(destination, format="PNG", optimize=True)
            name = str(region.get("name") or f"重点区域 {index}")
            reference_id = f"pose_calibration_{region['id']}"
            pixel_selection = {
                "x": left,
                "y": top,
                "width": selection_width,
                "height": selection_height,
            }
            pixel_crop = {
                "x": crop_box[0],
                "y": crop_box[1],
                "width": crop_box[2] - crop_box[0],
                "height": crop_box[3] - crop_box[1],
            }
            references.append({
                "url": url_for_path(str(destination)),
                "role": "source_calibration",
                "reference_type": "source_calibration",
                "reference_id": reference_id,
                "label": f"原图标定：{name}",
                "instruction": (
                    f"这是保留款原图中“{name}”的带上下文无损裁片。"
                    "只加强该部位的版型轮廓、裁片关系、走线、纹理和颜色；"
                    "不得把局部结构复制到其他部位，也不得提供人物姿势、构图或背景。"
                ),
                "calibration_region": dict(region),
                "pixel_selection": pixel_selection,
                "pixel_crop": pixel_crop,
                "source_size": {"width": source_width, "height": source_height},
            })
            audit_regions.append({
                "id": region["id"],
                "name": name,
                "reference_id": reference_id,
                "url": references[-1]["url"],
                "selection": pixel_selection,
                "crop": pixel_crop,
            })
    return references, {
        "status": "succeeded",
        "version": POSE_CALIBRATION_VERSION,
        "source_url": calibration.get("source_url") or "",
        "source_size": {"width": source_width, "height": source_height},
        "regions": audit_regions,
    }


def pose_calibration_prompt(references: List[Dict[str, Any]], all_references: List[Dict[str, Any]]) -> str:
    if not references:
        return ""
    items = []
    for reference in references:
        try:
            image_index = all_references.index(reference) + 1
        except ValueError:
            continue
        region = reference.get("calibration_region") or {}
        items.append(f"Image {image_index} = {region.get('name') or reference.get('label') or '重点区域'}")
    if not items:
        return ""
    return (
        "CALIBRATED SOURCE EVIDENCE: " + "; ".join(items) + ". "
        "These images are lossless context crops from the primary source, not independent designs. "
        "At each named garment location, preserve the visible panel boundary, silhouette transition, seam path, "
        "stitch density, fabric grain, wash and color. Reproject the evidence through the new pose with physically "
        "correct deformation and occlusion; never paste source pixels at fixed canvas coordinates, duplicate a local "
        "detail elsewhere, crop away the rest of the outfit, or let a calibration crop change identity, pose or background."
    )
