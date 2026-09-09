import asyncio
import copy
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import main
from canvas_core.fashion_director import (
    DIRECTOR_VERSION, FASHION_QA, full_skill, normalize_plan, planning_message,
)
from canvas_core.lookbook_story import (
    enforce_lookbook_shot_scale_contract, enforce_lookbook_story_rhythm_contract,
    resolve_lookbook_layout_intent,
)


def plan(outputs=1, panels=9):
    bible = {key: "按参考与用户需求确定" for key in (
        "identity", "wardrobe", "environment", "physical_light", "photographic_surface",
        "performance_amplitude", "facial_emotion", "axis_map")}
    bible.update(reference_roles=[{"reference_index": 1, "roles": ["WARDROBE"]}],
                 product_direction={"target": "牛仔裤", "coverage": ["腰线", "全裤型", "膝部车线"]},
                 camera_intensity=5, continuity_ledger=["同一人、同一条裤子"])
    cards = []
    for index in range(1, outputs + 1):
        shots = []
        for number in range(1, panels + 1):
            shot = {key: f"镜头 {number} 的具体决定" for key in (
                "beat", "story_purpose", "continuity_in", "continuity_out", "action_chain",
                "composition", "product_focus", "product_visibility", "lighting",
                "micro_expression", "weight_and_contact")}
            shot.update(index=number, camera={"shot_size": "24mm ground-level full-body denim hero", "angle": "20 degree Dutch tilt"})
            shots.append(shot)
        cards.append({"index": index, "panel_cards": shots,
                      "render_prompt": "A denim fashion campaign, preserve exact reference trousers and physical daylight. " + " ".join(f"PANEL {i}: 24mm ground-level full-body denim hero, 20 degree Dutch tilt, visible wide legs and knee seams." for i in range(1, panels + 1))})
    return {"campaign_bible": bible, "shot_cards": cards}


def snapshot(outputs=1, grid=True):
    layout = resolve_lookbook_layout_intent("", {"preset_id": "grid-3x3" if grid else "single-frame"}, "3:2")
    bible, cards = normalize_plan(plan(outputs, 9 if grid else 1), outputs, layout)
    return {"operation": "universal", "count": outputs, "aspect_ratio": "3:2", "size": "1536x1024",
            "quality": "high", "resolution": "2k", "inputs": [], "prompt": "base",
            "options": {"prompt_policy": "lookbook", "lookbook_mode": "story-campaign",
                        "lookbook_style": {"id": "fashion-advertising"},
                        "instruction": "牛仔裤是主角，胶片大片，大胆动作，不稳定构图，表情优雅轻松",
                        "lookbook_bible": bible, "lookbook_shot_cards": cards, "lookbook_layout_intent": layout}}


def test_full_skill_matches_archived_source_and_is_packaged():
    root = Path(__file__).resolve().parents[1]
    assert full_skill() == (root / "skills/fashion-editorial-sequence-director/SKILL.md").read_text(encoding="utf-8").strip()
    assert '"skills/fashion-editorial-sequence-director"' in (root / "canvas-backend.spec").read_text(encoding="utf-8")


def test_grid_compiles_all_nine_distinct_panels_without_single_beat_lock():
    value = snapshot()
    prompts = main.lookbook_generation_prompts(value)
    assert len(prompts) == 1
    prompt = prompts[0]
    assert full_skill() not in prompt
    assert "exactly 9 distinct photographs" in prompt
    assert "3 rows x 3 columns" in prompt
    assert "PANEL 9" in prompt
    assert "MANDATORY SHOT-SCALE LOCK" not in prompt
    assert "Every panel must advance the same narrative beat" not in prompt
    assert "execute only its assigned narrative beat" not in prompt
    assert "24mm ground-level full-body denim hero" in prompt
    assert "USER BRIEF (creative authority" in prompt


def test_director_cameras_survive_both_generic_contracts():
    cards = snapshot(9, False)["options"]["lookbook_shot_cards"]
    original = copy.deepcopy(cards)
    result = enforce_lookbook_story_rhythm_contract(enforce_lookbook_shot_scale_contract(cards, 9), 9)
    assert result == original
    assert "shot_scale_lock" not in result[3]
    assert "rhythm_lock" not in result[3]


