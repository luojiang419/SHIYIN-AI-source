from pathlib import Path
import json
import subprocess


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def _extract_javascript_function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError(f"JavaScript function {name} is incomplete")


def _run_javascript(script: str):
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_both_canvases_use_adaptive_grid_for_dense_layers():
    for source, shape_name, arrange_name in (
        (CANVAS_JS, "canvasArrangeGridShape", "arrangeCanvasLayerItems"),
        (SMART_JS, "smartArrangeGridShape", "arrangeSmartLayerItems"),
    ):
        assert f"function {shape_name}(count)" in source
        assert "if(Number.isInteger(square)) return {columns:square, rows:square};" in source
        assert "if(total % rows !== 0) continue;" in source
        assert "if(columns / rows <= 2) return {columns, rows};" in source
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
    # 行列均为可执行函数的真实结果：15=3x5、8=2x4、4=2x2、30=5x6。
    expected = [
        {"columns": 5, "rows": 3},
        {"columns": 4, "rows": 2},
        {"columns": 2, "rows": 2},
        {"columns": 6, "rows": 5},
        {"columns": 3, "rows": 2},
    ]
    for source, shape_name in (
        (CANVAS_JS, "canvasArrangeGridShape"),
        (SMART_JS, "smartArrangeGridShape"),
    ):
        function_source = _extract_javascript_function(source, shape_name)
        actual = _run_javascript(
            f"{function_source}; console.log(JSON.stringify([15,8,4,30,5].map({shape_name})));"
        )
        assert actual == expected
        assert "const rows = Math.max(1, shape.rows);" in source
        assert "const columns = Math.max(1, shape.columns);" in source


def test_classic_canvas_batches_disconnected_same_type_nodes_before_grid_layout():
    function_source = _extract_javascript_function(CANVAS_JS, "canvasArrangeLayoutBatches")
    nodes = [
        *({"id": f"image-{index}", "type": "image"} for index in range(9)),
        {"id": "flow-a", "type": "prompt"},
        {"id": "flow-b", "type": "generator"},
        {"id": "prompt-loose", "type": "prompt"},
    ]
    components = [
        *([f"image-{index}"] for index in range(9)),
        ["flow-a", "flow-b"],
        ["prompt-loose"],
    ]
    actual = _run_javascript(
        "const nodes=" + json.dumps(nodes) + ";"
        + function_source
        + ";console.log(JSON.stringify(canvasArrangeLayoutBatches("
        + json.dumps(components)
        + ")));"
    )
    assert actual == [
        {"ids": [f"image-{index}" for index in range(9)], "loose": True},
        {"ids": ["flow-a", "flow-b"], "loose": False},
        {"ids": ["prompt-loose"], "loose": True},
    ]

    arrange_start = CANVAS_JS.index("function arrangeSelectedCanvasNodes()")
    arrange_end = CANVAS_JS.index("function handoffExistingInputsToGroup", arrange_start)
    arrange_body = CANVAS_JS[arrange_start:arrange_end]
    assert "const batches = canvasArrangeLayoutBatches(components);" in arrange_body
    assert "arrangeCanvasLayerItems(items, rectById, baseX, nextY);" in arrange_body


def test_nine_classic_canvas_nodes_are_positioned_as_three_by_three_grid():
    shape_source = _extract_javascript_function(CANVAS_JS, "canvasArrangeGridShape")
    layer_source = _extract_javascript_function(CANVAS_JS, "arrangeCanvasLayerItems")
    actual = _run_javascript(
        "const items=Array.from({length:9},(_,index)=>({id:`image-${index}`,x:0,y:0}));"
        "const rectById=new Map(items.map(item=>[item.id,{w:320,h:180}]));"
        "const nodeRect=item=>({w:320,h:180,x:item.x,y:item.y});"
        "const moveCanvasNodeAtom=(item,x,y)=>{item.x=x;item.y=y;};"
        + shape_source
        + layer_source
        + ";const bounds=arrangeCanvasLayerItems(items,rectById,100,200);"
        "console.log(JSON.stringify({"
        "columns:new Set(items.map(item=>item.x)).size,"
        "rows:new Set(items.map(item=>item.y)).size,"
        "positions:items.map(item=>[item.x,item.y]),bounds}));"
    )
    assert actual["columns"] == 3
    assert actual["rows"] == 3
    assert actual["positions"] == [
        [100, 200], [600, 200], [1100, 200],
        [100, 436], [600, 436], [1100, 436],
        [100, 672], [600, 672], [1100, 672],
    ]
    assert actual["bounds"] == {"width": 1320, "height": 652}
