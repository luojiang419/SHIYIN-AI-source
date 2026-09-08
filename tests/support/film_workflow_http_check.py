"""隔离 main API、真实直传接收/本机 HTTP/工程包往返。由 pytest 在临时数据目录执行。"""
import hashlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from PIL import Image
from fastapi.testclient import TestClient
from canvas_core import film_workflow
import main

buffer = BytesIO(); Image.new("RGB", (16, 9), "green").save(buffer, "PNG")
content = buffer.getvalue()
digest = hashlib.sha256(content).hexdigest()
calls = []


class FilmHandler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        self.send_response(200); self.end_headers()
        if self.path == "/capabilities":
            self.wfile.write(json.dumps({"app": "filmstoryboard", "workflow_version": 1, "project_id": "p", "token": "local-test"}).encode())
        else:
            assert self.headers["X-Workflow-Token"] == "local-test"
            self.wfile.write(content)
    def do_POST(self):
        assert self.headers["X-Workflow-Token"] == "local-test"
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        calls.append(body)
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "snapshot": {"scriptId": "script-p", "shots": [{"id": "shot-a", "frame": f"/media/{digest}.png", "prompt": "已编辑的镜头提示词"}]}}).encode())


server = ThreadingHTTPServer(("127.0.0.1", 0), FilmHandler)
thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
RealProxy = film_workflow.FilmWorkflowProxy


class IsolatedProxy(RealProxy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs, port=server.server_port)