@pytest.mark.parametrize("mutate", [
    lambda data: data["shot_cards"][0]["panel_cards"].pop(),
    lambda data: data["shot_cards"][0]["panel_cards"][2].update(index=1),
    lambda data: data["shot_cards"][0]["panel_cards"][0].pop("camera"),
    lambda data: data["campaign_bible"].pop("product_direction"),
    lambda data: data["shot_cards"].append(data["shot_cards"][0]),
    lambda data: data["shot_cards"][0].update(render_prompt=data["shot_cards"][0]["render_prompt"].replace("PANEL 9", "LAST PANEL")),
])
def test_invalid_plans_fail_instead_of_silent_generic_fallback(mutate):
    data = plan()
    mutate(data)
    with pytest.raises(ValueError):
        normalize_plan(data, 1, snapshot()["options"]["lookbook_layout_intent"])


def test_planner_receives_complete_skill_references_and_panel_count():
    value = snapshot()
    value["options"].pop("lookbook_bible")
    value["options"].pop("lookbook_shot_cards")
    value["inputs"] = [{"url": "/assets/input/person.png", "lookbook_role": "人物"},
                       {"url": "/assets/input/place.jpg", "lookbook_role": "场景"}]
    llm = AsyncMock(return_value={"text": json.dumps(plan(), ensure_ascii=False)})
    with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vlm"}), patch.object(main, "canvas_llm", llm):
        enriched, meta = asyncio.run(main.enrich_lookbook_storyboard(value))
    assert meta["status"] == "succeeded"
    request = llm.call_args.args[0]
    assert full_skill() in request.system_prompt
    assert "每个输出恰好 9" in request.system_prompt
    assert request.images == [item["url"] for item in value["inputs"]]
    assert "人物" in request.image_labels[0]
    assert len(enriched["options"]["lookbook_shot_cards"][0]["panel_cards"]) == 9


@pytest.mark.parametrize("outputs,grid,calls", [(1, True, 1), (2, False, 3), (2, True, 2)])
def test_generation_count_and_internal_master_anchor(outputs, grid, calls):
    value = snapshot(outputs, grid)
    requests = []

    async def generate(**kwargs):
        requests.append(kwargs)
        return {"images": [f"/assets/output/{len(requests)}.png"], "image_items": [], "raw": {}, "generation_elapsed_seconds": 1}

    with patch.object(main, "execute_ai_image_batch", side_effect=generate):
        result = asyncio.run(main.execute_lookbook_story_batch(value, {"provider_id": "images", "model": "image-model"}))
    assert len(requests) == calls
    assert len(result["images"]) == outputs
    assert all("COMPILED PHOTOGRAPHIC DIRECTION" in request["prompt"] for request in requests)
    assert all(full_skill() not in request["prompt"] for request in requests)
    if not grid:
        assert result["director_master"]["images"] == ["/assets/output/1.png"]
        assert "/assets/output/1.png" not in result["images"]
        for request in requests[1:]:
            assert request["references"][-1]["url"] == "/assets/output/1.png"
            assert "ONE standalone full-bleed photograph" in request["prompt"]


def test_fashion_quality_uses_product_and_style_instead_of_generic_plot_template():
    value = snapshot()
    llm = AsyncMock(return_value={"text": '{"passed":true,"score":90,"weak_indices":[]}'})
    with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vlm"}), patch.object(main, "canvas_llm", llm):
        result = asyncio.run(main.analyze_lookbook_outputs(value, ["/assets/output/grid.png"]))
    request = llm.call_args.args[0]
    assert FASHION_QA in request.system_prompt
    assert value["options"]["instruction"] in request.system_prompt
    assert '"index": 9' in request.system_prompt
    assert "在指定锚点发生真实转折" not in request.system_prompt
    assert result["passed"]


def test_old_cache_invalidates_when_director_version_changes():
    value = snapshot()
    before = main.lookbook_context_signature(value)
    with patch.object(main, "fashion_skill_signature", return_value="next-version"):
        assert main.lookbook_context_signature(value) != before


def test_same_skill_adapts_to_other_products_and_restrained_briefs():
    value = snapshot()
    value["options"]["instruction"] = "雨夜腕表广告，克制构图，只拍一个人"
    message = planning_message(value, value["options"]["lookbook_layout_intent"])
    assert "雨夜腕表广告" in message
    assert "For restrained briefs honor restraint" in message
    assert "never invent denim or a second person" in message


