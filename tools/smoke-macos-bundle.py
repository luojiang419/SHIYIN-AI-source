"""Validate the bundled macOS backend without using user data or API keys."""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import signal
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


def request_json(
    url: str,
    token: str = "",
    method: str = "GET",
    opener: urllib.request.OpenerDirector | None = None,
) -> dict:
    headers = {"X-Desktop-Token": token} if token else {}
    data = b"" if method == "POST" else None
    request = urllib.request.Request(url, headers=headers, data=data, method=method)
    open_request = opener.open if opener else urllib.request.urlopen
    with open_request(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_health(process: subprocess.Popen, port: int, timeout: float = 60) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            detail = (process.stderr.read() if process.stderr else b"").decode("utf-8", "replace")
            raise SystemExit(f"Process exited early ({process.returncode}): {detail[-2000:]}")
        try:
            health = request_json(f"http://127.0.0.1:{port}/api/health")
            if health.get("status") == "ok":
                return health
        except Exception:
            time.sleep(0.2)
    raise SystemExit("Backend did not become healthy")


def authenticated_runtime_info(port: int) -> dict:
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    with opener.open(f"http://127.0.0.1:{port}/api/auth/bootstrap", timeout=3) as response:
        response.read()
    if not any(cookie.name == "canvas_account_session" for cookie in cookie_jar):
        raise SystemExit("Desktop bootstrap did not create an authenticated session cookie")
    return request_json(f"http://127.0.0.1:{port}/api/runtime/info", opener=opener)


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
            wait_for_health(process, port, 45)
            version = authenticated_runtime_info(port)
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

    app_executable = next(
        (candidate for candidate in (
            app / "Contents" / "MacOS" / "SHIYIN-AI",
            app / "Contents" / "MacOS" / "SHIYIN AI",
        ) if candidate.is_file()),
        None,
    )
    if app_executable is None:
        raise SystemExit("Missing macOS desktop executable in app bundle")
    app_port = free_port()
    data_root = Path.home() / "Library" / "Application Support" / "SHIYIN AI"
    config_dir = data_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "app.json").write_text(json.dumps({
        "host": "127.0.0.1",
        "port": app_port,
        "lan_enabled": False,
        "cache_max_bytes": 1024 * 1024 * 1024,
        "close_behavior": "exit",
    }), encoding="utf-8")
    desktop = subprocess.Popen(
        ["open", "-n", "-W", str(app)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    backend_pid = 0
    try:
        wait_for_health(desktop, app_port)
        info = authenticated_runtime_info(app_port)
        actual = str(info.get("version") or "").strip()
        expected = (app_root / "VERSION").read_text(encoding="utf-8").strip()
        if actual != expected:
            raise SystemExit(f"Desktop version mismatch: expected {expected}, got {actual}")
        paths = info.get("paths") or {}
        if Path(paths.get("app_root") or "").resolve() != app_root.resolve():
            raise SystemExit(f"Desktop app_root mismatch: {paths.get('app_root')}")
        if Path(paths.get("data_root") or "").resolve() != data_root.resolve():
            raise SystemExit(f"Desktop data_root mismatch: {paths.get('data_root')}")
        backend_pid = int(info.get("pid") or 0)
        print(json.dumps({
            "desktop": "ok", "health": "ok", "version": actual,
            "app_root": str(app_root), "data_root": str(data_root),
        }))
    finally:
        subprocess.run(
            ["pkill", "-TERM", "-f", str(app_executable)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        try:
            desktop.wait(timeout=8)
        except subprocess.TimeoutExpired:
            desktop.terminate()
            desktop.wait(timeout=5)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            try:
                request_json(f"http://127.0.0.1:{app_port}/api/health")
            except Exception:
                break
            time.sleep(0.2)
        else:
            if backend_pid > 0:
                os.kill(backend_pid, signal.SIGTERM)
            raise SystemExit("Desktop backend did not stop after its parent exited")


if __name__ == "__main__":
    main()