film_workflow.FilmWorkflowProxy = IsolatedProxy
try:
    manifest = {"schema": "shiyin-film-bridge", "schema_version": 2, "bridge_id": "film:p:b", "direction": "film-to-shiyin",
        "source": {"project_id": "p", "board_id": "b"}, "canvas": {"workflow": "film-production-v1"},
        "storyboard": {"board_name": "工作流往返", "selected_variant": "original", "frames": [{"stable_id": "frame:b:0", "slot_index": 0,
            "shot_number": 1, "frame_index": 0, "relative_path": "images/a.png", "upload_name": "a.png", "width": 16, "height": 9,
            "sha256": digest, "metadata": {"source_storyboard_asset_id": "film-asset"}}]}}
    with TestClient(main.app, client=("127.0.0.1", 50000)) as client:
        # 实装复现：GP01 含同一个来源组和用户自建节点，不能被自动导出再次认领。
        legacy = main.new_canvas(title="GP01")
        legacy["nodes"] = [
            {"id": "old-group", "type": "group", "bridgeId": manifest["bridge_id"], "bridgeDirection": "film-to-shiyin",
             "bridgeBoardName": "工作流往返", "items": ["old-frame"]},
            {"id": "old-frame", "type": "image", "url": "/input/old-frame.png"},
            {"id": "user-prompt", "type": "prompt", "text": "用户的已有工作"}]
        main.save_canvas(legacy)
        legacy_before = json.dumps(main.load_canvas(legacy["id"]), sort_keys=True)
        receive = client.post("/api/canvas-bridges/film/receive-direct", data={"manifest": json.dumps(manifest)}, files={"frames": ("a.png", content, "image/png")})
        assert receive.status_code == 200, receive.text
        canvas = main.load_canvas(receive.json()["canvas_id"])
        assert canvas["id"] != legacy["id"]
        assert canvas["title"] == "工作流往返"
        assert canvas["filmBridgeOwner"] == {"bridgeId": manifest["bridge_id"], "canvasId": canvas["id"]}
        assert json.dumps(main.load_canvas(legacy["id"]), sort_keys=True) == legacy_before
        receipt_ids = receive.json()["workflow_node_ids"]
        assert len(receipt_ids) == 3
        assert set(receipt_ids) == {n["id"] for n in canvas["nodes"] if n.get("workflowKey")}
        assert len([n for n in canvas["nodes"] if n.get("type") == "group"]) == 4
        assert len(canvas["connections"]) == 3
        assert receive.json()["workflow_ready"] is True
        assert all(n.get("workflowScriptId") == "script-p" for n in canvas["nodes"] if n.get("workflowKey"))
        assert calls[0]["action"] == "sync", "backend initializes without opening any canvas page"
        assert client.post('/api/account/login', json={'account': 'jiang', 'password': 'jiang'}).status_code == 200
        prepare = next(n for n in canvas["nodes"] if n["type"] == "film-prepare-assets")
        response = client.post("/api/canvas-film-workflow", json={"canvas_id": canvas["id"], "node_id": prepare["id"], "action": "sync", "graph": canvas})
        assert response.status_code == 200, response.text
        snapshot = response.json()["snapshot"]
        assert calls[0]["frames"][0]["source_asset_id"] == "film-asset"
        assert snapshot["scriptId"] == "script-p"
        assert client.get(snapshot["shots"][0]["frame"]).content == content
        prepare.update(workflowScriptId="script-p", workflowSnapshot=snapshot)
        main.save_canvas(canvas)
        archive = client.get(f"/api/canvases/{canvas['id']}/export-package")
        assert archive.status_code == 200, archive.text
        restored = client.post('/api/canvas-packages/import', files={'file': ('workflow.zip', archive.content, 'application/zip')})
        assert restored.status_code == 200, restored.text
        restored_canvas = restored.json()["canvas"]
        restored_prepare = next(n for n in restored_canvas["nodes"] if n["type"] == "film-prepare-assets")
        assert restored_prepare["workflowSnapshot"]["shots"][0]["prompt"] == "已编辑的镜头提示词"
        assert client.get(restored_prepare["workflowSnapshot"]["shots"][0]["frame"]).content == content
        assert len(restored_canvas["connections"]) == 3
        # 列表生成必须具备真实确认镜头来源，不能用图片组冒充。
        video = next(n for n in canvas["nodes"] if n["type"] == "film-video")
        canvas["connections"] = [e for e in canvas["connections"] if e["to"] != video["id"]]
        invalid = client.post("/api/canvas-film-workflow", json={"canvas_id": canvas["id"], "node_id": video["id"], "action": "generate", "graph": canvas})
        assert invalid.status_code == 400, invalid.text
        # film 暂时离线：保留已经落盘的工程，明确失败；恢复后原工程补齐脚本。
        class OfflineProxy(IsolatedProxy):
            def execute(self, *args):
                raise film_workflow.FilmWorkflowUnavailable("film temporarily offline")
        film_workflow.FilmWorkflowProxy = OfflineProxy
        manifest['bridge_id'] = 'film:p:offline'
        failed = client.post('/api/canvas-bridges/film/receive-direct',
            data={'manifest': json.dumps(manifest)}, files={'frames': ('a.png', content, 'image/png')})
        assert failed.status_code == 200, failed.text
        assert failed.json()['workflow_ready'] is False
        assert 'temporarily offline' in failed.json()['workflow_warning']
        failed_canvas = main.load_canvas(failed.json()['canvas_id'])
        assert len([n for n in failed_canvas['nodes'] if n['type'] == 'group']) == 4
        unavailable = client.post('/api/canvas-film-workflow', json={
            'canvas_id': failed_canvas['id'], 'node_id': failed.json()['workflow_node_ids'][0], 'action': 'sync'})
        assert unavailable.status_code == 503 and unavailable.json()['retryable'] is True
        film_workflow.FilmWorkflowProxy = IsolatedProxy
        recovered = client.post('/api/canvas-bridges/film/receive-direct',
            data={'manifest': json.dumps(manifest)}, files={'frames': ('a.png', content, 'image/png')})
        assert recovered.json()['canvas_id'] == failed_canvas['id']
        assert recovered.json()['workflow_ready'] is True
        assert recovered.json()['workflow_node_ids'] == failed.json()['workflow_node_ids']
        class EditedDuringInitProxy(IsolatedProxy):
            def execute(self, payload, graph, canvas_id):
                result = super().execute(payload, graph, canvas_id)
                edited = main.load_canvas(canvas_id)
                edited['title'] = '初始化期间用户编辑的标题'
                next(n for n in edited['nodes'] if n['type'] == 'image')['bridgeCaption'] = '新的分镜内容'
                main.save_canvas(edited)
                return result
        film_workflow.FilmWorkflowProxy = EditedDuringInitProxy
        manifest['bridge_id'] = 'film:p:concurrent'
        concurrent = client.post('/api/canvas-bridges/film/receive-direct',
            data={'manifest': json.dumps(manifest)}, files={'frames': ('a.png', content, 'image/png')})
        assert concurrent.json()['workflow_ready'] is False
        edited = main.load_canvas(concurrent.json()['canvas_id'])
        assert edited['title'] == '初始化期间用户编辑的标题'
        assert next(n for n in edited['nodes'] if n['type'] == 'image')['bridgeCaption'] == '新的分镜内容'
    print("film workflow HTTP, owned media and package roundtrip passed")
finally:
    server.shutdown(); server.server_close(); thread.join()
