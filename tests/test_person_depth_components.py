from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from canvas_core.person_depth_client import PersonDepthWorkerClient
from canvas_core.person_depth_components import (
    PersonDepthComponentManager,
    PersonDepthComponentUnavailable,
)


def make_archive(*, unsafe: bool = False) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("../outside.txt" if unsafe else "runtime/person-depth-worker.exe", b"worker")
        bundle.writestr("models/depth-anything-v2-large/config.json", b"{}")
        bundle.writestr("models/birefnet/config.json", b"{}")
    return buffer.getvalue()


def make_archive_with_files(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)
    return buffer.getvalue()


def make_manifest(archive: bytes, *, enabled: bool = True) -> dict[str, object]:
    return {
        "schema_version": 1,
        "component": "person-depth",
        "version": "1.0.0-test",
        "enabled": enabled,
        "message": "release pending",
        "command": ["runtime/person-depth-worker.exe"],
        "required_paths": [
            "runtime/person-depth-worker.exe",
            "models/depth-anything-v2-large/config.json",
            "models/birefnet/config.json",
        ],
        "packages": [
            {
                "id": "bundle",
                "size": len(archive),
                "sha256": hashlib.sha256(archive).hexdigest(),
                "domestic_url": "domestic://bundle",
                "official_url": "official://bundle",
            }
        ],
    }


def test_pending_manifest_never_starts_network_install():
    with tempfile.TemporaryDirectory() as temp_root:
        manager = PersonDepthComponentManager(
            Path(temp_root),
            manifest={
                "schema_version": 1,
                "component": "person-depth",
                "version": "1.0.0",
                "enabled": False,
                "message": "发布清单尚未配置",
                "command": ["runtime/person-depth-worker.exe"],
                "required_paths": [],
                "packages": [],
            },
        )
        assert manager.start_background() is False
        assert manager.public_status()["state"] == "unavailable"
        assert manager.public_status()["install_available"] is False
        assert "发布清单" in str(manager.public_status()["message"])


def test_domestic_archive_is_verified_smoked_and_atomically_activated():
    archive = make_archive()
    smoke_calls = []
    with tempfile.TemporaryDirectory() as temp_root:
        manager = PersonDepthComponentManager(
            Path(temp_root),
            manifest=make_manifest(archive),
            proxy_provider=lambda: {},
            smoke_runner=lambda command, root: smoke_calls.append((list(command), root)),
        )

        def fake_download(url, target, *_args):
            assert url == "domestic://bundle"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive)

        with patch.object(manager, "_download_url", side_effect=fake_download):
            assert manager.ensure_now() is True
        installation = manager.installation_path()
        assert installation is not None
        assert (installation / "runtime/person-depth-worker.exe").read_bytes() == b"worker"
        assert manager.worker_command()[0].endswith("runtime\\person-depth-worker.exe")
        assert smoke_calls and smoke_calls[0][1].parent == manager.staging_root
        assert manager.public_status()["state"] == "ready"
        assert manager.public_status()["progress"] == 1.0


def test_local_candidate_install_persists_manifest_and_survives_reload():
    archive = make_archive()
    smoke_calls = []
    with tempfile.TemporaryDirectory() as temp_root:
        root = Path(temp_root)
        archive_path = root / "candidate.zip"
        archive_path.write_bytes(archive)
        component_root = root / "component"
        manager = PersonDepthComponentManager(
            component_root,
            manifest=make_manifest(archive, enabled=False),
            smoke_runner=lambda command, install_root: smoke_calls.append((list(command), install_root)),
        )

        assert manager.install_local_archives({"bundle": archive_path}) is True
        assert manager.local_manifest_path.is_file()
        assert manager.public_status()["state"] == "ready"
        assert manager.public_status()["source_label"] == "本机私有候选包"
        assert smoke_calls

        reloaded = PersonDepthComponentManager(component_root, smoke_runner=lambda _command, _root: None)
        assert reloaded.manifest_path == manager.local_manifest_path
        assert reloaded.public_status()["ready"] is True
        assert reloaded.worker_command()[0].endswith("runtime\\person-depth-worker.exe")


