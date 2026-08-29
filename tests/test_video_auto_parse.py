from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
CANVAS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
FILM = (ROOT / "static" / "js" / "canvas-film-nodes.js").read_text(encoding="utf-8")
SMART = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def test_backend_auto_parse_is_serial_analysis_case_search_then_skill_generation():
    assert "class CanvasVideoAutoParseRequest" in MAIN
    assert '@app.post("/api/canvas-video-auto-parse")' in MAIN
    endpoint = MAIN[MAIN.index('@app.post("/api/canvas-video-auto-parse")'):]
    assert "analysis_result = await canvas_llm(analysis_request)" in endpoint
    assert "case_context = _video_prompt_case_context(analysis_text)" in endpoint
    assert "final_result = await canvas_llm(final_request)" in endpoint
    assert endpoint.index("analysis_result = await canvas_llm(analysis_request)") < endpoint.index("case_context = _video_prompt_case_context(analysis_text)") < endpoint.index("final_result = await canvas_llm(final_request)")
    assert "严格遵循下方当前模型 skill" in MAIN
    assert "优秀案例经验（仅作方法参考）" in MAIN
    assert "Path(PROJECT_MODULE_DIR) / \"案例\"" in MAIN


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

