from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANVAS_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
CANVAS_CSS = (ROOT / "static/css/canvas.css").read_text(encoding="utf-8")


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
    assert "body:JSON.stringify({paths:orderedPaths})" in SMART_JS


def test_normal_canvas_bulk_drop_reuses_arrange_layout_before_group_bounds():
    layout_start = CANVAS_JS.index("function layoutUploadedMediaNodes(created, base)")
    layout_end = CANVAS_JS.index("function createGroupForUploadedNodes", layout_start)
    layout_body = CANVAS_JS[layout_start:layout_end]
    assert "render();" in layout_body
    assert "const columns = Math.max(1, Math.ceil(Math.sqrt(list.length * 4 / 3)));" in layout_body
    assert "const rows = Math.ceil(list.length / columns);" in layout_body
    assert "colWidths[col] = Math.max" in layout_body
    assert "rowHeights[row] = Math.max" in layout_body
    assert "CANVAS_NODE_LAYOUT_GAP" in layout_body
    assert "CANVAS_NODE_LAYOUT_ROW_GAP" in layout_body
    assert "const gapX = 280;" not in layout_body
    assert "const gapY = 250;" not in layout_body

    upload_start = CANVAS_JS.index("async function uploadMediaFiles")
    upload_end = CANVAS_JS.index("async function uploadImages", upload_start)
    upload_body = CANVAS_JS[upload_start:upload_end]
    assert upload_body.index("layoutUploadedMediaNodes(created, base);") < upload_body.index(
        "createGroupForUploadedNodes(created, base)"
    )
    group_start = CANVAS_JS.index("function createGroupForUploadedNodes(created, point)")
    group_end = CANVAS_JS.index("async function uploadMediaFiles", group_start)
    group_body = CANVAS_JS[group_start:group_end]
    assert "arrangeCanvasGroupContents(group.id, {skipUndo:true});" in group_body


def test_shared_arrange_layout_accounts_for_real_node_dimensions():
    arrange_start = CANVAS_JS.index("function arrangeIdsByConnections(ids)")
    arrange_end = CANVAS_JS.index("function arrangeSelectedCanvasNodes", arrange_start)
    arrange_body = CANVAS_JS[arrange_start:arrange_end]
    assert "const rectById = new Map" in arrange_body
    assert "const layerWidth = Math.max" in arrange_body
    assert "let layerY = startY" in arrange_body
    assert "const columnGap = 180;" in arrange_body
    assert "const rowGap = 56;" in arrange_body


def test_bulk_import_is_uncapped_and_local_path_import_uses_same_grid_and_group():
    assert "const CANVAS_UPLOAD_MAX" not in CANVAS_JS
    assert "const SMART_UPLOAD_MAX" not in SMART_JS
    assert ".slice(0, CANVAS_UPLOAD_MAX)" not in CANVAS_JS
    assert ".slice(0, SMART_UPLOAD_MAX)" not in SMART_JS
    assert "requested = [p for p in requested if str(p or \"\").strip()]" in (
        (ROOT / "main.py").read_text(encoding="utf-8")
    )
    local_start = CANVAS_JS.index("async function createImageCardsFromLocalPaths")
    local_end = CANVAS_JS.index("async function applyImageDropPayloadToBoard", local_start)
    local_body = CANVAS_JS[local_start:local_end]
    assert "layoutUploadedMediaNodes(created, base);" in local_body
    assert "created.group = createGroupForUploadedNodes(created, base);" in local_body


def test_import_grid_has_requested_48_item_shape_and_smart_canvas_uses_same_ratio():
    layout_start = CANVAS_JS.index("function layoutUploadedMediaNodes(created, base)")
    layout_end = CANVAS_JS.index("function createGroupForUploadedNodes", layout_start)
    layout_body = CANVAS_JS[layout_start:layout_end]
    assert "Math.ceil(Math.sqrt(list.length * 4 / 3))" in layout_body
    assert "const rows = Math.ceil(list.length / columns);" in layout_body
    assert "function smartMediaGridColumns(count)" in SMART_JS
    assert "Math.ceil(Math.sqrt(Math.max(1, Number(count) || 1) * 4 / 3))" in SMART_JS


def test_group_headers_show_image_count_next_to_group_title():
    assert "const groupImageCount = node.type === 'group'" in CANVAS_JS
    assert "<span class=\"group-image-count\">${groupImageCount}张</span>" in CANVAS_JS
    assert "<div class=\"node-title-wrap\"><span class=\"node-title\">${displayTitle}</span>${groupCountHtml}" in CANVAS_JS
    assert ".group-image-count" in (ROOT / "static/css/canvas.css").read_text(encoding="utf-8")
    assert "const smartGroupImageCount = isSmartGroup ? smartGroupImageRefs(node).length" in SMART_JS
    assert "<span class=\"group-image-count\">${smartGroupImageCount}张</span>" in SMART_JS
    assert "<div class=\"node-title-wrap\"><div class=\"node-title\">${title}</div>${smartGroupCountHtml}" in SMART_JS


def test_selected_or_hovered_image_node_raises_its_floating_controls_above_neighbors():
    assert ".node.image-node:hover" in CANVAS_CSS
    assert ".node.image-node.selected" in CANVAS_CSS
    assert "z-index:1000" in CANVAS_CSS
