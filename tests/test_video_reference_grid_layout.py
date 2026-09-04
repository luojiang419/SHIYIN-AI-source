from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")


def test_video_reference_list_uses_six_column_wrapping_grid():
    assert ".video-img-list { display:grid; grid-template-columns:repeat(6,minmax(0,1fr));" in CSS
    assert "grid-auto-rows:max-content" in CSS
    assert "column-gap:8px; row-gap:12px" in CSS
    assert ".video-img-list .video-input-item { width:auto; min-width:0; }" in CSS
    assert ".video-img-list .video-input-thumb { width:100%; height:auto; aspect-ratio:1; }" in CSS
    assert ".video-img-list { display:grid;" in CSS
    assert ".video-img-list { display:flex;" not in CSS


def test_video_node_keeps_six_thumbnails_readable_and_prevents_unbounded_width():
    assert "const CLASSIC_VIDEO_NODE_MIN_WIDTH = 440;" in JS
    assert "const CLASSIC_VIDEO_NODE_MAX_WIDTH = 520;" in JS
    assert "const width = Number.isFinite(storedWidth) ? storedWidth : limits.minWidth;" in JS
    assert ".video-node { width:440px; min-width:440px; max-width:520px; }" in CSS
    assert "const minWidth = limits.minWidth;" in JS
    assert "const maxWidth = limits.maxWidth;" in JS
    assert "feature=video-reference-grid.2" in HTML


def test_video_node_height_is_content_driven_during_render_and_resize():
    assert "function normalizeClassicNodeLayout(node)" in JS
    assert "const autoHeight = portraitMedia || (isControlNode && !(Number(size.h) > 0));" in JS
    assert "normalizeClassicNodeLayout(node);" in JS
    assert "if(isAutoHeightNode) delete resizeNode.node.h;" in JS
    assert "el.classList.remove('sized');" in JS
    assert "el.style.removeProperty('height');" in JS
    assert ".auto-height-node .resize-handle { cursor:ew-resize; }" in CSS
    assert ".video-node .node-bottom-controls { position:relative; bottom:auto; }" in CSS
    assert "feature=video-auto-height.1" in HTML
