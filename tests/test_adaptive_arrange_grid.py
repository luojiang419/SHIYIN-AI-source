from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def test_both_canvases_use_adaptive_grid_for_dense_layers():
    for source, shape_name, arrange_name in (
        (CANVAS_JS, "canvasArrangeGridShape", "arrangeCanvasLayerItems"),
        (SMART_JS, "smartArrangeGridShape", "arrangeSmartLayerItems"),
    ):
        assert f"function {shape_name}(count)" in source
        assert "if(Number.isInteger(square)) return {columns:square, rows:square};" in source
        assert "Math.ceil(Math.sqrt(total * 4 / 3))" in source
        assert "return {columns, rows:Math.ceil(total / columns)};" in source
        assert f"function {arrange_name}(items, rectById, startX, startY)" in source
        assert "if(ordered.length < 4)" in source
        assert "const colWidths = Array(columns).fill(0);" in source
        assert "const rowHeights = Array(rows).fill(0);" in source
        assert "move" in source[source.index(f"function {arrange_name}"):source.index(f"function {arrange_name}") + 4000]


def test_adaptive_grid_is_only_applied_inside_existing_topology_layers():
    normal_start = CANVAS_JS.index("function arrangeIdsByConnections(ids)")
    normal_end = CANVAS_JS.index("function arrangeSelectedCanvasNodes", normal_start)
    normal_body = CANVAS_JS[normal_start:normal_end]
    smart_start = SMART_JS.index("function arrangeSmartIdsByConnections(ids)")
    smart_end = SMART_JS.index("function arrangeSelectedSmartNodes", smart_start)
    smart_body = SMART_JS[smart_start:smart_end]
    assert "const levels = new Map(selectedNodes.map(node => [node.id, 0]));" in normal_body
    assert "const levels = new Map(selectedNodes.map(node => [node.id, 0]));" in smart_body
    assert "arrangeCanvasLayerItems(items, rectById, layerX, startY)" in normal_body
    assert "arrangeSmartLayerItems(items, rectById, layerX, startY)" in smart_body
    # 网格只替换层内位置写入，不应引入新的连接/上下游判断。
    assert "connections.forEach(connection =>" in normal_body
    assert "(canvas?.connections || []).forEach(connection =>" in smart_body


def test_dense_grid_examples_have_expected_shapes_in_source_contract():
    # 这些数量对应产品约定：24 个为 4 行 6 列，6/5 个为 2 行 3 列，4 个为 2x2。
    for source in (CANVAS_JS, SMART_JS):
        assert "const columns = Math.max(1, Math.ceil(Math.sqrt(total * 4 / 3)));" in source
        assert "const rows = Math.max(1, shape.rows);" in source
        assert "const columns = Math.max(1, shape.columns);" in source
