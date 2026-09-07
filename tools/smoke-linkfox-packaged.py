"""验证真实打包后端的 LinkFox 上传、子进程、轮询和结果转存；仅访问本机模拟网关。"""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--unified", action="store_true", help="验证统一节点与纯文本跨模型适配")
    args = parser.parse_args()
    stage = args.stage.resolve()
    backend = stage / "app/backend/canvas-backend/canvas-backend.exe"
    assert backend.is_file(), backend
    skills = backend.parent / "_internal/skills/linkfox-expert-aigc-videogen-image-to-video/skills"
    for folder, script in [("linkfox-aigc-videogen", "aigc_videogen.py"), ("linkfox-aigc-videogen-multi", "aigc_videogen_multi.py")]:
        assert (skills / folder / "scripts" / script).is_file()
    image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jEOsAAAAASUVORK5CYII=")
    video = b"\x00\x00\x00\x18ftypmp42" + b"local-transport-fixture"
    calls = []
    adapted_prompt = "图片1、图片2、图片3保持同一演员外观，演员向左行走，镜头平稳跟随，无配乐。"

    class Gateway(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, data, mime="application/json"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, data))
            if self.path == '/v1/chat/completions':
                assert self.headers['Authorization'] == 'Bearer linkfox-packaged-fixture'
                assert 'image_url' not in json.dumps(data['messages'])
                assert 'video_url' not in json.dumps(data['messages'])
                return self.reply({'choices': [{'message': {'role': 'assistant', 'content': adapted_prompt}}]})
            assert self.headers['Authorization'] == 'linkfox-packaged-fixture'
            if self.path == "/oss/file/presignedPut":
                assert data == {"contentType": "image/png", "fileExtension": "png"}
                self.reply({"errcode": 200, "url": gateway_url + "/image.png?signature=fixture"})
            elif self.path == "/aigc/multiImageVideoGenAsync":
                assert data["videoType"] == "SEED"
                assert data["imageList"] == [gateway_url + "/image.png"] * 3
                assert "entry" not in data and "mode" not in data
                if args.unified: assert data["prompt"] == adapted_prompt
                print("Packaged upload and SEED submission passed; waiting for the bundled skill poll.", flush=True)
                self.reply({"taskId": "local-fixture", "costToken": 0})
            elif self.path == "/aigc/taskQuery":
                assert data["taskId"] == "local-fixture"
                self.reply({"taskId": "local-fixture", "status": "SUCCESS", "resultList": [{"id": "1", "url": gateway_url + "/result.mp4", "type": "video"}]})
            else:
                raise AssertionError(self.path)

        def do_PUT(self):
            assert self.rfile.read(int(self.headers["Content-Length"])) == image
            assert self.headers["x-oss-object-acl"] == "public-read"
            assert "Authorization" not in self.headers
            calls.append(("PUT", self.path))
            self.reply(b"")

        def do_GET(self):
            self.reply(video, "video/mp4")

    gateway = ThreadingHTTPServer(("127.0.0.1", 0), Gateway)
    gateway_url = f"http://127.0.0.1:{gateway.server_port}"
    threading.Thread(target=gateway.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    try:
        with tempfile.TemporaryDirectory(prefix="shiyin-linkfox-packaged-") as temp_dir:
            env = os.environ.copy()
            env.update(CANVAS_DWPOSE_AUTO_DOWNLOAD="0", CANVAS_DESKTOP_MODE="1", CANVAS_APP_ROOT=str(stage / "app"),
                       LINKFOX_AGENT_API_KEY="linkfox-packaged-fixture", LINKFOX_TOOL_GATEWAY=gateway_url,
                       PUBLIC_MEDIA_BASE_URL="", PUBLIC_BASE_URL="", NO_PROXY="127.0.0.1,localhost", ACPX_WORKSPACES=temp_dir)
            with open(Path(temp_dir) / "backend.log", "wb") as log:
                process = subprocess.Popen([str(backend), "--data-dir", str(Path(temp_dir) / "data"), "--app-root", str(stage / "app"),
                    "--port", str(port), "--host", "127.0.0.1", "--runtime-mode", "desktop",
                    "--desktop-token", "linkfox-packaged-fixture", "--parent-pid", str(os.getpid())], cwd=temp_dir, env=env, stdout=log, stderr=log,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                try:
                    with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=180, trust_env=False) as client:
                        for _ in range(120):
                            if process.poll() is not None:
                                detail = (Path(temp_dir) / "backend.log").read_text(encoding="utf-8", errors="replace")
                                raise RuntimeError(f"Packaged backend exited: {process.returncode}\n{detail[-4000:]}")
                            try:
                                if client.get("/api/health", timeout=1).status_code == 200:
                                    break
                            except httpx.HTTPError:
                                pass
                            time.sleep(0.25)
                        else:
                            raise TimeoutError("Backend health timed out")
                        login = client.post("/api/account/login", json={"account": "jiang", "password": "jiang"})
                        assert login.status_code == 200, login.text
                        capabilities = client.get("/api/linkfox-video/capabilities").json()
                        assert capabilities["installed"] and capabilities["configured"], capabilities
                        references = ["data:image/png;base64," + base64.b64encode(image).decode()] * 3
                        if args.unified:
                            configured = client.put('/api/providers', json=[{'id': 'ecommerce-vision', 'name': 'Fixture AI助手',
                                'base_url': gateway_url + '/v1', 'protocol': 'openai', 'enabled': True,
                                'chat_models': ['fixture-vision'], 'api_key': 'linkfox-packaged-fixture'}])
                            assert configured.status_code == 200, configured.text
                            response = client.post('/api/canvas-video', json={'provider_id': 'linkfox', 'model': 'seedance2.0',
                                'duration': 5, 'images': [{'url': url} for url in references],
                                'prompt': '已有模型解析词：演员向左行走，无配乐。', 'prompt_source_model': 'wan2.6',
                                'prompt_source_provider': 'local', 'auto_adapt_prompt': True,
                                'prompt_optimizer_provider': 'ecommerce-vision', 'prompt_optimizer_model': 'fixture-vision'})
                        else:
                            response = client.post('/api/linkfox-video', json={'entry': 'img2video', 'mode': 'reference',
                                'videoType': 'seedance2.0', 'videoTime': 5, 'imageList': references})
                        assert response.status_code == 200, response.text
                        result = response.json()
                        if args.unified:
                            assert result['request']['prompt'] == adapted_prompt
                            assert result['request']['prompt_adaptation']['profile'] == 'seedance'
                            assert result['request']['prompt_adaptation']['visual_analysis'] is False
                            assert sum(path == '/v1/chat/completions' for path, _ in calls) == 1
                        assert len(result["videos"]) == 1, result
                        assert client.get(result["videos"][0]).content == video
                        assert sum(path == "/oss/file/presignedPut" for path, _ in calls) == 1
                        print(json.dumps({"result": "pass", "installed": True, "reference_count": 3,
                            "upload_count": 1, "model": "SEED", "skill": result["skill"],
                            "result_bytes": len(video), "unified_prompt_adaptation": args.unified, "real_paid_api_called": False}), flush=True)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
    finally:
        gateway.shutdown()
        gateway.server_close()


if __name__ == "__main__":
    main()
