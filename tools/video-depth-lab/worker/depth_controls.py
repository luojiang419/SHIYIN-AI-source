from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

import cv2
import numpy as np


@dataclass(frozen=True)
class DepthControls:
    far_point: float = 0.0
    near_point: float = 100.0
    midtone: float = 0.0
    contrast: float = 100.0
    brightness: float = 0.0
    smooth: float = 0.0
    invert: bool = False

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "DepthControls":
        source = value or {}
        aliases = {
            "far_point": "farPoint",
            "near_point": "nearPoint",
        }
        fields: dict[str, Any] = {}
        for name in cls.__dataclass_fields__:
            candidate = source.get(name, source.get(aliases.get(name, name), getattr(cls(), name)))
            fields[name] = bool(candidate) if name == "invert" else float(candidate)
        result = cls(**fields)
        result.validate()
        return result

    def validate(self) -> None:
        ranges = {
            "far_point": (0.0, 99.0),
            "near_point": (1.0, 100.0),
            "midtone": (-100.0, 100.0),
            "contrast": (0.0, 300.0),
            "brightness": (-100.0, 100.0),
            "smooth": (0.0, 50.0),
        }
        for name, (minimum, maximum) in ranges.items():
            number = float(getattr(self, name))
            if not minimum <= number <= maximum:
                raise ValueError(f"{name} 必须位于 {minimum:g}–{maximum:g}")
        if self.near_point <= self.far_point:
            raise ValueError("近景白点必须大于远景黑点")

    def as_camel_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["farPoint"] = value.pop("far_point")
        value["nearPoint"] = value.pop("near_point")
        return value


def normalize_relative_depth(depths: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    values = np.asarray(depths, dtype=np.float32)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        raise ValueError("模型输出不包含有限深度值")
    low, high = np.percentile(finite, [2.0, 98.0]).astype(float)
    if high - low < 1e-7:
        low = float(finite.min())
        high = float(finite.max())
    if high - low < 1e-7:
        return np.zeros_like(values, dtype=np.float32), {"p02": low, "p98": high}
    normalized = np.clip((values - low) / (high - low), 0.0, 1.0)
    normalized[~np.isfinite(normalized)] = 0.0
    return normalized.astype(np.float32, copy=False), {"p02": low, "p98": high}


def apply_depth_controls(depths: np.ndarray, controls: DepthControls) -> np.ndarray:
    controls.validate()
    values = np.asarray(depths, dtype=np.float32)
    low = controls.far_point / 100.0
    high = controls.near_point / 100.0
    values = np.clip((values - low) / max(high - low, 1e-6), 0.0, 1.0)

    if controls.midtone >= 0:
        gamma = 1.0 / (1.0 + 1.75 * controls.midtone / 100.0)
    else:
        gamma = 1.0 + 2.0 * abs(controls.midtone) / 100.0
    values = np.power(values, gamma, dtype=np.float32)
    values = (values - 0.5) * (controls.contrast / 100.0) + 0.5
    values += controls.brightness / 100.0
    values = np.clip(values, 0.0, 1.0)

    if controls.smooth > 0:
        sigma = 0.25 + controls.smooth * 0.12
        values = np.stack(
            [cv2.GaussianBlur(frame, (0, 0), sigmaX=sigma, sigmaY=sigma) for frame in values],
            axis=0,
        )
    if controls.invert:
        values = 1.0 - values
    return np.rint(np.clip(values, 0.0, 1.0) * 255.0).astype(np.uint8)
