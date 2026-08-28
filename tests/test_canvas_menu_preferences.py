from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")


def test_bottom_toolbar_is_data_driven_and_has_settings_entry():
    assert '<div id="toolbarNodeItems" class="toolbar-items"></div>' in HTML
    assert 'id="canvasToolbarSettingsBtn"' in HTML
    assert 'id="canvasSettingsModal"' in HTML
    assert "const QUICK_TOOLBAR_ITEMS_KEY = 'canvas_quick_toolbar_items_v1';" in JS
    assert "function renderQuickToolbarItems()" in JS
    assert "function openCanvasSettings(mode='toolbar')" in JS
    assert "for(let start = 0; start < items.length; start += 9)" in JS
    assert "if(canvasSettingsModal?.classList.contains('open')) return '__blocked__';" in JS


def test_media_toolbar_has_two_line_limit_and_more_entry():
    assert "const MEDIA_TOOLBAR_MAX_ITEMS = 7;" in JS
    assert "const more = {id:'more', label:'更多', icon:'ellipsis'};" in JS
    assert "[...items, more]" in JS
    assert ".node-media-toolbar {" in CSS
    assert "grid-template-columns:repeat(4,minmax(54px,1fr))" in CSS
    assert "grid-auto-rows:28px" in CSS
    assert "toolbar.querySelectorAll('[data-media-toolbar-action]')" in JS
    assert "runClassicMediaToolbarAction(button.dataset.nodeId" in JS


def test_generation_nodes_keep_prompt_and_settings_in_bottom_workspace():
    assert 'class="generator-canvas-content"' in JS
    assert 'class="node-bottom-controls"' in JS
    assert JS.count('class="node-bottom-controls"') >= 2
    assert ".node-bottom-controls .gen-settings" in CSS
    assert ".node-bottom-controls .generator-inline-prompt" in CSS
