from pathlib import Path
import asyncio

import main
from main import (
    _video_auto_parse_system_prompt,
    clean_video_prompt_output,
    video_prompt_limit,
    video_prompt_limit_rule,
    validate_video_prompt_for_model,
    video_prompt_polish_system_prompt,
    video_prompt_reference_coverage,
)


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
CANVAS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
FILM = (ROOT / "static" / "js" / "canvas-film-nodes.js").read_text(encoding="utf-8")
SMART = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def test_backend_auto_parse_uses_ordered_multimodal_request_and_never_compacts_rules():
    assert "class CanvasVideoAutoParseRequest" in MAIN
    assert '@app.post("/api/canvas-video-auto-parse")' in MAIN
    endpoint = MAIN[MAIN.index('@app.post("/api/canvas-video-auto-parse")'):MAIN.index('@app.post("/api/canvas-llm")')]
    assert "result = await canvas_llm(request)" in endpoint
    assert endpoint.count("await canvas_llm(") == 1
    assert "retry_524=2" in endpoint
    assert "始终使用完整版导演规则" in endpoint
    assert "_video_compact_fallback_system_prompt" not in MAIN
    assert "images=images" in endpoint
    assert "message=user_message" in endpoint
    assert "严格遵循下方当前模型 skill" in MAIN
    assert "全部图片已经按用户输入顺序一次性上传" in MAIN
    assert "请先使用模型可用的联网搜索工具检索优秀的视频提示词" in MAIN
    assert 'body["tools"] = [{"type": "web_search"}]' in MAIN
    assert "用户没有提供文字提示词。请启动自主导演模式" in endpoint
    assert "raw_user_prompt = str(payload.prompt or \"\").strip()" in endpoint
    assert "message=user_message" in endpoint
    assert '"image_count": len(images)' in endpoint


def test_auto_parse_system_prompt_injects_selected_video_skill_content():
    kling = _video_auto_parse_system_prompt(
        "kling-cli", "kling-v3-omni", "mapping", duration=8, aspect_ratio="16:9", resolution="1080p"
    )
    assert "当前视频模型必须执行的 skill（kling-cli）" in kling
    assert "Latest official Omni reference syntax" in kling
    assert "<<<element_1>>>" in kling
    assert "自主导演模式" in kling
    assert "禁止输出或追加与镜头无关的泛化质量标签" in kling
    assert "多主体不要同步机械重复同一动作" in kling
    assert "禁止默认静止镜头" in kling
    assert "运动最终揭示的信息" in kling
    assert "脚步有接地、摩擦和重量转移" in kling

    h3 = _video_auto_parse_system_prompt("minimax-h3", "MiniMax H3", "mapping", duration=6)
    assert "当前视频模型必须执行的 skill（minimax-h3）" in h3
    assert "subject_definitions" in h3
    assert "integrated_multimodal_description" in h3
    assert "开场、发展、变化或揭示、收束" in h3


def test_prompt_polish_injects_director_rules_without_overriding_user_intent():
    prompt = video_prompt_polish_system_prompt(
        "minimax-h3", "MiniMax H3", text_to_video=False, reference_context="mapping"
    )
    assert "用户原意优先" in prompt
    assert "用户明确写出的故事、动作、情绪、镜头与否定要求是不可覆盖的主线" in prompt
    assert "人物要有眼神先行" in prompt
    assert "动物或拟动物" in prompt
    assert "不得预设牛仔裤、牧场、动物或任何示例主体" in prompt
    assert "每个镜头只承载一个主动作和一个主导运镜" in prompt


def test_classic_video_button_switches_to_auto_parse_for_images_without_prompt():
    assert "data-video-prompt-mode" in CANVAS
    assert "自动解析" in CANVAS
    assert "connectedMedia.every(kind => kind === 'image')" in CANVAS
    assert "autoParseCanvasVideoPrompt" in CANVAS
    assert "'/api/canvas-video-auto-parse-tasks'" in CANVAS
    assert "mode === 'auto-parse'" in CANVAS


def test_prompt_task_stream_progress_is_rendered_and_final_result_can_overwrite_draft():
    assert "progress_text" in MAIN
    assert "progress_status" in MAIN
    assert "on_text_delta=on_text_delta" in MAIN
    assert "renderCanvasPromptTaskProgress" in CANVAS
    assert "onProgress?.(task)" in CANVAS
    assert "progress_text" in FILM
    assert "onProgress" in SMART