def test_local_candidate_install_rejects_incomplete_package_set():
    archive = make_archive()
    with tempfile.TemporaryDirectory() as temp_root:
        manager = PersonDepthComponentManager(
            Path(temp_root),
            manifest=make_manifest(archive, enabled=False),
            smoke_runner=lambda _command, _root: None,
        )
        with pytest.raises(PersonDepthComponentUnavailable, match="本地候选包不完整"):
            manager.install_local_archives({})


def test_domestic_failure_falls_back_to_official_source():
    archive = make_archive()
    calls = []
    with tempfile.TemporaryDirectory() as temp_root:
        manager = PersonDepthComponentManager(
            Path(temp_root),
            manifest=make_manifest(archive),
            proxy_provider=lambda: {},
            smoke_runner=lambda _command, _root: None,
        )

        def fake_download(url, target, *_args):
            calls.append(url)
            if url.startswith("domestic:"):
                raise RuntimeError("mirror unavailable")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive)

        with patch.object(manager, "_download_url", side_effect=fake_download):
            assert manager.ensure_now() is True
        assert calls == ["domestic://bundle", "official://bundle"]
        assert manager.public_status()["source_label"] == "官方源直连"


def test_split_packages_are_downloaded_and_merged_before_activation():
    archives = {
        "runtime-001": make_archive_with_files({"runtime/person-depth-worker.exe": b"worker"}),
        "runtime-002": make_archive_with_files({"runtime/_internal/torch_cuda.dll": b"cuda"}),
        "models": make_archive_with_files(
            {
                "models/depth-anything-v2-large/config.json": b"{}",
                "models/birefnet/config.json": b"{}",
            }
        ),
    }
    manifest = {
        "schema_version": 1,
        "component": "person-depth",
        "version": "1.0.0-split-test",
        "enabled": True,
        "command": ["runtime/person-depth-worker.exe"],
        "required_paths": [
            "runtime/person-depth-worker.exe",
            "runtime/_internal/torch_cuda.dll",
            "models/depth-anything-v2-large/config.json",
            "models/birefnet/config.json",
        ],
        "packages": [
            {
                "id": package_id,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "domestic_url": f"memory://{package_id}",
                "official_url": "",
            }
            for package_id, content in archives.items()
        ],
    }
    with tempfile.TemporaryDirectory() as temp_root:
        manager = PersonDepthComponentManager(
            Path(temp_root),
            manifest=manifest,
            proxy_provider=lambda: {},
            smoke_runner=lambda _command, _root: None,
        )

        def fake_download(url, target, *_args):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archives[url.removeprefix("memory://")])

        with patch.object(manager, "_download_url", side_effect=fake_download):
            assert manager.ensure_now() is True
        installation = manager.installation_path()
        assert installation is not None
        assert (installation / "runtime/person-depth-worker.exe").read_bytes() == b"worker"
        assert (installation / "runtime/_internal/torch_cuda.dll").read_bytes() == b"cuda"
        assert manager.public_status()["downloaded_bytes"] == sum(map(len, archives.values()))


def test_zip_path_traversal_is_rejected_before_activation():
    archive = make_archive(unsafe=True)
    with tempfile.TemporaryDirectory() as temp_root:
        manager = PersonDepthComponentManager(
            Path(temp_root),
            manifest=make_manifest(archive),
            proxy_provider=lambda: {},
            smoke_runner=lambda _command, _root: None,
        )
        target = Path(temp_root) / "unsafe.zip"
        target.write_bytes(archive)
        with pytest.raises(PersonDepthComponentUnavailable, match="不安全路径"):
            manager._safe_extract(target, Path(temp_root) / "staging")
        assert not (Path(temp_root).parent / "outside.txt").exists()


