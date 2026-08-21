from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def test_normal_canvas_arrange_groups_by_functional_categories_and_uses_square_grid():
    assert "function canvasArrangeCategory(node)" in CANVAS_JS
    assert "['image','group'].includes(type)" in CANVAS_JS
    assert "type === 'output' || type.endsWith('-output')" in CANVAS_JS
    assert "const columns = Math.max(1, Math.ceil(Math.sqrt(items.length)));" in CANVAS_JS
    assert "const categoryGap = 180;" in CANVAS_JS


def test_smart_canvas_arrange_groups_media_prompt_process_and_output():
    assert 'id="smartArrangeMenuBtn"' in SMART_HTML
    assert "function smartArrangeCategory(node)" in SMART_JS
    assert "if(isSmartGroupNode(node)) return {rank:0, key:'media'};" in SMART_JS
    assert "return generated ? {rank:3, key:'output'} : {rank:0, key:'media'};" in SMART_JS
    assert "const columns = Math.max(1, Math.ceil(Math.sqrt(items.length)));" in SMART_JS


def test_context_menu_can_be_opened_from_a_selected_node_in_both_canvases():
    assert "selectedNodeEl = e.target.closest?.('.node[data-id]')" in CANVAS_JS
    assert "selectedNodeEl?.dataset?.id && selected.size > 1" in CANVAS_JS
    assert "nodeEl?.dataset?.id && selected.size > 1 && selected.has(nodeEl.dataset.id)" in SMART_JS
    assert "smartArrangeMenuBtn.hidden = selectedNodeIds().length < 2" in SMART_JS
