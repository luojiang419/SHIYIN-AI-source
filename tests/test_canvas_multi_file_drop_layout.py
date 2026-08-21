from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANVAS_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")


def test_both_canvases_use_stable_numeric_filename_sorting():
    assert "new Intl.Collator('zh-CN', {numeric:true, sensitivity:'base'})" in CANVAS_JS
    assert "new Intl.Collator('zh-CN', {numeric:true, sensitivity:'base'})" in SMART_JS
    assert "CANVAS_MEDIA_FILENAME_COLLATOR.compare(a.name, b.name) || a.index - b.index" in CANVAS_JS
    assert "SMART_MEDIA_FILENAME_COLLATOR.compare(a.name, b.name) || a.index - b.index" in SMART_JS


def test_normal_canvas_sorts_files_before_upload_and_uploaded_results_afterward():
    assert "return sortCanvasMediaByFilename(raw.filter(isSupportedUploadFile));" in CANVAS_JS
    assert "const supported = sortCanvasMediaByFilename([...files].filter(file =>" in CANVAS_JS
    assert "const uploaded = sortCanvasMediaByFilename((data.files || []).map" in CANVAS_JS
    assert "entry => entry.source?.name || entry.file?.name || ''" in CANVAS_JS


def test_smart_canvas_sorts_files_before_upload_and_uploaded_results_afterward():
    assert "return sortSmartMediaByFilename(raw.filter(isSupportedUploadFile));" in SMART_JS
    assert "const supported = sortSmartMediaByFilename([...(files || [])].filter(isSupportedUploadFile))" in SMART_JS
    assert "return sortSmartMediaByFilename(uploaded, entry => entry.source?.name || entry.file?.name || '').map(entry => entry.file);" in SMART_JS
    assert "const fileList = sortSmartMediaByFilename([...(files || [])].filter(isSupportedUploadFile))" in SMART_JS


def test_local_path_drop_is_sorted_in_both_canvases():
    assert "const orderedPaths = sortCanvasMediaByFilename(paths);" in CANVAS_JS
    assert "body:JSON.stringify({paths:orderedPaths})" in CANVAS_JS
    assert "const orderedPaths = sortSmartMediaByFilename(paths);" in SMART_JS
    assert "body:JSON.stringify({paths:orderedPaths.slice(0, SMART_UPLOAD_MAX)})" in SMART_JS


def test_normal_canvas_bulk_drop_reuses_arrange_layout_before_group_bounds():
    layout_start = CANVAS_JS.index("function layoutUploadedMediaNodes(created, base)")
    layout_end = CANVAS_JS.index("function createGroupForUploadedNodes", layout_start)
    layout_body = CANVAS_JS[layout_start:layout_end]
    assert "render();" in layout_body
    assert "return arrangeIdsByConnections(list.map(node => node.id));" in layout_body
    assert "const gapX = 280;" not in layout_body
    assert "const gapY = 250;" not in layout_body

    upload_start = CANVAS_JS.index("async function uploadMediaFiles")
    upload_end = CANVAS_JS.index("async function uploadImages", upload_start)
    upload_body = CANVAS_JS[upload_start:upload_end]
    assert upload_body.index("layoutUploadedMediaNodes(created, base);") < upload_body.index(
        "createGroupForUploadedNodes(created, base)"
    )


def test_shared_arrange_layout_accounts_for_real_node_dimensions():
    arrange_start = CANVAS_JS.index("function arrangeIdsByConnections(ids)")
    arrange_end = CANVAS_JS.index("function arrangeSelectedCanvasNodes", arrange_start)
    arrange_body = CANVAS_JS[arrange_start:arrange_end]
    assert "const rectById = new Map" in arrange_body
    assert "colWidths[col] = Math.max" in arrange_body
    assert "rowHeights[row] = Math.max" in arrange_body
    assert "const columnGap = 72;" in arrange_body
    assert "const rowGap = 56;" in arrange_body