def test_public_status_hides_local_paths_and_attempt_details():
    archive = make_archive()
    with tempfile.TemporaryDirectory() as temp_root:
        manager = PersonDepthComponentManager(Path(temp_root), manifest=make_manifest(archive))
        public = manager.public_status()
        assert public["consent_required"] is True
        for private_key in ("component_root", "manifest_path", "attempts", "license_notice", "error"):
            assert private_key not in public


def test_worker_client_uses_persistent_ndjson_protocol_with_unicode_temp_path(monkeypatch):
    script_source = """
import json, shutil, sys
for line in sys.stdin:
    request = json.loads(line)
    if request.get('op') == 'shutdown':
        break
    if request.get('op') == 'hello':
        response = {'id': request['id'], 'ok': True, 'protocol_version': 1}
    else:
        shutil.copyfile(request['input'], request['output'])
        response = {'id': request['id'], 'ok': True, 'width': 2, 'height': 3, 'bit_depth': request['bit_depth']}
    print(json.dumps(response), flush=True)
"""
    with tempfile.TemporaryDirectory(prefix="人物深度-") as temp_root:
        root = Path(temp_root)
        script = root / "fake_worker.py"
        script.write_text(script_source, encoding="utf-8")

        class FakeManager:
            def worker_command(self):
                return [sys.executable, str(script)]

            def installation_path(self):
                return root

        monkeypatch.setattr(tempfile, "tempdir", str(root))
        client = PersonDepthWorkerClient(FakeManager(), timeout=5)
        try:
            result = client.estimate(b"fake-png", bit_depth=16)
        finally:
            client.close()
        assert result.content == b"fake-png"
        assert (result.width, result.height, result.bit_depth) == (2, 3, 16)


def test_backend_exposes_person_depth_contract_without_replacing_fast_depth():
    root = Path(__file__).resolve().parents[1]
    main = (root / "main.py").read_text(encoding="utf-8")
    spec = (root / "canvas-backend.spec").read_text(encoding="utf-8")
    assert '@app.get("/api/person-depth/component/status")' in main
    assert '@app.post("/api/person-depth/component/install", status_code=202)' in main
    assert '@app.post("/api/person-depth/component/retry", status_code=202)' in main
    assert '@app.post("/api/person-depth/estimate")' in main
    assert '@app.post("/api/depth/estimate")' in main
    assert 'datas=[("canvas_core/person_depth_manifest.json", "canvas_core")]' in spec
    assert '"torch"' in spec and '"transformers"' in spec


def test_builtin_manifest_is_a_downloadable_split_release():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "canvas_core/person_depth_manifest.json").read_text(encoding="utf-8"))
    packages = manifest.get("packages") or []
    if not manifest.get("enabled"):
        pytest.skip("正式组件发布后由发布脚本启用内置 manifest")
    assert manifest["release_status"] == "released"
    assert len(packages) >= 3
    assert sum(str(package["id"]).startswith("runtime-windows-x64-") for package in packages) >= 2
    assert all(0 < int(package["size"]) < 2_000_000_000 for package in packages)
    assert all(len(str(package["sha256"])) == 64 for package in packages)
    assert all(str(package["official_url"]).startswith("https://github.com/") for package in packages)


def test_component_release_script_enforces_verified_prerelease_assets():
    root = Path(__file__).resolve().parents[1]
    script = (root / "tools/publish-person-depth-component.ps1").read_text(encoding="utf-8")
    assert "Package exceeds the GitHub safe asset limit" in script
    assert "Get-FileHash -LiteralPath $asset -Algorithm SHA256" in script
    assert "gh release create $tag" in script and "--draft" in script
    assert "gh release edit $tag" in script and "--prerelease" in script
    assert "Remote package verification failed" in script
    assert "$candidate.enabled = $true" in script
