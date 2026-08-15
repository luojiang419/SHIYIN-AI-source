from __future__ import annotations

import hashlib
import os
import shutil
import threading
import time
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional

import requests

from .data_layout import atomic_write_json


DWPOSE_DOMESTIC_ARCHIVE_URL = "https://dit.hunyuan.tencent.com/download/HunyuanDiT/dwpose.zip"
DWPOSE_DOMESTIC_ARCHIVE_SIZE = 326_766_854
DWPOSE_MODEL_SET_VERSION = "yzd-v-dwpose-onnx-2023-08"


@dataclass(frozen=True)
class DWPoseModelSpec:
    name: str
    size: int
    sha256: str
    official_url: str


DWPOSE_MODEL_SPECS = (
    DWPoseModelSpec(
        name="yolox_l.onnx",
        size=216_746_733,
        sha256="7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411",
        official_url="https://huggingface.co/yzd-v/DWPose/resolve/main/yolox_l.onnx",
    ),
    DWPoseModelSpec(
        name="dw-ll_ucoco_384.onnx",
        size=134_399_116,
        sha256="724f4ff2439ed61afb86fb8a1951ec39c6220682803b4a8bd4f598cd913b1843",
        official_url="https://huggingface.co/yzd-v/DWPose/resolve/main/dw-ll_ucoco_384.onnx",
    ),
)


