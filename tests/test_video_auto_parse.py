from pathlib import Path

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
    assert "message=user_prompt or" in endpoint
    assert "严格遵循下方当前模型 skill" in MAIN
    assert "全部图片已经按用户输入顺序一次性上传" in MAIN
    assert "请先使用模型可用的联网搜索工具检索优秀的视频提示词" in MAIN
    assert 'body["tools"] = [{"type": "web_search"}]' in MAIN
    assert "用户没有提供文字提示词。请启动自主导演模式" in endpoint


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
