from __future__ import annotations

import importlib.util
import threading
import urllib.error
import urllib.request
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "tools" / "remote-clip-service" / "clip_media_server.py"
    spec = importlib.util.spec_from_file_location("clip_media_server_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_read_only_server_supports_head_get_and_range(tmp_path):
    module = load_module()
    target = tmp_path / "acct" / "canvas"
    target.mkdir(parents=True)
    payload = bytes(range(256))
    (target / "clip.mp4").write_bytes(payload)
    server = module.ThreadingHTTPServer(("127.0.0.1", 0), module.ClipHandler)
    server.clip_root = tmp_path
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/clip/acct/canvas/clip.mp4"
    try:
        request = urllib.request.Request(base, method="HEAD")
        with urllib.request.urlopen(request, timeout=3) as response:
            assert response.status == 200
            assert response.headers["Content-Type"] == "video/mp4"
            assert response.headers["Content-Length"] == "256"
        request = urllib.request.Request(base, headers={"Range": "bytes=10-19"})
        with urllib.request.urlopen(request, timeout=3) as response:
            assert response.status == 206
            assert response.read() == payload[10:20]
        request = urllib.request.Request(base, method="DELETE")
        try:
            urllib.request.urlopen(request, timeout=3)
        except urllib.error.HTTPError as error:
            assert error.code == 405
        else:
            raise AssertionError("read-only server accepted DELETE")
    finally:
        server.shutdown()
        server.server_close()


def test_gc_keeps_recent_files_and_reclaims_oldest_when_over_limit(tmp_path):
    gc_path = Path(__file__).parents[1] / "tools" / "remote-clip-service" / "clip_media_gc.py"
    spec = importlib.util.spec_from_file_location("clip_media_gc_test", gc_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    old = tmp_path / "old.mp4"
    recent = tmp_path / "recent.mp4"
    old.write_bytes(b"a" * 8)
    recent.write_bytes(b"b" * 8)
    old.touch()
    recent.touch()
    import os
    import time
    os.utime(old, (time.time() - 7200, time.time() - 7200))
    result = module.cleanup(tmp_path, max_bytes=10, min_age_seconds=3600)
    assert result["deleted"] == 1
    assert not old.exists()
    assert recent.exists()
