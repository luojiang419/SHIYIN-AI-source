"""Validate the bundled macOS backend without using user data or API keys."""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def request_json(url: str, token: str = "", method: str = "GET") -> dict:
    headers = {"X-Desktop-Token": token} if token else {}
    data = b"" if method == "POST" else None
    request = urllib.request.Request(url, headers=headers, data=data, method=method)
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    args = parser.parse_args()
    app = args.app.resolve()
    resources = app / "Contents" / "Resources"
    app_root = resources / "app"
    backend = app_root / "backend" / "canvas-backend" / "canvas-backend"
    web_root = app_root / "web"
    if not backend.is_file() or not os.access(backend, os.X_OK):
        raise SystemExit(f"Missing executable backend: {backend}")
    for required in (web_root / "index.html", app_root / "VERSION"):
        if not required.is_file() or required.stat().st_size <= 0:
            raise SystemExit(f"Missing bundle resource: {required}")

    port = free_port()
    token = "macos-bundle-smoke-token"
    with tempfile.TemporaryDirectory(prefix="shiyin-macos-smoke-") as temporary:
        data_root = Path(temporary) / "data"
        command = [
            str(backend), "--data-dir", str(data_root), "--app-root", str(app_root),
            "--portable-root", str(resources), "--host", "127.0.0.1", "--port", str(port),
            "--desktop-token", token, "--runtime-mode", "desktop",
        ]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 45
            health = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    detail = (process.stderr.read() if process.stderr else b"").decode("utf-8", "replace")
                    raise SystemExit(f"Bundled backend exited early ({process.returncode}): {detail[-2000:]}")
                try:
                    health = request_json(f"http://127.0.0.1:{port}/api/health")
                    if health.get("status") == "ok":
                        break
                except Exception:
                    time.sleep(0.2)
            if not health or health.get("status") != "ok":
                raise SystemExit("Bundled backend did not become healthy")
            version = request_json(f"http://127.0.0.1:{port}/api/version", token)
            expected = (app_root / "VERSION").read_text(encoding="utf-8").strip()
            actual = str(version.get("version") or version.get("current_version") or "").strip()
            if actual != expected:
                raise SystemExit(f"Version mismatch: expected {expected}, got {actual}")
            print(json.dumps({"health": "ok", "version": actual, "backend": str(backend)}))
        finally:
            try:
                request_json(f"http://127.0.0.1:{port}/api/runtime/shutdown", token, "POST")
            except Exception:
                pass
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
