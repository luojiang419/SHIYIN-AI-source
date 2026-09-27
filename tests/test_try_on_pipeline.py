import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from canvas_core.try_on_pipeline import compile_outfit_edit
from canvas_core.pose_replicate_prompts import compile_pose_replicate_prompt


def ref(kind, id=None, **extra):
    return {"role": kind, "reference_type": kind, "reference_id": id or kind,
            "url": f"/assets/input/{id or kind}.png", **extra}


def test_single_product_keeps_batch_template_and_original_pixels():
    inputs = [ref("upper_garment"), ref("detail", detail_target_id="upper_garment")]
    refs, prompt, template = compile_outfit_edit(ref("source"), ref("control_map"), inputs, "3:4")
    baseline = compile_pose_replicate_prompt("depth", has_fabric_detail=True, output_aspect_ratio="3:4")
    assert prompt.startswith(baseline.final_prompt)
    assert template == baseline.template_variant
    assert [r["url"] for r in refs[2:]] == [r["url"] for r in inputs]


def test_multi_product_cannot_bypass_sequential_pipeline():
    with pytest.raises(ValueError, match="只处理一件"):
        compile_outfit_edit(ref("source"), ref("control_map"),
                           [ref("upper_garment"), ref("lower_garment")], "3:4")


def test_anchor_excludes_products_and_final_excludes_original_pose(tmp_path):
    import main
    inputs = [ref("source"), ref("upper_garment"), ref("pose")]
    snapshot = {"inputs": inputs, "options": {"studio_reference": "studio_warm"},
                "size": "3072x4096", "quality": "high", "aspect_ratio": "3:4"}
    generate = AsyncMock(return_value={"images": ["/assets/output/anchor.png"], "generation_elapsed_seconds": 10})
    depth = AsyncMock(return_value=(b"depth", "quality"))
    with (patch.object(main, "execute_ai_image_batch", generate), patch.object(main, "render_try_on_depth", depth),
          patch.object(main, "update_ecommerce_task"), patch.object(main, "read_app_config", return_value={}),
          patch.object(main, "output_file_from_url", return_value="anchor-file.png"),
          patch.object(main, "OUTPUT_OUTPUT_DIR", str(tmp_path)),
          patch.object(main, "media_url_from_path", side_effect=lambda p: "/assets/output/" + Path(p).name)):
        refs, prompt, audit = asyncio.run(main.prepare_try_on_product_edit(
            "test", snapshot, {"provider_id": "test", "model": "test"}, [*inputs, ref("control_map")]))
    assert [r["role"] for r in generate.call_args.kwargs["references"]] == ["pose", "source", "control_map"]
    assert "IMMUTABLE FOREGROUND" not in generate.call_args.kwargs["prompt"]
    assert "图2的同一张脸" in generate.call_args.kwargs["prompt"]
    assert [r["role"] for r in refs] == ["source", "control_map", "upper_garment"]
    assert refs[0]["url"] == "/assets/output/anchor.png"
    depth.assert_awaited_once_with("anchor-file.png", {})
    assert audit["edit_depth"]["source_url"] == refs[0]["url"]
    assert audit["studio_prepared"]


def test_simple_tryon_has_no_extra_image_generation():
    import main
    inputs = [ref("source"), ref("upper_garment"), ref("control_map")]
    with patch.object(main, "execute_ai_image_batch", new=AsyncMock()) as generate, patch.object(main, "update_ecommerce_task"):
        refs, _, audit = asyncio.run(main.prepare_try_on_product_edit(
            "test", {"inputs": inputs, "aspect_ratio": "3:4"}, {}, inputs))
    generate.assert_not_awaited()
    assert refs[0] == inputs[0]
    assert audit["status"] == "not_required"


def test_sequential_edit_never_mixes_products_and_refreshes_depth(tmp_path):
    import main
    inputs = [ref("source"), ref("upper_garment"), ref("lower_garment"), ref("control_map"),
              ref("detail", "lower_detail", detail_target_id="lower_garment")]
    generate = AsyncMock(return_value={"images": ["/assets/output/top-done.png"], "generation_elapsed_seconds": 5})
    with (patch.object(main, "execute_ai_image_batch", generate),
          patch.object(main, "render_try_on_depth", new=AsyncMock(return_value=(b"depth", "quality"))) as depth,
          patch.object(main, "read_app_config", return_value={}), patch.object(main, "update_ecommerce_task"),
          patch.object(main, "OUTPUT_OUTPUT_DIR", str(tmp_path)),
          patch.object(main, "output_file_from_url", return_value="top-done.png"),
          patch.object(main, "media_url_from_path", side_effect=lambda p: "/assets/output/" + Path(p).name)):
        refs, prompt, audit = asyncio.run(main.prepare_try_on_product_edit(
            "test", {"inputs": inputs, "aspect_ratio": "3:4", "size": "4k", "quality": "high"},
            {"provider_id": "test", "model": "test"}, inputs))
    first = generate.call_args.kwargs["references"]
    assert [r["role"] for r in first] == ["source", "control_map", "upper_garment"]
    assert [r["role"] for r in refs] == ["source", "control_map", "lower_garment", "detail"]
    assert refs[0]["url"] == "/assets/output/top-done.png"
    assert refs[1]["url"] != inputs[3]["url"]
    depth.assert_awaited_once_with("top-done.png", {})
    assert audit["product_steps"][0]["product_id"] == "upper_garment"
    assert audit["generation_elapsed_seconds"] == 5
    assert "图4只补充图3" in prompt
