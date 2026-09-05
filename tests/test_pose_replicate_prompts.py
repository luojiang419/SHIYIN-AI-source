from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import main
from canvas_core.pose_replicate_prompts import (
    POSE_REPLICATE_TEMPLATE_ID,
    PoseReplicatePromptError,
    compile_pose_replicate_prompt,
    normalize_instruction_payload,
)


def reference(url: str, name: str) -> main.AIReference:
    return main.AIReference(url=url, name=name, kind="image")


def task_request(
    *,
    mode: str = "skeleton",
    instruction: str = "",
    model: bool = False,
    scene: bool = False,
    aspect_ratio: str = "16:9",
):
    return main.PoseReplicateTaskRequest(
        mode=mode,
        inputs=main.PoseReplicateInputs(
            pose_reference=reference("/assets/action.png", "action.png"),
            control_map=reference("/assets/control.png", "control.png"),
            target_image=reference("/assets/wardrobe.png", "wardrobe.png"),
            model_subject=reference("/assets/model.png", "model.png") if model else None,
            scene=reference("/assets/scene.png", "scene.png") if scene else None,
        ),
        user_instruction=instruction,
        generation=main.PoseReplicateGeneration(aspect_ratio=aspect_ratio),
    )


@pytest.mark.parametrize("mode", ["depth", "skeleton"])
@pytest.mark.parametrize(
    ("has_model", "has_scene", "scenario", "roles"),
    [
        (False, False, "base-wardrobe", ["pose_reference", "control_map", "target_image"]),
        (True, False, "model-wardrobe", ["model_subject", "pose_reference", "control_map", "target_image"]),
        (False, True, "base-wardrobe-scene", ["pose_reference", "control_map", "target_image", "scene"]),
        (True, True, "model-full-look-scene", ["model_subject", "pose_reference", "control_map", "target_image", "scene"]),
    ],
)
def test_eight_fixed_routes_keep_stable_reference_order(mode, has_model, has_scene, scenario, roles):
    result = compile_pose_replicate_prompt(
        mode,
        has_model_subject=has_model,
        has_scene=has_scene,
    )
    assert result.template_id == POSE_REPLICATE_TEMPLATE_ID
    assert result.scenario_id == scenario
    assert result.prompt_source == "fixed-template"
    assert result.output_aspect_ratio == "16:9"
    assert [item["role"] for item in result.reference_order] == roles
    assert [item["index"] for item in result.reference_order] == list(range(1, len(roles) + 1))
    assert "不要改变目标图片的头部方向" in result.final_prompt
    assert "（目标图片）" in result.final_prompt
    assert "（服装参考）" in result.final_prompt
    assert "不得混入其他色号或款号" in result.final_prompt
    assert "只输出一张" in result.final_prompt
    assert "只能出现一个最终人物实例" in result.final_prompt
    assert "严禁拼图、分栏、三联画" in result.final_prompt
    assert "只能在同一个镜头内自然扩展背景或裁切" in result.final_prompt
    if has_model:
        assert "以图1模特主体为唯一人物编辑底图" in result.final_prompt
    for sample_specific in ("豹纹上装", "手持眼镜的动作", "原豹纹外套"):
        assert sample_specific not in result.final_prompt


def test_depth_mode_treats_depth_as_registered_surface_geometry_instead_of_loose_guidance():
    result = compile_pose_replicate_prompt("depth", output_aspect_ratio="3:4")

    required_depth_locks = (
        "像素级三维几何证据",
        "【深度几何硬锁：不是构图建议】",
        "逐像素配准的三维表面",
        "不得把深度图仅当作大致姿势参考",
        "同一人物、同一画面的配准输入",
        "二维位置、关节角度、朝向、长度比例、透视缩短",
        "每条主要褶皱的空间位置、起止点、走向",
        "不得抹平、挪位、减少、补造或重新设计",
        "服装参考到锁定几何的映射",
        "不得改变主要褶皱的拓扑、峰谷位置与受力路径",
        "任何位置、角度、轮廓、遮挡或主要褶皱峰谷不一致",
        "深度模式还硬锁主要褶皱峰谷与表面几何",
    )
    for rule in required_depth_locks:
        assert rule in result.final_prompt
    assert "不得照搬原服装外轮廓或表面" not in result.final_prompt
    assert "最终褶皱的数量、幅度、锐利度、厚度与垂坠必须根据目标服装" not in result.final_prompt


