import io
import json
import zipfile

import main


class FakeCanvasDatabase:
    def __init__(self):
        self.saved_canvas = None

    def load_projects(self):
        return [{"id": "default", "name": "默认项目", "order": 0}]

    def save_projects(self, projects):
        return None

    def save_canvas(self, canvas, touch=True):
        value = dict(canvas)
        value["revision"] = 1
        canvas.clear()
        canvas.update(value)
        self.saved_canvas = value
        return canvas


def _patch_package_paths(monkeypatch, tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setattr(main, "OUTPUT_INPUT_DIR", str(input_dir))
    monkeypatch.setattr(main, "OUTPUT_OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(main, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(main, "ASSETS_DIR", str(tmp_path))
    monkeypatch.setattr(main, "DATABASE", FakeCanvasDatabase())
    monkeypatch.setattr(main, "publish_entity_changed", lambda *args, **kwargs: None)
    return input_dir, output_dir


def _source_canvas():
    return {
        "id": "original-id",
        "title": "测试工程",
        "icon": "layers",
        "kind": "classic",
        "project": "default",
        "nodes": [{"id": "image-1", "type": "image", "url": "/assets/output/sample.png", "nested": {"url": "/assets/output/sample.png"}}],
        "connections": [],
        "viewport": {"x": 10, "y": 20, "scale": 1},
    }


def test_canvas_package_roundtrip_rewrites_local_resources(monkeypatch, tmp_path):
    _input_dir, output_dir = _patch_package_paths(monkeypatch, tmp_path)
    (output_dir / "sample.png").write_bytes(b"sample-bytes")

    archive, manifest = main.build_canvas_package_archive(_source_canvas())
    names = set(zipfile.ZipFile(io.BytesIO(archive)).namelist())
    assert {"manifest.json", "canvas.json", "resources/sample.png"}.issubset(names)
    assert manifest["stats"]["resource_count"] == 1

    package_path = tmp_path / "project.zip"
    package_path.write_bytes(archive)
    imported, meta = main.import_canvas_package_archive(str(package_path))

    assert imported["id"] != "original-id"
    assert imported["title"] == "测试工程"
    imported_url = imported["nodes"][0]["url"]
    assert imported_url.startswith("/assets/input/canvas_package_")
    assert main.output_file_from_url(imported_url)
    assert meta == {"format": main.CANVAS_PACKAGE_FORMAT, "version": 1, "resource_count": 1, "node_count": 1, "connection_count": 0}


def test_canvas_package_rejects_unsafe_archive_paths_without_writing(monkeypatch, tmp_path):
    _patch_package_paths(monkeypatch, tmp_path)
    package_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("../escape.txt", b"bad")
        archive.writestr("canvas.json", json.dumps({"nodes": [], "connections": []}))

    try:
        main.import_canvas_package_archive(str(package_path))
    except main.CanvasPackageError as exc:
        assert "不安全路径" in str(exc)
    else:
        raise AssertionError("unsafe path was accepted")
    assert not list((tmp_path / "input").iterdir())


def test_canvas_package_imports_legacy_browser_zip(monkeypatch, tmp_path):
    _input_dir, _output_dir = _patch_package_paths(monkeypatch, tmp_path)
    package_path = tmp_path / "legacy.zip"
    canvas = _source_canvas()
    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("canvas.json", json.dumps(canvas))
        archive.writestr("resources/sample.png", b"legacy-bytes")
        archive.writestr("resources-manifest.json", json.dumps({"resources": [{"url": "/output/sample.png", "file": "resources/sample.png", "name": "sample.png"}]}))

    imported, meta = main.import_canvas_package_archive(str(package_path))
    assert imported["id"] != canvas["id"]
    assert meta["resource_count"] == 1


def test_canvas_package_rejects_broken_canvas_json(monkeypatch, tmp_path):
    _patch_package_paths(monkeypatch, tmp_path)
    package_path = tmp_path / "broken.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"format": main.CANVAS_PACKAGE_FORMAT, "version": 1, "resources": []}))
        archive.writestr("canvas.json", b"{broken")

    try:
        main.import_canvas_package_archive(str(package_path))
    except main.CanvasPackageError as exc:
        assert "canvas.json" in str(exc)
    else:
        raise AssertionError("broken canvas JSON was accepted")
