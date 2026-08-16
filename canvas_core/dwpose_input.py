from __future__ import annotations

import math
from io import BytesIO

from PIL import Image, ImageOps


class DWPoseInputTooLarge(ValueError):
    pass


def fit_dwpose_size(
    width: int,
    height: int,
    *,
    max_pixels: int,
    max_edge: int,
) -> tuple[int, int]:
    width = int(width)
    height = int(height)
    if width < 1 or height < 1:
        raise ValueError("DWPose 输入图片尺寸无效")
    if max_pixels < 1 or max_edge < 1:
        raise ValueError("DWPose 推理尺寸限制无效")
    scale = min(
        1.0,
        max_edge / max(width, height),
        math.sqrt(max_pixels / (width * height)),
    )
    return max(1, int(width * scale)), max(1, int(height * scale))


def prepare_dwpose_input(
    content: bytes,
    *,
    decode_max_pixels: int,
    inference_max_pixels: int,
    inference_max_edge: int,
) -> Image.Image:
    with Image.open(BytesIO(content)) as source:
        width, height = source.size
        if width < 1 or height < 1:
            raise ValueError("DWPose 输入图片尺寸无效")
        if width * height > decode_max_pixels:
            raise DWPoseInputTooLarge(f"DWPose 输入图片像素不能超过 {decode_max_pixels // 10_000} 万")
        draft_size = fit_dwpose_size(
            width,
            height,
            max_pixels=inference_max_pixels,
            max_edge=inference_max_edge,
        )
        source.draft("RGB", draft_size)
        image = ImageOps.exif_transpose(source).convert("RGB")
        target_size = fit_dwpose_size(
            *image.size,
            max_pixels=inference_max_pixels,
            max_edge=inference_max_edge,
        )
        if image.size != target_size:
            image = image.resize(target_size, Image.Resampling.LANCZOS)
        image.load()
        return image
