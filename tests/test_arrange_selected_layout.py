from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def test_normal_canvas_arrange_uses_connection_topology_and_real_node_dimensions():
    assert "const outgoing = new Map(selectedNodes.map(node => [node.id, new Set()]));" in CANVAS_JS
    assert "const incoming = new Map(selectedNodes.map(node => [node.id, new Set()]));" in CANVAS_JS
    assert "const levels = new Map(selectedNodes.map(node => [node.id, 0]));" in CANVAS_JS
    assert "const layers = new Map();" in CANVAS_JS
    assert "const canonicalId = id => scopeById.get(id) || id;" in CANVAS_JS
    assert "const unresolved = selectedNodes.map(node => node.id).filter(id => !processed.has(id)).sort(compareIds);" in CANVAS_JS
    assert "const columnGap = 180;" in CANVAS_JS


def test_smart_canvas_arrange_uses_connection_topology_and_real_node_dimensions():
    assert 'id="smartArrangeMenuBtn"' in SMART_HTML
    assert "const outgoing = new Map(selectedNodes.map(node => [node.id, new Set()]));" in SMART_JS
    assert "const incoming = new Map(selectedNodes.map(node => [node.id, new Set()]));" in SMART_JS
    assert "const levels = new Map(selectedNodes.map(node => [node.id, 0]));" in SMART_JS
    assert "const layers = new Map();" in SMART_JS
    assert "const canonicalId = id => scopeById.get(id) || id;" in SMART_JS
    assert "const unresolved = selectedNodes.map(node => node.id).filter(id => !processed.has(id)).sort(compareIds);" in SMART_JS
    assert "const columnGap = 160;" in SMART_JS


def test_context_menu_can_be_opened_from_a_selected_node_in_both_canvases():
    assert "selectedNodeEl = e.target.closest?.('.node[data-id]')" in CANVAS_JS
    assert "selectedNodeEl?.dataset?.id && selected.size > 1" in CANVAS_JS
    assert "nodeEl?.dataset?.id && selected.size > 1 && selected.has(nodeEl.dataset.id)" in SMART_JS
    assert "smartArrangeMenuBtn.hidden = selectionCount < 2" in SMART_JS


def test_connected_node_creation_uses_non_overlapping_arranged_spacing_in_both_canvases():
    assert "const CANVAS_NODE_LAYOUT_GAP = 72;" in CANVAS_JS
    assert "const CANVAS_NODE_LAYOUT_ROW_GAP = 56;" in CANVAS_JS
    assert "function canvasFreeNodePoint(source, created, direction='downstream')" in CANVAS_JS
    assert "positionCanvasNodeRelative(created, origin, state.originKind === 'out' ? 'downstream' : 'upstream');" in CANVAS_JS

    assert "const SMART_NODE_LAYOUT_GAP = 72;" in SMART_JS
    assert "const SMART_NODE_LAYOUT_ROW_GAP = 52;" in SMART_JS
    assert "function smartFreeNodePoint(source, created, direction='downstream')" in SMART_JS
    assert "positionSmartNodeRelative(newNode, sourceNode, drag.fromPort === 'out' ? 'downstream' : 'upstream');" in SMART_JS

    quick_action_start = CANVAS_JS.index("function addQuickActionNode(source, type)")
    quick_action_end = CANVAS_JS.index("function runMediaQuickAction", quick_action_start)
    quick_action = CANVAS_JS[quick_action_start:quick_action_end]
    assert "const point = {x:Math.round(source.x + sourceRect.w + 110), y:Math.round(source.y)};" in quick_action
    assert "positionCanvasNodeRelative(created, source, 'downstream');" not in quick_action


def test_auto_created_output_nodes_use_free_position_algorithm():
    assert "positionCanvasNodeRelative(out, node, 'downstream');" in CANVAS_JS
    assert "positionCanvasNodeRelative(out, sourceNode, 'downstream');" in CANVAS_JS
    assert "positionCanvasNodeRelative(output, node, 'downstream');" in CANVAS_JS

    assert "function smartOutputPointForImages(sourceNode, images=[], options={})" in SMART_JS
    assert "return smartFreeNodePoint(sourceNode, candidate, 'downstream');" in SMART_JS
    assert "const point = smartFreeNodePoint(sourceNode, output, 'downstream');" in SMART_JS
    assert "const point = smartFreeNodePoint(rootNode, output, 'downstream');" in SMART_JS
    assert "const point = smartOutputPointForImages(node, outputImages);" in SMART_JS
