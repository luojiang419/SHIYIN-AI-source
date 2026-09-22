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


def post_json(url: str, payload: dict[str, str], cookie_jar: http.cookiejar.CookieJar) -> int:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener.open(request, timeout=5) as response:
        return int(response.status)


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
            env={**os.environ, "CANVAS_DWPOSE_AUTO_DOWNLOAD": "0"},
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
            first_location = normalized_headers.get("location")
            if first_location != "/login":
                raise AssertionError(f"Desktop bootstrap did not open login page: {first_location}")
            register_status = post_json(
                f"http://127.0.0.1:{arguments.port}/api/account/register",
                {"account": "desktopSmoke", "password": "desktop-smoke-password"},
                cookie_jar,
            )
            if register_status != 201:
                raise AssertionError(f"Desktop user registration failed: {register_status}")
            authenticated_opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(cookie_jar)
            )
            with authenticated_opener.open(f"http://127.0.0.1:{arguments.port}/", timeout=5) as page:
                page_html = page.read().decode("utf-8", errors="replace")
            if "SHIYIN AI" not in page_html or "<html" not in page_html.lower():
                raise AssertionError("Authenticated desktop homepage did not return HTML")
            with authenticated_opener.open(
                f"http://127.0.0.1:{arguments.port}/api/canvases", timeout=5
            ) as canvases_response:
                canvases_payload = json.loads(canvases_response.read().decode("utf-8"))
            if not isinstance(canvases_payload.get("canvases"), list):
                raise AssertionError("Authenticated canvas API did not return a canvas list")
            with authenticated_opener.open(f"http://127.0.0.1:{arguments.port}/api/account/me", timeout=5) as response:
                identity = json.load(response)["account"]
            if not identity["is_admin"]:
                raise AssertionError("First local registration must be administrator")
            # 实际结束冻结后端并重启，新的 Cookie 容器从加密本机凭据恢复。
            process.terminate()
            process.wait(timeout=10)
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, creationflags=creation_flags,
                                       env={**os.environ, "CANVAS_DWPOSE_AUTO_DOWNLOAD": "0"})
            wait_for_health(arguments.port, process)
            restored_cookies = http.cookiejar.CookieJar()
            restored_status, restored_headers = request_status(bootstrap_url, restored_cookies)
            if restored_status != 303 or {key.lower(): value for key, value in restored_headers.items()}.get('location') != '/':
                raise AssertionError("Packaged desktop login was not restored after process restart")
            restored = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(restored_cookies))
            with restored.open(f"http://127.0.0.1:{arguments.port}/api/account/me", timeout=5) as response:
                if json.load(response)["account"] != identity:
                    raise AssertionError("Restored account identity changed")
            post_json(f"http://127.0.0.1:{arguments.port}/api/account/logout", {}, restored_cookies)
            if {key.lower(): value for key, value in request_status(bootstrap_url)[1].items()}.get('location') != '/login':
                raise AssertionError("Logout must revoke saved desktop login")
            print(json.dumps({"statuses": statuses, "register_status": register_status, "first_admin": True,
                              "process_restart_restored": True, "logout_revoked": True, "result": "pass"}, ensure_ascii=False))
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