def test_film_video_and_smart_canvas_use_ordered_auto_parse_flow():
    assert "data-film-prompt-mode" in FILM
    assert "autoParseVideoPrompt" in FILM
    assert "options.promptConnected?.(node)" in FILM
    assert "images:refs.map(item=>item.url)" in FILM
    assert "promptConnected:target =>" in SMART
    assert "polishPrompt:(changed,prompt,assets)" in SMART
    assert "{role:'prompt',label:'提示词'" in FILM
    assert "promptText:target => connectedCanvasPromptText(target)" in CANVAS
    assert "promptText:target => smartFilmConnectedPromptText(target)" in SMART


def test_auto_parse_forwards_node_prompt_and_requires_all_reference_images():
    assert "connectedCanvasPromptText(node)" in CANVAS
    assert "prompt, images, image_labels:labels" in CANVAS
    assert "提示词解析必须看到 output/group 中连接的全部图片" in CANVAS
    assert "mediaRefsFromNode(source)" in CANVAS
    assert "prompt:effectivePrompt(node, options)," in FILM
    assert "images:refs.map(item=>item.url)" in FILM
    assert "必须逐张检查并在最终提示词中实际使用本次收到的每一张图片" in MAIN
    assert "不能只使用第一张和最后一张" in MAIN
    assert "逐张建立图片使用清单" in MAIN
    assert "参考图载入不完整" in MAIN
    assert '"used_images": min(len(image_inputs), 20)' in MAIN
    assert "video_prompt_reference_coverage" in MAIN
    assert "系统不会静默交付不完整引用" in MAIN
    assert "duration:Number(node.duration || 0) || null" in FILM
    assert "duration:Number(node?.duration || 0) || null" in CANVAS
    assert "duration:Number(node?.duration || node?.runSettings?.videoDuration || 0) || null" in SMART
    assert "目标视频总时长为" in FILM
    assert "class CanvasPromptPolishRequest" in MAIN
    assert "duration: Optional[float] = None" in MAIN
    assert "本次视频节点控制参数（仅供内部规划，不得原样输出）" in MAIN
    assert "最终提示词不得出现视频模型名称、时长数值、画幅、分辨率" in MAIN


def test_empty_prompt_rechecks_auto_parse_mode_at_click_time():
    # 按钮的 data 属性来自上一次渲染，连接关系变化后可能短暂过期；
    # 点击时必须依据当前输入和参考图再次选择自动解析。
    assert "const currentPrompt = [String(original || node.prompt || '').trim(), connectedCanvasPromptText(node)]" in CANVAS
    assert "const autoParseNow = !currentPrompt && imageRefs.length > 0" in CANVAS
    assert "const mode = autoParseNow ? 'auto-parse'" in CANVAS
    assert "const currentPrompt=[String(prompt.value || '').trim(), externalPromptText(node, options)]" in FILM
    assert "const autoParseNow=!currentPrompt && currentImageRefs.length>0" in FILM
    assert "const mode=autoParseNow ? 'auto-parse'" in FILM


def test_auto_parse_endpoint_keeps_four_images_and_story_prompt_together(monkeypatch):
    captured = {}

    async def fake_canvas_llm(request):
        captured["request"] = request
        return {"text": "<Picture 1> <Picture 2> <Picture 3> <Picture 4>"}

    monkeypatch.setattr(main, "canvas_llm", fake_canvas_llm)
    payload = main.CanvasVideoAutoParseRequest(
        prompt="四条牛仔裤在黄昏草原上依次站起，镜头从远景推进到腰头细节。",
        images=["https://example.test/1.png", "https://example.test/2.png", "https://example.test/3.png", "https://example.test/4.png"],
        image_labels=["图1场景", "图2动作", "图3材质", "图4细节"],
        video_provider="minimax-h3",
        video_model="MiniMax H3",
    )
    result = asyncio.run(main.canvas_video_auto_parse(payload))
    request = captured["request"]
    assert request.images == payload.images
    assert request.image_labels == ["<Picture 1>；用户口语图1/图片1；图1场景", "<Picture 2>；用户口语图2/图片2；图2动作", "<Picture 3>；用户口语图3/图片3；图3材质", "<Picture 4>；用户口语图4/图片4；图4细节"]
    assert "牛仔裤" in request.message
    assert "所有图片标签" in request.message
    assert result["image_count"] == 4
    assert result["reference_coverage"]["complete"] is True


