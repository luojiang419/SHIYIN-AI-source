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
    assert "（目标图片）" in result.final_prompt
    assert "（服装参考）" in result.final_prompt
    assert "只有一个最终模特主体实例" in result.final_prompt
    if mode == "depth" and not has_model and not has_scene:
        assert "图1（目标图片）提供目标人物照片" in result.final_prompt
        assert "不输出数字标签、拼图或解释" in result.final_prompt
        assert "只替换图3主要目标服装对应的区域" in result.final_prompt
        assert "豹纹" not in result.final_prompt
        return
    if has_scene:
        assert "【参考图分工】" in result.final_prompt
        assert "场景不是背板" in result.final_prompt
        assert "补充要求只修改明确涉及的项目" in result.final_prompt
        assert "只输出一张单镜头、连续彩色照片" in result.final_prompt
        assert "不出现拼图、对照面板、重复主体" in result.final_prompt
        if has_model:
            assert "图1（模特主体）：唯一身份来源" in result.final_prompt
    else:
        assert "【参考图角色：按编号分别使用】" in result.final_prompt
        assert "不是复制参考图拼成新画面" in result.final_prompt
        assert "本次补充要求只覆盖明确涉及的默认项" in result.final_prompt
        assert "只输出一张单镜头、连续的彩色照片" in result.final_prompt
        assert "不输出拼图、分栏、重复模特" in result.final_prompt
        assert "以连续背景扩展或只裁切空余背景适配" in result.final_prompt
        if has_model:
            assert "图1（模特主体）：只提供最终人物身份" in result.final_prompt
            assert "不得把图1当作布局底图" in result.final_prompt
    for sample_specific in ("豹纹上装", "手持眼镜的动作", "原豹纹外套"):
        assert sample_specific not in result.final_prompt


def test_depth_mode_targets_fold_alignment_without_claiming_native_depth_control():
    result = compile_pose_replicate_prompt("depth", output_aspect_ratio="3:4")

    required_depth_targets = (
        "深度图只约束人体轮廓、姿势、遮挡和可靠的大尺度受力起伏",
        "不要求与旧衣逐褶或逐像素一致",
        "图1旧衣的表面像素没有保留权限",
        "微观肌理",
        "不擅自推断纤维成分",
    )
    for rule in required_depth_targets:
        assert rule in result.final_prompt
    assert "【深度几何硬锁：不是构图建议】" not in result.final_prompt
    assert "逐像素配准的三维表面" not in result.final_prompt
    assert "像素级三维几何证据" not in result.final_prompt


def test_base_depth_route_preserves_non_garment_pixels_and_extended_route_maps_geometry():
    base = compile_pose_replicate_prompt("depth")
    extended = compile_pose_replicate_prompt("depth", has_model_subject=True)
    scene = compile_pose_replicate_prompt("depth", has_model_subject=True, has_scene=True)

    assert "完整清除，按图3的新面料重新形成衣片" in base.final_prompt
    assert "保留图1非服装区域" in base.final_prompt
    assert "同画幅沿用图1裁切与主体占比" in base.final_prompt
    assert "随新体型作最小映射，不贴死旧人物的绝对像素" in extended.final_prompt
    assert "必要的主体调整只能整体等比" in extended.final_prompt
    assert "随新体型作最小映射，再按场景镜头呈现" in scene.final_prompt
    assert "允许重绘人物的光照、透视和边缘" in scene.final_prompt


@pytest.mark.parametrize("mode", ["depth", "skeleton"])
@pytest.mark.parametrize("has_model", [False, True])
def test_v31_scene_routes_rebuild_camera_lighting_contact_and_imaging(mode, has_model):
    result = compile_pose_replicate_prompt(mode, has_model_subject=has_model, has_scene=True)

    for rule in (
        "场景不是背板",
        "最终空间与摄影条件的主参考",
        "【先确定场景中的相机和人物位置】",
        "【全主体重打光：脸、头发、身体、服装、配饰一起处理】",
        "【接触、投影、遮挡与环境反馈】",
        "【统一摄影成像与边缘】",
        "不能保留旧图视角再将场景当背板",
        "【输出前场景融合检查】",
    ):
        assert rule in result.final_prompt


def test_skeleton_mode_does_not_claim_depth_surface_or_fold_geometry():
    result = compile_pose_replicate_prompt("skeleton")

    assert "不提供表面深度、衣物体积或褶皱" in result.final_prompt
    assert "【褶皱参考：来自目标原图，不来自骨架】" in result.final_prompt
    assert "不宣称骨架能提供精确深度" in result.final_prompt
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
    submit.assert_awaited_once()
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
    assert "补充要求只修改明确涉及的项目" in image_payload.prompt
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
    assert "输出画幅为 3:4" in image_payload.prompt
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
    assert "输出画幅为 4:5" in image_payload.prompt
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
        ("target_image", None, True),
    ]


