from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

from .component_profiles import (
    RuntimeCapabilities,
    compatible_variants,
    probe_runtime_capabilities,
    select_variant,
)
from .data_layout import atomic_write_json


PERSON_DEPTH_COMPONENT = "person-depth"
PERSON_DEPTH_MANIFEST_ENV = "CANVAS_PERSON_DEPTH_MANIFEST_PATH"
PERSON_DEPTH_BUILTIN_MANIFEST = Path(__file__).with_name("person_depth_manifest.json")
PERSON_DEPTH_DOWNLOAD_RETRY_DELAYS = (0.0, 2.0, 5.0)


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
    target_path: str = ""
    mirror_url: str = ""


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
        "selected_variant",
        "capabilities",
    )

    def __init__(
        self,
        component_root: Path,
        *,
        manifest_path: Optional[Path] = None,
        manifest: Optional[Mapping[str, object]] = None,
        proxy_provider: Callable[[], Mapping[str, str]] = windows_system_proxies,
        smoke_runner: Optional[Callable[[Sequence[str], Path], None]] = None,
        sleep: Callable[[float], None] = time.sleep,
        component_name: str = PERSON_DEPTH_COMPONENT,
        display_name: str = "高精度人物深度组件",
        lan_path: str = "person-depth",
        capability_provider: Callable[[], RuntimeCapabilities] = probe_runtime_capabilities,
    ) -> None:
        self.component_name = str(component_name or PERSON_DEPTH_COMPONENT)
        self.display_name = str(display_name or "高精度人物深度组件")
        self.lan_path = str(lan_path or self.component_name).strip("/")
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
        self.capability_provider = capability_provider
        self.capabilities = capability_provider()
        self.selected_variant_id = ""
        self.selected_package_ids: tuple[str, ...] = ()
        self.smoke_runner = smoke_runner or self._run_smoke
        self.sleep = sleep
        self._state_lock = threading.RLock()
        self._ensure_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._lan_source_url = ""
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
            "consent_required": False,
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

    def set_lan_source(self, value: str) -> None:
        self._lan_source_url = str(value or "").strip().rstrip("/")
        if self._state.get("state") == "unavailable" and self._install_available():
            self._update_state(
                state="idle",
                install_available=True,
                message=f"{self.display_name}尚未安装",
            )

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, object]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise PersonDepthManifestError("person-depth manifest 必须是 JSON 对象")
        return payload

    def _pending_manifest(self, message: str) -> dict[str, object]:
        return {
            "schema_version": 1,
            "component": self.component_name,
            "version": "",
            "enabled": False,
            "message": message or f"{self.display_name}发布清单不可用",
            "command": [],
            "required_paths": [],
            "packages": [],
        }

    def _normalize_manifest(self, raw: Mapping[str, object]) -> dict[str, object]:
        payload = dict(raw)
        schema_version = int(payload.get("schema_version") or 0)
        if schema_version not in (1, 2):
            raise PersonDepthManifestError("不支持的组件 manifest 版本")
        if str(payload.get("component") or "") != self.component_name:
            raise PersonDepthManifestError("person-depth manifest 组件名称不匹配")
        if schema_version == 2:
            variants = payload.get("variants")
            if not isinstance(variants, list) or not variants:
                raise PersonDepthManifestError("schema v2 manifest 缺少 variants")
            try:
                compatible = compatible_variants(variants, self.capabilities)
                selected = select_variant(variants, self.capabilities)
            except ValueError as exc:
                raise PersonDepthManifestError(str(exc)) from exc
            current = self._read_current()
            if str(current.get("version") or "") == str(payload.get("version") or ""):
                current_variant = str(current.get("variant") or "")
                selected = next(
                    (variant for variant in compatible if str(variant.get("id") or "") == current_variant),
                    selected,
                )
            variant_id = str(selected.get("id") or "").strip()
            if not variant_id:
                raise PersonDepthManifestError("运行时变体缺少 id")
            self.selected_variant_id = variant_id
            for key in ("command", "required_paths", "required_free_bytes", "assemble_archive"):
                if key in selected:
                    payload[key] = selected[key]
            selected_packages = selected.get("packages") or []
            if not isinstance(selected_packages, list):
                raise PersonDepthManifestError("运行时变体 packages 必须是数组")
            self.selected_package_ids = tuple(str(item) for item in selected_packages)
            all_packages = payload.get("all_packages") or payload.get("packages") or []
            if all_packages and not all(isinstance(item, Mapping) for item in all_packages):
                raise PersonDepthManifestError("schema v2 顶层 packages 必须是对象数组")
            payload["all_packages"] = all_packages
            payload["packages"] = [
                item for item in all_packages
                if str(item.get("id") or "") in self.selected_package_ids
            ]
            payload["selected_variant"] = variant_id
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
            target_path = str(raw.get("target_path") or "").replace("\\", "/").strip("/")
            if target_path and (Path(target_path).is_absolute() or ".." in Path(target_path).parts):
                raise PersonDepthManifestError(f"person-depth package {package_id} target_path 无效")
            specs.append(
                PersonDepthPackageSpec(
                    package_id=package_id,
                    size=size,
                    sha256=digest,
                    domestic_url=str(raw.get("domestic_url") or "").strip(),
                    official_url=str(raw.get("official_url") or "").strip(),
                    target_path=target_path,
                    mirror_url=str(raw.get("mirror_url") or "").strip(),
                )
            )
        return specs

    def _install_available(self) -> bool:
        return bool(
            self.manifest.get("enabled")
            and self.manifest.get("version")
            and (
                self._lan_source_url
                or (self.specs and any(item.domestic_url or item.mirror_url or item.official_url for item in self.specs))
            )
        )

    def _initial_message(self) -> str:
        if self._manifest_error:
            return f"{self.display_name}发布清单无效"
        if not self._install_available():
            return str(self.manifest.get("message") or f"{self.display_name}暂不可安装")
        return f"{self.display_name}尚未安装"

    def status(self) -> dict[str, object]:
        with self._state_lock:
            payload = dict(self._state)
            payload["attempts"] = list(self._state.get("attempts") or [])
        payload["component_root"] = str(self.component_root)
        payload["manifest_path"] = str(self.manifest_path)
        payload["license_notice"] = str(self.manifest.get("license_notice") or "")
        payload["selected_variant"] = self.selected_variant_id
        payload["capabilities"] = self.capabilities.public_dict()
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
                message=f"正在检查{self.display_name}",
                error="",
            )
            self._thread = threading.Thread(
                target=self.ensure_now,
                name=f"{self.component_name}-component-install",
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
            if self.verify_installed(run_smoke=True):
                self._mark_ready(self._current_source_label() or "已安装组件")
                return True
            if not self._install_available():
                self._update_state(
                    state="unavailable",
                    ready=False,
                    install_available=False,
                    consent_required=False,
                    message=self._initial_message(),
                )
                return False
            try:
                self._check_disk_space()
                return self._download_and_install()
            except Exception as exc:  # noqa: BLE001
                message = str(exc) or exc.__class__.__name__
                self._update_state(
                    state="failed",
                    ready=False,
                    message=f"{self.display_name}安装失败，可重试",
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
                    message=f"本机{self.display_name}安装失败",
                    error=(str(exc) or exc.__class__.__name__)[:2000],
                )
                raise

    def install_local_directory(self, directory: Path) -> bool:
        """Install the selected runtime from a user-supplied portable package directory."""
        if self.component_name != "video-depth-runtime":
            raise PersonDepthComponentUnavailable("此组件不支持目录导入")
        folder = Path(directory).expanduser().resolve()
        if not folder.is_dir():
            raise PersonDepthComponentUnavailable("运行时目录不存在")
        legacy = (self.manifest.get("legacy_offline_packages") or {}).get(self.selected_variant_id)
        if isinstance(legacy, Mapping):
            filename = str(legacy.get("file") or "")
            if not filename or Path(filename).name != filename:
                raise PersonDepthComponentUnavailable("旧版运行时包文件名无效")
            archive = folder / filename
            if archive.is_file():
                spec = PersonDepthPackageSpec(
                    f"legacy-{self.selected_variant_id}", int(legacy.get("size") or 0),
                    str(legacy.get("sha256") or ""), "", "",
                )
                with self._ensure_lock:
                    self._check_disk_space()
                    if not self._valid_archive(archive, spec):
                        raise PersonDepthComponentUnavailable("旧版运行时包校验失败")
                    self._install_archives([(spec, archive)], "local", "本地导入运行时")
                    self._mark_ready("本地导入运行时")
                    return True
        packages = {str(item.get("id") or ""): item for item in self.manifest.get("packages") or []}
        paths: dict[str, Path] = {}
        for spec in self.specs:
            filename = str(packages[spec.package_id].get("file") or "")
            if not filename or Path(filename).name != filename:
                raise PersonDepthComponentUnavailable(f"运行时包文件名无效：{spec.package_id}")
            candidate = folder / filename
            if not candidate.is_file():
                raise PersonDepthComponentUnavailable(f"缺少适用于本机的运行时包：{filename}")
            paths[spec.package_id] = candidate
        return self.install_local_archives(paths, source_label="本地导入运行时")

    def _download_and_install(self) -> bool:
        if self._lan_source_url:
            try:
                if self._download_lan_files():
                    return True
            except Exception as exc:  # noqa: BLE001
                self._record_attempt("局域网服务器", str(exc) or exc.__class__.__name__)
        proxies = dict(self.proxy_provider() or {})
        attempts: list[tuple[str, str, Optional[Mapping[str, str]]]] = [
            ("domestic", "国内源直连", None),
            ("mirror", "国内镜像直连", None),
        ]
        if proxies:
            attempts.extend(
                [
                    ("domestic", "国内源（系统代理）", proxies),
                    ("mirror", "国内镜像（系统代理）", proxies),
                    ("official", "官方源（系统代理）", proxies),
                ]
            )
        attempts.append(("official", "官方源直连", None))
        variants = self.manifest.get("variants") if self.component_name.endswith("-runtime") else None
        candidates = compatible_variants(variants, self.capabilities) if isinstance(variants, list) else [None]
        candidates.sort(key=lambda item: bool(item and item.get("id") == self.selected_variant_id), reverse=True)
        errors: list[str] = []
        for variant in candidates:
            if variant is not None:
                self._select_public_variant(variant)
            for source, label, proxy_map in attempts:
                if not self.specs or not all(self._url_for(spec, source) for spec in self.specs):
                    continue
                source_label = f"{label} · {self.selected_variant_id}" if variant is not None else label
                self._update_state(
                    state="downloading", source=source, source_label=source_label,
                    downloaded_bytes=0, total_bytes=sum(item.size for item in self.specs),
                    message=f"正在通过{source_label}下载{self.display_name}", error="",
                )
                try:
                    archives = self._download_packages(source, source_label, proxy_map)
                    self._install_archives(archives, source, source_label)
                    self._record_attempt(source_label)
                    self._mark_ready(source_label)
                    return True
                except Exception as exc:  # noqa: BLE001
                    message = str(exc) or exc.__class__.__name__
                    errors.append(f"{source_label}：{message}")
                    self._record_attempt(source_label, message)
        raise PersonDepthComponentUnavailable("；".join(errors) or "发布清单没有可用下载源")

    def _select_public_variant(self, variant: Mapping[str, object]) -> None:
        self.selected_variant_id = str(variant.get("id") or "")
        self.selected_package_ids = tuple(str(item) for item in variant.get("packages") or [])
        for key in ("command", "required_paths", "required_free_bytes", "assemble_archive"):
            if key in variant:
                self.manifest[key] = variant[key]
            else:
                self.manifest.pop(key, None)
        self.manifest["packages"] = [
            item for item in self.manifest.get("all_packages") or []
            if str(item.get("id") or "") in self.selected_package_ids
        ]
        self.manifest["selected_variant"] = self.selected_variant_id
        self.specs = tuple(self._package_specs(self.manifest))

    def _download_lan_files(self) -> bool:
        from .distribution_client import discover_source
        base = self._lan_source_url
        session = self._new_session(None)
        try:
            try:
                response = session.get(f"{base}/{self.lan_path}/manifest.json", timeout=(3, 10))
                response.raise_for_status()
            except requests.RequestException:
                discovered = discover_source(base)
                if discovered == base:
                    raise
                base = discovered
                response = session.get(f"{base}/{self.lan_path}/manifest.json", timeout=(3, 10))
                response.raise_for_status()
            payload = response.json()
        finally:
            session.close()
        if self.component_name.endswith("-runtime"):
            payload = self._verify_lan_envelope(payload)
        if not isinstance(payload, dict) or str(payload.get("component") or "") != self.component_name:
            raise PersonDepthComponentUnavailable("局域网清单的组件标识无效")
        protocol_version = int(payload.get("protocol_version") or 0)
        if protocol_version == 2:
            return self._download_lan_packages(base, payload)
        if protocol_version != 1:
            raise PersonDepthComponentUnavailable("局域网组件传输协议版本不匹配")
        raw_files = payload.get("files")
        if not isinstance(raw_files, list) or not raw_files or len(raw_files) > 20000:
            raise PersonDepthComponentUnavailable("局域网组件清单不完整")
        files: list[tuple[Path, int, str]] = []
        for item in raw_files:
            relative = Path(str(item.get("path") or "").replace("\\", "/")) if isinstance(item, dict) else Path()
            size = int(item.get("size") or 0) if isinstance(item, dict) else 0
            digest = str(item.get("sha256") or "").lower() if isinstance(item, dict) else ""
            if not relative.parts or relative.is_absolute() or ".." in relative.parts or size < 0 or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise PersonDepthComponentUnavailable("局域网组件文件清单无效")
            files.append((relative, size, digest))
        total = sum(size for _relative, size, _digest in files)
        if total <= 0 or total != int(payload.get("total_bytes") or 0):
            raise PersonDepthComponentUnavailable("局域网组件总大小无效")
        self.staging_root.mkdir(parents=True, exist_ok=True)
        staging = self.staging_root / uuid.uuid4().hex
        staging.mkdir(parents=True, exist_ok=False)
        self._update_state(
            state="downloading", source="lan", source_label="局域网服务器",
            downloaded_bytes=0, total_bytes=total, message=f"正在从 {base} 直接传输{self.display_name}", error="",
        )
        completed = 0
        progress_lock = threading.Lock()

        def download_one(entry: tuple[Path, int, str]) -> None:
            nonlocal completed
            relative, size, digest = entry
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            spec = PersonDepthPackageSpec(relative.as_posix(), size, digest, "", "")
            url = f"{base}/{self.lan_path}/files/{urllib.parse.quote(relative.as_posix(), safe='/')}"
            self._download_package_with_retries(url, target, spec, None, "局域网服务器", 0, total)
            with progress_lock:
                completed += size
                self._update_state(downloaded_bytes=completed, total_bytes=total)

        try:
            with ThreadPoolExecutor(max_workers=8, thread_name_prefix=f"{self.component_name}-lan") as pool:
                futures = [pool.submit(download_one, entry) for entry in files]
                for future in as_completed(futures):
                    future.result()
            self._activate_staging(staging, "lan", "局域网服务器", [])
            self._record_attempt("局域网服务器")
            self._mark_ready("局域网服务器")
            return True
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _verify_lan_envelope(value: object) -> dict[str, object]:
        from .distribution_client import trusted_key

        if not isinstance(value, Mapping):
            raise PersonDepthComponentUnavailable("局域网运行时签名清单无效")
        raw = value.get("payload")
        signature = str(value.get("signature") or "")
        public_key = str(value.get("public_key") or "")
        if not isinstance(raw, str) or public_key != trusted_key():
            raise PersonDepthComponentUnavailable("局域网运行时清单公钥不受信任")
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key)).verify(
                bytes.fromhex(signature), raw.encode("utf-8")
            )
            payload = json.loads(raw)
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise PersonDepthComponentUnavailable("局域网运行时清单签名校验失败") from exc
        if not isinstance(payload, dict):
            raise PersonDepthComponentUnavailable("局域网运行时签名载荷无效")
        return payload

    def _download_lan_packages(self, base: str, payload: Mapping[str, object]) -> bool:
        variants = payload.get("variants")
        if not isinstance(variants, list):
            raise PersonDepthComponentUnavailable("局域网运行时清单缺少 variants")
        raw_packages = payload.get("packages")
        if not isinstance(raw_packages, list):
            raise PersonDepthComponentUnavailable("局域网运行时清单缺少下载包")
        by_id = {
            str(item.get("id") or ""): item
            for item in raw_packages
            if isinstance(item, Mapping)
        }
        candidates = compatible_variants(variants, self.capabilities)
        candidates.sort(
            key=lambda item: str(item.get("id") or "") == self.selected_variant_id,
            reverse=True,
        )
        errors: list[str] = []
        for selected in candidates:
            variant_id = str(selected.get("id") or "")
            package_ids = [str(value) for value in selected.get("packages") or []]
            try:
                if not package_ids:
                    raise PersonDepthComponentUnavailable("运行时档位没有下载包")
                specs: list[PersonDepthPackageSpec] = []
                for package_id in package_ids:
                    item = by_id.get(package_id)
                    if not item:
                        raise PersonDepthComponentUnavailable(f"局域网运行时缺少下载包：{package_id}")
                    specs.append(PersonDepthPackageSpec(
                        package_id=package_id,
                        size=int(item.get("size") or 0),
                        sha256=str(item.get("sha256") or "").lower(),
                        domestic_url=f"{base}/{self.lan_path}/packages/{urllib.parse.quote(package_id, safe='')}",
                        official_url="",
                        target_path=str(item.get("target_path") or ""),
                    ))
                if any(spec.size <= 0 or not re.fullmatch(r"[0-9a-f]{64}", spec.sha256) for spec in specs):
                    raise PersonDepthComponentUnavailable("局域网运行时下载包信息无效")
                total = sum(spec.size for spec in specs)
                self.selected_variant_id = variant_id
                self._update_state(
                    state="downloading", source="lan", source_label=f"局域网服务器 · {variant_id}",
                    downloaded_bytes=0, total_bytes=total, message=f"正在下载适配本机的{self.display_name}", error="",
                )
                version_root = self.download_root / str(payload.get("version") or self.manifest.get("version"))
                version_root.mkdir(parents=True, exist_ok=True)
                archives: list[tuple[PersonDepthPackageSpec, Path]] = []
                completed = 0
                for spec in specs:
                    target = version_root / f"lan-{variant_id}-{spec.package_id}.zip"
                    if not self._valid_archive(target, spec):
                        self._download_package_with_retries(
                            spec.domestic_url, target, spec, None, "局域网服务器", completed, total
                        )
                    completed += spec.size
                    archives.append((spec, target))
                self._install_archives(archives, "lan", f"局域网服务器 · {variant_id}")
                self._record_attempt(f"局域网服务器 · {variant_id}")
                self._mark_ready(f"局域网服务器 · {variant_id}")
                return True
            except Exception as exc:  # noqa: BLE001
                message = str(exc) or exc.__class__.__name__
                errors.append(f"{variant_id}：{message}")
                self._record_attempt(f"局域网服务器 · {variant_id}", message)
        raise PersonDepthComponentUnavailable("；".join(errors) or "没有兼容的局域网运行时")

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
        return {"domestic": spec.domestic_url, "mirror": spec.mirror_url,
                "official": spec.official_url}[source]

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
                self._download_package_with_retries(
                    self._url_for(spec, source), target, spec, proxies,
                    source_label, progress_base, total,
                )
            if not self._valid_archive(target, spec):
                raise PersonDepthComponentUnavailable(f"{spec.package_id} 下载包校验失败")
            progress_base += spec.size
            self._update_state(downloaded_bytes=progress_base, total_bytes=total)
            archives.append((spec, target))
        return archives

    def _download_package_with_retries(
        self,
        url: str,
        target: Path,
        spec: PersonDepthPackageSpec,
        proxies: Optional[Mapping[str, str]],
        source_label: str,
        progress_base: int,
        progress_total: int,
    ) -> None:
        last_error: Optional[Exception] = None
        for attempt, delay in enumerate(PERSON_DEPTH_DOWNLOAD_RETRY_DELAYS, start=1):
            if delay:
                self._update_state(
                    message=f"{source_label}连接中断，{int(delay)} 秒后断点续传（{attempt}/{len(PERSON_DEPTH_DOWNLOAD_RETRY_DELAYS)}）"
                )
                self.sleep(delay)
            try:
                self._download_url(
                    url, target, spec, proxies, source_label, progress_base, progress_total
                )
                if self._valid_archive(target, spec):
                    return
                target.unlink(missing_ok=True)
                last_error = PersonDepthComponentUnavailable(f"{spec.package_id} 下载包校验失败")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not self._retryable_download_error(exc):
                    raise
        assert last_error is not None
        raise last_error

    @staticmethod
    def _retryable_download_error(error: Exception) -> bool:
        if isinstance(error, requests.HTTPError):
            status = error.response.status_code if error.response is not None else 0
            return status in (408, 429) or status >= 500
        return isinstance(error, (requests.RequestException, PersonDepthComponentUnavailable))

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
        headers = {"User-Agent": f"SHIYIN-AI-{self.component_name}/1.0"}
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
                if append:
                    content_range = str(response.headers.get("Content-Range") or "")
                    if not content_range.startswith(f"bytes {existing}-"):
                        partial.unlink(missing_ok=True)
                        raise PersonDepthComponentUnavailable(
                            f"{spec.package_id} 服务端返回了无效断点范围"
                        )
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
        self._update_state(state="verifying", message=f"正在校验{self.display_name}下载包")
        for spec, archive in archives:
            if not self._valid_archive(archive, spec):
                raise PersonDepthComponentUnavailable(f"{spec.package_id} SHA-256 校验失败")
        self.staging_root.mkdir(parents=True, exist_ok=True)
        staging = self.staging_root / uuid.uuid4().hex
        staging.mkdir(parents=True, exist_ok=False)
        try:
            self._update_state(state="installing", message=f"正在安装{self.display_name}")
            assembly = self.manifest.get("assemble_archive")
            selected_ids = set(self.selected_package_ids)
            if isinstance(assembly, Mapping) and selected_ids == {spec.package_id for spec, _ in archives}:
                expected_size = int(assembly.get("size") or 0)
                expected_hash = str(assembly.get("sha256") or "").lower()
                assembled = staging / "__assembled_runtime.zip"
                digest = hashlib.sha256()
                written = 0
                with assembled.open("wb") as output:
                    for _spec, archive in archives:
                        with archive.open("rb") as source_file:
                            while chunk := source_file.read(4 * 1024 * 1024):
                                output.write(chunk)
                                digest.update(chunk)
                                written += len(chunk)
                if written != expected_size or digest.hexdigest() != expected_hash:
                    raise PersonDepthComponentUnavailable("运行时分片合并后校验失败")
                self._safe_extract(assembled, staging)
                assembled.unlink()
            else:
                for spec, archive in archives:
                    if spec.target_path:
                        target = staging / Path(spec.target_path)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(archive, target)
                    else:
                        self._safe_extract(archive, staging)
            self._activate_staging(staging, source, source_label, [
                {"id": spec.package_id, "size": spec.size, "sha256": spec.sha256}
                for spec, _archive in archives
            ])
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _activate_staging(
        self,
        staging: Path,
        source: str,
        source_label: str,
        packages: list[dict[str, object]],
    ) -> None:
            self._validate_required_paths(staging)
            atomic_write_json(
                staging / "component-manifest.json",
                {
                    "component": self.component_name,
                    "version": self.manifest["version"],
                    "variant": self.selected_variant_id,
                    "source": source,
                    "source_label": source_label,
                    "installed_at": int(time.time() * 1000),
                    "packages": packages,
                },
            )
            self._update_state(state="smoke", message=f"正在进行{self.display_name} smoke 验证")
            self.smoke_runner(self._worker_command_for(staging), staging)
            self.installations_root.mkdir(parents=True, exist_ok=True)
            installed = self.installations_root / f"{self.manifest['version']}-{uuid.uuid4().hex}"
            os.replace(staging, installed)
            atomic_write_json(
                self.current_path,
                {
                    "component": self.component_name,
                    "version": self.manifest["version"],
                    "variant": self.selected_variant_id,
                    "installation": installed.name,
                    "source": source,
                    "source_label": source_label,
                    "activated_at": int(time.time() * 1000),
                },
            )

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
        if self.selected_variant_id and str(current.get("variant") or "") != self.selected_variant_id:
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
            raise PersonDepthComponentUnavailable(f"{self.display_name}尚未就绪")
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
            message=f"{self.display_name}已就绪",
            error="",
        )
