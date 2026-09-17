from __future__ import annotations

import os
from dataclasses import dataclass

from .component_profiles import RuntimeCapabilities, probe_runtime_capabilities


QUALITY_MIN_GPU_MEMORY_BYTES = 8 * 1024**3
DEPTH_TIER_ENV = "SHIYIN_DEPTH_MODEL_TIER"


@dataclass(frozen=True)
class DepthModelSelection:
    tier: str
    reason: str
    capabilities: RuntimeCapabilities

    @property
    def quality(self) -> bool:
        return self.tier == "quality"


def select_depth_model_tier(
    capabilities: RuntimeCapabilities | None = None,
    override: str | None = None,
) -> DepthModelSelection:
    capabilities = capabilities or probe_runtime_capabilities()
    requested = str(override if override is not None else os.getenv(DEPTH_TIER_ENV, "auto")).strip().lower()
    if requested in {"lite", "quality"}:
        return DepthModelSelection(requested, f"用户固定为{requested}档", capabilities)
    if capabilities.accelerator == "cuda" and capabilities.gpu_memory_bytes >= QUALITY_MIN_GPU_MEMORY_BYTES:
        return DepthModelSelection("quality", "检测到至少 8GB NVIDIA 显存", capabilities)
    if capabilities.accelerator != "cuda":
        reason = "未检测到兼容的 NVIDIA CUDA GPU"
    else:
        gib = capabilities.gpu_memory_bytes / 1024**3
        reason = f"NVIDIA 显存 {gib:.1f}GB，低于高质量档所需的 8GB"
    return DepthModelSelection("lite", reason, capabilities)
