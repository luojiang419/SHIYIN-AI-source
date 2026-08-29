from pathlib import Path
import asyncio

import main
from main import _video_auto_parse_system_prompt, clean_video_prompt_output


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
CANVAS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
FILM = (ROOT / "static" / "js" / "canvas-film-nodes.js").read_text(encoding="utf-8")
SMART = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def test_backend_auto_parse_uses_one_ordered_multimodal_request_with_skill_and_cases():
    assert "class CanvasVideoAutoParseRequest" in MAIN
    assert '@app.post("/api/canvas-video-auto-parse")' in MAIN
    endpoint = MAIN[MAIN.index('@app.post("/api/canvas-video-auto-parse")'):MAIN.index('@app.post("/api/canvas-llm")')]
    assert "result = await canvas_llm(request)" in endpoint
    assert endpoint.count("await canvas_llm(") == 1
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

    h3 = _video_auto_parse_system_prompt("minimax-h3", "MiniMax H3", "mapping", duration=6)
    assert "当前视频模型必须执行的 skill（minimax-h3）" in h3
    assert "subject_definitions" in h3
    assert "integrated_multimodal_description" in h3


def test_classic_video_button_switches_to_auto_parse_for_images_without_prompt():
    assert "data-video-prompt-mode" in CANVAS
    assert "自动解析" in CANVAS
    assert "connectedMedia.every(kind => kind === 'image')" in CANVAS
    assert "autoParseCanvasVideoPrompt" in CANVAS
    assert "fetch('/api/canvas-video-auto-parse'" in CANVAS
    assert "mode === 'auto-parse'" in CANVAS


def test_film_video_and_smart_canvas_use_ordered_auto_parse_flow():
    assert "data-film-prompt-mode" in FILM
    assert "autoParseVideoPrompt" in FILM
    assert "options.promptConnected?.(node)" in FILM
    assert "images:refs.map(item=>item.url)" in FILM
    assert "promptConnected:target =>" in SMART
    assert "polishPrompt:(changed,prompt,assets)" in SMART


def test_auto_parse_forwards_node_prompt_and_requires_all_reference_images():
    assert "const prompt = String(node?.prompt || '').trim();" in CANVAS
    assert "prompt, images, image_labels:labels" in CANVAS
    assert "提示词解析必须看到 output/group 中连接的全部图片" in CANVAS
    assert "mediaRefsFromNode(source)" in CANVAS
    assert "prompt:String(node.prompt || '').trim()," in FILM
    assert "images:refs.map(item=>item.url)" in FILM
    assert "必须逐张检查并在最终提示词中实际使用本次收到的每一张图片" in MAIN
    assert "不能只使用第一张和最后一张" in MAIN
    assert "逐张建立图片使用清单" in MAIN
    assert "参考图载入不完整" in MAIN
    assert '"used_images": min(len(image_inputs), 20)' in MAIN


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