def test_reference_coverage_uses_current_model_tags():
    h3 = video_prompt_reference_coverage("<Picture 1> then <Picture 3>", "minimax-h3", 3)
    assert h3["found"] == ["<Picture 1>", "<Picture 3>"]
    assert h3["missing"] == ["<Picture 2>"]
    assert h3["complete"] is False

    kling = video_prompt_reference_coverage(
        "<<<image_1>>> and <<<image_2>>>", "kling-cli", 2
    )
    assert kling["complete"] is True


def test_auto_parse_rejects_missing_reference_tags(monkeypatch):
    async def fake_canvas_llm(_request):
        return {"text": "<Picture 1> and <Picture 3> are used in a moving camera shot."}

    monkeypatch.setattr(main, "canvas_llm", fake_canvas_llm)
    payload = main.CanvasVideoAutoParseRequest(
        images=[
            "https://example.test/1.png",
            "https://example.test/2.png",
            "https://example.test/3.png",
        ],
        video_provider="minimax-h3",
        video_model="MiniMax H3",
    )
    try:
        asyncio.run(main.canvas_video_auto_parse(payload))
    except main.HTTPException as exc:
        assert exc.status_code == 422
        assert "<Picture 2>" in str(exc.detail)
    else:
        raise AssertionError("缺少图片标签时必须拒绝交付")


def test_no_prompt_auto_parse_requests_continuous_action_acting_and_moving_camera(monkeypatch):
    captured = {}

    async def fake_canvas_llm(request):
        captured["request"] = request
        return {"text": "<Picture 1> becomes <Subject 1>; the camera tracks its grounded movement."}

    monkeypatch.setattr(main, "canvas_llm", fake_canvas_llm)
    payload = main.CanvasVideoAutoParseRequest(
        prompt="",
        images=["https://example.test/1.png"],
        video_provider="minimax-h3",
        video_model="MiniMax H3",
        duration=6,
    )
    result = asyncio.run(main.canvas_video_auto_parse(payload))
    request = captured["request"]
    assert "先识别画面中可连续延展的主体行为" in request.message
    assert "人物、动物、拟人化物体" in request.message
    assert "错峰反应、环境反馈和重量感" in request.message
    assert "不是固定机位的自然运镜" in request.message
    assert result["reference_coverage"]["complete"] is True


def test_auto_parse_requires_temporal_action_choreography_and_causal_camera_response():
    system = _video_auto_parse_system_prompt("minimax-h3", "MiniMax H3", "mapping", duration=13)
    assert "每个镜头至少包含 3 个连续微节拍" in system
    assert "准备/蓄势" in system
    assert "启动与加速/减速" in system
    assert "互动、碰撞或空间关系变化" in system
    assert "反应与收束" in system
    assert "触发者" in system
    assert "镜头不能只写‘轻微跟随/静态保持/展示动态’" in system
    assert "H3 Ref2VA 生成任务的 detailed_description 通常写 350-500 个英文词" in system


def test_no_prompt_message_explicitly_requests_three_action_beats(monkeypatch):
    captured = {}

    async def fake_canvas_llm(request):
        captured["request"] = request
        return {"text": "<Picture 1> <Subject 1> moves with preparation, interaction, and settle beats."}

    monkeypatch.setattr(main, "canvas_llm", fake_canvas_llm)
    payload = main.CanvasVideoAutoParseRequest(
        prompt="",
        images=["https://example.test/1.png"],
        video_provider="minimax-h3",
        video_model="MiniMax H3",
        duration=6,
    )
    asyncio.run(main.canvas_video_auto_parse(payload))
    assert "每个镜头至少写出准备、执行/互动、反应/收束三个连续节拍" in captured["request"].message


def test_no_prompt_message_preserves_image_order_as_story_timeline(monkeypatch):
    captured = {}

    async def fake_canvas_llm(request):
        captured["request"] = request
        return {"text": "<Picture 1> then <Picture 2> then <Picture 3> in a continuous sequence."}

    monkeypatch.setattr(main, "canvas_llm", fake_canvas_llm)
    payload = main.CanvasVideoAutoParseRequest(
        images=[
            "https://example.test/1.png",
            "https://example.test/2.png",
            "https://example.test/3.png",
        ],
        video_provider="minimax-h3",
        video_model="MiniMax H3",
    )
    asyncio.run(main.canvas_video_auto_parse(payload))
    assert "图片顺序就是用户希望保留的叙事/时间顺序" in captured["request"].message
    assert "第 1 张作为开场视觉锚点" in captured["request"].message