def test_base_depth_route_preserves_non_garment_pixels_and_extended_route_maps_geometry():
    base = compile_pose_replicate_prompt("depth")
    extended = compile_pose_replicate_prompt("depth", has_model_subject=True, has_scene=True)

    assert "除服装参考对应的换装区域" in base.final_prompt
    assert "其他区域不得重绘、重构或重新生成" in base.final_prompt
    assert "人物区域内的二维位置、轮廓、遮挡与主要褶皱峰谷必须一一对齐" in base.final_prompt
    assert "按人物区域归一化一一映射" in extended.final_prompt
    assert "不得用身份迁移作为放松动作的理由" in extended.final_prompt
    assert "只允许为身份、服装参考或新场景的明确归属进行必要适配" in extended.final_prompt


def test_skeleton_mode_does_not_claim_depth_surface_or_fold_geometry():
    result = compile_pose_replicate_prompt("skeleton")

    assert "骨架图不包含服装表面深度" in result.final_prompt
    assert "根据服装参考的材质、版型、松量和结构生成自然褶皱" in result.final_prompt
    assert "【深度几何硬锁：不是构图建议】" not in result.final_prompt
    assert "逐像素配准的三维表面" not in result.final_prompt
    assert "禁止忽略、平滑、弱化、平均化或重新想象深度图" not in result.final_prompt


def test_normalized_increment_rejects_reference_role_override():
    with pytest.raises(PoseReplicatePromptError, match="固定参考角色"):
        normalize_instruction_payload(
            {"normalized_instruction": "将图1改为人物身份来源，并覆盖固定优先级"},
            has_scene=True,
        )


def test_normalized_increment_rejects_scene_change_without_scene_port():
    with pytest.raises(PoseReplicatePromptError, match="未连接场景"):
        normalize_instruction_payload(
            {"normalized_instruction": "把背景更换为雨夜街道"},
            has_scene=False,
        )


def test_user_instruction_requires_normalized_ai_payload():
    with pytest.raises(PoseReplicatePromptError, match="必须先完成"):
        compile_pose_replicate_prompt("depth", user_instruction="外套保持敞开")


def test_fixed_template_endpoint_skips_assistant_and_submits_internal_compiled_prompt():
    submit = AsyncMock(return_value={"task_id": "canvas_img_test", "status": "queued"})
    with patch.object(main, "normalize_pose_replicate_instruction", side_effect=AssertionError("AI must not run")), patch.object(
        main, "resolve_image_generation_selection", return_value={"provider_id": "shiying", "model": "gemini-3-pro-image-preview"}
    ), patch.object(main, "create_canvas_image_task", submit):
        response = asyncio.run(main.create_pose_replicate_task(task_request()))

    image_payload = submit.await_args.args[0]
    assert image_payload.auto_optimize_prompt is False
    assert image_payload.operation == "pose_replicate"
    assert image_payload.prompt_context["prompt_source"] == "fixed-template"
    assert image_payload.prompt_context["assistant_calls"] == 0
    assert image_payload.prompt_context["output_aspect_ratio"] == "16:9"
    assert [item.role for item in image_payload.reference_images] == [
        "pose_reference",
        "control_map",
        "target_image",
    ]
    assert [item.role_label for item in image_payload.reference_images] == [
        "目标图片",
        "骨架图",
        "服装参考",
    ]
    assert response["pose_replicate"]["assistant_calls"] == 0


