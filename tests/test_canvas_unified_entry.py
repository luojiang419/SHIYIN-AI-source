from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_LIST = (ROOT / "static/js/canvas-list.js").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
ASSET_MANAGER = (ROOT / "static/js/asset-manager.js").read_text(encoding="utf-8")
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
LEGACY_SMART_PAGE = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")


def test_canvas_list_has_one_canvas_entry_and_name_only_creation():
    assert "/static/canvas.html?id=${enc}" in CANVAS_LIST
    assert "data-kind=\"smart\"" not in CANVAS_LIST
    assert "createCanvasOnBoard(input.value.trim(), worldPt)" in CANVAS_LIST
    assert "智能画布" not in CANVAS_LIST
    assert "普通画布" not in CANVAS_LIST


def test_canvas_editor_never_routes_to_smart_canvas():
    assert "smart-canvas.html" not in CANVAS_JS
    assert "createSmartCanvas" not in CANVAS_JS
    assert "kind:'smart'" not in CANVAS_JS


def test_canvas_assets_are_not_split_by_canvas_kind():
    assert "return '画布';" in ASSET_MANAGER
    assert "id:'all'" in ASSET_MANAGER
    assert "id:'smart'" not in ASSET_MANAGER
    assert "smart-canvas.html" not in ASSET_MANAGER


def test_backend_normalizes_legacy_smart_kind_to_canvas():
    assert 'return "classic"' in MAIN
    assert '"name": "全部画布"' in MAIN
    assert '"name": "智能画布"' not in MAIN
    assert '"name": "普通画布"' not in MAIN


def test_legacy_smart_url_redirects_to_canvas_editor():
    assert "location.replace(target)" in LEGACY_SMART_PAGE
    assert "'/static/canvas.html'" in LEGACY_SMART_PAGE