def test_auto_parse_repairs_missing_reference_tags_once(monkeypatch):
    calls = []

    async def fake_canvas_llm(request):
        calls.append(request)
        if len(calls) == 1:
            return {"text": "<Picture 1> A continuous moving shot."}
        return {"text": "<Picture 1> and <Picture 2> A continuous moving shot."}

    monkeypatch.setattr(main, "canvas_llm", fake_canvas_llm)
    payload = main.CanvasVideoAutoParseRequest(
        images=["https://example.test/1.png", "https://example.test/2.png"],
        video_provider="minimax-h3",
        video_model="MiniMax H3",
    )
    result = asyncio.run(main.canvas_video_auto_parse(payload))
    assert len(calls) == 2
    assert result["reference_coverage"]["complete"] is True


def test_director_rules_are_content_driven_not_case_template_driven():
    system = _video_auto_parse_system_prompt("kling-cli", "kling-v3-omni", "mapping")
    assert "这是内容无关的导演决策" in system
    assert "先识别当前参考图与用户描述的真实语境" in system
    assert "没有充分视觉或叙事依据时，宁可保持克制" in system
    assert "不得预设牛仔裤、牧场、动物或任何示例主体" in system


def test_video_prompt_output_removes_generic_quality_suffix_without_touching_scene_text():
    raw = (
        "A cinematic sequence in a desert at sunset. The camera pushes in toward the subject. "
        "Photorealistic, 8k resolution."
    )
    cleaned = clean_video_prompt_output(raw)
    assert cleaned == "A cinematic sequence in a desert at sunset. The camera pushes in toward the subject."
    assert "Photorealistic" not in cleaned
    assert "8k resolution" not in cleaned

    detailed = "Photorealistic denim jacket with visible stitching; the actor turns left."
    assert clean_video_prompt_output(detailed) == detailed


def test_video_prompt_output_keeps_reference_tags_when_cleaning_quality_terms():
    raw = "Shot 1: <<<image_1>>> remains still, then the camera tilts down, photorealistic, 8k."
    cleaned = clean_video_prompt_output(raw)
    assert "<<<image_1>>>" in cleaned
    assert "photorealistic" not in cleaned.lower()
    assert "8k" not in cleaned.lower()


def test_video_prompt_limits_are_model_specific_and_no_longer_fixed_at_4000():
    assert video_prompt_limit("minimax-h3", "MiniMax H3") == 7000
    assert video_prompt_limit("kling-cli", "kling-v3-omni") == 2500
    assert video_prompt_limit("comfly", "veo3-fast") == 20000
    assert "7000 个字符" in video_prompt_limit_rule("minimax-h3", "MiniMax H3")
    assert "2500 个字符" in video_prompt_limit_rule("kling-cli", "kling-v3-omni")
    assert 'VIDEO_PROMPT_MAX_LENGTH = int(os.getenv("VIDEO_PROMPT_MAX_LENGTH", "4000"))' not in MAIN
    # H3 的合法 4000～7000 字符提示词应能通过统一请求体模型。
    h3_request = main.CanvasVideoRequest(prompt="x" * 5000, provider_id="minimax-h3", model="MiniMax H3")
    assert validate_video_prompt_for_model(h3_request) == 7000
    try:
        validate_video_prompt_for_model(
            main.CanvasVideoRequest(prompt="x" * 2501, provider_id="kling-cli", model="kling-v3-omni")
        )
    except main.HTTPException as exc:
        assert exc.status_code == 422
        assert "不能超过 2500 个字符" in str(exc.detail)
    else:
        raise AssertionError("Kling 超限必须返回模型级限长错误")


def test_overlong_auto_parse_is_compacted_to_h3_limit(monkeypatch):
    calls = []

    async def fake_canvas_llm(request, progress_callback=None):
        calls.append(request)
        if len(calls) == 1:
            return {"text": "<Picture 1> " + ("重复细节 " * 1400)}
        return {"text": "<Picture 1> A concise moving shot with a clear action beat."}

    monkeypatch.setattr(main, "canvas_llm", fake_canvas_llm)
    payload = main.CanvasVideoAutoParseRequest(
        images=["https://example.test/1.png"],
        video_provider="minimax-h3",
        video_model="MiniMax H3",
    )
    result = asyncio.run(main.canvas_video_auto_parse(payload))
    assert len(calls) == 2
    assert result["prompt_compacted"] is True
    assert result["prompt_limit"] == 7000
    assert result["prompt_chars"] <= 7000
    assert result["reference_coverage"]["complete"] is True