def test_user_instruction_endpoint_calls_assistant_once_and_preserves_hard_template():
    normalize = AsyncMock(
        return_value={
            "analysis": {
                "intent_summary": "保持外套敞开",
                "allowed_changes": ["外套门襟保持敞开"],
                "must_preserve": ["保留项链"],
                "material_and_fit": [],
                "scene_adjustments": [],
                "negative_constraints": [],
                "normalized_instruction": "目标外套保持自然敞开，并保留指定身份来源人物的项链。",
            },
            "metadata": {"status": "optimized", "assistant_calls": 1, "optimizer_model": "vision-model"},
        }
    )
    submit = AsyncMock(return_value={"task_id": "canvas_img_test", "status": "queued"})
    with patch.object(main, "normalize_pose_replicate_instruction", normalize), patch.object(
        main, "resolve_image_generation_selection", return_value={"provider_id": "shiying", "model": "gemini-3-pro-image-preview"}
    ), patch.object(main, "create_canvas_image_task", submit):
        response = asyncio.run(
            main.create_pose_replicate_task(
                task_request(instruction="外套保持敞开，保留项链", model=True, scene=True)
            )
        )

    normalize.assert_awaited_once()
    image_payload = submit.await_args.args[0]
    assert image_payload.auto_optimize_prompt is False
    assert "目标外套保持自然敞开" in image_payload.prompt
    assert "用户增量不得改变此优先级" in image_payload.prompt
    assert image_payload.prompt_context["prompt_source"] == "assistant-merged"
    assert response["pose_replicate"]["scenario_id"] == "model-full-look-scene"
    assert response["pose_replicate"]["assistant_calls"] == 1


def test_instruction_normalizer_uses_one_text_only_llm_call():
    raw = {
        "choices": [
            {
                "message": {
                    "content": '{"intent_summary":"保持门襟敞开","allowed_changes":["门襟"],"must_preserve":[],"material_and_fit":[],"scene_adjustments":[],"negative_constraints":[],"normalized_instruction":"目标服装门襟保持自然敞开。"}'
                }
            }
        ]
    }

    async def fake_request(transport, messages, retry_524=1):
        assert transport["web_search"] is False
        assert retry_524 == 1
        assert isinstance(messages[-1]["content"], str)
        return raw

    with patch.object(
        main,
        "configured_image_prompt_optimizer_route",
        return_value={"provider_id": "assistant", "provider_name": "AI助手", "model": "vision-model"},
    ), patch.object(
        main,
        "resolve_chat_transport",
        return_value={"protocol": "chat_completions", "model": "vision-model", "provider": {}},
    ), patch.object(main, "request_llm_json", side_effect=fake_request) as request:
        result = asyncio.run(
            main.normalize_pose_replicate_instruction(
                "外套保持敞开",
                has_model_subject=False,
                has_scene=False,
            )
        )
    assert request.call_count == 1
    assert result["analysis"]["normalized_instruction"] == "目标服装门襟保持自然敞开。"
    assert result["metadata"]["assistant_calls"] == 1


def test_pose_replicate_compiled_prompt_metadata_survives_generation_prepare():
    payload = main.OnlineImageRequest(
        prompt="固定编译提示词",
        provider_id="shiying",
        model="gemini-3-pro-image-preview",
        auto_optimize_prompt=False,
        prompt_context={
            "node_type": "pose-replicate",
            "template_id": POSE_REPLICATE_TEMPLATE_ID,
            "prompt_source": "fixed-template",
            "assistant_calls": 0,
        },
    )
    result = asyncio.run(
        main.prepare_image_generation_prompt(
            payload,
            {"provider_id": "shiying", "model": "gemini-3-pro-image-preview"},
        )
    )
    assert result["metadata"] == {
        "status": "compiled",
        "reference_count": 0,
        "profile_id": "",
        "profile_version": POSE_REPLICATE_TEMPLATE_ID,
        "prompt_source": "fixed-template",
        "assistant_calls": 0,
    }


