from __future__ import annotations

import hashlib
import json
import socket
import tempfile
import urllib.request
from pathlib import Path

from canvas_core.person_depth_lan import PersonDepthLanServer
from canvas_core.person_depth_components import PersonDepthComponentManager


class FakeManager:
    def __init__(self, root: Path) -> None:
        self.component_root = root / "data" / "system" / "components" / "person-depth"
        self.installation = self.component_root / "installations" / "test"
        self.installation.mkdir(parents=True)
        (self.installation / "runtime").mkdir()
        (self.installation / "runtime" / "worker.exe").write_bytes(b"0123456789")
        self.manifest = {"version": "1.0.0-test"}

    def installation_path(self):
        return self.installation

    def verify_installed(self, *, run_smoke: bool = False):
        return True

    def _read_current(self):
        return {"installation": "test"}


def test_lan_server_serves_manifest_and_byte_ranges():
    with tempfile.TemporaryDirectory() as tmp:
        manager = FakeManager(Path(tmp))
        service = PersonDepthLanServer(manager)  # type: ignore[arg-type]
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        try:
            status = service.configure(True, "127.0.0.1", port)
            assert status["running"] is True
            manifest = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/person-depth/manifest.json").read())
            assert manifest["protocol_version"] == 1
            assert manifest["total_bytes"] == 10
            assert manifest["files"][0]["sha256"] == hashlib.sha256(b"0123456789").hexdigest()
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/person-depth/files/runtime/worker.exe",
                headers={"Range": "bytes=2-5"},
            )
            with urllib.request.urlopen(request) as response:
                assert response.status == 206
                assert response.headers["Content-Range"] == "bytes 2-5/10"
                assert response.read() == b"2345"

            update_root = service._update_roots()[1]
            update_root.mkdir(parents=True, exist_ok=True)
            installer = update_root / "SHIYIN-AI-Setup-1.2.3.exe"
            installer.write_bytes(b"installer-content")
            digest = hashlib.sha256(installer.read_bytes()).hexdigest()
            checksum = installer.with_name(f"{installer.name}.sha256")
            checksum.write_text(f"{digest}  {installer.name}\n", encoding="utf-8")
            release = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/update/manifest.json").read())
            assert release["tag_name"] == "v1.2.3"
            assert release["assets"][0]["digest"] == f"sha256:{digest}"
            update_request = urllib.request.Request(
                release["assets"][0]["browser_download_url"], headers={"Range": "bytes=0-8"}
            )
            with urllib.request.urlopen(update_request) as response:
                assert response.status == 206
                assert response.read() == b"installer"
        finally:
            service.stop()


def test_client_directly_transfers_and_activates_lan_files_across_release_labels():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = FakeManager(root / "source")
        required = {
            "runtime/worker.exe": b"worker",
            "models/depth/config.json": b'{"depth":true}',
            "models/birefnet/config.json": b'{"mask":true}',
        }
        for relative, content in required.items():
            path = source.installation / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        source.manifest["version"] = "1.0.0-candidate.3"
        service = PersonDepthLanServer(source)  # type: ignore[arg-type]
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        manifest = {
            "schema_version": 1,
            "component": "person-depth",
            "version": "1.0.0",
            "enabled": True,
            "release_status": "released",
            "command": ["runtime/worker.exe"],
            "required_paths": list(required),
            "packages": [{
                "id": "fallback", "size": 1, "sha256": hashlib.sha256(b"x").hexdigest(),
                "domestic_url": "", "official_url": "http://127.0.0.1/fallback.zip",
            }],
        }
        client = PersonDepthComponentManager(
            root / "client", manifest=manifest, smoke_runner=lambda _command, _root: None
        )
        try:
            assert service.configure(True, "127.0.0.1", port)["running"] is True
            client.set_lan_source(f"http://127.0.0.1:{port}")
            assert client._download_lan_files() is True
            installed = client.installation_path()
            assert installed is not None
            for relative, content in required.items():
                assert (installed / relative).read_bytes() == content
            assert client.status()["source_label"] == "局域网服务器"
        finally:
            service.stop()
