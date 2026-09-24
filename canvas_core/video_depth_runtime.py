"""按实际发行清单选择深度视频设备，安装及执行使用同一张 GPU。"""
from __future__ import annotations

import json
from pathlib import Path

from .component_profiles import RuntimeCapabilities, compatible_variants, probe_runtime_devices


def probe_video_depth_capabilities() -> RuntimeCapabilities:
    variants = json.loads(Path(__file__).with_name('video_depth_runtime_manifest.json').read_text(encoding='utf-8'))['variants']
    return select_video_depth_device(probe_runtime_devices(), variants)


def select_video_depth_device(devices, variants) -> RuntimeCapabilities:
    def score(device):
        matches = compatible_variants(variants, device)
        best = matches[0] if matches else {}
        accelerated = (best.get('constraints') or {}).get('accelerator') == 'cuda'
        return (accelerated, device.gpu_memory_bytes, int(best.get('priority') or 0))
    return max(devices, key=score)


def configure_video_depth_device(env: dict, variant: str, capabilities: RuntimeCapabilities | None) -> None:
    if variant.endswith('-cpu'):
        env['CUDA_VISIBLE_DEVICES'] = ''
    elif capabilities is not None and capabilities.gpu_uuid:
        env['CUDA_VISIBLE_DEVICES'] = capabilities.gpu_uuid
