import asyncio
from unittest.mock import patch
from pathlib import Path

import main


ROOT = Path(__file__).resolve().parent.parent


def test_image_prompt_profile_matches_known_families_and_falls_back():
    assert main.image_prompt_profile("grsai", "gpt-image-2")["id"] == "nano-banana-gemini-image"
    assert main.image_prompt_profile("shiying", "gemini-3-pro-image-preview")["id"] == "nano-banana-gemini-image"
    assert main.image_prompt_profile("volcengine", "doubao-seedream-5")["id"] == "nano-banana-gemini-image"
    assert main.image_prompt_profile("custom", "unknown-model")["id"] == "nano-banana-gemini-image"


def test_image_prompt_compiler_preserves_original_and_all_reference_order():
    result = main.compile_image_prompt(
        "女人穿着牛仔裤，顶级时尚大片",
        {
            "intent_summary": "高端时尚编辑大片，而非电商白底图",
            "subject": ["成年女性模特，穿着牛仔裤"],
            "environment": "城市建筑与硬朗光影",
            "composition": "全身构图，低机位，留出编辑版面空间",
            "style_context": "高端 denim campaign 的造型叙事",
            "reference_map": [
                {"role": "人物身份"},
                {"role": "牛仔裤材质与版型"},
            ],
        },
        [
            {"url": "/assets/model.png", "name": "人物参考"},
            {"url": "/assets/jeans.png", "name": "服装参考"},
        ],
        main.image_prompt_profile("grsai", "gpt-image-2"),
    )
    assert "女人穿着牛仔裤，顶级时尚大片" in result
    assert "参考图 1（人物参考）" in result
    assert "参考图 2（服装参考）" in result
    assert result.index("参考图 1") < result.index("参考图 2")
    assert "电商白底图" in result


def test_optimizer_uses_assistant_multimodal_request_and_returns_compiled_prompt():
    raw = {
        "choices": [{
            "message": {
                "content": '{"intent_summary":"厨房内的高压锅压力爆炸","subject":["高压锅、蒸汽和飞散碎片"],"environment":"家庭厨房","composition":"中近景，爆炸向画面外扩散","reference_map":[{"role":"锅具外形"}]}',
            }
        }]
    }

    async def fake_request(transport, messages, retry_524=2, on_text_delta=None):
        assert transport["model"] == "vision-model"
        assert transport["web_search"] is False
        content = messages[-1]["content"]
        assert any(item.get("type") == "image_url" for item in content)
        return raw

    with patch.object(main, "configured_image_prompt_optimizer_route", return_value={
        "provider_id": "ecommerce-vision",
        "provider_name": "AI助手",
        "model": "vision-model",
    }), patch.object(main, "resolve_chat_transport", return_value={
        "provider": {"id": "ecommerce-vision"},
        "protocol": "chat_completions",
        "model": "vision-model",
        "url": "http://127.0.0.1/v1/chat/completions",
        "headers": {},
    }), patch.object(main, "reference_to_data_url", return_value="data:image/png;base64,abc"), patch.object(main, "request_llm_json", side_effect=fake_request):
        result = asyncio.run(main.optimize_image_prompt(
            "一个高压锅爆炸了",
            "grsai",
            "gpt-image-2",
            [{"url": "/assets/cooker.png", "name": "厨房参考", "kind": "image"}],
        ))

    assert result["metadata"]["status"] == "optimized"
    assert result["metadata"]["reference_analysis_count"] == 1
    assert "用户原始要求：一个高压锅爆炸了" in result["prompt"]
    assert "家庭厨房" in result["prompt"]


def test_optimizer_falls_back_without_assistant_route():
    with patch.object(main, "configured_image_prompt_optimizer_route", return_value=None):
        result = asyncio.run(main.optimize_image_prompt("原始提示词", "custom", "unknown", []))

    assert result["prompt"] == "原始提示词"
    assert result["metadata"]["status"] == "fallback"
    assert result["metadata"]["error"] == "没有可用的 AI助手聊天/视觉模型"


def test_canvas_prepare_stops_before_image_api_when_optimizer_is_unavailable():
    payload = main.OnlineImageRequest(
        prompt="背景更换为森林，氛围调整为傍晚下雨，需要完美匹配氛围",
        provider_id="grsai",
        model="nano-banana-pro",
        auto_optimize_prompt=True,
    )
    with patch.object(main, "optimize_image_prompt", return_value={
        "prompt": payload.prompt,
        "original_prompt": payload.prompt,
        "metadata": {"status": "fallback", "error": "没有可用的 AI助手聊天/视觉模型"},
    }):
        try:
            asyncio.run(main.prepare_image_generation_prompt(payload, {"provider_id": "grsai", "model": "nano-banana-pro"}))
        except main.HTTPException as exc:
            assert exc.status_code == 424
            assert "停止提交原始提示词" in exc.detail
        else:
            raise AssertionError("expected mandatory optimization failure")


