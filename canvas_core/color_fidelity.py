"""商品局部色彩可信度检查，不修改输入图像。"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class ColorFidelityReport:
    delta_e00_mean: float
    delta_e00_p90: float
    lightness_offset: float
    a_offset: float
    b_offset: float
    palette_overlap: float
    normalized_delta_e00_mean: float
    normalized_palette_overlap: float
    confidence: str

    def as_dict(self):
        return asdict(self)


def crop_rgb(image: np.ndarray, box: Iterable[int]) -> np.ndarray:
    x, y, width, height = (int(value) for value in box)
    if width < 8 or height < 8 or x < 0 or y < 0 or x + width > image.shape[1] or y + height > image.shape[0]:
        raise ValueError("roi_out_of_bounds")
    return image[y:y + height, x:x + width].copy()


def rgb_to_lab(image: np.ndarray) -> np.ndarray:
    # OpenCV 的 Lab 为 0..255，转换到 CIE L*=0..100、a/b=-128..127。
    encoded = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float64)
    encoded[..., 0] *= 100.0 / 255.0
    encoded[..., 1:] -= 128.0
    return encoded


def delta_e_ciede2000(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """向量化 CIEDE2000；输入末维为 L*, a*, b*。"""
    l1, a1, b1 = (left[..., index] for index in range(3))
    l2, a2, b2 = (right[..., index] for index in range(3))
    c1, c2 = np.hypot(a1, b1), np.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = .5 * (1 - np.sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = (np.degrees(np.arctan2(b1, a1p)) + 360) % 360
    h2p = (np.degrees(np.arctan2(b2, a2p)) + 360) % 360
    dl, dc = l2 - l1, c2p - c1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    d_h = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh / 2))
    l_bar, c_bar_p = (l1 + l2) / 2, (c1p + c2p) / 2
    h_sum = h1p + h2p
    h_bar = np.where(np.abs(h1p - h2p) <= 180, h_sum / 2, np.where(h_sum < 360, (h_sum + 360) / 2, (h_sum - 360) / 2))
    t = (1 - .17 * np.cos(np.radians(h_bar - 30)) + .24 * np.cos(np.radians(2 * h_bar))
         + .32 * np.cos(np.radians(3 * h_bar + 6)) - .20 * np.cos(np.radians(4 * h_bar - 63)))
    sl = 1 + .015 * (l_bar - 50) ** 2 / np.sqrt(20 + (l_bar - 50) ** 2)
    sc, sh = 1 + .045 * c_bar_p, 1 + .015 * c_bar_p * t
    rt = -2 * np.sqrt(c_bar_p ** 7 / (c_bar_p ** 7 + 25 ** 7)) * np.sin(np.radians(60 * np.exp(-((h_bar - 275) / 25) ** 2)))
    return np.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (d_h / sh) ** 2 + rt * (dc / sc) * (d_h / sh))


def palette_overlap(left: np.ndarray, right: np.ndarray, bins: int = 12) -> float:
    ranges = [(0, 100), (-128, 128), (-128, 128)]
    h1, _ = np.histogramdd(left.reshape(-1, 3), bins=bins, range=ranges)
    h2, _ = np.histogramdd(right.reshape(-1, 3), bins=bins, range=ranges)
    h1, h2 = h1 / max(1, h1.sum()), h2 / max(1, h2.sum())
    return float(np.minimum(h1, h2).sum())


def _resized_lab(image: np.ndarray, size: int = 256) -> np.ndarray:
    return rgb_to_lab(cv2.resize(image, (size, size), interpolation=cv2.INTER_AREA))


def inspect_color_fidelity(reference: np.ndarray, generated: np.ndarray) -> ColorFidelityReport:
    reference_lab, generated_lab = _resized_lab(reference), _resized_lab(generated)
    raw_delta = delta_e_ciede2000(reference_lab, generated_lab)
    offsets = generated_lab.reshape(-1, 3).mean(axis=0) - reference_lab.reshape(-1, 3).mean(axis=0)
    # 环境造成的整体明暗和中性色偏移只用于第二组指标；原始指标始终保留。
    normalized = generated_lab.copy()
    normalized[..., 0] -= offsets[0]
    normalized[..., 1:] -= offsets[1:] * .35
    normalized_delta = delta_e_ciede2000(reference_lab, normalized)
    raw_overlap = palette_overlap(reference_lab, generated_lab)
    normalized_overlap = palette_overlap(reference_lab, normalized)
    mean = float(raw_delta.mean())
    normalized_mean = float(normalized_delta.mean())
    # 归一化结果只用于解释环境造成的偏移。商品色号验收仍必须通过原始亮度、
    # 原始色差和原始色板覆盖度，不能把明显曝光差异误判为同一色号。
    raw_lightness_ok = abs(float(offsets[0])) <= 3.5
    raw_color_ok = mean <= 6 and raw_overlap >= .62
    if raw_lightness_ok and raw_color_ok and normalized_mean <= 6 and normalized_overlap >= .62:
        confidence = "可信：原始亮度与色彩均接近，仍需人工检查材质与光线"
    elif normalized_mean <= 6 and normalized_overlap >= .62:
        confidence = "不通过：综合色相接近，但原始亮度或色板覆盖度不符"
    elif normalized_mean <= 12 and normalized_overlap >= .42:
        confidence = "待人工确认：存在可见色差或环境不确定性"
    else:
        confidence = "不可信：商品色彩偏差明显"
    return ColorFidelityReport(
        delta_e00_mean=round(mean, 2), delta_e00_p90=round(float(np.percentile(raw_delta, 90)), 2),
        lightness_offset=round(float(offsets[0]), 2), a_offset=round(float(offsets[1]), 2), b_offset=round(float(offsets[2]), 2),
        palette_overlap=round(raw_overlap, 3), normalized_delta_e00_mean=round(normalized_mean, 2),
        normalized_palette_overlap=round(normalized_overlap, 3), confidence=confidence,
    )
