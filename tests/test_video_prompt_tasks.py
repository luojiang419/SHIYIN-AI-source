import asyncio

import pytest

import main
from tests.test_video_prompt_quality import reference_prompt


@pytest.mark.parametrize("kind", ["auto-parse", "polish"])
def test_prompt_task_defaults_skip_search(monkeypatch, kind):
    calls = []

    async def search(_):
        raise AssertionError("默认任务不能进入搜索")

    async def generate(_, progress_callback=None):
        calls.append(kind)
        progress_callback.set_stage("compact", "压缩中")
        await progress_callback("Valid draft")
        return {"text": "Valid prompt"}

    monkeypatch.setattr(main, "_canvas_prompt_web_search", search)
    monkeypatch.setattr(main, "canvas_video_auto_parse", generate)
    monkeypatch.setattr(main, "canvas_prompt_polish", generate)
    monkeypatch.setattr(main, "CANVAS_PROMPT_TASKS", {"test": {"id": "test", "status": "queued"}})
    payload = main.CanvasVideoAutoParseRequest() if kind == "auto-parse" else main.CanvasPromptPolishRequest(prompt="Walk")
    assert payload.web_search is False
    asyncio.run(main._run_canvas_prompt_task("test", kind, payload))
    task = main.CANVAS_PROMPT_TASKS["test"]
    assert calls == [kind] and task["status"] == "succeeded"
    assert [t["stage"] for t in task["stage_timings"]] == ["queued", "visual-parse", "compact"]
    assert task["elapsed_ms"] >= 0


@pytest.mark.parametrize("timeout", [False, True])
def test_optional_search_failure_continues_visual_parse(monkeypatch, timeout):
    async def search(_):
        if timeout:
            await asyncio.sleep(1)
        raise main.HTTPException(status_code=502, detail="search failed")

    async def generate(payload, progress_callback=None):
        assert payload.search_context == ""
        return {"text": "Valid prompt"}

    monkeypatch.setattr(main, "_canvas_prompt_web_search", search)
    monkeypatch.setattr(main, "CANVAS_PROMPT_SEARCH_TIMEOUT", .001)
    monkeypatch.setattr(main, "canvas_video_auto_parse", generate)
    monkeypatch.setattr(main, "CANVAS_PROMPT_TASKS", {"test": {"id": "test", "status": "queued"}})
    payload = main.CanvasVideoAutoParseRequest(web_search=True, search_context="stale")
    asyncio.run(main._run_canvas_prompt_task("test", "auto-parse", payload))
    task = main.CANVAS_PROMPT_TASKS["test"]
    assert task["status"] == "succeeded"
    assert "联网增强未完成" in task["search_warning"]
    assert task["result"]["search_warning"] == task["search_warning"]


def test_optional_search_requires_real_tool_evidence(monkeypatch):
    monkeypatch.setattr(main, "resolve_chat_transport", lambda *_: {"protocol": "responses", "provider": {}})

    async def llm(_):
        return {"text": "An unverified summary", "web_search": {"used": False}}

    monkeypatch.setattr(main, "canvas_llm", llm)
    with pytest.raises(main.HTTPException, match="实际检索记录"):
        asyncio.run(main._canvas_prompt_web_search(main.CanvasVideoAutoParseRequest(provider="test", model="test", web_search=True)))


def test_reference_repair_cannot_bypass_h3_length_validation(monkeypatch):
    calls = []

    async def llm(_):
        calls.append(1)
        return {"text": reference_prompt("<Picture 1> walks." if len(calls) == 1 else
                                         "<Picture 1> and <Picture 2> walk. " + "Long detail. " * 700)}

    monkeypatch.setattr(main, "canvas_llm", llm)
    with pytest.raises(main.HTTPException, match="超过 7000"):
        asyncio.run(main.canvas_video_auto_parse(main.CanvasVideoAutoParseRequest(
            video_provider="minimax-h3", video_model="MiniMax H3", images=["one.png", "two.png"],
        )))
    assert len(calls) == 2


def test_polish_rejects_missing_h3_fields_instead_of_reporting_success(monkeypatch):
    async def llm(_, progress_callback=None):
        return {"text": "subject_definitions:\n<Picture 1> is a woman.\n\ndetailed_description:\nShe walks."}

    monkeypatch.setattr(main, "canvas_llm", llm)
    with pytest.raises(main.HTTPException, match="retention_analysis"):
        asyncio.run(main.canvas_prompt_polish(main.CanvasPromptPolishRequest(
            prompt="A woman walks.", images=["one.png"], video_provider="minimax-h3", video_model="MiniMax H3",
        )))
