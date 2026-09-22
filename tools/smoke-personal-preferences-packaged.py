"""在隔离数据目录验证热更新冻结后端的个人偏好、普通账号及快捷保存。"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

import requests


def run(stage: Path):
    stage = stage.resolve()
    root = Path(tempfile.mkdtemp(prefix="preferences-smoke-", dir=stage.parent))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    backend = stage / "app/backend/canvas-backend/canvas-backend.exe"
    env = {**os.environ, "CANVAS_DWPOSE_AUTO_DOWNLOAD": "0"}
    with (root / "stdout.log").open("wb") as stdout, (root / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen([str(backend), "--host", "127.0.0.1", "--port", str(port), "--data-dir", str(root / "data"), "--app-root", str(stage / "app"), "--portable-root", str(stage), "--runtime-mode", "desktop"], cwd=stage, env=env, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            for _ in range(300):
                assert process.poll() is None, "冻结后端提前退出"
                try:
                    if requests.get(base + "/api/health", timeout=1).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(.1)
            else:
                raise RuntimeError("冻结后端启动超时")
            sessions = []
            for index in range(2):
                session = requests.Session()
                session.trust_env = False
                response = session.post(base + "/api/account/register", json={"account": f"PreferenceSmoke{index}", "password": "local-test-only"}, timeout=15)
                response.raise_for_status()
                preference = {"video": {"youyun-h3": {"duration": 9 + index}}, "quickSave": {"mode": "silent", "directory": str(root / f"downloads-{index}")}}
                response = session.put(base + "/api/personal-preferences", json=preference, timeout=15)
                response.raise_for_status()
                assert response.json() == preference
                response = session.post(base + "/api/personal-preferences/quick-save", files={"file": ("verification.txt", b"personal-preferences-smoke", "text/plain")}, timeout=15)
                response.raise_for_status()
                assert Path(response.json()["path"]).read_bytes() == b"personal-preferences-smoke"
                assert session.get(base + "/static/personal-preferences.html", timeout=10).ok
                sessions.append(session)
            for index, session in enumerate(sessions):
                assert session.get(base + "/api/personal-preferences", timeout=10).json()["video"]["youyun-h3"]["duration"] == 9 + index
            assert sessions[1].get(base + "/api/app-settings", timeout=10).status_code == 403
            result = {"passed": True, "accounts": 2, "ordinary_account_preferences": True, "account_isolation": True, "actual_download_write": True, "stage": str(stage)}
            (root / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False))
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", type=Path)
    run(parser.parse_args().stage)
