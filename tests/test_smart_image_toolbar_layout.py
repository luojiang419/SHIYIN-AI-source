from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
SMART_CSS = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")


def test_image_toolbar_uses_a_seven_column_auto_row_grid():
    assert 'smart-node-image-menu' in SMART_JS
    assert '.smart-node-floating-menu.smart-node-image-menu {' in SMART_CSS
    assert 'grid-template-columns:repeat(7, minmax(0, 1fr))' in SMART_CSS
    assert 'grid-auto-rows:30px' in SMART_CSS


def test_image_toolbar_buttons_fill_each_grid_cell_without_horizontal_overflow():
    assert '.smart-node-floating-menu.smart-node-image-menu button { width:100%; min-width:0; }' in SMART_CSS
    assert '.smart-node-floating-menu.smart-node-image-menu { overflow:visible; }' in SMART_CSS


def test_group_toolbar_keeps_the_base_menu_class_without_image_grid_modifier():
    group_start = SMART_JS.index('function smartGroupToolbarHtml(node)')
    group_end = SMART_JS.index('function runSmartGroupToolbarAction', group_start)
    group_body = SMART_JS[group_start:group_end]
    assert 'class="smart-node-floating-menu" data-smart-group-menu' in group_body
    assert 'smart-node-image-menu' not in group_body
