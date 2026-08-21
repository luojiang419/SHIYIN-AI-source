from __future__ import annotations

import copy
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from .data_layout import DataLayout


GIB = 1024 * 1024 * 1024
DEFAULT_CACHE_LIMIT = 10 * GIB
HARD_CACHE_LIMIT = 20 * GIB
DEFAULT_TEMP_MAX_AGE = 24 * 60 * 60
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024


class MaintenanceManager:
    """Keep disposable data bounded without touching user media or database files."""

    def __init__(self, layout: DataLayout, interval_seconds: int = 60 * 60):
        self.layout = layout
        self.interval_seconds = max(60, int(interval_seconds))
        self._started = False
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._last_report: dict[str, Any] = {
            "status": "pending",
            "started_at": 0,
            "completed_at": 0,
            "cache": {},
            "temp_removed": 0,
            "logs_rotated": 0,
        }

    def latest_report(self) -> dict[str, Any]:
        with self._state_lock:
            return copy.deepcopy(self._last_report)

    def _store_report(self, report: dict[str, Any]) -> dict[str, Any]:
        with self._state_lock:
            self._last_report = copy.deepcopy(report)
        return copy.deepcopy(report)

    def _cache_limit(self) -> int:
        value = DEFAULT_CACHE_LIMIT
        try:
            payload = json.loads(self.layout.app_config.read_text(encoding="utf-8"))
            value = int(payload.get("cache_max_bytes", value))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return max(0, min(value, HARD_CACHE_LIMIT))

    @staticmethod
    def _files(root: Path) -> list[Path]:
        if not root.exists():
            return []
        return [path for path in root.rglob("*") if path.is_file() and not path.is_symlink()]

    def _trim_cache(self) -> dict[str, int]:
        entries: list[tuple[float, int, Path]] = []
        for path in self._files(self.layout.cache):
            try:
                stat = path.stat()
                entries.append((stat.st_atime or stat.st_mtime, stat.st_size, path))
            except OSError:
                continue
        total = sum(item[1] for item in entries)
        removed = 0
        removed_bytes = 0
        limit = self._cache_limit()
        for _accessed_at, size, path in sorted(entries, key=lambda item: item[0]):
            if total <= limit:
                break
            try:
                path.unlink()
                total -= size
                removed += 1
                removed_bytes += size
            except OSError:
                continue
        return {"limit": limit, "remaining_bytes": total, "removed": removed, "removed_bytes": removed_bytes}

    def _clean_temp(self, max_age_seconds: int = DEFAULT_TEMP_MAX_AGE) -> int:
        cutoff = time.time() - max_age_seconds
        removed = 0
        for path in self._files(self.layout.temp):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        for directory in sorted((path for path in self.layout.temp.rglob("*") if path.is_dir()), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        return removed

    def _rotate_logs(self, max_bytes: int = DEFAULT_LOG_MAX_BYTES, backups: int = 5) -> int:
        rotated = 0
        for path in self.layout.logs.glob("*.log"):
            try:
                if path.stat().st_size <= max_bytes:
                    continue
                oldest = path.with_name(f"{path.name}.{backups}")
                if oldest.exists():
                    oldest.unlink()
                for number in range(backups - 1, 0, -1):
                    source = path.with_name(f"{path.name}.{number}")
                    if source.exists():
                        os.replace(source, path.with_name(f"{path.name}.{number + 1}"))
                os.replace(path, path.with_name(f"{path.name}.1"))
                rotated += 1
            except OSError:
                continue
        return rotated

    def run_once(self) -> dict[str, Any]:
        started_at = 0
        try:
            with self._lock:
                started_at = int(time.time() * 1000)
                self._store_report({
                    "status": "running",
                    "started_at": started_at,
                    "completed_at": 0,
                    "cache": {},
                    "temp_removed": 0,
                    "logs_rotated": 0,
                })
                report = {
                    "status": "complete",
                    "started_at": started_at,
                    "cache": self._trim_cache(),
                    "temp_removed": self._clean_temp(),
                    "logs_rotated": self._rotate_logs(),
                    "completed_at": int(time.time() * 1000),
                }
        except Exception as exc:
            self._store_report({
                "status": "error",
                "started_at": started_at,
                "completed_at": int(time.time() * 1000),
                "cache": {},
                "temp_removed": 0,
                "logs_rotated": 0,
                "error": str(exc)[:500],
            })
            raise
        return self._store_report(report)

    def start(self) -> None:
        if self._started:
            return
        self._started = True

        def loop() -> None:
            while True:
                time.sleep(self.interval_seconds)
                self.run_once()

        threading.Thread(target=loop, name="canvas-data-maintenance", daemon=True).start()
