from __future__ import annotations

import hashlib
import json
import socket
import urllib.request
from pathlib import Path

from canvas_core.person_depth_components import PersonDepthComponentManager
from canvas_core.person_depth_lan import PersonDepthLanServer


def video_manifest(content: bytes) -> dict:
    return {
        "schema_version": 1,
        "component": "video-depth",
        "version": "test-1",
        "enabled": True,
        "command": ["models/video-depth-anything-base/video_depth_anything_vitb.pth"],
        "required_paths": ["models/video-depth-anything-base/video_depth_anything_vitb.pth"],
        "packages": [{
            "id": "vda-base-model",
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "target_path": "models/video-depth-anything-base/video_depth_anything_vitb.pth",
            "domestic_url": "https://mirror.invalid/model.pth",
            "official_url": "https://official.invalid/model.pth",
        }],
    }


def manager(root: Path, content: bytes) -> PersonDepthComponentManager:
    return PersonDepthComponentManager(
        root,
        manifest=video_manifest(content),
        component_name="video-depth",
        display_name="深度视频模型",
        lan_path="video-depth",
        smoke_runner=lambda _command, _root: None,
    )


def test_single_model_file_installs_to_declared_target(tmp_path):
    content = b"vda-model-content"
    source = tmp_path / "video_depth_anything_vitb.pth"
    source.write_bytes(content)
    component = manager(tmp_path / "component", content)

    assert component.install_local_archives({"vda-base-model": source}, source_label="测试模型") is True
    installation = component.installation_path()
    assert installation is not None
    assert (installation / "models/video-depth-anything-base/video_depth_anything_vitb.pth").read_bytes() == content
    assert component.public_status()["message"] == "深度视频模型已就绪"


def test_shared_lan_server_serves_and_transfers_video_depth_model(tmp_path):
    content = b"shared-vda-model"
    source_file = tmp_path / "source.pth"
    source_file.write_bytes(content)
    source = manager(tmp_path / "source-component", content)
    source.install_local_archives({"vda-base-model": source_file}, source_label="源机器")
    client = manager(tmp_path / "client-component", content)

    class PersonStub:
        component_root = tmp_path / "person-depth"
        manifest = {"version": "test"}
        def installation_path(self): return None
        def verify_installed(self, *, run_smoke=False): return False
        def _read_current(self): return {}

    server = PersonDepthLanServer(PersonStub(), source)  # type: ignore[arg-type]
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    try:
        assert server.configure(True, "127.0.0.1", port)["running"] is True
        manifest = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/video-depth/manifest.json").read())
        assert manifest["component"] == "video-depth"
        assert manifest["total_bytes"] == len(content)
        client.set_lan_source(f"http://127.0.0.1:{port}")
        assert client._download_lan_files() is True
        installed = client.installation_path()
        assert installed is not None
        assert (installed / "models/video-depth-anything-base/video_depth_anything_vitb.pth").read_bytes() == content
        assert client.status()["source_label"] == "局域网服务器"
    finally:
        server.stop()
