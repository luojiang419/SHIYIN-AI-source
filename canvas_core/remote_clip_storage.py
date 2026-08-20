"""SSH-backed remote storage for Kling reference video clips.

The remote host exposes clips as read-only HTTP media on a dedicated port.  Upload
and deletion stay on the SSH channel so the public service never needs a write API.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


class RemoteClipStorageError(RuntimeError):
    """Raised when a remote clip cannot be uploaded or removed."""


_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")
_CLIP_PATH = re.compile(
    r"(?:^|/)canvases/(?P<canvas>[A-Za-z0-9][A-Za-z0-9._-]{0,159})/"
    r"video-clips/(?P<clip>[A-Za-z0-9][A-Za-z0-9._-]{0,159})\.mp4$",
    re.IGNORECASE,
)
_SECURE_KEY_CACHE: dict[str, str] = {}


@dataclass(frozen=True)
class RemoteClipConfig:
    host: str = "64.90.17.178"
    port: int = 419
    user: str = "root"
    key_path: str = ""
    remote_root: str = "/opt/clipdata"
    public_base_url: str = "http://64.90.17.178:18080/clip"
    connect_timeout: int = 15
    transfer_timeout: int = 900

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.user and self.key_path and self.public_base_url)


Runner = Callable[..., subprocess.CompletedProcess]


def _truthy(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _config_candidates(environ: dict[str, str] | None = None) -> tuple[Path, ...]:
    env = os.environ if environ is None else environ
    explicit = str(env.get("CLIP_REMOTE_CONFIG_FILE") or "").strip()
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    data_root = str(env.get("CANVAS_DATA_DIR") or "").strip()
    if data_root:
        candidates.append(Path(data_root).expanduser() / "config" / "remote-clip.json")
    portable_root = str(env.get("CANVAS_PORTABLE_ROOT") or "").strip()
    if portable_root:
        candidates.append(Path(portable_root).expanduser() / "data" / "config" / "remote-clip.json")
    candidates.append(Path.cwd() / "data" / "config" / "remote-clip.json")
    candidates.append(Path(__file__).resolve().parents[1] / "data" / "config" / "remote-clip.json")
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        normalized = str(path.resolve())
        if normalized not in seen:
            seen.add(normalized)
            unique.append(Path(normalized))
    return tuple(unique)


def _read_file_config(environ: dict[str, str] | None = None) -> dict[str, str]:
    for path in _config_candidates(environ):
        try:
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(key): str(value) for key, value in data.items() if value is not None}
        except (OSError, ValueError, TypeError):
            continue
    return {}


def _default_key_path(
    environ: dict[str, str] | None = None,
    file_config: dict[str, str] | None = None,
) -> str:
    env = os.environ if environ is None else environ
    explicit = str(env.get("CLIP_REMOTE_SSH_KEY_PATH") or "").strip()
    if explicit:
        return explicit
    config = file_config if file_config is not None else _read_file_config(environ)
    configured = str(config.get("ssh_key_path") or config.get("CLIP_REMOTE_SSH_KEY_PATH") or "").strip()
    if configured:
        return configured
    project_root = Path(__file__).resolve().parents[1]
    candidates = (
        project_root / "api文档" / "香港云key" / "id_ed25519_1panel",
        project_root / "data" / "system" / "remote-clip" / "id_ed25519",
    )
    return next((str(path) for path in candidates if path.is_file()), "")


def remote_clip_config(environ: dict[str, str] | None = None) -> RemoteClipConfig:
    env = os.environ if environ is None else environ
    if "CLIP_REMOTE_MEDIA_ENABLED" in env and not _truthy(env.get("CLIP_REMOTE_MEDIA_ENABLED", "")):
        return RemoteClipConfig()
    file_config = _read_file_config(environ)

    def setting(env_name: str, file_name: str, default: str) -> str:
        return str(env.get(env_name) or file_config.get(file_name) or file_config.get(env_name) or default).strip()

    return RemoteClipConfig(
        host=setting("CLIP_REMOTE_SSH_HOST", "host", "64.90.17.178"),
        port=int(setting("CLIP_REMOTE_SSH_PORT", "port", "419") or "419"),
        user=setting("CLIP_REMOTE_SSH_USER", "user", "root"),
        key_path=_default_key_path(environ, file_config),
        remote_root=setting("CLIP_REMOTE_ROOT", "remote_root", "/opt/clipdata").rstrip("/"),
        public_base_url=setting(
            "CLIP_REMOTE_PUBLIC_BASE_URL", "public_base_url", "http://64.90.17.178:18080/clip"
        ).rstrip("/"),
        connect_timeout=max(3, int(setting("CLIP_REMOTE_CONNECT_TIMEOUT", "connect_timeout", "15"))),
        transfer_timeout=max(30, int(setting("CLIP_REMOTE_TRANSFER_TIMEOUT", "transfer_timeout", "900"))),
    )


def clip_identity_from_path(path: str | Path) -> tuple[str, str] | None:
    normalized = str(path).replace("\\", "/")
    match = _CLIP_PATH.search(normalized)
    if not match:
        return None
    return match.group("canvas"), match.group("clip")


def _safe_component(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_COMPONENT.fullmatch(text):
        raise RemoteClipStorageError(f"远端素材 {label} 无效")
    return text


def _safe_account_id(account_id: str) -> str:
    text = str(account_id or "").strip() or "admin"
    return _safe_component(text, "账号目录")


def remote_clip_path(config: RemoteClipConfig, account_id: str, canvas_id: str, clip_id: str) -> str:
    return "/".join(
        (
            config.remote_root,
            _safe_account_id(account_id),
            _safe_component(canvas_id, "画布目录"),
            f"{_safe_component(clip_id, '片段文件')}.mp4",
        )
    )


def remote_clip_url(config: RemoteClipConfig, account_id: str, canvas_id: str, clip_id: str) -> str:
    components = [
        _safe_account_id(account_id),
        _safe_component(canvas_id, "画布目录"),
        f"{_safe_component(clip_id, '片段文件')}.mp4",
    ]
    return "/".join(
        [config.public_base_url.rstrip("/"), *(urllib.parse.quote(item, safe="._-") for item in components)]
    )


def _decode_output(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _secure_key_path(path: str) -> str:
    """Copy a Windows key into an ACL-restricted temp file when needed."""
    source = str(Path(path).expanduser().resolve())
    if not os.path.isfile(source):
        raise RemoteClipStorageError("未找到远端 SSH 私钥，请配置 CLIP_REMOTE_SSH_KEY_PATH")
    cached = _SECURE_KEY_CACHE.get(source)
    if cached and os.path.isfile(cached):
        return cached
    if os.name != "nt":
        try:
            os.chmod(source, 0o600)
        except OSError:
            pass
        _SECURE_KEY_CACHE[source] = source
        return source
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    target = Path(tempfile.gettempdir()) / f"shiyin-clip-key-{digest}"
    shutil.copyfile(source, target)
    result = subprocess.run(
        ["icacls", str(target), "/inheritance:r", "/grant:r", f"{os.getenv('USERNAME') or os.getenv('USER')}:F"],
        capture_output=True,
        check=False,
        shell=False,
        timeout=15,
    )
    if result.returncode != 0:
        target.unlink(missing_ok=True)
        raise RemoteClipStorageError("无法为 SSH 私钥设置 Windows 安全权限")
    _SECURE_KEY_CACHE[source] = str(target)
    return str(target)


def _cleanup_secure_keys() -> None:
    if os.name != "nt":
        return
    for path in list(_SECURE_KEY_CACHE.values()):
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass


atexit.register(_cleanup_secure_keys)


def _ssh_base(config: RemoteClipConfig) -> list[str]:
    key = _secure_key_path(config.key_path)
    return [
        "ssh",
        "-i",
        key,
        "-p",
        str(config.port),
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"ConnectTimeout={config.connect_timeout}",
        f"{config.user}@{config.host}",
    ]


def _run_process(
    args: Sequence[str],
    *,
    timeout: int,
    runner: Runner | None = None,
) -> subprocess.CompletedProcess:
    process_runner = runner or subprocess.run
    try:
        result = process_runner(
            list(args),
            capture_output=True,
            check=False,
            shell=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RemoteClipStorageError("系统未找到 ssh/scp，请安装 Windows OpenSSH Client") from exc
    if result.returncode != 0:
        detail = _decode_output(getattr(result, "stderr", "")).strip()
        raise RemoteClipStorageError(f"远端素材服务执行失败：{detail[-600:] or result.returncode}")
    return result


def _remote_shell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\\''") + "'"


def upload_video_clip(
    local_path: str | Path,
    *,
    account_id: str,
    canvas_id: str,
    clip_id: str,
    config: RemoteClipConfig | None = None,
    runner: Runner | None = None,
) -> str:
    cfg = config or remote_clip_config()
    if not cfg.enabled:
        raise RemoteClipStorageError("远端视频素材服务未配置")
    source = Path(local_path).resolve()
    if not source.is_file():
        raise RemoteClipStorageError("本地视频片段不存在，无法上传")
    target = remote_clip_path(cfg, account_id, canvas_id, clip_id)
    ssh_target = f"{cfg.user}@{cfg.host}"
    remote_directory = target.rsplit("/", 1)[0]
    _run_process(
        [*_ssh_base(cfg), "mkdir", "-p", remote_directory],
        timeout=cfg.connect_timeout,
        runner=runner,
    )
    scp = shutil.which("scp") or shutil.which("scp.exe") or "scp"
    _run_process(
        [
            scp,
            "-i",
            _secure_key_path(cfg.key_path),
            "-P",
            str(cfg.port),
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            f"ConnectTimeout={cfg.connect_timeout}",
            str(source),
            f"{ssh_target}:{target}",
        ],
        timeout=cfg.transfer_timeout,
        runner=runner,
    )
    return remote_clip_url(cfg, account_id, canvas_id, clip_id)


def validate_public_clip_url(url: str, *, timeout: int = 15) -> None:
    """Fail fast when the uploaded clip is not reachable by an HTTP client."""
    target = str(url or "").strip()
    if not target.startswith(("http://", "https://")):
        raise RemoteClipStorageError("远端素材没有生成有效的公网 HTTP(S) 地址")

    def request(method: str, headers: dict[str, str] | None = None) -> tuple[int, str, str]:
        req = urllib.request.Request(target, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=max(3, int(timeout))) as response:
                if method == "GET":
                    response.read(1)
                return (
                    int(getattr(response, "status", 200)),
                    str(response.headers.get("Content-Type") or ""),
                    str(response.headers.get("Content-Length") or ""),
                )
        except urllib.error.HTTPError as exc:
            raise RemoteClipStorageError(f"公网素材地址返回 HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RemoteClipStorageError(f"公网素材地址无法访问：{exc}") from exc

    try:
        status, content_type, content_length = request("HEAD")
    except RemoteClipStorageError as exc:
        if "HTTP 405" not in str(exc) and "HTTP 501" not in str(exc):
            raise
        status, content_type, content_length = request("GET", {"Range": "bytes=0-0"})
    if not 200 <= status < 300:
        raise RemoteClipStorageError(f"公网素材地址返回 HTTP {status}")
    if content_type and not (
        content_type.lower().startswith("video/") or "octet-stream" in content_type.lower()
    ):
        raise RemoteClipStorageError(f"公网素材地址返回的类型不是视频：{content_type}")
    if content_length and content_length.strip() == "0":
        raise RemoteClipStorageError("公网素材地址返回空文件")


def delete_video_clip(
    *,
    account_id: str,
    canvas_id: str,
    clip_id: str,
    config: RemoteClipConfig | None = None,
    runner: Runner | None = None,
) -> bool:
    cfg = config or remote_clip_config()
    if not cfg.enabled:
        return False
    target = remote_clip_path(cfg, account_id, canvas_id, clip_id)
    _run_process(
        [*_ssh_base(cfg), "rm", "-f", "--", target],
        timeout=cfg.connect_timeout,
        runner=runner,
    )
    return True


def purge_canvas_video_clips(
    *,
    account_id: str,
    canvas_id: str,
    config: RemoteClipConfig | None = None,
    runner: Runner | None = None,
) -> bool:
    cfg = config or remote_clip_config()
    if not cfg.enabled:
        return False
    canvas = _safe_component(canvas_id, "画布目录")
    account = _safe_account_id(account_id)
    target = f"{cfg.remote_root}/{account}/{canvas}"
    _run_process(
        [*_ssh_base(cfg), "rm", "-rf", "--", target],
        timeout=cfg.connect_timeout,
        runner=runner,
    )
    return True
