from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")


def test_asset_library_drag_is_parsed_before_generic_url_drop_handling():
    start = JS.index("function imageDropPayload(dataTransfer)")
    body = JS[start:JS.index("async function resolveImageDropPayload", start)]
    assert "const asset = canvasAssetDropPayload(dataTransfer);" in body
    assert "if(asset) return {type:'asset', asset};" in body


def test_asset_library_drop_replaces_an_image_node_without_reuploading_it():
    start = JS.index("async function applyImageDropPayloadToNode")
    body = JS[start:JS.index("function allowImageNodeDropEvent", start)]
    assert "if(payload.type === 'asset' && payload.asset?.url)" in body
    assert "node.url = payload.asset.url;" in body
    assert "node.name = payload.asset.name" in body


def test_asset_library_drop_can_fill_registered_image_upload_inputs():
    assert "function canvasImageUploadDropTarget(target)" in JS
    assert "input[type=\"file\"][accept*=\"image\"]" in JS
    assert "async function applyCanvasAssetToUploadTarget(input, asset)" in JS
    assert "input.dispatchEvent(new Event('change', {bubbles:true}));" in JS
    assert "const uploadTarget = canvasAssetDropPayload(e.dataTransfer) && canvasImageUploadDropTarget(e.target);" in JS


def test_asset_drag_does_not_use_a_blurred_canvas_overlay():
    overlay = CSS[CSS.index(".drop-overlay {"):CSS.index(".drop-overlay.active", CSS.index(".drop-overlay {"))]
    assert "backdrop-filter" not in overlay
