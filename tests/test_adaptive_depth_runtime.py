from __future__ import annotations

import hashlib
import json
import socket
import urllib.request
import zipfile
from pathlib import Path
import shutil

from canvas_core.component_profiles import RuntimeCapabilities, select_variant
from canvas_core.person_depth_components import PersonDepthComponentManager
from distribution.service import Center
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def runtime_manifest(package: Path) -> dict:
    return {
        "schema_version": 2,
        "component": "video-depth-runtime",
        "version": "1.2.3",
        "enabled": True,
        "command": [],
        "required_paths": [],
        "packages": [{
            "id": "runtime-windows-x86_64-cpu",
            "size": package.stat().st_size,
            "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "domestic_url": "",
            "official_url": "",
        }],
        "variants": [{
            "id": "windows-x86_64-cuda126",
            "priority": 100,
            "constraints": {"os": "windows", "arch": "x86_64", "accelerator": "cuda", "min_compute_capability": 7.0},
            "command": ["runtime/worker.exe"],
            "required_paths": ["runtime/worker.exe"],
            "packages": ["runtime-windows-x86_64-cuda126"],
        }, {
            "id": "windows-x86_64-cpu",
            "priority": 10,
            "constraints": {"os": "windows", "arch": "x86_64", "accelerator": "cpu"},
            "command": ["runtime/worker.exe"],
            "required_paths": ["runtime/worker.exe"],
            "packages": ["runtime-windows-x86_64-cpu"],
        }],
    }


def test_runtime_profile_prefers_compatible_cuda_and_falls_back_to_cpu():
    rows = [
        {"id": "cuda128", "priority": 110, "constraints": {"accelerator": "cuda", "min_compute_capability": 12.0, "min_driver_version": "570.65"}},
        {"id": "cuda", "priority": 100, "constraints": {"accelerator": "cuda", "min_compute_capability": 7.0, "max_compute_capability": 9.9, "min_driver_version": "560.76"}},
        {"id": "cpu", "priority": 10, "constraints": {"accelerator": "cpu"}},
    ]
    assert select_variant(rows, RuntimeCapabilities("windows", "x86_64", "cuda", compute_capability=8.6, driver_version="572.83"))["id"] == "cuda"
    assert select_variant(rows, RuntimeCapabilities("windows", "x86_64", "cuda", compute_capability=12.0, driver_version="576.80"))["id"] == "cuda128"
    assert select_variant(rows, RuntimeCapabilities("windows", "x86_64", "cpu"))["id"] == "cpu"
    assert select_variant(rows, RuntimeCapabilities("windows", "x86_64", "cuda", compute_capability=6.1))["id"] == "cpu"
    assert select_variant(rows, RuntimeCapabilities("windows", "x86_64", "cuda", compute_capability=8.6, driver_version="552.44"))["id"] == "cpu"


def test_schema_v2_manager_selects_cpu_package_and_command(tmp_path):
    package = tmp_path / "cpu.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("runtime/worker.exe", b"worker")
    manifest = runtime_manifest(package)
    manager = PersonDepthComponentManager(
        tmp_path / "component",
        manifest=manifest,
        component_name="video-depth-runtime",
        display_name="深度视频运行时",
        lan_path="video-depth-runtime",
        capability_provider=lambda: RuntimeCapabilities("windows", "x86_64", "cpu"),
        smoke_runner=lambda _command, _root: None,
    )
    assert manager.selected_variant_id == "windows-x86_64-cpu"
    assert [spec.package_id for spec in manager.specs] == ["runtime-windows-x86_64-cpu"]
    assert manager.install_local_archives({"runtime-windows-x86_64-cpu": package})
    assert manager.worker_command()[0].endswith("runtime\\worker.exe")


