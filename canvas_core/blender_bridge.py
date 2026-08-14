from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any


PROTOCOL = "shiyin-blender/2"
DEFAULT_PORT = 9876
MAX_MESSAGE_BYTES = 1024 * 1024
PUBLIC_ACTIONS = frozenset({"ping", "authenticate"})
COMMAND_ACTIONS = frozenset({"scene_state", "set_camera", "render_still", "render_animation"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".exr"})
VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm"})
SECRET_FILE_NAME = "blender-bridge.key"
MIN_SECRET_LENGTH = 48


class BlenderBridgeError(RuntimeError):
    pass


def blender_bridge_secret_path() -> Path:
    local_app_data = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_app_data:
        return Path(local_app_data) / "SHIYIN AI" / SECRET_FILE_NAME
    return Path.home() / ".shiyin-ai" / SECRET_FILE_NAME


def load_or_create_bridge_secret() -> str:
    path = blender_bridge_secret_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    for _attempt in range(20):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            try:
                secret = path.read_text(encoding="ascii").strip()
            except OSError:
                secret = ""
            if len(secret) >= MIN_SECRET_LENGTH:
                return secret
            time.sleep(0.05)
            continue
        secret = secrets.token_urlsafe(48)
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as handle:
            handle.write(secret + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return secret
    raise BlenderBridgeError(f"Blender 自动连接密钥文件无效：{path}")


def _version_key(path: Path) -> tuple[int, ...]:
    values = tuple(int(value) for value in re.findall(r"\d+", str(path.parent.name)))
    return values or (0,)


def _candidate_blender_roots() -> list[Path]:
    roots: list[Path] = []
    for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        value = str(os.environ.get(variable) or "").strip()
        if value:
            roots.extend((Path(value) / "Blender Foundation", Path(value) / "Steam" / "steamapps" / "common"))
    if os.name == "nt":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if not drive.exists():
                continue
            roots.extend(
                (
                    drive / "Program Files" / "Blender Foundation",
                    drive / "Program Files (x86)" / "Blender Foundation",
                    drive / "SteamLibrary" / "steamapps" / "common",
                    drive / "Program Files" / "Steam" / "steamapps" / "common",
                    drive / "Program Files (x86)" / "Steam" / "steamapps" / "common",
                )
            )
    unique: dict[str, Path] = {}
    for root in roots:
        unique.setdefault(os.path.normcase(str(root)), root)
    return list(unique.values())


def _registry_blender_candidates() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    candidates: list[Path] = []
    subkey = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    views = (0, getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0))
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in views:
            try:
                root = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view)
            except OSError:
                continue
            with root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        child = winreg.OpenKey(root, winreg.EnumKey(root, index))
                    except OSError:
                        continue
                    with child:
                        try:
                            display_name = str(winreg.QueryValueEx(child, "DisplayName")[0])
                        except OSError:
                            continue
                        if not display_name.lower().startswith("blender"):
                            continue
                        for value_name in ("InstallLocation", "DisplayIcon"):
                            try:
                                value = str(winreg.QueryValueEx(child, value_name)[0]).strip().strip('"')
                            except OSError:
                                continue
                            value = value.split(",", 1)[0].strip().strip('"')
                            candidate = Path(value)
                            candidates.append(candidate / "blender.exe" if candidate.is_dir() else candidate)
    return candidates


def discover_blender_executables() -> list[Path]:
    candidates = _registry_blender_candidates()
    path_match = shutil.which("blender") or shutil.which("blender.exe")
    if path_match:
        candidates.append(Path(path_match))
    for root in _candidate_blender_roots():
        if not root.is_dir():
            continue
        candidates.extend(root.glob("Blender *\\blender.exe"))
        candidates.extend(root.glob("blender*\\blender.exe"))
    unique: dict[str, Path] = {}
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if resolved.is_file() and resolved.name.lower() == "blender.exe":
            version = _version_key(resolved)
            if version != (0,) and version < (3, 6):
                continue
            unique.setdefault(os.path.normcase(str(resolved)), resolved)
    return sorted(unique.values(), key=_version_key, reverse=True)


