import pytest
from unittest.mock import AsyncMock, patch
import main

from canvas_core.lookbook_brief import (
    editorial_generation_prompt, normalize_story, requested_optics, validate_story_shots,
)
from tests.test_lookbook_editorial import grid_plan, options
from tests.test_lookbook_two_stage import story_response, fixture


def campaign():
    value = grid_plan()["shot_cards"]
    settings = options()
    settings["instruction"] = "卖牛仔裤，大胆使用广角和鱼眼"
    settings["lookbook_story"]["wardrobe"].update(focus_mode="product", target="参考图中的牛仔裤")
    for index, panel in enumerate(value[0]["panel_cards"]):
        panel["camera"].update(lens_mm=[14, 12, 70, 20][index], projection="fisheye" if index==1 else "rectilinear",
                               distance_m=.5, height_m=.2, perspective_effect="近侧裤腿放大，远侧裤腿沿对角线退入空间")
        panel.update(product_focus="丹宁宽腿体积", product_visibility="裤腿占据前景并清楚保留拼缝", product_emphasis="dominant")
    return value, settings


def test_bold_camera_and_product_decisions_survive_compilation():
    cards, settings = campaign()
    cards = validate_story_shots(cards, settings)
    prompt = editorial_generation_prompt(settings["instruction"], {"camera_intensity": 5, "wardrobe": "现有造型"}, cards[0], [], settings["lookbook_layout_intent"])
    for evidence in ("fisheye", '"lens_mm":12', '"distance_m":0.5', "参考图中的牛仔裤", "丹宁宽腿体积", "近侧裤腿放大", '"camera_intensity": 5'):
        assert evidence in prompt


def test_low_angle_words_cannot_replace_requested_wide_optics():
    cards, settings = campaign()
    for panel in cards[0]["panel_cards"]:
        panel["camera"].update(lens_mm=50, projection="rectilinear", angle="大胆低机位")
    with pytest.raises(ValueError, match="近距离广角"):
        validate_story_shots(cards, settings)


def test_focal_number_without_proximity_and_projection_is_rejected():
    cards, settings = campaign()
    cards[0]["panel_cards"][1]["camera"].pop("distance_m")
    with pytest.raises(ValueError, match="distance_m"):
        validate_story_shots(cards, settings)


def test_explicit_fisheye_is_not_satisfied_by_rectilinear_wide():
    cards, settings = campaign()
    cards[0]["panel_cards"][1]["camera"]["projection"] = "rectilinear"
    with pytest.raises(ValueError, match="没有fisheye"):
        validate_story_shots(cards, settings)


def test_jeans_campaign_cannot_be_mostly_faces_or_other_clothes():
    cards, settings = campaign()
    for panel in cards[0]["panel_cards"][:3]:
        panel["product_emphasis"] = "supporting"
    with pytest.raises(ValueError, match="构图主体"):
        validate_story_shots(cards, settings)


@pytest.mark.parametrize("instruction,expected", [
    ("不要鱼眼，但用广角", {"wide"}),
    ("no fisheye, use wide-angle", {"wide"}),
    ("不用广角和鱼眼", set()),
    ("广角和鱼眼都大胆使用", {"wide", "fisheye"}),
])
def test_explicit_optics_respects_negation(instruction, expected):
    assert requested_optics({"instruction": instruction}) == expected


def test_story_preserves_explicit_product_focus():
    data = story_response()
    data["wardrobe"].update(focus_mode="product", target="牛仔裤")
    assert normalize_story(data, 1)["wardrobe"]["focus_mode"] == "product"


@pytest.mark.asyncio
async def test_quality_receives_real_dimensions_instead_of_guessing_thumbnail_ratio(tmp_path):
    from PIL import Image
    import json
    path = tmp_path / "grid.png"
    Image.new("RGB", (1600, 900)).save(path)
    source = fixture(count=1, **options())
    source["aspect_ratio"] = "16:9"
    with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "test", "model": "test"}), patch.object(main, "output_file_from_url", return_value=str(path)), patch.object(main, "canvas_llm", new=AsyncMock(return_value={"text": json.dumps({"passed": True, "score": 90, "weak_indices": []})})) as llm:
        await main.analyze_lookbook_outputs(source, ["/assets/output/grid.png"])
    request = llm.call_args.args[0]
    assert '"width": 1600' in request.system_prompt
    assert '"height": 900' in request.system_prompt
    assert "不能因各格等大" in request.message


@pytest.mark.asyncio
async def test_normal_editorial_repair_preserves_grid_and_uses_existing_image():
    source = fixture(count=1, **options())
    source["options"].update(lookbook_shot_cards=grid_plan()["shot_cards"], lookbook_bible={"identity": "same person"},
                             lookbook_quality_gate=True, lookbook_auto_repair=True)
    initial = {"status": "succeeded", "passed": False, "score": 50, "weak_indices": [0], "corrections": {"0": "只修复裤子口袋，保留强透视"}}
    final = {"status": "succeeded", "passed": True, "score": 90, "weak_indices": []}
    with patch.object(main, "analyze_lookbook_outputs", new=AsyncMock(side_effect=[initial, final])), patch.object(main, "execute_ai_image_batch", new=AsyncMock(return_value={"images": ["/assets/output/repaired.png"]})) as generate:
        result, quality = await main.improve_lookbook_batch({"images": ["/assets/output/weak.png"]}, source, {"provider_id": "test", "model": "test"})
    request = generate.call_args.kwargs
    assert "COMPLETE original layout" in request["prompt"]
    assert request["references"][-1]["url"] == "/assets/output/weak.png"
    assert quality["passed"]
