import copy
import json
from unittest.mock import AsyncMock, patch

import pytest
import main
from canvas_core.lookbook_brief import STORY_VERSION, normalize_story, validate_story_shots
from canvas_core.lookbook_story import resolve_lookbook_layout_intent
from tests.test_lookbook_two_stage import fixture, story_response, shots_response


def grid_plan():
    shots = shots_response(4)["shot_cards"]
    for shot, action in zip(shots, ["倚墙抬眼轻笑", "指尖轻捏衣料", "俯拍侧脸沉思", "低位伸展身体"]):
        shot.update(action_chain=action, micro_expression=action, composition=action)
    outer = {**shots[0], "index": 1, "panel_cards": shots}
    return {"campaign_bible": {"wardrobe": "现有造型"}, "shot_cards": [outer]}


def options():
    return {"lookbook_story": normalize_story(story_response(count=1), 1),
            "lookbook_layout_intent": resolve_lookbook_layout_intent("", {"preset_id": "grid-2x2"}, "16:9")}


def test_grid_requires_exact_inner_panels_and_contiguous_numbers():
    value = grid_plan()["shot_cards"]
    for corrupt in ("missing", "count", "index"):
        cards = copy.deepcopy(value)
        if corrupt == "missing":
            cards[0].pop("panel_cards")
        elif corrupt == "count":
            cards[0]["panel_cards"].pop()
        else:
            cards[0]["panel_cards"][2]["index"] = 8
        with pytest.raises(ValueError):
            validate_story_shots(cards, options())


def test_cosmetic_number_changes_do_not_pass_visual_plan_deduplication():
    cards = grid_plan()["shot_cards"]
    for number, panel in enumerate(cards[0]["panel_cards"]):
        panel.update(action_chain=f"动作{number}站着", micro_expression="呆滞", composition="居中")
    with pytest.raises(ValueError, match="重复动作"):
        validate_story_shots(cards, options())


@pytest.mark.asyncio
async def test_normal_director_repairs_grid_then_compiles_every_inner_shot():
    source = fixture(count=1, lookbook_layout_selection={"preset_id": "grid-2x2"})
    responses = [story_response(count=1), shots_response(1), grid_plan()]
    with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "test", "model": "test"}), patch.object(main, "canvas_llm", new=AsyncMock(side_effect=[{"text": json.dumps(v)} for v in responses])) as llm:
        result, meta = await main.prepare_lookbook_creation(source)
    assert not meta.get("failed_stage")
    assert llm.await_count == 3  # 正常两次，仅错误方案增加一次修复。
    first_request = llm.call_args_list[0].args[0]
    assert '"panel_count": 4' in first_request.message
    prompt, = main.lookbook_generation_prompts(result)
    for number, action in enumerate(["倚墙抬眼轻笑", "指尖轻捏衣料", "俯拍侧脸沉思", "低位伸展身体"], 1):
        assert f"PANEL {number}" in prompt
        assert action in prompt
    assert "same narrative beat" not in prompt
    assert result["options"]["lookbook_story"]["version"] == STORY_VERSION


@pytest.mark.asyncio
@pytest.mark.parametrize("style", ["standard-advertising", "fashion-advertising"])
async def test_editorial_qa_does_not_reintroduce_forced_dramatic_arc(style):
    source = fixture(count=1, lookbook_style={"id": style}, **options())
    source["options"]["lookbook_shot_cards"] = [{"continuity_in": "四格必须露鞋，这是自动建议"}]
    with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "test", "model": "test"}), patch.object(main, "canvas_llm", new=AsyncMock(return_value={"text": json.dumps({"passed": True, "score": 90, "weak_indices": [], "issues": [], "corrections": {}, "summary": "ok"})})) as llm:
        await main.analyze_lookbook_outputs(source, ["/assets/generated/grid.png"])
    request = llm.call_args.args[0]
    assert "在指定锚点发生真实转折" not in request.message
    assert "不要求每格完整展示服装或发生剧情转折" in request.system_prompt
    assert "四格必须露鞋" not in request.system_prompt


def test_old_generated_story_cache_is_invalidated():
    source = fixture()
    source["options"]["lookbook_story"] = {"version": "lookbook-wardrobe-story-v1", "ad_brief": "过期试穿方案"}
    source["options"]["lookbook_context_signature"] = "old-version-signature"
    reset, invalid = main.invalidate_stale_lookbook_context(source)
    assert invalid
    assert "lookbook_story" not in reset["options"]


def test_nine_panel_story_does_not_hit_legacy_eight_beat_limit():
    story = story_response(count=1)
    story["beats"] = story["beats"] * 9
    assert len(normalize_story(story, 1)["beats"]) == 9


def test_compiler_uses_panel_decisions_not_redundant_render_prompt_or_process_state():
    from canvas_core.lookbook_brief import editorial_generation_prompt
    card = grid_plan()["shot_cards"][0]
    card["render_prompt"] = "OLD DUPLICATE POSE TEMPLATE"
    card["panel_cards"][1]["continuity_in"] = "PROCESS STATE SHOULD NOT BE RENDERED"
    result = editorial_generation_prompt("表情和触感", {"identity": "同一人", "selected_style_lock": "LEGACY FOUR SHOT TEMPLATE"}, card, ["R1 人物"], options()["lookbook_layout_intent"])
    assert "2 rows x 2 columns" in result
    assert "PANEL 4" in result
    assert "指尖轻捏衣料" in result
    assert "OLD DUPLICATE" not in result
    assert "PROCESS STATE" not in result
    assert "LEGACY FOUR" not in result
