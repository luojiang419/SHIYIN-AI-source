from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, unquote, urlsplit

from .person_depth_components import PersonDepthComponentManager, sha256_file


class PersonDepthLanServer:
    def __init__(self, manager: PersonDepthComponentManager) -> None:
        self.manager = manager
        self._lock = threading.RLock()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._host = ""
        self._port = 0
        self._error = ""

    def configure(self, enabled: bool, host: str, port: int) -> dict[str, Any]:
        with self._lock:
            if not enabled:
                self.stop()
                return self.status()
            if self._server and self._host == host and self._port == port:
                return self.status()
            self.stop()
            try:
                handler = self._handler_type()
                server = ThreadingHTTPServer((host, port), handler)
                server.daemon_threads = True
                self._server = server
                self._host = host
                self._port = port
                self._error = ""
                self._thread = threading.Thread(target=server.serve_forever, name="person-depth-lan", daemon=True)
                self._thread.start()
            except OSError as exc:
                self._error = str(exc)
            return self.status()

    def stop(self) -> None:
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server:
            server.shutdown()
            server.server_close()
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2)

    def status(self) -> dict[str, Any]:
        installation = self.manager.installation_path()
        update = self._latest_update()
        return {
            "running": self._server is not None,
            "host": self._host,
            "port": self._port,
            "url": f"http://{self._host}:{self._port}" if self._server else "",
            "component_ready": installation is not None,
            "manifest_ready": self._manifest_path().is_file() if installation else False,
            "update_ready": update is not None,
            "update_version": update[0] if update else "",
            "update_asset": update[1].name if update else "",
            "error": self._error,
        }

    def _update_roots(self) -> tuple[Path, ...]:
        data_root = self.manager.component_root.parents[2]
        return data_root / "update" / "downloads", data_root.parent / "dist" / "installer"

    def _latest_update(self) -> Optional[tuple[str, Path, Path]]:
        candidates: list[tuple[tuple[int, int, int], str, Path, Path]] = []
        pattern = re.compile(r"^SHIYIN-AI-Setup-(\d+)\.(\d+)\.(\d+)\.exe$")
        for root in self._update_roots():
            if not root.is_dir():
                continue
            for installer in root.glob("SHIYIN-AI-Setup-*.exe"):
                match = pattern.fullmatch(installer.name)
                checksum = installer.with_name(f"{installer.name}.sha256")
                if not match or not checksum.is_file() or installer.stat().st_size <= 0:
                    continue
                raw = checksum.read_text(encoding="utf-8").split()
                if len(raw) != 2 or raw[1] != installer.name or not re.fullmatch(r"[0-9a-fA-F]{64}", raw[0]):
                    continue
                version = ".".join(match.groups())
                candidates.append((tuple(map(int, match.groups())), version, installer, checksum))
        if not candidates:
            return None
        _parts, version, installer, checksum = max(candidates, key=lambda item: item[0])
        return version, installer, checksum

    def update_manifest(self) -> dict[str, Any]:
        update = self._latest_update()
        if update is None:
            raise RuntimeError("本机没有可分发的软件更新安装包")
        version, installer, checksum = update
        base = f"http://{self._host}:{self._port}/update/files"
        return {
            "tag_name": f"v{version}",
            "draft": False,
            "prerelease": False,
            "body": "通过局域网分发的软件更新",
            "assets": [
                {
                    "name": installer.name,
                    "browser_download_url": f"{base}/{installer.name}",
                    "size": installer.stat().st_size,
                    "digest": f"sha256:{checksum.read_text(encoding='utf-8').split()[0].lower()}",
                },
                {
                    "name": checksum.name,
                    "browser_download_url": f"{base}/{checksum.name}",
                    "size": checksum.stat().st_size,
                    "digest": "",
                },
            ],
        }

    def update_file(self, name: str) -> Optional[Path]:
        update = self._latest_update()
        if update is None:
            return None
        _version, installer, checksum = update
        return installer if name == installer.name else checksum if name == checksum.name else None

    def _manifest_path(self) -> Path:
        return self.manager.component_root / "lan-share" / "manifest.json"

    def ensure_manifest(self) -> dict[str, Any]:
        installation = self.manager.installation_path()
        if installation is None or not self.manager.verify_installed(run_smoke=False):
            raise RuntimeError("本机人物深度组件尚未安装或校验失败")
        target = self._manifest_path()
        current = self.manager._read_current()
        if target.is_file():
            cached = json.loads(target.read_text(encoding="utf-8"))
            if cached.get("installation") == current.get("installation") and cached.get("protocol_version") == 1:
                return cached
        files = []
        for path in sorted(installation.rglob("*")):
            if path.is_file() and path.name != "component-manifest.json":
                relative = path.relative_to(installation).as_posix()
                files.append({"path": relative, "size": path.stat().st_size, "sha256": sha256_file(path)})
        payload = {
            "protocol_version": 1,
            "component": "person-depth",
            "version": str(self.manager.manifest.get("version") or ""),
            "installation": current.get("installation"),
            "total_bytes": sum(item["size"] for item in files),
            "files": files,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temporary.replace(target)
        return payload

    def _handler_type(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "SHIYIN-PersonDepth-LAN/1.0"

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802
                try:
                    if self.path.split("?", 1)[0] == "/health":
                        self._json({"ok": True, **owner.status()})
                    elif self.path.split("?", 1)[0] == "/person-depth/manifest.json":
                        self._json(owner.ensure_manifest())
                    elif self.path.split("?", 1)[0].startswith("/person-depth/files/"):
                        installation = owner.manager.installation_path()
                        if installation is None:
                            raise RuntimeError("本机人物深度组件尚未安装")
                        relative = Path(unquote(urlsplit(self.path).path.removeprefix("/person-depth/files/")))
                        if relative.is_absolute() or ".." in relative.parts:
                            self.send_error(400)
                            return
                        path = (installation / relative).resolve()
                        path.relative_to(installation.resolve())
                        if not path.is_file():
                            self.send_error(404)
                            return
                        self._file(path)
                    elif self.path.split("?", 1)[0] == "/update/manifest.json":
                        self._json(owner.update_manifest())
                    elif self.path.split("?", 1)[0].startswith("/update/files/"):
                        name = unquote(urlsplit(self.path).path.removeprefix("/update/files/"))
                        if Path(name).name != name:
                            self.send_error(400)
                            return
                        path = owner.update_file(name)
                        if path is None:
                            self.send_error(404)
                            return
                        self._file(path)
                    else:
                        self.send_error(404)
                except Exception as exc:  # noqa: BLE001
                    self._json({"error": str(exc) or exc.__class__.__name__}, 503)

            def _json(self, payload: dict[str, Any], status: int = 200) -> None:
                content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)

            def _file(self, path: Path) -> None:
                size = path.stat().st_size
                start, end, status = 0, size - 1, 200
                value = self.headers.get("Range", "")
                if value:
                    match = re.fullmatch(r"bytes=(\d+)-(\d*)", value.strip())
                    if not match:
                        self.send_error(416)
                        return
                    start = int(match.group(1))
                    end = int(match.group(2)) if match.group(2) else size - 1
                    if start >= size or end < start:
                        self.send_error(416)
                        return
                    end, status = min(end, size - 1), 206
                length = end - start + 1
                self.send_response(status)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                if status == 206:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                with path.open("rb") as handle:
                    handle.seek(start)
                    remaining = length
                    while remaining:
                        chunk = handle.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)

        return Handler