def sha256_file(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def windows_system_proxies() -> dict[str, str]:
    raw = urllib.request.getproxies() or {}
    result: dict[str, str] = {}
    for key in ("http", "https"):
        value = str(raw.get(key) or "").strip()
        if value:
            result[key] = value
    return result


class DWPoseModelManager:
    def __init__(
        self,
        model_root: Path,
        *,
        specs: tuple[DWPoseModelSpec, ...] = DWPOSE_MODEL_SPECS,
        domestic_archive_url: str = DWPOSE_DOMESTIC_ARCHIVE_URL,
        domestic_archive_size: int = DWPOSE_DOMESTIC_ARCHIVE_SIZE,
        proxy_provider: Callable[[], Mapping[str, str]] = windows_system_proxies,
    ) -> None:
        self.model_root = Path(model_root).expanduser().resolve()
        self.download_root = self.model_root / ".downloads"
        self.manifest_path = self.model_root / "manifest.json"
        self.specs = tuple(specs)
        self.domestic_archive_url = str(domestic_archive_url)
        self.domestic_archive_size = int(domestic_archive_size)
        self.proxy_provider = proxy_provider
        self._state_lock = threading.RLock()
        self._ensure_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._state: dict[str, object] = {
            "state": "idle",
            "ready": False,
            "source": "",
            "source_label": "",
            "downloaded_bytes": 0,
            "total_bytes": sum(item.size for item in self.specs),
            "progress": 0.0,
            "message": "等待检查 DWPose 模型",
            "error": "",
            "attempts": [],
            "updated_at": int(time.time() * 1000),
        }

    def model_path(self, name: str) -> Path:
        return self.model_root / Path(name).name

    def status(self) -> dict[str, object]:
        with self._state_lock:
            payload = dict(self._state)
            payload["attempts"] = list(self._state.get("attempts") or [])
        payload["model_root"] = str(self.model_root)
        payload["files"] = [
            {
                "name": item.name,
                "size": item.size,
                "exists": self.model_path(item.name).is_file(),
            }
            for item in self.specs
        ]
        return payload

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

    def _valid_model(self, spec: DWPoseModelSpec) -> bool:
        path = self.model_path(spec.name)
        try:
            return path.is_file() and path.stat().st_size == spec.size and sha256_file(path) == spec.sha256
        except OSError:
            return False

    def verify_installed(self) -> bool:
        return all(self._valid_model(spec) for spec in self.specs)

    def start_background(self) -> bool:
        with self._state_lock:
            if self._thread and self._thread.is_alive():
                return False
            self._thread = threading.Thread(target=self.ensure_now, name="dwpose-model-download", daemon=True)
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
            self.model_root.mkdir(parents=True, exist_ok=True)
            self.download_root.mkdir(parents=True, exist_ok=True)
            self._update_state(
                state="checking",
                ready=False,
                downloaded_bytes=0,
                total_bytes=sum(item.size for item in self.specs),
                message="正在校验 DWPose 模型",
                error="",
                attempts=[],
            )
            if self.verify_installed():
                self._mark_ready(self._manifest_source() or "existing", "已安装模型")
                return True

            proxy_map = dict(self.proxy_provider() or {})
            attempts: list[tuple[str, str, Optional[dict[str, str]]]] = [
                ("domestic", "腾讯国内镜像直连", None),
            ]
            if proxy_map:
                attempts.append(("domestic", "腾讯国内镜像（系统代理）", proxy_map))
                attempts.append(("official", "Hugging Face 官方源（系统代理）", proxy_map))
            attempts.append(("official", "Hugging Face 官方源直连", None))

            errors: list[str] = []
            for source, label, proxies in attempts:
                self._update_state(
                    state="downloading",
                    ready=False,
                    source=source,
                    source_label=label,
                    downloaded_bytes=0,
                    total_bytes=self.domestic_archive_size if source == "domestic" else sum(x.size for x in self.specs),
                    message=f"正在通过{label}补齐 DWPose 模型",
                    error="",
                )
                try:
                    if source == "domestic":
                        self._install_from_domestic(proxies=proxies, source_label=label)
                    else:
                        self._install_from_official(proxies=proxies, source_label=label)
                    if not self.verify_installed():
                        raise RuntimeError("下载完成后模型校验未通过")
                    self._record_attempt(label)
                    self._mark_ready(source, label)
                    return True
                except Exception as exc:  # noqa: BLE001 - 记录后自动切换下载源
                    message = str(exc) or exc.__class__.__name__
                    errors.append(f"{label}：{message}")
                    self._record_attempt(label, message)
            error = "；".join(errors)
            self._update_state(
                state="failed",
                ready=False,
                message="DWPose 模型自动补齐失败，可由本机管理员重试",
                error=error[:2000],
            )
            return False

    def _manifest_source(self) -> str:
        try:
            import json

            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return str(payload.get("source_label") or payload.get("source") or "")
        except (OSError, ValueError, TypeError):
            return ""

    def _mark_ready(self, source: str, source_label: str) -> None:
        total = sum(item.size for item in self.specs)
        atomic_write_json(
            self.manifest_path,
            {
                "model_set": DWPOSE_MODEL_SET_VERSION,
                "source": source,
                "source_label": source_label,
                "installed_at": int(time.time() * 1000),
                "files": [
                    {"name": item.name, "size": item.size, "sha256": item.sha256} for item in self.specs
                ],
            },
        )
        self._update_state(
            state="ready",
            ready=True,
            source=source,
            source_label=source_label,
            downloaded_bytes=total,
            total_bytes=total,
            message="DWPose 模型已就绪",
            error="",
        )

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
        *,
        expected_size: int,
        proxies: Optional[Mapping[str, str]],
        source_label: str,
        progress_base: int = 0,
        progress_total: Optional[int] = None,
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f"{target.name}.part")
        existing = partial.stat().st_size if partial.is_file() else 0
        if existing > expected_size:
            partial.unlink(missing_ok=True)
            existing = 0
        headers = {"User-Agent": "SHIYIN-AI-DWPose/1.0"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        total = int(progress_total or expected_size)
        session = self._new_session(proxies)
        try:
            with session.get(url, headers=headers, stream=True, timeout=(15, 90), allow_redirects=True) as response:
                if response.status_code == 416 and existing == expected_size:
                    os.replace(partial, target)
                    self._update_state(downloaded_bytes=progress_base + expected_size, total_bytes=total)
                    return
                response.raise_for_status()
                append = bool(existing and response.status_code == 206)
                if not append:
                    existing = 0
                mode = "ab" if append else "wb"
                downloaded = existing
                with partial.open(mode) as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded += len(chunk)
                        self._update_state(
                            state="downloading",
                            source_label=source_label,
                            downloaded_bytes=progress_base + downloaded,
                            total_bytes=total,
                        )
                    handle.flush()
                    os.fsync(handle.fileno())
        finally:
            session.close()
        actual_size = partial.stat().st_size if partial.is_file() else 0
        if actual_size != expected_size:
            raise RuntimeError(f"下载大小不匹配：{target.name} 应为 {expected_size}，实际为 {actual_size}")
        os.replace(partial, target)

    def _install_from_domestic(
        self,
        *,
        proxies: Optional[Mapping[str, str]],
        source_label: str,
    ) -> None:
        archive = self.download_root / "dwpose-tencent.zip"
        self._download_url(
            self.domestic_archive_url,
            archive,
            expected_size=self.domestic_archive_size,
            proxies=proxies,
            source_label=source_label,
            progress_total=self.domestic_archive_size,
        )
        staging = self.download_root / f"staging-{uuid.uuid4().hex}"
        staging.mkdir(parents=True, exist_ok=False)
        try:
            with zipfile.ZipFile(archive) as bundle:
                members = {Path(info.filename).name: info for info in bundle.infolist() if not info.is_dir()}
                for spec in self.specs:
                    info = members.get(spec.name)
                    if not info:
                        raise RuntimeError(f"国内模型包缺少 {spec.name}")
                    candidate = staging / spec.name
                    with bundle.open(info) as source, candidate.open("wb") as destination:
                        shutil.copyfileobj(source, destination, length=4 * 1024 * 1024)
                    self._verify_candidate(candidate, spec)
            self._commit_staging(staging)
            archive.unlink(missing_ok=True)
        except Exception:
            archive.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _install_from_official(
        self,
        *,
        proxies: Optional[Mapping[str, str]],
        source_label: str,
    ) -> None:
        total = sum(item.size for item in self.specs)
        progress_base = 0
        cached_files: list[tuple[DWPoseModelSpec, Path]] = []
        staging = self.download_root / f"staging-{uuid.uuid4().hex}"
        try:
            for spec in self.specs:
                candidate = self.download_root / f"official-{spec.name}"
                try:
                    self._verify_candidate(candidate, spec)
                    self._update_state(downloaded_bytes=progress_base + spec.size, total_bytes=total)
                except (OSError, RuntimeError):
                    self._download_url(
                        spec.official_url,
                        candidate,
                        expected_size=spec.size,
                        proxies=proxies,
                        source_label=source_label,
                        progress_base=progress_base,
                        progress_total=total,
                    )
                self._verify_candidate(candidate, spec)
                cached_files.append((spec, candidate))
                progress_base += spec.size
            staging.mkdir(parents=True, exist_ok=False)
            for spec, candidate in cached_files:
                os.replace(candidate, staging / spec.name)
            self._commit_staging(staging)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _verify_candidate(self, path: Path, spec: DWPoseModelSpec) -> None:
        size = path.stat().st_size if path.is_file() else 0
        if size != spec.size:
            raise RuntimeError(f"{spec.name} 大小校验失败")
        if sha256_file(path) != spec.sha256:
            raise RuntimeError(f"{spec.name} SHA-256 校验失败")

    def _commit_staging(self, staging: Path) -> None:
        for spec in self.specs:
            self._verify_candidate(staging / spec.name, spec)
        self.model_root.mkdir(parents=True, exist_ok=True)
        for spec in self.specs:
            os.replace(staging / spec.name, self.model_path(spec.name))
