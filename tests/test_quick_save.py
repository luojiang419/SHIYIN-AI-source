import asyncio
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi import UploadFile
from starlette.requests import Request

import main
from canvas_core.quick_save import safe_download_name, save_stream


ROOT = Path(__file__).resolve().parents[1]


def request_for_quick_save() -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/app-settings/quick-save",
        "raw_path": b"/api/app-settings/quick-save",
        "query_string": b"",
        "headers": [(b"host", b"127.0.0.1:3000")],
        "client": ("127.0.0.1", 50120),
        "server": ("127.0.0.1", 3000),
    })


def test_safe_download_name_removes_path_and_windows_invalid_characters():
    assert safe_download_name(r"..\folder\bad:name?.png") == "bad_name_.png"
    assert safe_download_name(" . ") == "download.bin"


def test_save_stream_preserves_existing_files_and_cleans_failed_temporary_file():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        (directory / "result.txt").write_text("existing", encoding="utf-8")
        saved = save_stream(directory, "result.txt", lambda target: target.write(b"new"))
        assert saved.name == "result (2).txt"
        assert saved.read_bytes() == b"new"
        assert (directory / "result.txt").read_text(encoding="utf-8") == "existing"

        def fail(target):
            target.write(b"partial")
            raise OSError("disk failed")

        try:
            save_stream(directory, "failed.txt", fail)
        except OSError:
            pass
        else:
            raise AssertionError("writer failure should be propagated")
        assert not list(directory.glob(".shiyin-quick-save-*.part"))


def test_quick_save_endpoint_accepts_uploaded_blob_and_uses_unique_name():
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        (directory / "archive.zip").write_bytes(b"old")
        upload = UploadFile(filename="ignored.zip", file=BytesIO(b"zip-content"))
        with patch.object(main, "quick_save_configured_directory", return_value=directory):
            result = asyncio.run(main.quick_save_download(
                request_for_quick_save(),
                url="",
                name="archive.zip",
                file=upload,
            ))
        assert result["saved"] is True
        assert result["name"] == "archive (2).zip"
        assert (directory / result["name"]).read_bytes() == b"zip-content"


def test_quick_save_endpoint_streams_resolved_local_media():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source.mp4"
        source.write_bytes(b"video-bytes")
        destination = root / "downloads"
        with (
            patch.object(main, "quick_save_configured_directory", return_value=destination),
            patch.object(main, "output_file_from_url", return_value=str(source)),
        ):
            result = asyncio.run(main.quick_save_download(
                request_for_quick_save(),
                url="/assets/output/source.mp4",
                name="movie.mp4",
                file=None,
            ))
        assert (destination / result["name"]).read_bytes() == b"video-bytes"


def test_quick_save_frontend_is_loaded_on_download_surfaces_and_keeps_manual_fallback():
    pages = [
        "index.html",
        "canvas.html",
        "canvas-list.html",
        "works.html",
        "asset-manager.html",
        "ecommerce.html",
        "gpt-chat.html",
        "api-settings.html",
        "app-settings.html",
        "admin.html",
    ]
    for page in pages:
        assert "/static/js/quick-save.js" in (ROOT / "static" / page).read_text(encoding="utf-8")

    script = (ROOT / "static/js/quick-save.js").read_text(encoding="utf-8")
    styles = (ROOT / "static/css/app-settings.css").read_text(encoding="utf-8")
    assert "if(state.loaded && !isSilent()) return" in script
    assert "replayManualDownload(anchor)" in script
    assert "form.append('file', item.blob, name)" in script
    assert "form.append('url', url)" in script
    assert "BroadcastChannel(CHANNEL_NAME)" in script
    assert ".app-settings-output-control[hidden] { display:none !important; }" in styles


def test_batch_media_downloads_save_individual_files_without_zip_archives():
    canvas = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")
    smart = (ROOT / "static/js/smart-canvas.js").read_text(encoding="utf-8")
    assets = (ROOT / "static/js/asset-manager.js").read_text(encoding="utf-8")
    works = (ROOT / "static/js/works.js").read_text(encoding="utf-8")
    quick_save = (ROOT / "static/js/quick-save.js").read_text(encoding="utf-8")

    assert "window.showDirectoryPicker({mode:'readwrite'})" in quick_save
    assert "requestDesktopBatchSave(list)" in quick_save
    assert "getFileHandle(name, {create:true})" in quick_save
    assert "window.ShiyinQuickSave.saveAll" in canvas
    assert "saveDownloadImageItems" in smart
    assert "window.ShiyinQuickSave.saveAll" in assets
    assert "window.ShiyinQuickSave.saveAll(payload.items || [])" in works

    media_sources = canvas + smart + assets + works
    for archive_name in ("canvas-group.zip", "assets.zip", "local-assets.zip", "canvas-assets.zip"):
        assert archive_name not in media_sources
    assert "canvas-log-${log.id || Date.now()}.zip" not in canvas
