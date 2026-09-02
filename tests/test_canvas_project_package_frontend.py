from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIST_HTML = (ROOT / "static/canvas-list.html").read_text(encoding="utf-8")
LIST_JS = (ROOT / "static/js/canvas-list.js").read_text(encoding="utf-8")
CANVAS_HTML = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static/js/canvas.js").read_text(encoding="utf-8")


def test_canvas_list_exposes_project_package_import_and_backend_export():
    assert 'id="importCanvasPackageBtn"' in LIST_HTML
    assert 'accept=".zip,application/zip"' in LIST_HTML
    assert "function importCanvasPackage(file)" in LIST_JS
    assert "/api/canvas-packages/import" in LIST_JS
    assert "/export-package?name=" in LIST_JS
    assert "xhr.upload.onprogress" in LIST_JS
    assert "updateCanvasPackageProgress(100" in LIST_JS


def test_canvas_editor_prioritizes_project_package_drop_before_media_drop():
    assert "function importCanvasPackageFromDrop(file)" in CANVAS_JS
    assert "xhr.upload.onprogress" in CANVAS_JS
    assert "function canvasPackageFromTransfer(dataTransfer)" in CANVAS_JS
    dragover = CANVAS_JS[CANVAS_JS.index("board.addEventListener('dragover'"):CANVAS_JS.index("board.addEventListener('dragleave'")]
    drop = CANVAS_JS[CANVAS_JS.index("board.addEventListener('drop'"):CANVAS_JS.index("window.addEventListener('dragend'")]
    assert dragover.index("canvasPackageFromTransfer") < dragover.index("hasImageDropData")
    assert drop.index("canvasPackageFromTransfer") < drop.index("resolveImageDropPayload")
    assert "feature=canvas-package.1" in CANVAS_HTML