def blender_process_running() -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist.exe", "/FI", "IMAGENAME eq blender.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return '"blender.exe"' in str(result.stdout or "").lower()


def launch_blender() -> dict[str, Any]:
    installations = discover_blender_executables()
    if not installations:
        raise BlenderBridgeError("未检测到 Blender 3.6 或更高版本，请先安装 Blender 或重新运行 SHIYIN AI 安装包")
    executable = installations[0]
    try:
        process = subprocess.Popen(
            [str(executable)],
            cwd=str(executable.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            close_fds=True,
        )
    except OSError as exc:
        raise BlenderBridgeError(f"无法启动 Blender：{executable}") from exc
    return {"launched": True, "blender_path": str(executable), "pid": int(process.pid)}


def blender_exchange_root() -> Path:
    return (Path(tempfile.gettempdir()) / "SHIYIN-AI-Blender").resolve()


def validated_render_path(value: str | os.PathLike[str], kind: str) -> Path:
    root = blender_exchange_root()
    path = Path(value).expanduser().resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise BlenderBridgeError("Blender 返回了交换目录之外的文件") from exc
    allowed = IMAGE_EXTENSIONS if kind == "image" else VIDEO_EXTENSIONS
    if not path.is_file() or path.stat().st_size <= 0 or path.suffix.lower() not in allowed:
        raise BlenderBridgeError(f"Blender 返回的{kind}文件无效")
    return path


def blender_addon_source(app_root: str | os.PathLike[str]) -> Path:
    root = Path(app_root).resolve()
    candidates = (
        root / "connectors" / "blender" / "shiyin_blender_bridge",
        root / "tools" / "blender-addon" / "shiyin_blender_bridge",
    )
    for candidate in candidates:
        if (candidate / "__init__.py").is_file():
            return candidate
    raise FileNotFoundError("未找到 SHIYIN Blender 插件源码")


def build_blender_addon_zip(source: Path) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            archive.write(path, Path("shiyin_blender_bridge") / path.relative_to(source))
    return buffer.getvalue()


def _valid_port(value: int) -> int:
    port = int(value)
    if not 1024 <= port <= 65535:
        raise BlenderBridgeError("Blender 插件端口必须位于 1024-65535")
    return port


def _read_line(connection: socket.socket) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = connection.recv(min(65536, MAX_MESSAGE_BYTES + 1 - size))
        if not chunk:
            break
        marker = chunk.find(b"\n")
        if marker >= 0:
            chunks.append(chunk[:marker])
            size += marker
            break
        chunks.append(chunk)
        size += len(chunk)
        if size > MAX_MESSAGE_BYTES:
            raise BlenderBridgeError("Blender 插件响应过大")
    raw = b"".join(chunks)
    if not raw:
        raise BlenderBridgeError("Blender 插件未返回数据")
    if len(raw) > MAX_MESSAGE_BYTES:
        raise BlenderBridgeError("Blender 插件响应过大")
    return raw


class BlenderBridgeClient:
    def __init__(self, host: str = "127.0.0.1") -> None:
        if host != "127.0.0.1":
            raise ValueError("Blender 桥接仅允许本机回环地址")
        self.host = host
        self._sessions: dict[int, str] = {}
        self._lock = threading.RLock()

    def _request(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        *,
        port: int = DEFAULT_PORT,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        if action not in PUBLIC_ACTIONS | COMMAND_ACTIONS:
            raise BlenderBridgeError(f"不允许的 Blender 命令：{action}")
        safe_port = _valid_port(port)
        request_id = uuid.uuid4().hex
        message: dict[str, Any] = {
            "protocol": PROTOCOL,
            "id": request_id,
            "action": action,
            "payload": payload or {},
        }
        if action not in PUBLIC_ACTIONS:
            with self._lock:
                token = self._sessions.get(safe_port, "")
            if not token:
                raise BlenderBridgeError("Blender 自动连接会话尚未建立")
            message["session_token"] = token
        encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > MAX_MESSAGE_BYTES:
            raise BlenderBridgeError("Blender 请求过大")
        try:
            with socket.create_connection((self.host, safe_port), timeout=max(0.2, float(timeout))) as connection:
                connection.settimeout(max(0.2, float(timeout)))
                connection.sendall(encoded)
                raw = _read_line(connection)
        except (OSError, TimeoutError) as exc:
            raise BlenderBridgeError(f"无法连接 Blender 插件（127.0.0.1:{safe_port}）") from exc
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BlenderBridgeError("Blender 插件返回了无效响应") from exc
        if not isinstance(response, dict) or response.get("id") != request_id:
            raise BlenderBridgeError("Blender 插件响应与请求不匹配")
        if not response.get("ok"):
            message_text = str(response.get("error") or "Blender 命令执行失败")
            if action == "ping" and "协议" in message_text:
                raise BlenderBridgeError("Blender 插件版本过旧，请重新运行 SHIYIN AI 安装包更新插件")
            if "session" in message_text.lower() or "认证" in message_text:
                with self._lock:
                    self._sessions.pop(safe_port, None)
            raise BlenderBridgeError(message_text)
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def ping(self, port: int = DEFAULT_PORT) -> dict[str, Any]:
        data = self._request("ping", port=port, timeout=2.0)
        with self._lock:
            authenticated = bool(self._sessions.get(_valid_port(port)))
        return {**data, "connected": True, "authenticated": authenticated, "port": _valid_port(port)}

    def connect(self, port: int = DEFAULT_PORT) -> dict[str, Any]:
        safe_port = _valid_port(port)
        ping_data = self._request("ping", port=safe_port, timeout=2.0)
        data = self._request(
            "authenticate",
            {"shared_secret": load_or_create_bridge_secret()},
            port=safe_port,
            timeout=3.0,
        )
        token = str(data.pop("session_token", "") or "")
        if len(token) < 24:
            raise BlenderBridgeError("Blender 插件没有返回有效会话令牌")
        with self._lock:
            self._sessions[safe_port] = token
        return {
            **ping_data,
            **data,
            "connected": True,
            "authenticated": True,
            "port": safe_port,
        }

    def connect_or_launch(
        self,
        port: int = DEFAULT_PORT,
        *,
        wait_seconds: float = 30.0,
    ) -> dict[str, Any]:
        safe_port = _valid_port(port)
        try:
            return {**self.connect(safe_port), "launched": False}
        except BlenderBridgeError as first_error:
            if blender_process_running():
                deadline = time.monotonic() + min(max(float(wait_seconds), 1.0), 10.0)
                while time.monotonic() < deadline:
                    time.sleep(0.4)
                    try:
                        return {**self.connect(safe_port), "launched": False}
                    except BlenderBridgeError:
                        continue
                raise BlenderBridgeError(
                    "Blender 已运行，但 SHIYIN AI 插件未响应。请确认插件已安装并启用，然后重试"
                ) from first_error
        launch_result = launch_blender()
        deadline = time.monotonic() + max(3.0, min(float(wait_seconds), 60.0))
        last_error: BlenderBridgeError | None = None
        while time.monotonic() < deadline:
            time.sleep(0.5)
            try:
                return {**self.connect(safe_port), **launch_result}
            except BlenderBridgeError as exc:
                last_error = exc
        detail = str(last_error or "插件服务未就绪")
        raise BlenderBridgeError(
            f"Blender 已启动，但 SHIYIN AI 插件未响应：{detail}。请在 Blender 偏好设置中启用插件"
        )

    def command(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        *,
        port: int = DEFAULT_PORT,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        if action not in COMMAND_ACTIONS:
            raise BlenderBridgeError(f"不允许的 Blender 命令：{action}")
        safe_port = _valid_port(port)
        with self._lock:
            has_session = bool(self._sessions.get(safe_port))
        if not has_session:
            self.connect(safe_port)
        try:
            return self._request(action, payload, port=safe_port, timeout=timeout)
        except BlenderBridgeError as exc:
            if "session" not in str(exc).lower() and "认证" not in str(exc):
                raise
            self.connect(safe_port)
            return self._request(action, payload, port=safe_port, timeout=timeout)

    def clear_session(self, port: int = DEFAULT_PORT) -> None:
        with self._lock:
            self._sessions.pop(_valid_port(port), None)
