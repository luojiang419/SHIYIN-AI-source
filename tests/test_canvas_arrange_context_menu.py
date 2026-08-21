from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")


def test_create_context_menu_contains_arrange_selected_action():
    assert 'id="canvasArrangeMenuBtn"' in HTML
    assert 'class="menu-divider canvas-arrange-menu-divider"' in HTML
    assert 'onclick="arrangeSelectedCanvasNodes()' not in HTML


def test_arrange_context_action_only_appears_for_multiple_selection():
    assert "const canArrangeSelection = selected.size > 1;" in JAVASCRIPT
    assert "canvasArrangeMenuBtn.hidden = !canArrangeSelection" in JAVASCRIPT
    assert "canvasArrangeMenuDivider.hidden = !canArrangeSelection" in JAVASCRIPT


def test_arrange_context_action_reuses_existing_layout_handler_and_closes_menu():
    assert "canvasArrangeMenuBtn?.addEventListener('click'" in JAVASCRIPT
    action_start = JAVASCRIPT.index("canvasArrangeMenuBtn?.addEventListener('click'")
    action_body = JAVASCRIPT[action_start:JAVASCRIPT.index("function isZoomPreviewIgnoredTarget", action_start)]
    assert "arrangeSelectedCanvasNodes();" in action_body
    assert "closeCreateMenu();" in action_body