def test_text_only_campaign_does_not_invent_reference_roles():
    data = plan()
    data["campaign_bible"]["reference_roles"] = []
    bible, _ = normalize_plan(data, 1, snapshot()["options"]["lookbook_layout_intent"])
    assert bible["reference_roles"] == []


def test_missing_packaged_skill_fails_explicitly(tmp_path):
    import sys
    full_skill.cache_clear()
    try:
        with patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
            with pytest.raises(FileNotFoundError):
                full_skill()
    finally:
        full_skill.cache_clear()


def test_grid_repair_retains_all_panels_and_daring_camera():
    value = snapshot()
    value["options"].update(lookbook_quality_gate=True, lookbook_auto_repair=True)
    inspect = AsyncMock(side_effect=[
        {"status": "succeeded", "passed": False, "weak_indices": [0], "corrections": {"0": "只修复第六格的裤型"}},
        {"status": "succeeded", "passed": True, "score": 90},
    ])
    generate = AsyncMock(return_value={"images": ["/assets/output/repaired.png"]})
    with patch.object(main, "analyze_lookbook_outputs", inspect), patch.object(main, "execute_ai_image_batch", generate):
        batch, quality = asyncio.run(main.improve_lookbook_batch(
            {"images": ["/assets/output/original.png"]}, value, {"provider_id": "images", "model": "image-model"}))
    prompt = generate.call_args.kwargs["prompt"]
    assert "exactly 9 distinct photographs" in prompt
    assert "24mm ground-level full-body denim hero" in prompt
    assert "do not reduce it to a single panel" in prompt
    assert "LAST reference image is the repair target" in prompt
    assert generate.call_args.kwargs["references"][-1]["url"] == "/assets/output/original.png"
    assert "shot-scale lock; output one full-bleed image only" not in prompt
    assert batch["images"] == ["/assets/output/repaired.png"]
    assert quality["passed"]


def test_invalid_reference_role_is_not_silently_dropped():
    request = main.EcommerceTaskRequest(operation="universal", inputs=[{"url": "/assets/input/image.png", "role": "reference"}],
                                       options={"prompt_policy": "lookbook", "lookbook_style": {"id": "fashion-advertising"}})
    with pytest.raises(main.HTTPException, match="无效角色或地址"):
        main.prepare_ecommerce_request(request)


def test_frontend_semantic_role_survives_request_validation():
    ref = main.AIReference(url="/assets/input/person.png", role="subject", reference_type="subject", lookbook_role="人物")
    assert ref.model_dump()["lookbook_role"] == "人物"
    from canvas_core.ecommerce import normalize_universal_inputs
    normalized = normalize_universal_inputs([ref.model_dump()])
    assert normalized[0]["lookbook_role"] == "人物"


def test_complete_cached_plan_can_be_resubmitted_without_20kb_rejection():
    value = snapshot()
    value["options"]["lookbook_bible"]["product_direction"]["notes"] = "具体产品展示决定。" * 2000
    request = main.EcommerceTaskRequest(operation="universal", count=1, aspect_ratio="3:2", resolution="2k", quality="high", options=value["options"])
    result = main.prepare_ecommerce_request(request)
    assert result["count"] == 1
    assert len(result["options"]["lookbook_shot_cards"][0]["panel_cards"]) == 9


def test_legacy_node_selecting_fashion_enters_complete_director():
    request = main.EcommerceTaskRequest(operation="universal", count=1, aspect_ratio="3:2", resolution="2k", quality="high",
                                       options={"prompt_policy": "lookbook", "lookbook_mode": "quick",
                                                "lookbook_style": {"id": "fashion-advertising"}})
    result = main.prepare_ecommerce_request(request)
    assert result["options"]["lookbook_mode"] == "story-campaign"


def test_panel_repair_notes_do_not_drop_later_panels():
    notes = [f"第 {i} 格：" + "修复产品与机位。" * 25 for i in range(1, 10)]
    result = main.parse_lookbook_quality_result(json.dumps({"score": 70, "weak_indices": [0], "corrections": {"0": notes}}), 1, correction_limit=8000)
    assert "第 9 格" in result["corrections"]["0"]


