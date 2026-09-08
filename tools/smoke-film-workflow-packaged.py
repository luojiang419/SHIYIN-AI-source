"""验证 PyInstaller 打包后端的三步联动及工程包往返；数据和假 film 服务均隔离。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image


def run(stage: Path, data_root: Path, port: int, version: str) -> dict:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    data_root.mkdir(parents=True, exist_ok=True)
    buffer = BytesIO()
    Image.new("RGB", (24, 16), "green").save(buffer, "PNG")
    content = buffer.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    calls = []

    class FilmHandler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            if self.path == "/capabilities":
                result = {"app": "filmstoryboard", "workflow_version": 1,
                          "project_id": "packaged-smoke", "token": "isolated-test"}
                self.wfile.write(json.dumps(result).encode())
            else:
                assert self.headers["X-Workflow-Token"] == "isolated-test"
                self.wfile.write(content)

        def do_POST(self):
            assert self.headers["X-Workflow-Token"] == "isolated-test"
            calls.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "snapshot": {"scriptId": "packaged-script",
                "shots": [{"id": "shot-a", "frame": f"/media/{digest}.png", "prompt": "打包联动验证"}]}}).encode())

    film = ThreadingHTTPServer(("127.0.0.1", 3211), FilmHandler)
    thread = threading.Thread(target=film.serve_forever, daemon=True)
    thread.start()
    client = requests.Session()
    client.trust_env = False
    base = f"http://127.0.0.1:{port}"
    process = None
    # 与 Tauri 启动器一致，为 windowed Sidecar 提供日志句柄，避免无控制台启动时日志初始化失败。
    # 根目录日志会被旧数据迁移器移动，Windows 正在写入的日志不能移动。
    log_root = data_root / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    stdout_log = (log_root / "backend.stdout.log").open("ab")
    stderr_log = (log_root / "backend.stderr.log").open("ab")
    try:
        process = subprocess.Popen([str(stage / "app/backend/canvas-backend/canvas-backend.exe"),
            "--host", "127.0.0.1", "--port", str(port), "--app-root", str(stage / "app"),
            "--data-dir", str(data_root), "--parent-pid", str(os.getpid()),
            "--runtime-mode", "desktop", "--portable-root", str(stage)],
            cwd=stage, env={**os.environ, "CANVAS_DWPOSE_AUTO_DOWNLOAD": "0"},
            stdout=stdout_log, stderr=stderr_log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError(f"打包后端提前退出：{process.returncode}")
            try:
                health = client.get(base + "/api/health", timeout=1)
                if health.ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.25)
        else:
            raise RuntimeError("打包后端启动超时")

        def post(path, **kwargs):
            response = client.post(base + path, timeout=30, **kwargs)
            assert response.ok, response.text
            return response.json()

        caps = client.get(base + "/api/canvas-bridges/film/capabilities", timeout=5).json()
        assert caps["workflow_receive"] is True
        post("/api/account/login", json={"account": "jiang", "password": "jiang"})
        manifest = {"schema": "shiyin-film-bridge", "schema_version": 2, "bridge_id": "film:packaged-smoke:board",
            "direction": "film-to-shiyin", "source": {"project_id": "packaged-smoke", "board_id": "board"},
            "canvas": {"workflow": "film-production-v1"}, "storyboard": {"board_name": "打包联动验证",
            "selected_variant": "original", "frames": [{"stable_id": "frame:board:a", "relative_path": "images/a.png",
            "upload_name": "a.png", "width": 24, "height": 16, "sha256": digest}]}}
        imported = post("/api/canvas-bridges/film/receive-direct", data={"manifest": json.dumps(manifest)},
                        files={"frames": ("a.png", content, "image/png")})
        assert imported["workflow_ready"] is True, imported
        assert len(imported["workflow_node_ids"]) == 3
        assert calls and calls[0]["action"] == "sync", "导出后端必须直接初始化，不依赖打开网页"
        canvas = client.get(base + f"/api/canvases/{imported['canvas_id']}", timeout=10).json()["canvas"]
        assert len([n for n in canvas["nodes"] if n["type"] == "group"]) == 2
        steps = [n for n in canvas["nodes"] if n["id"] in imported["workflow_node_ids"]]
        assert len(steps) == 3
        assert all(n["workflowScriptId"] == "packaged-script" and n["workflowSnapshot"]["scriptId"] == "packaged-script" for n in steps)
        prepare = next(n for n in canvas["nodes"] if n["type"] == "film-prepare-assets")
        result = post("/api/canvas-film-workflow", json={"canvas_id": canvas["id"], "node_id": prepare["id"],
                      "action": "sync", "graph": canvas})
        assert result["snapshot"]["scriptId"] == "packaged-script"
        assert calls[0]["action"] == "sync"
        assert client.get(base + result["snapshot"]["shots"][0]["frame"], timeout=5).content == content
        for name in ("js/canvas-film-workflow.js", "css/canvas-film-workflow.css"):
            response = client.get(base + "/static/" + name, timeout=5)
            assert response.ok and response.content
        repeated = post("/api/canvas-bridges/film/receive-direct", data={"manifest": json.dumps(manifest)},
                        files={"frames": ("a.png", content, "image/png")})
        assert repeated["canvas_id"] == canvas["id"] and repeated["group_id"] == imported["group_id"]
        assert repeated["workflow_ready"] is True
        archive = client.get(base + f"/api/canvases/{canvas['id']}/export-package", timeout=30)
        assert archive.ok and archive.content.startswith(b"PK")
        restored = post("/api/canvas-packages/import", files={"file": ("workflow.zip", archive.content, "application/zip")})["canvas"]
        assert len(restored["connections"]) == 3
        assert (stage / "app/VERSION").read_text().strip() == version
        return {"version": version, "health": health.json(), "workflow_receive": True,
                "function_groups": 1, "standalone_steps": 2, "direct_receive": True, "script_sync": True, "backend_initializes_without_page": True,
                "media_bytes_match": True, "repeat_is_idempotent": True, "package_roundtrip": True}
    finally:
        client.close()
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
        stdout_log.close()
        stderr_log.close()
        film.shutdown()
        film.server_close()
        thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--port", type=int, default=3144)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.stage.resolve(), args.data_root.resolve(), args.port, args.version), ensure_ascii=False, indent=2))
