import json
from unittest.mock import AsyncMock, patch

import pytest
import main
from canvas_core.lookbook_brief import workflow_defaults, effective_optics, bold_direction_active
from tests.test_lookbook_two_stage import fixture, story_response
from tests.test_lookbook_optics_product import campaign


def test_default_workflow_enables_direction_review_and_one_repair_but_honors_off():
    result = workflow_defaults({})
    assert result["lookbook_bold_editorial"] is True
    assert result["lookbook_quality_gate"] is True
    assert result["lookbook_auto_repair"] is True
    assert result["lookbook_max_retries"] == 1
    disabled = {k: False for k in ("lookbook_bold_editorial", "lookbook_quality_gate", "lookbook_auto_repair")}
    assert all(workflow_defaults(disabled)[k] is False for k in disabled)


@pytest.mark.parametrize("instruction,wide", [
    ("主推牛仔裤", True), ("表情克制优雅", True), ("不要常规镜头", True),
    ("不用广角", False), ("只用85mm镜头", False),
])
def test_default_bold_does_not_require_user_to_type_lens_keywords(instruction, wide):
    assert ("wide" in effective_optics({"instruction": instruction, "lookbook_bold_editorial": True})) == wide


def test_semantic_camera_restraint_needs_real_user_evidence():
    options = {"instruction": "摄影保持克制", "lookbook_bold_editorial": True,
               "lookbook_story": {"camera_constraints": {"mode": "restrained", "quote": "摄影保持克制"}}}
    assert effective_optics(options) == set()
    assert not bold_direction_active(options)
    options["lookbook_story"]["camera_constraints"]["quote"] = "虚构的摄影限制"
    assert effective_optics(options) == {"wide"}
    assert bold_direction_active(options)


def test_trailing_comma_repair_preserves_quoted_content_and_does_not_invent_values():
    expected = {"text": 'quoted " ,} and ,]', "values": [1, 2]}
    raw = json.dumps(expected).replace('[1, 2]', '[1, 2,]')[:-1] + ',}'
    assert main._parse_lookbook_json(raw) == expected
    with pytest.raises(json.JSONDecodeError):
        main._parse_lookbook_json('{"missing": }')


@pytest.mark.asyncio
async def test_short_product_request_uses_defaults_and_repairs_conventional_plan():
    source = fixture(count=1, instruction="主推这条牛仔裤", lookbook_layout_selection={"preset_id": "grid-2x2"})
    source["options"].pop("lookbook_bold_editorial")
    story = story_response(count=1)
    story["wardrobe"].update(focus_mode="product", target="参考图牛仔裤")
    cards, _ = campaign()
    good = {"campaign_bible": {"identity": "same person", "wardrobe": "reference jeans"}, "shot_cards": cards}
    bad = json.loads(json.dumps(good))
    for panel in bad["shot_cards"][0]["panel_cards"]:
        panel["camera"].update(lens_mm=50, projection="rectilinear", distance_m=3)
    with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "test", "model": "test"}), patch.object(main, "canvas_llm", new=AsyncMock(side_effect=[{"text": json.dumps(v)} for v in (story, bad, good)])) as llm:
        result, meta = await main.prepare_lookbook_creation(source)
    assert not meta.get("failed_stage")
    assert llm.await_count == 3
    assert result["options"]["lookbook_bold_editorial"]
    assert result["options"]["lookbook_quality_gate"]
    assert result["options"]["lookbook_auto_repair"]
    assert "近距离广角" in llm.call_args.args[0].message
    assert "fisheye" in main.lookbook_generation_prompts(result)[0]
