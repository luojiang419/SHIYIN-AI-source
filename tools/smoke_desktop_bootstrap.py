from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def request_status(url: str, cookie_jar: http.cookiejar.CookieJar | None = None) -> tuple[int, dict[str, str]]:
    handlers: list[urllib.request.BaseHandler] = [NoRedirect()]
    if cookie_jar is not None:
        handlers.insert(0, urllib.request.HTTPCookieProcessor(cookie_jar))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(url, timeout=5) as response:
            return int(response.status), dict(response.headers.items())
    except urllib.error.HTTPError as error:
        return int(error.code), dict(error.headers.items())


def wait_for_health(port: int, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    url = f"http://127.0.0.1:{port}/api/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Packaged backend exited early: {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise TimeoutError("Packaged backend health check timed out")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--port", type=int, default=3119)
    arguments = parser.parse_args()
    if not 1024 <= arguments.port <= 65535:
        raise ValueError(f"Invalid smoke port: {arguments.port}")

    stage = arguments.stage.resolve(strict=True)
    backend = stage / "app" / "backend" / "canvas-backend" / "canvas-backend.exe"
    if not backend.is_file():
        raise FileNotFoundError(f"Packaged backend not found: {backend}")

    desktop_token = "packaged-bootstrap-smoke"
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with tempfile.TemporaryDirectory(prefix="shiyin-bootstrap-smoke-") as data_root:
        command = [
            str(backend),
            "--data-dir",
            data_root,
            "--app-root",
            str(stage / "app"),
            "--portable-root",
            str(stage),
            "--host",
            "127.0.0.1",
            "--port",
            str(arguments.port),
            "--desktop-token",
            desktop_token,
            "--parent-pid",
            str(os.getpid()),
            "--runtime-mode",
            "desktop",
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        try:
            wait_for_health(arguments.port, process)
            bootstrap_url = f"http://127.0.0.1:{arguments.port}/api/auth/bootstrap"
            cookie_jar = http.cookiejar.CookieJar()
            first_status, first_headers = request_status(bootstrap_url, cookie_jar)
            statuses = [
                first_status,
                request_status(bootstrap_url, cookie_jar)[0],
                request_status(bootstrap_url)[0],
                request_status(
                    f"http://127.0.0.1:{arguments.port}/api/auth/bootstrap?token=wrong"
                )[0],
                request_status(bootstrap_url)[0],
            ]
            if statuses != [303, 303, 303, 303, 303]:
                raise AssertionError(f"Unexpected bootstrap statuses: {statuses}")
            normalized_headers = {key.lower(): value for key, value in first_headers.items()}
            if normalized_headers.get("cache-control") != "no-store":
                raise AssertionError("Packaged bootstrap Cache-Control header is missing")
            if normalized_headers.get("referrer-policy") != "no-referrer":
                raise AssertionError("Packaged bootstrap Referrer-Policy header is missing")
            print(json.dumps({"statuses": statuses, "result": "pass"}, ensure_ascii=False))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
