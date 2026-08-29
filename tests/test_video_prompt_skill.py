from pathlib import Path

from main import (
    _video_prompt_skill,
    normalize_video_prompt_references,
    video_prompt_polish_system_prompt,
    video_prompt_reference_manifest,
)


def test_minimax_h3_loads_complete_embedded_skill_and_references():
    text, skill_id = _video_prompt_skill("minimax-h3", "MiniMax H3")
    assert skill_id == "minimax-h3"
    assert "integrated_multimodal_description" in text
    assert "subject_definitions" in text
    assert "===== base-en.txt =====" in text
    assert "===== ref-en.txt =====" in text
    assert len(text) > 30_000


def test_selected_video_model_is_reflected_in_polish_system_prompt():
    prompt = video_prompt_polish_system_prompt("minimax-h3", "MiniMax H3", text_to_video=True)
    assert "内置提示词 skill（minimax-h3）" in prompt
    assert "严格执行上述官方 H3 skill" in prompt


def test_kling_skill_has_source_note():
    source = Path("skills/video-prompt-polish/kling-cli/SOURCE.md")
    assert source.exists()
    assert "kling.ai/quickstart" in source.read_text(encoding="utf-8")

    text, skill_id = _video_prompt_skill("kling-cli", "Kling VIDEO 3.0 Omni")
    assert skill_id == "kling-cli"
    assert "<<<element_1>>>" in text
    assert "latest-official-syntax-2.0.txt" in text


def test_natural_reference_mentions_follow_selected_skill_tags():
    kling = normalize_video_prompt_references("图1里的主体看向图2，参考视频1的动作", "kling-cli", 2, 1)
    assert kling == "<<<image_1>>>里的主体看向<<<image_2>>>，<<<video_1>>>的动作"

    h3 = normalize_video_prompt_references("图片1作为首帧，主体1走向图片2", "minimax-h3", 2, 0)
    assert h3 == "<Picture 1>作为首帧，<Subject 1>走向<Picture 2>"


def test_reference_manifest_requires_vision_model_to_bind_subjects():
    context, manifest, labels = video_prompt_reference_manifest("minimax-h3", 2, 0, ["演员参考", "尾帧"])
    assert [item["tag"] for item in manifest] == ["<Picture 1>", "<Picture 2>"]
    assert labels[0].startswith("<Picture 1>")
    assert "<Subject N>" in context
    assert "同一主体时才合并" in context
