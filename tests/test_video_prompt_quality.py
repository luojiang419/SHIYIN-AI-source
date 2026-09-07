import asyncio

import pytest

from canvas_core.video_prompt_quality import (
    H3_BASE_FIELDS, H3_REFERENCE_FIELDS, compact_h3_prompt, parse_h3_prompt, render_h3_prompt,
)


def reference_prompt(description="<Picture 1> follows <Subject 1> walking left."):
    return render_h3_prompt(dict(zip(H3_REFERENCE_FIELDS, (
        "<Subject 1> is the woman in <Picture 1>.", "A measured walk.",
        "<Subject 1>: fully_preserved.", description, "Wind and gravel.", "N/A",
    ))))


def test_h3_rejects_missing_reordered_and_empty_fields():
    text = reference_prompt()
    with pytest.raises(ValueError, match="retention_analysis"):
        parse_h3_prompt(text.replace("retention_analysis:\n<Subject 1>: fully_preserved.\n\n", ""))
    sections = parse_h3_prompt(text)
    with pytest.raises(ValueError, match="顺序"):
        parse_h3_prompt(render_h3_prompt(dict(reversed(list(sections.items())))))
    with pytest.raises(ValueError, match="不能为空"):
        parse_h3_prompt(render_h3_prompt({**sections, "summary": ""}))


def test_h3_keeps_quoted_foreign_dialogue_but_rejects_translated_narrative():
    text = reference_prompt('The woman says “这是必须保留的中文对白，不允许把它翻译成其他语言。” and keeps walking.')
    assert parse_h3_prompt(text)
    with pytest.raises(ValueError, match="英文"):
        parse_h3_prompt(reference_prompt("人物在荒凉的沙漠中慢慢行走，她抬起右手整理头发，镜头向前推进展示周围环境。"))


def test_h3_compaction_preserves_other_sections_and_all_reference_tags():
    text = reference_prompt("<Picture 1> follows <Subject 1>. " + "Repeated description. " * 400)
    before = parse_h3_prompt(text)
    calls = []

    async def complete(system, message):
        calls.append((system, message))
        return "<Picture 1> follows <Subject 1> walking left."

    result = asyncio.run(compact_h3_prompt(text, 1000, complete))
    after = parse_h3_prompt(result)
    assert len(calls) == 1 and len(result) <= 1000
    assert all(after[k] == v for k, v in before.items() if k != "detailed_description")
    assert "英文" in calls[0][0]


def test_h3_compaction_retries_translation_but_never_returns_invalid_result():
    text = reference_prompt("<Picture 1> follows <Subject 1>. " + "Repeated detail. " * 400)
    calls = []

    async def complete(system, message):
        calls.append(message)
        if len(calls) == 1:
            return "女子走在沙漠的小路上，镜头向右移动并展示整个空间，她拨开头发继续向前。"
        return "<Picture 1> follows <Subject 1> walking left."

    assert parse_h3_prompt(asyncio.run(compact_h3_prompt(text, 1000, complete)))
    assert len(calls) == 2 and "错误地翻译" in calls[1]

    async def invalid(*_):
        return "x" * 2000

    with pytest.raises(ValueError, match="停止交付"):
        asyncio.run(compact_h3_prompt(text, 1000, invalid))


def test_h3_base_mode_does_not_require_reference_sections():
    text = render_h3_prompt(dict(zip(H3_BASE_FIELDS, ("The camera follows a walking person.", "Wind.", "N/A"))))

    async def unexpected(*_):
        raise AssertionError("无需压缩不应调用模型")

    assert asyncio.run(compact_h3_prompt(text, 7000, unexpected)) == text


def test_h3_fixed_sections_cannot_be_silently_truncated():
    parts = parse_h3_prompt(reference_prompt())
    text = render_h3_prompt({**parts, "subject_definitions": "A visible subject. " * 1000})

    async def unexpected(*_):
        raise AssertionError("固定字段超限应先报错")

    with pytest.raises(ValueError, match="固定字段"):
        asyncio.run(compact_h3_prompt(text, 7000, unexpected))
