import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from canvas_core.bridge_sync import sync_film_bridge_canvas
from canvas_core.film_workflow import FilmWorkflowProxy, workflow_context
from canvas_core.film_workflow import FilmWorkflowUnavailable
from contextlib import contextmanager


@contextmanager
def discovery_server(project_id=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            data = {"app": "filmstoryboard", "workflow_version": 1,
                    "project_id": project_id, "token": "test-token"} if project_id else {"app": "other-app"}
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps(data).encode())
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_discovery_skips_occupied_port_and_selects_matching_project(tmp_path):
    with discovery_server() as occupied, discovery_server("other") as other, discovery_server("target") as target:
        proxy = FilmWorkflowProxy(resolve_media=lambda _: None, media_url=lambda p: p,
            media_root=str(tmp_path), allowed_roots=[str(tmp_path)])
        proxy.ports = (occupied, other, target)
        assert proxy._discover("target")["project_id"] == "target"
        assert proxy.base == f"http://127.0.0.1:{target}"
        with pytest.raises(ValueError, match="多个 film"):
            proxy._discover(None)
        with pytest.raises(ValueError, match="源项目"):
            proxy._discover("missing")


def test_discovery_offline_is_retryable_and_does_not_accept_unrelated_service(tmp_path):
    with discovery_server() as occupied:
        proxy = FilmWorkflowProxy(resolve_media=lambda _: None, media_url=lambda p: p,
            media_root=str(tmp_path), allowed_roots=[str(tmp_path)], port=occupied)
        with pytest.raises(FilmWorkflowUnavailable, match="自动重连"):
            proxy._discover(None)


def fixture():
    frame = {"stable_id": "frame:a", "url": "/input/a.png", "width": 16, "height": 9,
             "relative_path": "images/a.png", "metadata": {"source_storyboard_asset_id": "asset-a"}}
    manifest = {"bridge_id": "film:project:board", "direction": "film-to-shiyin", "source": {"project_id": "project", "board_id": "board"},
                "canvas": {"workflow": "film-production-v1"}, "storyboard": {"board_name": "测试画板"}, "checksums": {"images/a.png": "a" * 64}}
    canvas = {"id": "canvas-a", "nodes": [], "connections": []}
    result = sync_film_bridge_canvas(canvas, manifest, [frame])
    return canvas, manifest, frame, result


def test_export_creates_named_board_three_function_groups_and_chain():
    graph, _, _, result = fixture()
    groups = [n for n in graph["nodes"] if n["type"] == "group"]
    assert [n["title"] for n in groups] == ["测试画板", "准备资产", "确认镜头", "视频生成"]
    assert len(result["workflow_node_ids"]) == 3
    assert len(graph["connections"]) == 3
    prepare, group, frames = workflow_context(graph, result["workflow_node_ids"][-1])
    assert prepare["type"] == "film-prepare-assets"
    assert group["bridgeProjectId"] == "project"
    assert frames[0]["bridgeSourceAssetId"] == "asset-a"


def test_repeat_preserves_parameters_positions_disconnections_and_old_exports():
    graph, manifest, frame, result = fixture()
    step = next(n for n in graph["nodes"] if n["type"] == "film-prepare-assets")
    step.update(x=9000, workflowScriptId="script-1", workflowParameters={"quality": "high"})
    graph["connections"].pop()
    expected = copy.deepcopy(graph)
    sync_film_bridge_canvas(graph, manifest, [frame])
    assert graph == expected
    old = {"nodes": [], "connections": []}
    manifest.pop("canvas")
    sync_film_bridge_canvas(old, manifest, [frame])
    assert len(old["nodes"]) == 2
    assert next(n for n in old["nodes"] if n["type"] == "group")["bridgeProjectId"] == "project"


def test_list_requires_direct_confirm_and_unique_root():
    graph, _, _, result = fixture()
    video_id = result["workflow_node_ids"][-1]
    graph["connections"][-1]["from"] = result["group"]["id"]
    with pytest.raises(ValueError, match="唯一"):
        workflow_context(graph, video_id)
    graph["connections"][-1]["from"] = result["workflow_node_ids"][1]
    graph["nodes"].append({"id": "other", "type": "group", "items": []})
    graph["connections"].append({"from": "other", "to": result["workflow_node_ids"][0]})
    with pytest.raises(ValueError, match="一个图片组"):
        workflow_context(graph, video_id)


def test_proxy_calls_real_http_scopes_project_and_materializes_media(tmp_path):
    graph, _, _, result = fixture()
    root = tmp_path / "media"
    root.mkdir()
    (root / "a.png").write_bytes(b"image bytes")
    media_id = "a" * 64 + ".png"
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            if self.path == "/capabilities":
                body = json.dumps({"app": "filmstoryboard", "workflow_version": 1, "project_id": "project", "token": "secret"}).encode()
            else:
                assert self.headers["X-Workflow-Token"] == "secret"
                body = b"generated image"
            self.send_response(200); self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            assert self.headers["X-Workflow-Token"] == "secret"
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(body)
            data = {"ok": True, "snapshot": {"scriptId": "script-1", "shots": [{"frame": f"/media/{media_id}"}]}}
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(data).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        proxy = FilmWorkflowProxy(resolve_media=lambda _: str(root / "a.png"), media_url=lambda p: "/input/" + Path(p).name,
                                  media_root=str(root), allowed_roots=[str(root)], port=server.server_port)
        response = proxy.execute({"node_id": result["workflow_node_ids"][0], "action": "sync"}, graph, "canvas-a")
        assert calls[0]["project_id"] == "project"
        assert calls[0]["source_board_id"] == "board"
        assert calls[0]["frames"][0]["source_asset_id"] == "asset-a"
        assert response["snapshot"]["shots"][0]["frame"].startswith("/input/film_")
        assert (root / ("film_" + media_id)).read_bytes() == b"generated image"
        graph["nodes"][0]["bridgeProjectId"] = "other-project"
        with pytest.raises(ValueError, match="源项目"):
            proxy.execute({"node_id": result["workflow_node_ids"][0], "action": "sync"}, graph, "canvas-a")
    finally:
        server.shutdown(); server.server_close(); thread.join()


def test_proxy_rejects_outside_media_root(tmp_path):
    allowed = tmp_path / "allowed"; allowed.mkdir()
    secret = tmp_path / "private.txt"; secret.write_text("private")
    proxy = FilmWorkflowProxy(resolve_media=lambda _: str(secret), media_url=lambda p: p, media_root=str(allowed), allowed_roots=[str(allowed)])
    with pytest.raises(ValueError, match="媒体目录"):
        proxy._image("/private")


def test_main_http_workflow_and_package_roundtrip(tmp_path):
    import os
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / "tests/support/film_workflow_http_check.py")],
        cwd=root, env={**os.environ, "CANVAS_DATA_DIR": str(tmp_path / "data"), "CANVAS_PORT": "3000"},
        capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
