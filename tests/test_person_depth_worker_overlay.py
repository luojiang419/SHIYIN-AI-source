import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from canvas_core.person_depth_client import PersonDepthWorkerClient
from canvas_core.person_depth_components import PersonDepthComponentUnavailable


def test_verified_512_worker_is_copied_beside_fixed_models(tmp_path):
    source = tmp_path / "bundle" / "person-depth-worker-512.exe"
    source.parent.mkdir()
    source.write_bytes(b"verified worker")
    root = tmp_path / "installed-component"
    root.mkdir()
    client = PersonDepthWorkerClient(component_manager=None)
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    with patch.object(client, "_worker_override_source", return_value=source), patch(
        "canvas_core.person_depth_client.PERSON_DEPTH_WORKER_512_SHA256", expected
    ):
        command = client._worker_command_with_override(["original.exe"], root)
        repeated = client._worker_command_with_override(["original.exe"], root)
    target = root / "runtime/person-depth-worker-512-vram.exe"
    assert command == repeated == [str(target)]
    assert target.read_bytes() == source.read_bytes()
    assert not list(target.parent.glob("*.tmp"))


def test_unverified_worker_is_not_installed(tmp_path):
    source = tmp_path / "person-depth-worker-512.exe"
    source.write_bytes(b"tampered")
    root = tmp_path / "installed-component"
    root.mkdir()
    client = PersonDepthWorkerClient(component_manager=None)
    with patch.object(client, "_worker_override_source", return_value=source):
        with pytest.raises(PersonDepthComponentUnavailable, match="校验失败"):
            client._worker_command_with_override(["original.exe"], root)
    assert not (root / "runtime").exists()


def test_source_mode_uses_worker_source_and_fixed_component_models(tmp_path):
    client = PersonDepthWorkerClient(component_manager=None)
    with patch("canvas_core.person_depth_client.sys.frozen", False, create=True), patch.dict(
        "canvas_core.person_depth_client.os.environ", {}, clear=True
    ):
        command = client._source_worker_command(tmp_path)
    assert command[0]
    assert Path(command[1]).name == "worker.py"
    assert command[2:] == ["--component-root", str(tmp_path), "--stdio"]
