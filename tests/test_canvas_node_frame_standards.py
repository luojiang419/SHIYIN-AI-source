from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
FILM_JS = (ROOT / "static" / "js" / "canvas-film-nodes.js").read_text(encoding="utf-8")
SMART_CSS = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")
SPECIAL_CSS = (ROOT / "static" / "css" / "canvas-special-nodes.css").read_text(encoding="utf-8")
LINKFOX_CSS = (ROOT / "static" / "css" / "canvas-linkfox-video.css").read_text(encoding="utf-8")


def test_all_classic_nodes_share_type_aware_minimum_frame_limits():
    assert "function classicNodeLayoutLimits(nodeOrType)" in JS
    assert "isControlNode ? CLASSIC_VIDEO_NODE_MIN_WIDTH : 0" in JS
    assert "minHeight:Math.max(96" in JS
    assert "normalizeClassicNodeLayout(node);" in JS
    assert "Number.isFinite(storedHeight) && storedHeight > 0" in JS
    assert "Object.prototype.hasOwnProperty.call(node,'h')" in JS
    assert "const autoHeight = portraitMedia || (isControlNode && !(Number(size.h) > 0) && !CLASSIC_FLEX_GENERATOR_NODE_TYPES.has(type));" in JS
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


def test_legacy_smart_function_nodes_keep_content_inside_their_frames():
    assert ".image-node.prompt-smart-node:not(.smart-group-member-node) .node-body { overflow:auto; }" in SMART_CSS
    assert ".smart-special-node.smart-angle-node{padding:12px;overflow:hidden;" in SPECIAL_CSS
    assert ".smart-special-node.smart-angle-node .node-body{width:100%;height:100%;min-height:0;padding:0;overflow:auto;" in SPECIAL_CSS
    assert ".smart-special-node.smart-panorama-node .node-body{height:100%;min-height:0;overflow:auto}" in SPECIAL_CSS
    assert ".smart-linkfox-video-node .node-body {\n    height:100%;\n    min-height:0;\n    overflow:auto;" in LINKFOX_CSS
    assert "function smartNodeResizeLimits(node)" in (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
    assert "SMART_MEDIA_GROUP_MIN_WIDTH = 160" in (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
    assert "SMART_LOOP_MIN_WIDTH = 304" in (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
