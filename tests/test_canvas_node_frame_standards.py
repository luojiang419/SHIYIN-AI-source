from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
FILM_JS = (ROOT / "static" / "js" / "canvas-film-nodes.js").read_text(encoding="utf-8")


def test_all_classic_nodes_share_type_aware_minimum_frame_limits():
    assert "function classicNodeLayoutLimits(nodeOrType)" in JS
    assert "isControlNode ? CLASSIC_VIDEO_NODE_MIN_WIDTH : 0" in JS
    assert "minHeight:Math.max(96" in JS
    assert "normalizeClassicNodeLayout(node);" in JS
    assert "Number.isFinite(storedHeight) && storedHeight > 0" in JS
    assert "Object.prototype.hasOwnProperty.call(node,'h')" in JS
    assert "const autoHeight = isControlNode && !(Number(size.h) > 0);" in JS
    assert "layoutLimits.autoHeight ? 'auto-height-node' : ''" in JS
    assert "--node-min-width" in JS
    assert "--node-min-height" in JS
    assert "min-width:var(--node-min-width,220px)" in CSS
    assert "min-height:var(--node-min-height,96px)" in CSS


def test_extension_size_provider_does_not_override_unrelated_node_types():
    assert "function size(type){ return SIZES[type] || null; }" in FILM_JS
    assert "feature=node-size-isolation.1" in HTML


def test_render_and_resize_use_the_same_node_layout_contract():
    resize_start = JS.index("function onNodeResize(e)")
    resize_end = JS.index("function startLink", resize_start)
    resize = JS[resize_start:resize_end]
    assert "const limits = classicNodeLayoutLimits(resizeNode.node);" in resize
    assert "const minWidth = limits.minWidth;" in resize
    assert "const minHeight = limits.minHeight;" in resize
    assert "const maxWidth = limits.maxWidth;" in resize


def test_node_shell_and_controls_cannot_overflow_the_standard_frame():
    assert ".node-visual-shell { position:relative; width:100%; min-width:0;" in CSS
    assert ".node-body { width:100%; min-width:0;" in CSS
    assert ".node-body > * { min-width:0; max-width:100%; }" in CSS
    assert ".node input,.node select,.node textarea { min-width:0; max-width:100%; }" in CSS
    assert ".auto-height-node .resize-handle { cursor:ew-resize; }" in CSS
    assert ".image-node.has-image .node-visual-shell { background:var(--canvas-node-fill); border-color:var(--canvas-node-stroke); }" in CSS
    assert "feature=node-frame-standards.1" in HTML
