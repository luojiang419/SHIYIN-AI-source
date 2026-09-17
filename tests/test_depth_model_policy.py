from __future__ import annotations

import json
from pathlib import Path

from canvas_core.component_profiles import RuntimeCapabilities
from canvas_core.depth_model_policy import QUALITY_MIN_GPU_MEMORY_BYTES, select_depth_model_tier
from canvas_core.person_depth_components import PersonDepthComponentManager
from canvas_core.video_depth import VideoDepthTaskService


def test_depth_tier_uses_quality_only_with_at_least_eight_gib_cuda():
    quality = select_depth_model_tier(RuntimeCapabilities(
        "windows", "x86_64", "cuda", gpu_memory_bytes=QUALITY_MIN_GPU_MEMORY_BYTES
    ))
    low_vram = select_depth_model_tier(RuntimeCapabilities(
        "windows", "x86_64", "cuda", gpu_memory_bytes=QUALITY_MIN_GPU_MEMORY_BYTES - 1
    ))
    cpu = select_depth_model_tier(RuntimeCapabilities("windows", "x86_64", "cpu"))

    assert quality.tier == "quality"
    assert low_vram.tier == "lite"
    assert cpu.tier == "lite"


def test_depth_tier_can_be_overridden_for_support_and_comparison():
    capabilities = RuntimeCapabilities("windows", "x86_64", "cpu")
    assert select_depth_model_tier(capabilities, "quality").tier == "quality"
    assert select_depth_model_tier(capabilities, "lite").tier == "lite"


def test_video_depth_manifest_selects_only_the_matching_model(tmp_path):
    manifest = json.loads(Path("canvas_core/video_depth_manifest.json").read_text(encoding="utf-8"))
    lite = PersonDepthComponentManager(
        tmp_path / "lite", manifest=manifest, component_name="video-depth",
        capability_provider=lambda: RuntimeCapabilities("windows", "x86_64", "cpu"),
        smoke_runner=lambda _command, _root: None,
    )
    quality = PersonDepthComponentManager(
        tmp_path / "quality", manifest=manifest, component_name="video-depth",
        capability_provider=lambda: RuntimeCapabilities(
            "windows", "x86_64", "cuda", gpu_memory_bytes=QUALITY_MIN_GPU_MEMORY_BYTES
        ),
        smoke_runner=lambda _command, _root: None,
    )

    assert lite.selected_variant_id == "lite"
    assert [spec.package_id for spec in lite.specs] == ["vda-small-model"]
    assert quality.selected_variant_id == "quality"
    assert [spec.package_id for spec in quality.specs] == ["vda-base-model"]


def test_video_depth_service_passes_selected_model_to_worker(tmp_path):
    class Manager:
        selected_variant_id = "lite"

    service = VideoDepthTaskService(tmp_path, model_manager=Manager())
    assert service._model_key() == "vda_small_fp16_relative"
    assert "Small" in service._model_label()
    Manager.selected_variant_id = "quality"
    assert service._model_key() == "vda_base_fp16_relative"
