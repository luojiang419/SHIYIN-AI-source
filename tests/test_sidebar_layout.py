from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def test_sidebar_settings_group_can_show_language_button():
    assert ".side-actions .settings-fold-group:not(.is-collapsed)" in INDEX
    assert "max-height: 300px;" in INDEX
    assert 'id="lang-toggle-btn"' in INDEX


def test_sidebar_drops_unused_bottom_direction_badge():
    assert 'id="project-version-badge"' not in INDEX
    assert '.project-version-badge::before' not in INDEX
