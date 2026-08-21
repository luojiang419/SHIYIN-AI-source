from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMART_JS = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
CANVAS_HTML = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
SPECIAL_CSS = (ROOT / "static/css/canvas-special-nodes.css").read_text(encoding="utf-8")
MULTI_VIEW_CSS = (ROOT / "static/css/canvas-multi-view-overrides.css").read_text(encoding="utf-8")


def test_image_toolbar_exposes_multi_view_action_and_creates_node():
    assert "{key:'multi-view', icon:'panels-top-left', label:'创建三视图'" in SMART_JS
    assert "function createMultiViewNode" in SMART_JS
    assert "createMultiViewNode(null, node)" in SMART_JS


def test_multi_view_has_all_role_ports_and_optional_multi_inputs():
    for role, label in [
        ("model-front", "模特正面"),
        ("model-side", "模特侧面"),
        ("model-back", "模特背面"),
        ("product-front", "产品正面"),
        ("product-side", "产品侧面"),
        ("product-back", "产品背面"),
        ("front-detail", "正面细节"),
        ("back-detail", "背面细节"),
        ("accessory", "配饰"),
    ]:
        assert role in SMART_JS
        assert label in SMART_JS
    assert "MULTI_VIEW_MULTI_INPUT_ROLES" in SMART_JS
    assert "front-detail', 'back-detail', 'accessory" in SMART_JS


def test_multi_view_generates_board_and_three_vertical_assets():
    assert "multi-view-board.png" in SMART_JS
    assert "`multi-view-${view}.png`" in SMART_JS
    assert "Promise.all([taskFor('front', true), taskFor('front'), taskFor('side'), taskFor('back')])" in SMART_JS
    assert "customRatio:ratio" in SMART_JS


def test_multi_view_is_available_from_create_menu_and_has_visual_styles():
    assert 'data-create-type="multi-view"' in SMART_HTML
    assert ".multi-view-input-list" in SPECIAL_CSS
    assert ".multi-view-output-grid" in SPECIAL_CSS


def test_classic_canvas_image_toolbar_exposes_create_three_views_action():
    assert "{id:'multi-view', label:langIsEn() ? 'Create three views' : '创建三视图'" in CANVAS_JS
    assert "type === 'multiView' || type === 'multi-view'" in CANVAS_JS
    assert "const inputRole = type === 'multi-view' ? 'model-front' : ''" in CANVAS_JS


def test_classic_canvas_multi_view_node_has_all_ports_and_four_asset_generation():
    assert "const CLASSIC_MULTI_VIEW_INPUT_SLOTS" in CANVAS_JS
    for role in [
        "model-front", "model-side", "model-back", "product-front", "product-side", "product-back",
        "front-detail", "back-detail", "accessory",
    ]:
        assert role in CANVAS_JS
    assert "Promise.all([taskFor('front', true), taskFor('front'), taskFor('side'), taskFor('back')])" in CANVAS_JS
    assert "classicMultiViewPrompt(view, refs, board)" in CANVAS_JS
    assert "data-multi-view-run" in CANVAS_JS
    assert ".classic-multi-view-output-grid" in SPECIAL_CSS


def test_classic_canvas_multi_view_is_available_from_toolbar_and_create_menu():
    assert "menuAdd('multiView')" in CANVAS_HTML


def test_multi_view_ports_have_explicit_labels_and_grouped_layout_overrides():
    assert 'aria-label="${escapeAttr(`输入端口：${label}`)}"' in SMART_JS
    assert 'aria-label="${escapeAttr(`输入端口：${label}`)}"' in CANVAS_JS
    assert 'data-input-role="${escapeAttr(role)}"' in SMART_JS
    assert 'data-input-role="${escapeAttr(role)}"' in CANVAS_JS
    assert ".multi-view-input-group" in MULTI_VIEW_CSS
    assert ".classic-multi-view-input-group" in MULTI_VIEW_CSS
    assert ".smart-special-node.smart-multi-view-node .multi-view-port::before" in MULTI_VIEW_CSS
    assert ".multi-view-run-row" in MULTI_VIEW_CSS


def test_both_canvas_pages_load_multi_view_layout_overrides():
    assert 'canvas-multi-view-overrides.css?v=2026.08.21.multi-view.2' in SMART_HTML
    assert 'canvas-multi-view-overrides.css?v=2026.08.21.multi-view.2' in CANVAS_HTML


def test_multi_view_uses_single_column_rows_for_port_alignment():
    assert "MULTI_VIEW_INPUT_SLOTS.map(([role, label, optional], index)" in SMART_JS
    assert "CLASSIC_MULTI_VIEW_INPUT_SLOTS.map(([role, label], index)" in CANVAS_JS
    assert "style=\"--multi-view-port-index:${index};--multi-view-port-top:${74 + index * 44}px\"" in SMART_JS
    assert "style=\"--multi-view-port-index:${index};--multi-view-port-top:${125 + index * 44}px\"" in CANVAS_JS
    assert ".multi-view-input-list,.classic-multi-view-input-list{display:flex;flex-direction:column" in MULTI_VIEW_CSS
    assert ".smart-special-node.smart-multi-view-node .multi-view-port{top:var(--multi-view-port-top" in MULTI_VIEW_CSS
    assert ".multiView-node .classic-multi-view-port{top:var(--multi-view-port-top" in MULTI_VIEW_CSS
