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
    assert "items.forEach(item =>" in JS
    assert "start += 9" not in JS
    assert "if(canvasSettingsModal?.classList.contains('open')) return '__blocked__';" in JS


def test_media_toolbar_has_responsive_click_targets_and_more_entry():
    assert "const MEDIA_TOOLBAR_MAX_ITEMS = 8;" in JS
    assert "const more = {id:'more', label:'更多', icon:'ellipsis'};" in JS
    assert "[...items, more]" in JS
    assert ".node-media-toolbar {" in CSS
    assert "grid-template-columns:repeat(auto-fit,minmax(clamp(76px,8vw,118px),1fr))" in CSS
    assert "grid-auto-rows:clamp(36px,3.2vw,44px)" in CSS
    assert "max-height:min(220px,38vh)" in CSS
    assert "min-height:36px" in CSS
    assert "toolbar.querySelectorAll('[data-media-toolbar-action]')" in JS
    assert "runClassicMediaToolbarAction(button.dataset.nodeId" in JS


def test_generation_nodes_keep_prompt_and_settings_in_bottom_workspace():
    assert 'class="generator-canvas-content"' in JS
    assert 'class="node-bottom-controls"' in JS
    assert JS.count('class="node-bottom-controls"') >= 2
    assert ".node-bottom-controls .gen-settings" in CSS
    assert ".node-bottom-controls .generator-inline-prompt" in CSS


def test_image_prompt_panel_is_separate_from_top_media_actions():
    render_start = JS.index("function renderSelectionHub")
    render_end = JS.index("function selectOutputMedia", render_start)
    render_source = JS[render_start:render_end]
    assert "selectionHub.classList.remove('open','image-prompt-hub')" in render_source
    assert "const actionPanel = imageNode ? ''" in render_source
    assert "selectionHub.classList.toggle('image-prompt-hub', Boolean(imageNode))" in render_source
    assert "const isImagePromptHub = selectionHub.classList.contains('image-prompt-hub');" in JS
    assert "? anchorRect.bottom - boardRect.top + gap" in JS
    assert "const maxTop = Math.max(margin, boardRect.height - hubRect.height - margin);" in JS
    assert "width:min(622px,calc(100vw - 24px))" in CSS
    assert "height:clamp(112px,18vh,160px)" in CSS
    assert "const gap = 16;" in JS


def test_canvas_preferences_preserve_an_explicit_empty_selection():
    assert "return filtered.slice(0, maxItems);" in JS


def test_image_media_toolbar_exposes_grid_and_downstream_actions_with_two_row_cap():
    for action in ("grid", "generator", "batchGenerator", "video", "panorama", "angle", "multi-view", "relight", "dwpose"):
        assert f"{{id:'{action}'" in JS
    assert "['edit','grid','batchGenerator','video','panorama','angle','multi-view','relight','dwpose','download']" in JS
    assert "else if(node.url) runMediaQuickAction(action" in JS


def test_connection_context_menu_uses_link_hit_path_and_disconnects_one_connection():
    assert '<div id="connectionContextMenu" class="create-menu connection-context-menu"' in HTML
    assert "const connectionContextMenu = document.getElementById('connectionContextMenu');" in JS
    assert "const connectionHit = e.target.closest?.('.link-hit[data-connection-id]');" in JS
    assert "openConnectionContextMenu(connectionHit.dataset.connectionId, e.clientX, e.clientY);" in JS
    assert 'data-connection-disconnect="${escapeAttr(connectionId)}"' in JS
    assert "deleteConnection(connectionId, event);" in JS
    assert "setHoveredConnection(connectionId);" in JS
    assert "hoveredConnectionId === connection.id" in JS
    assert ".connection-context-menu { width:172px; }" in CSS
    assert ".link-controls { position:absolute" in CSS and "display:none" in CSS


def test_canvas_node_colors_follow_reference_neutral_palette_and_blue_selection():
    assert "--canvas-node-fill:#e7e5df" in CSS
    assert "--canvas-node-stroke:#d6d3ca" in CSS
    assert "--canvas-selection:hsl(214 100% 59%)" in CSS
    assert ".node.selected { outline:2px solid var(--canvas-selection);" in CSS
    assert ".link.link-active { stroke:var(--canvas-selection);" in CSS