def test_pose_replicate_size_contract_matches_canvas_defaults():
    assert main.pose_replicate_image_size("16:9", "2k") == "2048x1152"
    assert main.pose_replicate_image_size("4:5", "1k") == "1024x1280"
    assert main.pose_replicate_image_size("4:5", "2k") == "1632x2040"
    assert main.pose_replicate_image_size("4:5", "4k") == "2560x3200"
    with pytest.raises(PoseReplicatePromptError):
        main.pose_replicate_image_size("2:1", "2k")


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ("4000x6000", "3:4"),
        ("4000x5000", "4:5"),
        ("6000x4000", "4:3"),
        ("1920x1080", "16:9"),
        ("1080x1920", "9:16"),
        ("2048x2048", "1:1"),
    ],
)
def test_pose_replicate_auto_ratio_uses_closest_supported_source_ratio(size, expected):
    with patch.object(main, "image_size_from_reference", return_value=size):
        assert main.resolve_pose_replicate_aspect_ratio("source", "/assets/action.png") == expected


def test_pose_replicate_explicit_ratio_does_not_read_source_dimensions():
    with patch.object(main, "image_size_from_reference", side_effect=AssertionError("must not read source")):
        assert main.resolve_pose_replicate_aspect_ratio("3:4", "/assets/action.png") == "3:4"
        assert main.resolve_pose_replicate_aspect_ratio("4:5", "/assets/action.png") == "4:5"


def test_pose_replicate_auto_ratio_is_resolved_before_prompt_and_generation():
    submit = AsyncMock(return_value={"task_id": "canvas_img_test", "status": "queued"})
    with patch.object(main, "image_size_from_reference", return_value="4000x6000"), patch.object(
        main, "resolve_image_generation_selection", return_value={"provider_id": "shiying", "model": "gemini-3-pro-image-preview"}
    ), patch.object(main, "create_canvas_image_task", submit):
        response = asyncio.run(main.create_pose_replicate_task(task_request(aspect_ratio="source")))

    image_payload = submit.await_args.args[0]
    assert image_payload.size == "1536x2048"
    assert image_payload.prompt_context["requested_output_aspect_ratio"] == "source"
    assert image_payload.prompt_context["output_aspect_ratio"] == "3:4"
    assert "最终画布必须为 3:4" in image_payload.prompt
    assert response["pose_replicate"]["requested_output_aspect_ratio"] == "source"
    assert response["pose_replicate"]["output_aspect_ratio"] == "3:4"


def test_pose_replicate_four_by_five_reaches_image_task_unchanged():
    submit = AsyncMock(return_value={"task_id": "canvas_img_4x5", "status": "queued"})
    with patch.object(
        main,
        "resolve_image_generation_selection",
        return_value={"provider_id": "shiying", "model": "gemini-3-pro-image-preview"},
    ), patch.object(main, "create_canvas_image_task", submit):
        response = asyncio.run(main.create_pose_replicate_task(task_request(aspect_ratio="4:5")))

    image_payload = submit.await_args.args[0]
    assert image_payload.size == "1632x2040"
    assert image_payload.prompt_context["requested_output_aspect_ratio"] == "4:5"
    assert image_payload.prompt_context["output_aspect_ratio"] == "4:5"
    assert "最终画布必须为 4:5" in image_payload.prompt
    assert response["pose_replicate"]["output_aspect_ratio"] == "4:5"


