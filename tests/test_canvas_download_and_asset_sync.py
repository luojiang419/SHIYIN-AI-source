from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANVAS_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
ASSET_MANAGER_JS = (ROOT / "static/js/asset-manager.js").read_text(encoding="utf-8")


def _body(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


def test_output_context_download_saves_each_file_to_selected_directory():
    body = _body(CANVAS_JS, "async function downloadOutputNodeImages", "async function downloadGroupNodeImages")
    assert "saveCanvasItemsToDirectory" in body
    assert "showDirectoryPicker" in CANVAS_JS
    assert "requestDesktopCanvasDownload" in CANVAS_JS
    assert "desktop-canvas-download:save" in CANVAS_JS
    assert "getFileHandle(filename, {create:true})" in CANVAS_JS
    assert "/api/canvas-assets/download" not in body
    assert ".zip`" not in body


def test_canvas_download_handles_duplicate_names_and_cancelled_folder_picker():
    assert "function uniqueCanvasDownloadName(name, used)" in CANVAS_JS
    assert "while(used.has(candidate.toLowerCase()))" in CANVAS_JS
    assert "error?.name === 'AbortError'" in CANVAS_JS
    assert "await writable.write(await response.blob())" in CANVAS_JS


def test_desktop_download_bridge_uses_native_folder_and_file_commands():
    updater = (ROOT / "static/js/desktop-updater.js").read_text(encoding="utf-8")
    tauri = (ROOT / "src-tauri/src/lib.rs").read_text(encoding="utf-8")
    assert "desktop-canvas-download:save" in updater
    assert "choose_download_directory" in updater
    assert "write_download_file" in updater
    assert "fn choose_download_directory" in tauri
    assert "fn write_download_file" in tauri
    assert "while target.exists()" in tauri
    assert 'format!("{stem} ({sequence}){extension}")' in tauri


def test_all_canvas_media_batch_downloads_save_individual_files():
    smart = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
    assert "await saveCanvasItemsToDirectory" in CANVAS_JS
    assert "canvas-group.zip" not in CANVAS_JS
    assert "canvas-log-${log.id || Date.now()}.zip" not in CANVAS_JS
    assert "async function saveDownloadImageItems" in smart
    assert "zipDownloadImageItems" not in smart


def test_canvas_asset_tab_loads_on_entry_and_tracks_canvas_realtime_changes():
    tab_body = _body(ASSET_MANAGER_JS, "document.querySelectorAll('[data-tab]')", "refreshBtn?.addEventListener")
    assert "ensureTabData(activeTab).catch" in tab_body
    assert "canvasAssetsLoadedToken !== canvasAssetsChangeToken" in ASSET_MANAGER_JS
    assert "function handleCanvasAssetRealtimeMessage(data)" in ASSET_MANAGER_JS
    assert "data.topic === 'canvas'" in ASSET_MANAGER_JS
    assert "scheduleCanvasAssetsRefresh" in ASSET_MANAGER_JS
    assert "window.addEventListener('canvas-realtime-message'" in ASSET_MANAGER_JS
