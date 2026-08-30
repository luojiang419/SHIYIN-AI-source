from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional
import urllib.request

import requests

from .data_layout import atomic_write_json


DEPTH_MODEL_BASE_URL = "https://huggingface.co/onnx-community/depth-anything-v2-small-ONNX/resolve/main/onnx/"
DEPTH_MODEL_NAME = "model_fp16.onnx"
DEPTH_MODEL_DATA_NAME = "model_fp16.onnx_data"
DEPTH_MODEL_SET_VERSION = "depth-anything-v2-small-onnx-fp16"


@dataclass(frozen=True)
class DepthModelSpec:
    name: str
    size: int
    sha256: str
    official_url: str


DEPTH_MODEL_SPECS = (
    DepthModelSpec(
        name=DEPTH_MODEL_NAME, size=180_471,
        sha256="3f220770bf259ef0cc1a8253f4f29419d4d15092902d78ded851669291d876e2",
        official_url=DEPTH_MODEL_BASE_URL + DEPTH_MODEL_NAME,
    ),
    DepthModelSpec(
        name=DEPTH_MODEL_DATA_NAME, size=50_392_064,
        sha256="4c3b600a87aa247593ceaafb11cd1f40568dc391cd1305d6ad01075079297ddd",
        official_url=DEPTH_MODEL_BASE_URL + DEPTH_MODEL_DATA_NAME,
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
    return {key: str(raw[key]) for key in ("http", "https") if raw.get(key)}


class DepthModelManager:
    """Download and validate the optional CPU depth model without bundling weights."""

    def __init__(
        self,
        model_root: Path,
        *,
        specs: tuple[DepthModelSpec, ...] = DEPTH_MODEL_SPECS,
        proxy_provider: Callable[[], Mapping[str, str]] = windows_system_proxies,
    ) -> None:
        self.model_root = Path(model_root).expanduser().resolve()
        self.download_root = self.model_root / ".downloads"
        self.manifest_path = self.model_root / "manifest.json"
        self.specs = tuple(specs)
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
            "message": "等待检查深度模型",
            "error": "",
            "attempts": [],
            "updated_at": int(time.time() * 1000),
        }

    def model_path(self, name: str = DEPTH_MODEL_NAME) -> Path:
        return self.model_root / Path(name).name

    def status(self) -> dict[str, object]:
        with self._state_lock:
            payload = dict(self._state)
            payload["attempts"] = list(self._state.get("attempts") or [])
        payload["model_root"] = str(self.model_root)
        payload["files"] = [
            {"name": item.name, "size": item.size, "exists": self.model_path(item.name).is_file()}
            for item in self.specs
        ]
        return payload

    def public_status(self) -> dict[str, object]:
        status = self.status()
        return {key: status.get(key) for key in (
            "state", "ready", "source_label", "downloaded_bytes", "total_bytes",
            "progress", "message", "updated_at",
        )}

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

    def _valid_model(self, spec: DepthModelSpec) -> bool:
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
            self._update_state(state="checking", ready=False, message="正在检查深度模型", error="")
            self._thread = threading.Thread(target=self.ensure_now, name="depth-model-download", daemon=True)
            self._thread.start()
            return True

    def ensure_now(self) -> bool:
        with self._ensure_lock:
            self.model_root.mkdir(parents=True, exist_ok=True)
            self.download_root.mkdir(parents=True, exist_ok=True)
            if self.verify_installed():
                self._mark_ready(self._manifest_source() or "existing", "已安装深度模型")
                return True
            proxies = dict(self.proxy_provider() or {})
            attempts = [("Hugging Face 官方源（系统代理）", proxies)] if proxies else []
            attempts.append(("Hugging Face 官方源直连", None))
            errors: list[str] = []
            for label, proxy_map in attempts:
                self._update_state(
                    state="downloading", ready=False, source="official", source_label=label,
                    downloaded_bytes=0, total_bytes=sum(item.size for item in self.specs),
                    message=f"正在通过{label}补齐深度模型", error="",
                )
                try:
                    self._install_from_official(proxy_map, label)
                    if not self.verify_installed():
                        raise RuntimeError("下载完成后深度模型校验未通过")
                    self._record_attempt(label)
                    self._mark_ready("official", label)
                    return True
                except Exception as exc:  # noqa: BLE001
                    message = str(exc) or exc.__class__.__name__
                    errors.append(f"{label}：{message}")
                    self._record_attempt(label, message)
            self._update_state(state="failed", ready=False, message="深度模型自动补齐失败，可由本机管理员重试", error="；".join(errors)[:2000])
            return False

    def _manifest_source(self) -> str:
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return str(payload.get("source_label") or payload.get("source") or "")
        except (OSError, ValueError, TypeError):
            return ""

    def _mark_ready(self, source: str, source_label: str) -> None:
        total = sum(item.size for item in self.specs)
        atomic_write_json(self.manifest_path, {
            "model_set": DEPTH_MODEL_SET_VERSION,
            "source": source,
            "source_label": source_label,
            "installed_at": int(time.time() * 1000),
            "files": [{"name": item.name, "size": item.size, "sha256": item.sha256} for item in self.specs],
        })
        self._update_state(
            state="ready", ready=True, source=source, source_label=source_label,
            downloaded_bytes=total, total_bytes=total, message="深度模型已就绪", error="",
        )

    def _new_session(self, proxies: Optional[Mapping[str, str]]) -> requests.Session:
        session = requests.Session()
        session.trust_env = False
        if proxies:
            session.proxies.update({str(key): str(value) for key, value in proxies.items() if value})
        return session

    def _install_from_official(self, proxies: Optional[Mapping[str, str]], source_label: str) -> None:
        for index, spec in enumerate(self.specs):
            candidate = self.download_root / f"official-{spec.name}"
            if not self._valid_candidate(candidate, spec):
                self._download_url(spec.official_url, candidate, spec, proxies, source_label, index)
            if not self._valid_candidate(candidate, spec):
                raise RuntimeError(f"{spec.name} 校验失败")
            os.replace(candidate, self.model_path(spec.name))

    def _download_url(self, url: str, target: Path, spec: DepthModelSpec, proxies: Optional[Mapping[str, str]], source_label: str, index: int) -> None:
        partial = target.with_name(f"{target.name}.part")
        existing = partial.stat().st_size if partial.is_file() else 0
        if existing > spec.size:
            partial.unlink(missing_ok=True)
            existing = 0
        headers = {"User-Agent": "SHIYIN-AI-Depth/1.0"}
        if existing:
            headers["Range"] = f"bytes={existing}-"
        session = self._new_session(proxies)
        try:
            with session.get(url, headers=headers, stream=True, timeout=(15, 90), allow_redirects=True) as response:
                response.raise_for_status()
                append = bool(existing and response.status_code == 206)
                if not append:
                    existing = 0
                downloaded = existing
                with partial.open("ab" if append else "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
                            downloaded += len(chunk)
                            self._update_state(state="downloading", source_label=source_label, downloaded_bytes=downloaded, total_bytes=spec.size)
                    handle.flush()
                    os.fsync(handle.fileno())
        finally:
            session.close()
        if partial.stat().st_size != spec.size:
            raise RuntimeError(f"下载大小不匹配：{spec.name}")
        os.replace(partial, target)

    @staticmethod
    def _valid_candidate(path: Path, spec: DepthModelSpec) -> bool:
        try:
            return path.is_file() and path.stat().st_size == spec.size and sha256_file(path) == spec.sha256
        except OSError:
            return False