def test_build_image_result_passes_compiled_prompt_to_image_adapter():
    captured = {}

    async def fake_execute(**kwargs):
        captured["prompt"] = kwargs["prompt"]
        return {
            "provider": {"id": "grsai", "name": "Grsai"},
            "model": "nano-banana-pro",
            "references": [],
            "raw": {},
            "images": ["/output/generated.png"],
            "image_items": [{"url": "/output/generated.png"}],
            "count": 1,
            "generation_started_at": 1.0,
            "generation_completed_at": 2.0,
            "generation_elapsed_seconds": 1.0,
        }

    payload = main.OnlineImageRequest(
        prompt="背景更换为森林，氛围调整为傍晚下雨，需要完美匹配氛围",
        provider_id="grsai",
        model="nano-banana-pro",
        auto_optimize_prompt=True,
    )
    optimized = "用户原始要求：背景更换为森林\n场景与环境：傍晚雨林氛围"
    with patch.object(main, "prepare_image_generation_prompt", return_value={
        "prompt": optimized,
        "original_prompt": payload.prompt,
        "metadata": {"status": "optimized", "profile_id": "nano-banana-gemini-image"},
    }), patch.object(main, "resolve_image_generation_selection", return_value={
        "provider_id": "grsai", "model": "nano-banana-pro"
    }), patch.object(main, "execute_ai_image_batch", side_effect=fake_execute), patch.object(main, "save_to_history"), patch.object(main, "GLOBAL_LOOP", None):
        result = asyncio.run(main.build_online_image_result(payload))

    assert captured["prompt"] == optimized
    assert result["prompt"] == optimized
    assert result["prompt_original"] == payload.prompt
    assert result["prompt_optimization"]["status"] == "optimized"


def test_image_request_snapshot_keeps_optimization_settings_without_secrets():
    payload = main.OnlineImageRequest(
        prompt="测试",
        provider_id="grsai",
        model="gpt-image-2",
        auto_optimize_prompt=True,
        optimizer_provider_id="ecommerce-vision",
        optimizer_model="vision-model",
        prompt_context={"node_type": "image"},
    )
    snapshot = main.online_image_request_snapshot(payload)
    assert snapshot["auto_optimize_prompt"] is True
    assert snapshot["optimizer_provider_id"] == "ecommerce-vision"
    assert snapshot["prompt_context"] == {"node_type": "image"}
    assert "api_key" not in snapshot


def test_canvas_generators_enable_automatic_optimization():
    classic = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
    smart = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
    assert classic.count("auto_optimize_prompt:true") >= 12
    for node_type in (
        "panorama",
        "special-image-edit",
        "pose-replicate",
        "building-multi-view",
        "multi-view",
        "film-storyboard",
        "film-line-art",
        "storyboard-transform",
    ):
        assert f"node_type:'{node_type}'" in classic
    assert "auto_optimize_prompt:true" in smart
    assert "auto_optimize_prompt:runSettings.autoOptimizePrompt !== false" not in smart
    assert "prompt_context:{node_type:'smart-image'" in smart
    assert "prompt_optimized: result.prompt || ''" in classic
    assert "prompt_optimization: result.prompt_optimization" in classic


def test_modelscope_direct_generation_calls_shared_optimizer_endpoint():
    smart = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
    run_start = smart.index("async function runModelscopeGeneration")
    run_end = smart.index("async function urlToBase64", run_start)
    body = smart[run_start:run_end]
    assert "optimizeSmartModelscopePrompt(prompt, refs, runSettings, modelId)" in body
    assert "fetch('/api/image-prompt-optimize'" in body
    assert "已停止提交原始提示词" in body
    assert "autoOptimizePrompt === false" not in body


def test_image_request_defaults_to_mandatory_optimization():
    payload = main.OnlineImageRequest(prompt="测试默认优化", provider_id="grsai", model="nano-banana-pro")
    assert payload.auto_optimize_prompt is True


def test_installer_and_browser_smoke_package_image_prompt_skill():
    installer = (ROOT / "tools" / "build-installer.ps1").read_text(encoding="utf-8")
    smoke = (ROOT / "tools" / "browser-smoke-server.ps1").read_text(encoding="utf-8")
    assert "app\\skills\\image-prompt-polish\\SKILL.md" in installer
    assert "app\\skills\\image-prompt-polish\\registry.json" in installer
    assert "skills\\image-prompt-polish')" in installer
    assert "skills\\image-prompt-polish\"))" in smoke