def test_lan_runtime_falls_back_to_cpu_and_remembers_profile(tmp_path, monkeypatch):
    archive = tmp_path / "runtime.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("runtime/worker.exe", b"worker")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    variants = [{
        "id": "cuda", "priority": 100,
        "constraints": {"accelerator": "cuda", "min_compute_capability": 7.0},
        "command": ["runtime/worker.exe"], "required_paths": ["runtime/worker.exe"],
        "packages": ["cuda-package"],
    }, {
        "id": "cpu", "priority": 10,
        "constraints": {"accelerator": "cpu"},
        "command": ["runtime/worker.exe"], "required_paths": ["runtime/worker.exe"],
        "packages": ["cpu-package"],
    }]
    manifest = {
        "schema_version": 2, "component": "video-depth-runtime", "version": "1.0.0",
        "enabled": True, "packages": [], "variants": variants,
    }
    manager = PersonDepthComponentManager(
        tmp_path / "component", manifest=manifest, component_name="video-depth-runtime",
        capability_provider=lambda: RuntimeCapabilities("windows", "x86_64", "cuda", compute_capability=8.6),
        smoke_runner=lambda _command, _root: (
            (_ for _ in ()).throw(RuntimeError("cuda smoke failed"))
            if manager.selected_variant_id == "cuda" else None
        ),
    )

    def copy_package(_url, target, _spec, *_args):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive, target)

    monkeypatch.setattr(manager, "_download_package_with_retries", copy_package)
    payload = {
        "version": "1.0.0", "variants": variants,
        "packages": [
            {"id": "cuda-package", "size": archive.stat().st_size, "sha256": digest},
            {"id": "cpu-package", "size": archive.stat().st_size, "sha256": digest},
        ],
    }
    assert manager._download_lan_packages("http://test", payload)
    assert manager.selected_variant_id == "cpu"
    assert manager.status()["attempts"][0]["source"].endswith("cuda")
    reloaded = PersonDepthComponentManager(
        tmp_path / "component", manifest=manifest, component_name="video-depth-runtime",
        capability_provider=lambda: RuntimeCapabilities("windows", "x86_64", "cuda", compute_capability=8.6),
        smoke_runner=lambda _command, _root: None,
    )
    assert reloaded.selected_variant_id == "cpu"
    assert reloaded.verify_installed()


def test_distribution_imports_and_serves_runtime_package(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    package = source / "runtime-cpu.zip"
    package.write_bytes(b"runtime-package")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 2,
        "component": "video-depth-runtime",
        "version": "1.2.3",
        "packages": [{"id": "runtime-cpu", "file": package.name, "size": package.stat().st_size, "sha256": digest}],
        "variants": [{"id": "cpu", "priority": 1, "constraints": {"accelerator": "cpu"}, "packages": ["runtime-cpu"]}],
    }
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    center = Center(tmp_path / "data", 0, 0)
    center.import_release(source, "video-depth-runtime")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = __import__("http.server", fromlist=["ThreadingHTTPServer"]).ThreadingHTTPServer(
        ("127.0.0.1", port), center.handler(False)
    )
    import threading
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/video-depth-runtime/manifest.json") as response:
            envelope = json.load(response)
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(envelope["public_key"])).verify(
            bytes.fromhex(envelope["signature"]), envelope["payload"].encode("utf-8")
        )
        published = json.loads(envelope["payload"])
        assert published["protocol_version"] == 2
        assert published["variants"][0]["packages"] == ["runtime-cpu"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/video-depth-runtime/packages/runtime-cpu") as response:
            assert response.read() == package.read_bytes()
    finally:
        server.shutdown()
        server.server_close()


def test_distribution_imports_and_serves_adaptive_video_model(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    package = source / "vda-small.pth"
    package.write_bytes(b"small-model")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 2,
        "component": "video-depth",
        "version": "2.0.0",
        "packages": [{
            "id": "vda-small", "file": package.name, "size": package.stat().st_size,
            "sha256": digest, "target_path": "models/vda-small.pth",
        }],
        "variants": [{
            "id": "lite", "priority": 1, "constraints": {"accelerator": "cpu"},
            "command": ["models/vda-small.pth"], "required_paths": ["models/vda-small.pth"],
            "packages": ["vda-small"],
        }],
    }
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    center = Center(tmp_path / "data", 0, 0)
    center.import_release(source, "video-depth")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = __import__("http.server", fromlist=["ThreadingHTTPServer"]).ThreadingHTTPServer(
        ("127.0.0.1", port), center.handler(False)
    )
    import threading
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/video-depth/manifest.json") as response:
            envelope = json.load(response)
        payload = json.loads(envelope["payload"])
        assert payload["protocol_version"] == 2
        assert payload["variants"][0]["packages"] == ["vda-small"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/video-depth/packages/vda-small") as response:
            assert response.read() == package.read_bytes()
    finally:
        server.shutdown()
        server.server_close()