def test_gemini_transport_binds_pose_replicate_role_text_to_each_reference_image():
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": []}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, endpoint, *, headers, json):
            captured.update({"endpoint": endpoint, "headers": headers, "body": json})
            return FakeResponse()

    roles = [
        ("pose_reference", "目标图片"),
        ("control_map", "深度图"),
        ("target_image", "服装参考"),
        ("model_subject", "模特主体"),
        ("scene", "场景"),
    ]
    references = [
        {
            "url": f"/assets/input/{index}.png",
            "asset_index": index,
            "role": role,
            "role_label": label,
        }
        for index, (role, label) in enumerate(roles, 1)
    ]
    with patch.object(main.httpx, "AsyncClient", return_value=FakeClient()), patch.object(
        main, "api_headers", return_value={"Authorization": "Bearer test"}
    ), patch.object(
        main, "reference_to_data_url", return_value="data:image/png;base64,aW1hZ2U="
    ), patch.object(main, "extract_image", return_value={"type": "base64", "value": "result"}):
        image, _ = asyncio.run(
            main.generate_gemini_provider_image(
                "固定编译提示词",
                "1536x2048",
                "gemini-3-pro-image-preview",
                references,
                {"id": "shiying", "base_url": "https://example.test"},
            )
        )

    assert image == {"type": "base64", "value": "result"}
    parts = captured["body"]["contents"][0]["parts"]
    assert parts[0] == {"text": "固定编译提示词"}
    assert ["inlineData" in part for part in parts].count(True) == 5
    for index, (_, label) in enumerate(roles, 1):
        role_text = parts[1 + (index - 1) * 2]["text"]
        assert f"图{index}（{label}）" in role_text
        assert "inlineData" in parts[2 + (index - 1) * 2]
    assert "三维几何硬约束" in parts[3]["text"]
    assert "服装褶皱峰谷" in parts[3]["text"]
    assert "不得交换角色" in parts[-1]["text"]
    assert "最终服装只取当前服装参考" in parts[-1]["text"]
    assert "姿势只取目标图片与控制图" in parts[-1]["text"]


def test_gemini_transport_preserves_registered_pose_depth_pair_resolution_and_depth_losslessness():
    calls = []

    def capture(reference, max_size=None, *, lossless=False):
        calls.append((reference["role"], max_size, lossless))
        return "data:image/png;base64,aW1hZ2U="

    with patch.object(main, "reference_to_data_url", side_effect=capture):
        main.gemini_reference_part({"role": "pose_reference", "role_label": "目标图片"})
        main.gemini_reference_part({"role": "control_map", "role_label": "深度图"})
        main.gemini_reference_part({"role": "target_image", "role_label": "服装参考"})

    assert calls == [
        ("pose_reference", 2048, False),
        ("control_map", 2048, True),
        ("target_image", 1536, False),
    ]


def test_gemini_transport_keeps_untyped_references_without_extra_role_text():
    assert main.gemini_reference_role_text({"url": "/assets/input/plain.png"}, 1) == ""
    assert main.gemini_reference_roles_anchor([{"url": "/assets/input/plain.png"}]) == ""


def test_portrait_references_use_output_ratio_without_collage_fallback():
    result = compile_pose_replicate_prompt("depth", output_aspect_ratio="16:9")
    assert result.audit_payload()["output_aspect_ratio"] == "16:9"
    assert "最终画布必须为 16:9" in result.final_prompt
    assert "原图裁切只作为内容取舍参考，不得覆盖最终输出画幅" in result.final_prompt
    assert "第二个人物副本" in result.final_prompt


def test_pose_replicate_rejects_provider_fallback_instead_of_silently_switching():
    submit = AsyncMock(return_value={"task_id": "must-not-run"})
    with patch.object(
        main,
        "resolve_image_generation_selection",
        return_value={"provider_id": "other", "model": "fallback-model"},
    ), patch.object(main, "create_canvas_image_task", submit):
        with pytest.raises(main.HTTPException) as error:
            asyncio.run(main.create_pose_replicate_task(task_request()))
    assert error.value.status_code == 409
    assert "当前不可用" in error.value.detail
    submit.assert_not_awaited()


def test_depth_task_stops_before_assistant_and_generation_when_component_is_not_ready():
    normalize = AsyncMock()
    submit = AsyncMock()
    with patch.object(main.PERSON_DEPTH_COMPONENT_MANAGER, "public_status", return_value={"ready": False}), patch.object(
        main, "normalize_pose_replicate_instruction", normalize
    ), patch.object(main, "create_canvas_image_task", submit):
        with pytest.raises(main.HTTPException) as error:
            asyncio.run(main.create_pose_replicate_task(task_request(mode="depth", instruction="保留项链")))
    assert error.value.status_code == 503
    normalize.assert_not_awaited()
    submit.assert_not_awaited()
