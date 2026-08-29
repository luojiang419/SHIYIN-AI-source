from pathlib import Path

from main import _video_prompt_skill, video_prompt_polish_system_prompt


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