def test_quality_receives_measured_aspect_ratio(tmp_path):
    from PIL import Image
    path = tmp_path / "result.png"
    Image.new("RGB", (150, 100)).save(path)
    llm = AsyncMock(return_value={"text": '{"passed":true,"score":90,"weak_indices":[]}'})
    with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vlm"}), patch.object(main, "canvas_llm", llm), patch.object(main, "output_file_from_url", return_value=str(path)):
        asyncio.run(main.analyze_lookbook_outputs(snapshot(), ["/assets/output/result.png"]))
    assert '"actual_ratio": 1.5' in llm.call_args.args[0].system_prompt
    assert '"width": 150' in llm.call_args.args[0].system_prompt


def test_incomplete_render_prompt_gets_one_targeted_plan_correction():
    value = snapshot()
    value["options"].pop("lookbook_bible")
    broken = plan()
    broken["shot_cards"][0].pop("render_prompt")
    llm = AsyncMock(side_effect=[{"text": json.dumps(broken)}, {"text": json.dumps(plan())}])
    with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vlm"}), patch.object(main, "canvas_llm", llm):
        enriched, result = asyncio.run(main.enrich_lookbook_storyboard(value))
    assert result["status"] == "succeeded"
    assert llm.await_count == 2
    assert "方案校验失败" in llm.call_args.args[0].message
    assert "PANEL 9" in enriched["options"]["lookbook_shot_cards"][0]["render_prompt"]


def test_bold_execution_is_visual_and_restrained_campaign_is_unchanged():
    value = snapshot()
    assert "in at least 3" in main.lookbook_generation_prompts(value)[0]
    assert "Diagonal parking lines" in main.lookbook_generation_prompts(value)[0]
    value["options"]["lookbook_bible"]["camera_intensity"] = 2
    assert "BOLD CAMERA EXECUTION" not in main.lookbook_generation_prompts(value)[0]


def test_regressing_repair_preserves_original_image():
    value = snapshot()
    value["options"].update(lookbook_quality_gate=True, lookbook_auto_repair=True)
    initial = {"status": "succeeded", "passed": False, "score": 78, "weak_indices": [0], "corrections": {"0": "修复膝部车线"}}
    candidate = {"status": "succeeded", "passed": False, "score": 76, "weak_indices": [0]}
    with patch.object(main, "analyze_lookbook_outputs", AsyncMock(side_effect=[initial, candidate])), patch.object(main, "execute_ai_image_batch", AsyncMock(return_value={"images": ["/assets/output/worse.png"]})):
        batch, meta = asyncio.run(main.improve_lookbook_batch({"images": ["/assets/output/original.png"]}, value, {"provider_id": "images", "model": "image-model"}))
    assert batch["images"] == ["/assets/output/original.png"]
    assert meta["score"] == 78
    assert meta["repair_candidate_quality"]["score"] == 76
    assert meta["retries"][0]["reverted"]


def test_product_detail_crop_preserves_source_and_reference_ownership(tmp_path):
    from PIL import Image
    original = tmp_path / "product.png"
    im = Image.new("RGB", (200, 100), "red")
    im.paste("blue", (100, 0, 200, 100))
    im.save(original)
    before = original.read_bytes()
    value = snapshot()
    refs = [{"url": "/assets/input/product.png"}, {"url": "/assets/input/scene.png"}]
    value["inputs"] = refs
    value["options"]["lookbook_bible"]["product_direction"]["detail_regions"] = [
        {"reference_index": 1, "box": [0.5, 0, 1, 1], "purpose": "蓝色区域的工艺结构"}]
    with patch.object(main, "output_file_from_url", return_value=str(original)), patch.object(main, "OUTPUT_OUTPUT_DIR", str(tmp_path)):
        packaged = main.fashion_product_detail_references(value, list(reversed(refs)), 3)
    assert len(packaged) == 3
    assert packaged[-1]["fashion_product_source_index"] == 2
    with Image.open(tmp_path / Path(packaged[-1]["url"]).name) as detail:
        assert detail.size == (100, 100)
        assert detail.getpixel((50, 50))[2] > 250
    assert original.read_bytes() == before
    assert "PRODUCT EVIDENCE PACKAGE" in main.lookbook_scene_reference_package_prompt(packaged)
