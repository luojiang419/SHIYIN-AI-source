from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

import requests

from .data_layout import atomic_write_json


PERSON_DEPTH_COMPONENT = "person-depth"
PERSON_DEPTH_MANIFEST_ENV = "CANVAS_PERSON_DEPTH_MANIFEST_PATH"
PERSON_DEPTH_BUILTIN_MANIFEST = Path(__file__).with_name("person_depth_manifest.json")


def sha256_file(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def windows_system_proxies() -> dict[str, str]:
    raw = urllib.request.getproxies() or {}
    return {
        key: str(raw[key]).strip()
        for key in ("http", "https")
        if str(raw.get(key) or "").strip()
    }


@dataclass(frozen=True)
class PersonDepthPackageSpec:
    package_id: str
    size: int
    sha256: str
    domestic_url: str
    official_url: str


class PersonDepthManifestError(ValueError):
    pass


class PersonDepthComponentUnavailable(RuntimeError):
    pass


class PersonDepthComponentManager:
    """Install and validate the optional person-depth runtime outside the app bundle."""

    PUBLIC_STATUS_KEYS = (
        "state",
        "ready",
        "install_available",
        "consent_required",
        "version",
        "source_label",
        "downloaded_bytes",
        "total_bytes",
        "progress",
        "message",
        "updated_at",
    )

    def __init__(
        self,
        component_root: Path,
        *,
        manifest_path: Optional[Path] = None,
        manifest: Optional[Mapping[str, object]] = None,
        proxy_provider: Callable[[], Mapping[str, str]] = windows_system_proxies,
        smoke_runner: Optional[Callable[[Sequence[str], Path], None]] = None,
    ) -> None:
        self.component_root = Path(component_root).expanduser().resolve()
        self.download_root = self.component_root / "downloads"
        self.installations_root = self.component_root / "installations"
        self.staging_root = self.component_root / "staging"
        self.current_path = self.component_root / "current.json"
        self.local_manifest_path = self.component_root / "manifest.json"
        configured_path = os.getenv(PERSON_DEPTH_MANIFEST_ENV, "").strip()
        self.manifest_path = Path(
            manifest_path
            or configured_path
            or (self.local_manifest_path if self.local_manifest_path.is_file() else PERSON_DEPTH_BUILTIN_MANIFEST)
        ).expanduser().resolve()
        self.proxy_provider = proxy_provider
        self.smoke_runner = smoke_runner or self._run_smoke
        self._state_lock = threading.RLock()
        self._ensure_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._manifest_error = ""
        try:
            self.manifest = self._normalize_manifest(
                dict(manifest) if manifest is not None else self._read_manifest(self.manifest_path)
            )
            self.specs = tuple(self._package_specs(self.manifest))
        except (OSError, ValueError, TypeError, PersonDepthManifestError) as exc:
            self._manifest_error = str(exc) or exc.__class__.__name__
            self.manifest = self._pending_manifest(self._manifest_error)
            self.specs = ()
        available = self._install_available()
        self._state: dict[str, object] = {
            "state": "idle" if available else "unavailable",
            "ready": False,
            "install_available": available,
            "consent_required": available,
            "version": str(self.manifest.get("version") or ""),
            "source": "",
            "source_label": "",
            "downloaded_bytes": 0,
            "total_bytes": sum(item.size for item in self.specs),
            "progress": 0.0,
            "message": self._initial_message(),
            "error": self._manifest_error,
            "attempts": [],
            "updated_at": int(time.time() * 1000),
        }
        if self.verify_installed(run_smoke=False):
            self._mark_ready(self._current_source_label() or "已安装组件")

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, object]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise PersonDepthManifestError("person-depth manifest 必须是 JSON 对象")
        return payload

    @staticmethod
    def _pending_manifest(message: str) -> dict[str, object]:
        return {
            "schema_version": 1,
            "component": PERSON_DEPTH_COMPONENT,
            "version": "",
            "enabled": False,
            "message": message or "高精度人物深度组件发布清单不可用",
            "command": [],
            "required_paths": [],
            "packages": [],
        }

    @classmethod
    def _normalize_manifest(cls, raw: Mapping[str, object]) -> dict[str, object]:
        payload = dict(raw)
        if int(payload.get("schema_version") or 0) != 1:
            raise PersonDepthManifestError("不支持的 person-depth manifest 版本")
        if str(payload.get("component") or "") != PERSON_DEPTH_COMPONENT:
            raise PersonDepthManifestError("person-depth manifest 组件名称不匹配")
        payload["version"] = str(payload.get("version") or "").strip()
        command = payload.get("command")
        if not isinstance(command, list) or any(not str(item).strip() for item in command):
            raise PersonDepthManifestError("person-depth manifest 缺少有效 command")
        required_paths = payload.get("required_paths")
        if not isinstance(required_paths, list):
            raise PersonDepthManifestError("person-depth manifest 缺少 required_paths")
        packages = payload.get("packages")
        if not isinstance(packages, list):
            raise PersonDepthManifestError("person-depth manifest 缺少 packages")
        return payload

    @staticmethod
    def _package_specs(manifest: Mapping[str, object]) -> list[PersonDepthPackageSpec]:
        specs: list[PersonDepthPackageSpec] = []
        for raw in manifest.get("packages") or []:
            if not isinstance(raw, Mapping):
                raise PersonDepthManifestError("person-depth package 必须是对象")
            package_id = str(raw.get("id") or "").strip()
            size = int(raw.get("size") or 0)
            digest = str(raw.get("sha256") or "").strip().lower()
            if not package_id or not package_id.replace("-", "").replace("_", "").isalnum():
                raise PersonDepthManifestError("person-depth package id 无效")
            if size <= 0 or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise PersonDepthManifestError(f"person-depth package {package_id} 缺少大小或 SHA-256")
            specs.append(
                PersonDepthPackageSpec(
                    package_id=package_id,
                    size=size,
                    sha256=digest,
                    domestic_url=str(raw.get("domestic_url") or "").strip(),
                    official_url=str(raw.get("official_url") or "").strip(),
                )
            )
        return specs

    def _install_available(self) -> bool:
        return bool(
            self.manifest.get("enabled")
            and self.manifest.get("version")
            and self.specs
            and any(item.domestic_url or item.official_url for item in self.specs)
        )

    def _initial_message(self) -> str:
        if self._manifest_error:
            return "高精度人物深度组件发布清单无效"
        if not self._install_available():
            return str(self.manifest.get("message") or "高精度人物深度组件暂不可安装")
        return "高精度人物深度组件尚未安装"

    def status(self) -> dict[str, object]:
        with self._state_lock:
            payload = dict(self._state)
            payload["attempts"] = list(self._state.get("attempts") or [])
        payload["component_root"] = str(self.component_root)
        payload["manifest_path"] = str(self.manifest_path)
        payload["license_notice"] = str(self.manifest.get("license_notice") or "")
        return payload

    def public_status(self) -> dict[str, object]:
        status = self.status()
        return {key: status.get(key) for key in self.PUBLIC_STATUS_KEYS}

    def _update_state(self, **values: object) -> None:
        with self._state_lock:
            self._state.update(values)
            total = max(0, int(self._state.get("total_bytes") or 0))
            downloaded = max(0, int(self._state.get("downloaded_bytes") or 0))
            self._state["progress"] = min(1.0, downloaded / total) if total else 0.0
            self._state["updated_at"] = int(time.time() * 1000)

    def _record_attempt(self, label: str, error: str = "") -> None:
        with self._state_lock:
            attempts = list(self._state.get("attempts") or [])
            attempts.append({"source": label, "ok": not error, "error": str(error)[:500]})
            self._state["attempts"] = attempts
            self._state["updated_at"] = int(time.time() * 1000)

    def start_background(self) -> bool:
        if not self._install_available():
            self._update_state(
                state="unavailable",
                ready=False,
                install_available=False,
                consent_required=False,
                message=self._initial_message(),
            )
            return False
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                return False
            self._update_state(
                state="checking",
                ready=False,
                consent_required=False,
                message="正在检查高精度人物深度组件",
                error="",
            )
            self._thread = threading.Thread(
                target=self.ensure_now,
                name="person-depth-component-install",
                daemon=True,
            )
            self._thread.start()
            return True

    def wait(self, timeout: Optional[float] = None) -> bool:
        with self._state_lock:
            thread = self._thread
        if thread:
            thread.join(timeout=timeout)
        return bool(self.status().get("ready"))

    def ensure_now(self) -> bool:
        with self._ensure_lock:
            if not self._install_available():
                self._update_state(
                    state="unavailable",
                    ready=False,
                    install_available=False,
                    consent_required=False,
                    message=self._initial_message(),
                )
                return False
            if self.verify_installed(run_smoke=True):
                self._mark_ready(self._current_source_label() or "已安装组件")
                return True
            try:
                self._check_disk_space()
                return self._download_and_install()
            except Exception as exc:  # noqa: BLE001
                message = str(exc) or exc.__class__.__name__
                self._update_state(
                    state="failed",
                    ready=False,
                    message="高精度人物深度组件安装失败，可重试",
                    error=message[:2000],
                )
                return False

    def install_local_archives(
        self,
        package_paths: Mapping[str, Path],
        *,
        source_label: str = "本机私有候选包",
    ) -> bool:
        """Install already-downloaded archives and persist a local-only manifest override."""

        with self._ensure_lock:
            expected_ids = {spec.package_id for spec in self.specs}
            provided_ids = {str(package_id) for package_id in package_paths}
            if not self.specs or provided_ids != expected_ids:
                missing = sorted(expected_ids - provided_ids)
                extra = sorted(provided_ids - expected_ids)
                details = []
                if missing:
                    details.append("缺少 " + ", ".join(missing))
                if extra:
                    details.append("未知 " + ", ".join(extra))
                raise PersonDepthComponentUnavailable("本地候选包不完整" + ("：" + "；".join(details) if details else ""))
            self._check_disk_space()
            archives: list[tuple[PersonDepthPackageSpec, Path]] = []
            for spec in self.specs:
                archive = Path(package_paths[spec.package_id]).expanduser().resolve()
                if not self._valid_archive(archive, spec):
                    raise PersonDepthComponentUnavailable(f"本地候选包校验失败：{spec.package_id}")
                archives.append((spec, archive))
            try:
                self._install_archives(archives, "local", source_label)
                self.component_root.mkdir(parents=True, exist_ok=True)
                atomic_write_json(self.local_manifest_path, self.manifest)
                self.manifest_path = self.local_manifest_path.resolve()
                self._mark_ready(source_label)
                return True
            except Exception as exc:
                self._update_state(
                    state="failed",
                    ready=False,
                    message="本机高精度人物深度组件安装失败",
                    error=(str(exc) or exc.__class__.__name__)[:2000],
                )
                raise

    def _download_and_install(self) -> bool:
        proxies = dict(self.proxy_provider() or {})
        attempts: list[tuple[str, str, Optional[Mapping[str, str]]]] = [
            ("domestic", "国内镜像直连", None),
        ]
        if proxies:
            attempts.extend(
                [
                    ("domestic", "国内镜像（系统代理）", proxies),
                    ("official", "官方源（系统代理）", proxies),
                ]
            )
        attempts.append(("official", "官方源直连", None))
        errors: list[str] = []
        for source, label, proxy_map in attempts:
            if not all(self._url_for(spec, source) for spec in self.specs):
                continue
            self._update_state(
                state="downloading",
                source=source,
                source_label=label,
                downloaded_bytes=0,
                total_bytes=sum(item.size for item in self.specs),
                message=f"正在通过{label}下载高精度人物深度组件",
                error="",
            )
            try:
                archives = self._download_packages(source, label, proxy_map)
                self._install_archives(archives, source, label)
                self._record_attempt(label)
                self._mark_ready(label)
                return True
            except Exception as exc:  # noqa: BLE001
                message = str(exc) or exc.__class__.__name__
                errors.append(f"{label}：{message}")
                self._record_attempt(label, message)
        raise PersonDepthComponentUnavailable("；".join(errors) or "发布清单没有可用下载源")

    def _check_disk_space(self) -> None:
        self.component_root.mkdir(parents=True, exist_ok=True)
        required = int(self.manifest.get("required_free_bytes") or 0)
        if not required:
            required = sum(item.size for item in self.specs) * 2
        free = shutil.disk_usage(self.component_root).free
        if free < required:
            raise PersonDepthComponentUnavailable(
                f"磁盘空间不足：至少需要 {required} 字节，当前可用 {free} 字节"
            )

    @staticmethod
    def _url_for(spec: PersonDepthPackageSpec, source: str) -> str:
        return spec.domestic_url if source == "domestic" else spec.official_url

    def _download_packages(
        self,
        source: str,
        source_label: str,
        proxies: Optional[Mapping[str, str]],
    ) -> list[tuple[PersonDepthPackageSpec, Path]]:
        version = str(self.manifest["version"])
        version_download_root = self.download_root / version
        version_download_root.mkdir(parents=True, exist_ok=True)
        total = sum(item.size for item in self.specs)
        progress_base = 0
        archives: list[tuple[PersonDepthPackageSpec, Path]] = []
        for spec in self.specs:
            target = version_download_root / f"{source}-{spec.package_id}.zip"
            if not self._valid_archive(target, spec):
                self._download_url(
                    self._url_for(spec, source),
                    target,
                    spec,
                    proxies,
                    source_label,
                    progress_base,
                    total,
                )
            if not self._valid_archive(target, spec):
                raise PersonDepthComponentUnavailable(f"{spec.package_id} 下载包校验失败")
            progress_base += spec.size
            self._update_state(downloaded_bytes=progress_base, total_bytes=total)
            archives.append((spec, target))
        return archives

    def _new_session(self, proxies: Optional[Mapping[str, str]]) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        if proxies:
            session.proxies.update({str(key): str(value) for key, value in proxies.items() if value})
        return session

    def _download_url(
        self,
        url: str,
        target: Path,
        spec: PersonDepthPackageSpec,
        proxies: Optional[Mapping[str, str]],
        source_label: str,
        progress_base: int,
        progress_total: int,
    ) -> None:
        partial = target.with_name(f"{target.name}.part")
        existing = partial.stat().st_size if partial.is_file() else 0
        if existing > spec.size:
            partial.unlink(missing_ok=True)
            existing = 0
        headers = {"User-Agent": "SHIYIN-AI-Person-Depth/1.0"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        session = self._new_session(proxies)
        try:
            with session.get(url, headers=headers, stream=True, timeout=(15, 120), allow_redirects=True) as response:
                if response.status_code == 416 and existing == spec.size:
                    os.replace(partial, target)
                    return
                response.raise_for_status()
                append = bool(existing and response.status_code == 206)
                if not append:
                    existing = 0
                downloaded = existing
                with partial.open("ab" if append else "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded += len(chunk)
                        self._update_state(
                            state="downloading",
                            source_label=source_label,
                            downloaded_bytes=progress_base + downloaded,
                            total_bytes=progress_total,
                        )
                    handle.flush()
                    os.fsync(handle.fileno())
        finally:
            session.close()
        actual = partial.stat().st_size if partial.is_file() else 0
        if actual != spec.size:
            raise PersonDepthComponentUnavailable(
                f"{spec.package_id} 下载大小不匹配：应为 {spec.size}，实际为 {actual}"
            )
        os.replace(partial, target)

    @staticmethod
    def _valid_archive(path: Path, spec: PersonDepthPackageSpec) -> bool:
        try:
            return path.is_file() and path.stat().st_size == spec.size and sha256_file(path) == spec.sha256
        except OSError:
            return False

    def _install_archives(
        self,
        archives: Sequence[tuple[PersonDepthPackageSpec, Path]],
        source: str,
        source_label: str,
    ) -> None:
        self._update_state(state="verifying", message="正在校验高精度人物深度组件下载包")
        for spec, archive in archives:
            if not self._valid_archive(archive, spec):
                raise PersonDepthComponentUnavailable(f"{spec.package_id} SHA-256 校验失败")
        self.staging_root.mkdir(parents=True, exist_ok=True)
        staging = self.staging_root / uuid.uuid4().hex
        staging.mkdir(parents=True, exist_ok=False)
        try:
            self._update_state(state="installing", message="正在安装高精度人物深度组件")
            for _spec, archive in archives:
                self._safe_extract(archive, staging)
            self._validate_required_paths(staging)
            atomic_write_json(
                staging / "component-manifest.json",
                {
                    "component": PERSON_DEPTH_COMPONENT,
                    "version": self.manifest["version"],
                    "source": source,
                    "source_label": source_label,
                    "installed_at": int(time.time() * 1000),
                    "packages": [
                        {"id": spec.package_id, "size": spec.size, "sha256": spec.sha256}
                        for spec, _archive in archives
                    ],
                },
            )
            self._update_state(state="smoke", message="正在进行高精度人物深度组件小图 smoke 验证")
            self.smoke_runner(self._worker_command_for(staging), staging)
            self.installations_root.mkdir(parents=True, exist_ok=True)
            installed = self.installations_root / f"{self.manifest['version']}-{uuid.uuid4().hex}"
            os.replace(staging, installed)
            atomic_write_json(
                self.current_path,
                {
                    "component": PERSON_DEPTH_COMPONENT,
                    "version": self.manifest["version"],
                    "installation": installed.name,
                    "source": source,
                    "source_label": source_label,
                    "activated_at": int(time.time() * 1000),
                },
            )
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _safe_extract(archive: Path, target: Path) -> None:
        target_root = target.resolve()
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                member = Path(info.filename.replace("\\", "/"))
                if member.is_absolute() or ".." in member.parts:
                    raise PersonDepthComponentUnavailable(f"下载包包含不安全路径：{info.filename}")
                destination = (target / member).resolve()
                try:
                    destination.relative_to(target_root)
                except ValueError as exc:
                    raise PersonDepthComponentUnavailable(f"下载包路径越界：{info.filename}") from exc
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(info) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output, length=4 * 1024 * 1024)

    def _required_paths(self) -> list[Path]:
        result: list[Path] = []
        for raw in self.manifest.get("required_paths") or []:
            relative = Path(str(raw).replace("\\", "/"))
            if relative.is_absolute() or ".." in relative.parts:
                raise PersonDepthManifestError(f"required_paths 包含不安全路径：{raw}")
            result.append(relative)
        return result

    def _validate_required_paths(self, root: Path) -> None:
        missing = [str(path) for path in self._required_paths() if not (root / path).is_file()]
        if missing:
            raise PersonDepthComponentUnavailable("组件缺少必要文件：" + ", ".join(missing))

    def _read_current(self) -> dict[str, object]:
        try:
            payload = json.loads(self.current_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def installation_path(self) -> Optional[Path]:
        current = self._read_current()
        if str(current.get("version") or "") != str(self.manifest.get("version") or ""):
            return None
        name = str(current.get("installation") or "").strip()
        if not name or Path(name).name != name:
            return None
        candidate = (self.installations_root / name).resolve()
        try:
            candidate.relative_to(self.installations_root.resolve())
        except ValueError:
            return None
        return candidate if candidate.is_dir() else None

    def _current_source_label(self) -> str:
        return str(self._read_current().get("source_label") or "")

    def verify_installed(self, *, run_smoke: bool = False) -> bool:
        root = self.installation_path()
        if root is None:
            return False
        try:
            self._validate_required_paths(root)
            if run_smoke:
                self.smoke_runner(self._worker_command_for(root), root)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _worker_command_for(self, root: Path) -> list[str]:
        command = [str(item).strip() for item in self.manifest.get("command") or []]
        if not command:
            raise PersonDepthComponentUnavailable("组件发布清单缺少 worker command")
        executable = Path(command[0].replace("\\", "/"))
        if executable.is_absolute() or ".." in executable.parts:
            raise PersonDepthManifestError("worker command 必须使用组件内相对路径")
        return [str((root / executable).resolve()), *command[1:]]

    def worker_command(self) -> list[str]:
        root = self.installation_path()
        if root is None or not self.verify_installed(run_smoke=False):
            raise PersonDepthComponentUnavailable("高精度人物深度组件尚未就绪")
        return self._worker_command_for(root)

    @staticmethod
    def _run_smoke(command: Sequence[str], component_root: Path) -> None:
        result = subprocess.run(
            [*command, "--smoke-test", "--component-root", str(component_root)],
            cwd=str(component_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "worker smoke 失败").strip()
            raise PersonDepthComponentUnavailable(detail[-1000:])

    def _mark_ready(self, source_label: str) -> None:
        total = sum(item.size for item in self.specs)
        self._update_state(
            state="ready",
            ready=True,
            install_available=True,
            consent_required=False,
            source_label=source_label,
            downloaded_bytes=total,
            total_bytes=total,
            message="高精度人物深度组件已就绪",
            error="",
        )
