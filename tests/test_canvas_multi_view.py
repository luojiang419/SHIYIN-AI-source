from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMART_JS = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")
SPECIAL_CSS = (ROOT / "static/css/canvas-special-nodes.css").read_text(encoding="utf-8")


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
