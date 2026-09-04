from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANVAS_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
CANVAS_HTML = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
CANVAS_CSS = (ROOT / "static/css/canvas.css").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static/smart-canvas.html").read_text(encoding="utf-8")


def body(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index + len(start))
    return source[start_index:end_index]


def test_retired_smart_canvas_redirects_to_the_unified_canvas_entry():
    assert "location.replace(target)" in SMART_HTML
    assert "'/static/canvas.html'" in SMART_HTML


def test_media_node_menus_always_offer_add_to_assets_for_images_and_videos():
    toolbar = body(CANVAS_JS, "function mediaToolbarItemsForNode", "function classicMediaToolbarHtml")
    selection_hub = body(CANVAS_JS, "function renderSelectionHub", "const CANVAS_IMAGE_CAMERA_DEFAULTS")
    action = body(CANVAS_JS, "function runMediaQuickAction", "function startSelectionLink")

    assert "{id:'addAsset', label:'添加为素材', icon:'library-big'}" in CANVAS_JS
    assert "available.add('addAsset')" in toolbar
    assert "!items.some(item => item.id === 'addAsset')" in toolbar
    assert "target.mediaKind === 'video'" in selection_hub
    assert selection_hub.count("id:'addAsset'") >= 2
    assert "openCanvasAssetSaveDialog" in action


def test_add_to_assets_dialog_selects_an_explicit_library_category_and_name():
    dialog = body(CANVAS_JS, "function canvasWritableAssetLibraries", "function beginCanvasAssetInlineRename")

    for element_id in (
        "canvasAssetSaveModal",
        "canvasAssetSaveName",
        "canvasAssetSaveLibrary",
        "canvasAssetSaveCategory",
        "canvasAssetSaveConfirm",
    ):
        assert f'id="{element_id}"' in CANVAS_HTML
    assert "fetch('/api/asset-library')" in CANVAS_JS
    assert "String(category.type || 'image').toLowerCase() === 'image'" in dialog
    assert "{libraryId, categoryId, render:true}" in dialog
    assert "body:JSON.stringify({library_id:libraryId, category_id:cat.id, url, name})" in CANVAS_JS
    assert ".canvas-asset-save-modal.open" in CANVAS_CSS
    assert "feature=asset-quick-save.1" in CANVAS_HTML


def test_external_asset_drop_locks_the_current_destination_before_async_resolution():
    drop = body(CANVAS_JS, "function hasCanvasAssetSaveDrop", "gateAssetManagerBtn?.addEventListener")

    assert "types.includes('application/x-canvas-asset')" in drop
    assert "const destination = canvasAssetDropDestination();" in drop
    assert drop.index("const destination = canvasAssetDropDestination();") < drop.index("await resolveImageDropPayload")
    assert "uploadFilesToLibrary(payload.files, destination.libraryId, destination.categoryId)" in drop
    assert "'/api/asset-library/items/batch'" in drop
    assert "canvasAssetPanel?.addEventListener('drop', handleCanvasAssetDrop)" in drop
    assert ".canvas-asset-panel.drag-over" in CANVAS_CSS


def test_asset_card_name_double_click_uses_inline_rename_without_adding_a_node():
    rename = body(CANVAS_JS, "function beginCanvasAssetInlineRename", "function renameCanvasAssetItem")
    render = body(CANVAS_JS, "function renderCanvasAssetLibrary", "function toggleCanvasAssetLibrary")

    assert "canvas-asset-name-input" in rename
    assert "event.key === 'Enter'" in rename
    assert "event.key === 'Escape'" in rename
    assert "'/api/local-assets/items'" in rename
    assert "`/api/asset-library/items/${encodeURIComponent(item.id)}`" in rename
    assert "card.querySelector('.canvas-asset-name')?.addEventListener('dblclick'" in render
    assert "event.stopPropagation()" in render
    assert "event.target.closest('.canvas-asset-name,.canvas-asset-name-input,.canvas-asset-action')" in render
