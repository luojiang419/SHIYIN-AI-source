from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")


def test_portrait_image_and_video_media_nodes_use_wide_auto_height_layout():
    assert "const CLASSIC_PORTRAIT_MEDIA_NODE_MIN_WIDTH = 520;" in JS
    assert "const classicPortraitMediaNodeIds = new Set();" in JS
    assert "function classicMediaNodeIsPortrait(node)" in JS
    assert "['image','video'].includes(mediaKindForNode(node))" in JS
    assert "const portraitMedia = classicMediaNodeIsPortrait(nodeOrType);" in JS
    assert "portraitMedia ? CLASSIC_PORTRAIT_MEDIA_NODE_MIN_WIDTH : 0" in JS
    assert "const autoHeight = portraitMedia ||" in JS
    assert "const hasFixedSize = !layoutLimits.autoHeight && Boolean" in JS
    assert "portraitMedia ? 'portrait-media-node' : ''" in JS


def test_portrait_media_stage_is_16_by_9_and_preserves_the_whole_asset():
    assert ".image-node.portrait-media-node .image-preview-wrap {" in CSS
    assert "aspect-ratio:16/9" in CSS
    assert ".image-node.portrait-media-node img" in CSS
    assert ".image-node.portrait-media-node video" in CSS
    assert "object-fit:contain" in CSS
    assert ".image-node.portrait-media-node .image-node-prompt-panel" in CSS


def test_loaded_media_dimensions_can_promote_legacy_nodes_to_portrait_layout():
    assert "function syncClassicMediaNodeOrientation(el, node, mediaEl=null)" in JS
    assert "classicPortraitMediaNodeIds.add(node.id)" in JS
    assert "refreshNodes([node.id]);" in JS
    assert "syncClassicMediaNodeOrientation(el, node, loadedImg);" in JS
    assert "feature=portrait-media-stage.1" in HTML
