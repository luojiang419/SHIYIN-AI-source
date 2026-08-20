from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from canvas_core.remote_clip_storage import (
    RemoteClipConfig,
    RemoteClipStorageError,
    clip_identity_from_path,
    default_remote_process_runner,
    delete_video_clip,
    remote_clip_url,
    remote_clip_config,
    upload_video_clip,
    validate_public_clip_url,
)


def test_windows_remote_process_runner_never_opens_console_window(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr("canvas_core.remote_clip_storage.os.name", "nt")
    monkeypatch.setattr("canvas_core.remote_clip_storage.subprocess.run", run)

    default_remote_process_runner(["ssh.exe", "example"])

    assert calls[0][1]["creationflags"] & 0x08000000 == 0x08000000


def test_all_remote_clip_processes_share_hidden_runner():
    import canvas_core.remote_clip_storage as remote_clip_storage

    tree = ast.parse(Path(remote_clip_storage.__file__).read_text(encoding="utf-8"))
    direct_runs = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
    ]

    assert len(direct_runs) == 1, "远端素材外部命令必须统一经过隐藏窗口运行器"


def test_clip_identity_and_public_url_are_stable():
    path = r"E:\data\accounts\abc\media\generated\canvases\canvas-1\video-clips\clip-2.mp4"
    assert clip_identity_from_path(path) == ("canvas-1", "clip-2")
    config = RemoteClipConfig(key_path="key")
    assert remote_clip_url(config, "acct", "canvas-1", "clip-2") == (
        "http://64.90.17.178:18080/clip/acct/canvas-1/clip-2.mp4"
    )


def test_clip_identity_rejects_unrelated_media():
    assert clip_identity_from_path("/assets/output/ordinary.mp4") is None


def test_upload_and_delete_use_dedicated_remote_tree(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video")
    key = tmp_path / "id_ed25519"
    key.write_text("dummy", encoding="utf-8")
    config = RemoteClipConfig(key_path=str(key))
    calls = []

    def runner(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr("canvas_core.remote_clip_storage._secure_key_path", lambda value: str(key))
    url = upload_video_clip(
        source,
        account_id="acct",
        canvas_id="canvas-1",
        clip_id="clip-2",
        config=config,
        runner=runner,
    )
    assert url.endswith("/clip/acct/canvas-1/clip-2.mp4")
    assert calls[0][-3:] == ["mkdir", "-p", "/opt/clipdata/acct/canvas-1"]
    assert calls[1][-1] == "root@64.90.17.178:/opt/clipdata/acct/canvas-1/clip-2.mp4"

    assert delete_video_clip(
        account_id="acct",
        canvas_id="canvas-1",
        clip_id="clip-2",
        config=config,
        runner=runner,
    )
    assert calls[-1][-3:] == ["rm", "-f", "--"] or calls[-1][-4:] == ["rm", "-f", "--", "/opt/clipdata/acct/canvas-1/clip-2.mp4"]
    assert calls[-1][-1] == "/opt/clipdata/acct/canvas-1/clip-2.mp4"


def test_remote_clip_paths_are_validated(tmp_path):
    key = tmp_path / "key"
    key.write_text("dummy", encoding="utf-8")
    config = RemoteClipConfig(key_path=str(key))
    with pytest.raises(RemoteClipStorageError):
        remote_clip_url(config, "../escape", "canvas", "clip")


def test_installed_runtime_reads_remote_clip_config_from_data_dir(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    key = tmp_path / "id_ed25519_1panel"
    key.write_text("dummy", encoding="utf-8")
    (config_dir / "remote-clip.json").write_text(
        '{"ssh_key_path": "' + str(key).replace("\\", "\\\\") + '", "public_base_url": "http://example.test/clip"}',
        encoding="utf-8",
    )
    config = remote_clip_config({"CANVAS_DATA_DIR": str(tmp_path)})
    assert config.enabled
    assert config.key_path == str(key)
    assert config.public_base_url == "http://example.test/clip"


def test_validate_public_clip_url_accepts_video_head(monkeypatch):
    class Response:
        status = 200
        headers = {"Content-Type": "video/mp4", "Content-Length": "12"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("canvas_core.remote_clip_storage.urllib.request.urlopen", lambda *args, **kwargs: Response())
    validate_public_clip_url("http://example.test/clip/a/c.mp4")


def test_validate_public_clip_url_reports_unreachable(monkeypatch):
    def fail(*_args, **_kwargs):
        raise urllib.error.URLError("connection refused")

    import urllib.error

    monkeypatch.setattr("canvas_core.remote_clip_storage.urllib.request.urlopen", fail)
    with pytest.raises(RemoteClipStorageError, match="公网素材地址无法访问"):
        validate_public_clip_url("http://example.test/clip/a/c.mp4")