@pytest.mark.parametrize("image_format", ["PNG", "JPEG"])
def test_gemini_garment_transport_keeps_fine_color_pixels_without_jpeg_or_downsampling(tmp_path, image_format):
    import base64
    from io import BytesIO
    from PIL import Image

    original = Image.frombytes("RGB", (256, 5000), bytes([70, 56, 55, 187, 179, 184]) * (256 * 5000 // 2))
    path = tmp_path / ("fine-fabric.png" if image_format == "PNG" else "fine-fabric.jpg")
    original.save(path, format=image_format)
    with Image.open(path) as decoded:
        expected_pixels = decoded.convert("RGB").tobytes()
    with patch.object(main, "output_file_from_url", return_value=str(path)):
        part = main.gemini_reference_part({"url": "/assets/fine-fabric.png", "role": "target_image", "role_label": "服装参考"})
    assert part["inlineData"]["mimeType"] == "image/png"
    with Image.open(BytesIO(base64.b64decode(part["inlineData"]["data"]))) as actual:
        assert actual.size == original.size
        assert actual.tobytes() == expected_pixels


def test_gemini_transport_keeps_untyped_references_without_extra_role_text():
    assert main.gemini_reference_role_text({"url": "/assets/input/plain.png"}, 1) == ""
    assert main.gemini_reference_roles_anchor([{"url": "/assets/input/plain.png"}]) == ""


def test_portrait_references_use_output_ratio_without_collage_fallback():
    result = compile_pose_replicate_prompt("depth", output_aspect_ratio="16:9")
    assert result.audit_payload()["output_aspect_ratio"] == "16:9"
    assert "输出画幅为 16:9" in result.final_prompt
    assert "不同时优先保持完整可见动作与主体比例" in result.final_prompt
    assert "不输出数字标签、拼图或解释" in result.final_prompt


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


@pytest.mark.parametrize("mode", ["depth", "skeleton"])
@pytest.mark.parametrize("has_model", [False, True])
@pytest.mark.parametrize("has_scene", [False, True])
def test_garment_fidelity_owns_structure_material_and_pattern(mode, has_model, has_scene):
    result = compile_pose_replicate_prompt(mode, has_model_subject=has_model, has_scene=has_scene)
    garment = next(item["index"] for item in result.reference_order if item["role"] == "target_image")
    if mode == "depth" and not has_model and not has_scene:
        for rule in ("只取图3", "微观肌理", "无翻领时不新增领片", "扣式门襟不改成拉链", "不能共享旧衣表面"):
            assert rule in result.final_prompt
        assert "豹纹" not in result.final_prompt
        return
    assert f"图{garment}是待换衣物结构、面料和纹样的唯一来源" in result.final_prompt
    assert result.final_prompt.count("【服装保真：先识别再替换】") == 1
    for rule in ("参考无翻领就不得新增翻领", "扣式门襟不得改成拉链", "相对衣片的大小、密度、间距", "绒毛/毛羽", "禁止混合两图印花"):
        assert rule in result.final_prompt
    for conflict in ("默认以最大限度逐褶复刻", "先匹配衣片起伏，再", "动作褶皱的布局与峰谷关系优先于自由整理面料"):
        assert conflict not in result.final_prompt


@pytest.mark.parametrize("mode", ["depth", "skeleton"])
@pytest.mark.parametrize("has_model", [False, True])
@pytest.mark.parametrize("has_scene", [False, True])
def test_color_fidelity_keeps_garment_palette_above_scene_grading(mode, has_model, has_scene):
    result = compile_pose_replicate_prompt(mode, has_model_subject=has_model, has_scene=has_scene)
    garment = next(item["index"] for item in result.reference_order if item["role"] == "target_image")
    if mode == "depth" and not has_model and not has_scene:
        for rule in ("配色同样只取图3", "不混入图1旧衣配色", "不以校色为理由冻结旧衣织纹", "暖色也不强行灰化"):
            assert rule in result.final_prompt
        return
    assert f"图{garment}服装参考是新衣配色的唯一来源" in result.final_prompt
    assert result.final_prompt.count("【商品配色还原：先建立色彩基准，再完成一次成片】") == 1
    for rule in ("面料底色、每一组印花或织纹色", "作为底色和纹样色各自的基准", "优先于目标照片的整体调色风格", "参考本来是暖色、鲜艳色或高反差时也不强行灰化", "纹理正确但配色不同仍不合格", "配色接近但纹样变大、材质改变或多出领片也不合格", "在一次生成的最终成片中同时满足"):
        assert rule in result.final_prompt
    assert "人物和场景服从同一套白平衡" not in result.final_prompt
    assert "不能为保留源图RGB数值而拒绝重打光" not in result.final_prompt
