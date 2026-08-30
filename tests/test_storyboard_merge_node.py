from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
CANVAS_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
CANVAS_CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")


def test_storyboard_merge_is_registered_in_creation_and_media_menus():
    assert "id:'storyboardMerge'" in CANVAS_JS
    assert "menuAdd('storyboardMerge')" in CANVAS_HTML


def test_storyboard_merge_has_ordered_thumbnails_and_output_pipeline():
    for marker in (
        "function storyboardMergeEntries(node)",
        "storyboard-merge-index",
        "function runStoryboardMergeNode(nodeId)",
        "ctx.fillStyle = '#ffffff'",
        "uploadCroppedBlob(blob",
        "outputForNode(node, 520, true)",
    ):
        assert marker in CANVAS_JS


def test_storyboard_merge_uses_theme_variables_for_new_visuals():
    css_start = CANVAS_CSS.index(".storyboardMerge-node")
    css_block = CANVAS_CSS[css_start : css_start + 5000]
    assert "var(--strong)" in css_block
    assert "var(--line)" in css_block
    assert "var(--soft)" in css_block
    assert "#3b82f6" not in css_block.lower()
    assert "#2563eb" not in css_block.lower()
