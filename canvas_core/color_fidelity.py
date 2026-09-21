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


def calibrate_lightness_preview(reference: np.ndarray, generated: np.ndarray, max_shift: float = 12.0) -> np.ndarray:
    """仅校正预览 ROI 的 CIE L* 中位数，禁止改动 a/b 色相和织物细节。"""
    ref_lab, generated_lab = rgb_to_lab(reference), rgb_to_lab(generated)
    shift = float(np.clip(np.median(ref_lab[..., 0]) - np.median(generated_lab[..., 0]), -max_shift, max_shift))
    adjusted = generated_lab.copy()
    adjusted[..., 0] = np.clip(adjusted[..., 0] + shift, 0, 100)
    encoded = adjusted.copy()
    encoded[..., 0] *= 255.0 / 100.0
    encoded[..., 1:] += 128.0
    return cv2.cvtColor(np.clip(encoded, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


def _lab_to_rgb(lab: np.ndarray) -> np.ndarray:
    encoded = lab.copy()
    encoded[..., 0] *= 255.0 / 100.0
    encoded[..., 1:] += 128.0
    return cv2.cvtColor(np.clip(encoded, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


def _affine_lab_match(reference: np.ndarray, generated: np.ndarray, target: np.ndarray, strength: float) -> np.ndarray:
    ref_lab, source_lab, target_lab = rgb_to_lab(reference), rgb_to_lab(generated), rgb_to_lab(target)
    ref_mean, source_mean = ref_lab.reshape(-1, 3).mean(0), source_lab.reshape(-1, 3).mean(0)
    ref_std = ref_lab.reshape(-1, 3).std(0).clip(min=3)
    source_std = source_lab.reshape(-1, 3).std(0).clip(min=3)
    fitted = (target_lab - source_mean) * (ref_std / source_std) + ref_mean
    return _lab_to_rgb(target_lab * (1 - strength) + fitted * strength)


def _quantile_lab_match(reference: np.ndarray, generated: np.ndarray, target: np.ndarray, strength: float) -> np.ndarray:
    """按 L/a/b 的分位点做单调映射，保留每个像素的织纹相对层次。"""
    ref_lab, source_lab, target_lab = rgb_to_lab(reference), rgb_to_lab(generated), rgb_to_lab(target)
    quantiles = np.linspace(.005, .995, 199)
    fitted = target_lab.copy()
    for channel in range(3):
        source_values = source_lab[..., channel].reshape(-1)
        source_points = np.quantile(source_values, quantiles)
        reference_points = np.quantile(ref_lab[..., channel].reshape(-1), quantiles)
        # 平坦面料会出现相同分位点；先合并节点，保证插值单调有效。
        source_points, indices = np.unique(source_points, return_index=True)
        reference_points = reference_points[indices]
        if source_points.size > 1:
            fitted[..., channel] = np.interp(target_lab[..., channel], source_points, reference_points)
        else:
            fitted[..., channel] = reference_points[0]
    return _lab_to_rgb(target_lab * (1 - strength) + fitted * strength)


def smart_color_match_preview(reference: np.ndarray, generated: np.ndarray, strength: float = .82,
                              strategy: str = "quantile", target: np.ndarray | None = None) -> np.ndarray:
    """在商品 ROI 内拟合完整 Lab 色彩分布；默认分位数映射覆盖阴影、中间调和高光。"""
    target = generated if target is None else target
    if strategy == "affine":
        return _affine_lab_match(reference, generated, target, strength)
    if strategy == "quantile":
        return _quantile_lab_match(reference, generated, target, strength)
    raise ValueError("unsupported_color_match_strategy")


def smart_color_match_auto(reference: np.ndarray, generated: np.ndarray,
                           strengths: Iterable[float] = (.58, .72, .82, .92, 1.0),
                           strategies: Iterable[str] = ("quantile", "affine")) -> tuple[np.ndarray, dict]:
    """在有限候选中选取综合色差、尾部误差和色板覆盖度最优的实际拟合。"""
    candidates = []
    for strategy in strategies:
        for strength in strengths:
            image = smart_color_match_preview(reference, generated, float(strength), strategy)
            report = inspect_color_fidelity(reference, image)
            # DeltaE、P90 和综合色板分布共同决定，避免只把平均值压低。
            score = report.delta_e00_mean + report.delta_e00_p90 * .08 + (1 - report.palette_overlap) * 5
            candidates.append((score, image, {"strategy": strategy, "strength": float(strength), "score": round(score, 3),
                                              "report": report.as_dict()}))
    _, image, selected = min(candidates, key=lambda item: item[0])
    return image, selected


def feathered_roi_blend(source: np.ndarray, fitted_crop: np.ndarray, box: Iterable[int],
                         feather: int = 16) -> np.ndarray:
    """把 ROI 以渐变 alpha 融入原图，避免矩形色块边界。"""
    x, y, width, height = (int(value) for value in box)
    if fitted_crop.shape[:2] != (height, width):
        raise ValueError("fitted_crop_shape_mismatch")
    result = source.copy()
    feather = max(0, min(int(feather), width // 3, height // 3))
    if feather == 0:
        result[y:y + height, x:x + width] = fitted_crop
        return result
    alpha = np.ones((height, width), dtype=np.float32)
    ramp = np.linspace(0, 1, feather + 2, dtype=np.float32)[1:-1]
    alpha[:feather, :] *= ramp[:, None]
    alpha[-feather:, :] *= ramp[::-1, None]
    alpha[:, :feather] *= ramp[None, :]
    alpha[:, -feather:] *= ramp[None, ::-1]
    original = result[y:y + height, x:x + width].astype(np.float32)
    result[y:y + height, x:x + width] = np.clip(
        original * (1 - alpha[..., None]) + fitted_crop.astype(np.float32) * alpha[..., None], 0, 255
    ).astype(np.uint8)
    return result


def seeded_fabric_mask(image: np.ndarray, sample_box: Iterable[int], apply_box: Iterable[int]) -> np.ndarray:
    """用纯布面样本和粗略服装范围生成连通面料掩码。"""
    x, y, width, height = (int(value) for value in apply_box)
    sample = crop_rgb(image, sample_box)
    lab, sample_lab = rgb_to_lab(image), rgb_to_lab(sample)
    mean = sample_lab.reshape(-1, 3).mean(0)
    std = sample_lab.reshape(-1, 3).std(0).clip(min=np.array([7., 4., 4.]))
    distance = np.sqrt(np.mean(((lab - mean) / std) ** 2, axis=2))
    mask = np.full(image.shape[:2], cv2.GC_BGD, dtype=np.uint8)
    mask[y:y + height, x:x + width] = cv2.GC_PR_BGD
    likely_fabric = distance[y:y + height, x:x + width] <= 2.8
    mask[y:y + height, x:x + width][likely_fabric] = cv2.GC_PR_FGD
    sx, sy, sw, sh = (int(value) for value in sample_box)
    mask[sy:sy + sh, sx:sx + sw] = cv2.GC_FGD
    for edge in (mask[:4], mask[-4:], mask[:, :4], mask[:, -4:]):
        edge[...] = cv2.GC_BGD
    background = np.zeros((1, 65), np.float64)
    foreground = np.zeros((1, 65), np.float64)
    cv2.grabCut(image, mask, None, background, foreground, 3, cv2.GC_INIT_WITH_MASK)
    binary = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    binary[:y, :] = 0
    binary[y + height:, :] = 0
    binary[:, :x] = 0
    binary[:, x + width:] = 0
    # 仅保留与样本相连的区域，避免同色背景或另一件服装被一起校正。
    count, labels, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    sample_labels = labels[sy:sy + sh, sx:sx + sw].reshape(-1)
    valid = sample_labels[sample_labels > 0]
    if valid.size:
        chosen = int(np.bincount(valid).argmax())
        binary = (labels == chosen).astype(np.uint8)
    elif count > 1:
        binary = np.zeros_like(binary)
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))


def feathered_mask_blend(source: np.ndarray, fitted: np.ndarray, mask: np.ndarray, feather: int = 16) -> np.ndarray:
    """以服装掩码羽化融合完整拟合图，保留掩码外的原始像素。"""
    if source.shape != fitted.shape or mask.shape != source.shape[:2]:
        raise ValueError("mask_blend_shape_mismatch")
    feather = max(0, int(feather))
    alpha = mask.astype(np.float32)
    if feather:
        radius = max(1, feather * 2 + 1)
        alpha = cv2.GaussianBlur(alpha, (radius | 1, radius | 1), feather / 2)
    alpha = np.clip(alpha, 0, 1)[..., None]
    return np.clip(source.astype(np.float32) * (1 - alpha) + fitted.astype(np.float32) * alpha, 0, 255).astype(np.uint8)


def masked_fit_samples(image: np.ndarray, mask: np.ndarray, limit: int = 180_000) -> np.ndarray:
    """从服装掩码均匀抽样，避免高分辨率整件图的拟合耗时随像素数失控。"""
    pixels = image[mask > 0]
    if pixels.shape[0] < 4096:
        raise ValueError("fabric_mask_too_small")
    if pixels.shape[0] > limit:
        pixels = pixels[np.linspace(0, pixels.shape[0] - 1, limit, dtype=np.intp)]
    return pixels.reshape(1, -1, 3)


def apply_lab_controls(image: np.ndarray, lightness: float = 0, contrast: float = 1,
                       chroma: float = 1, a_shift: float = 0, b_shift: float = 0) -> np.ndarray:
    """验证节点的可解释人工微调，供面料档案保存和复用。"""
    lab = rgb_to_lab(image)
    lab[..., 0] = (lab[..., 0] - 50) * contrast + 50 + lightness
    lab[..., 1:] = lab[..., 1:] * chroma
    lab[..., 1] += a_shift
    lab[..., 2] += b_shift
    return _lab_to_rgb(lab)
