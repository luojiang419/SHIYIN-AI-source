from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from canvas_core.remote_clip_storage import (
    RemoteClipConfig,
    RemoteClipStorageError,
    clip_identity_from_path,
    delete_video_clip,
    remote_clip_url,
    upload_video_clip,
)


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
