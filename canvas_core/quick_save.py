from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from threading import RLock
from typing import BinaryIO, Callable


_FINALIZE_LOCK = RLock()


def safe_download_name(name: str, fallback: str = "download.bin") -> str:
    filename = Path(str(name or "").strip()).name or fallback
    filename = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", filename).strip(" .")
    if not filename:
        filename = fallback
    stem, suffix = os.path.splitext(filename)
    if len(filename) > 220:
        filename = f"{stem[: max(1, 220 - len(suffix))]}{suffix}"
    return filename


def unique_destination(directory: str | Path, filename: str) -> Path:
    root = Path(directory).expanduser().resolve()
    safe_name = safe_download_name(filename)
    stem, suffix = os.path.splitext(safe_name)
    candidate = root / safe_name
    sequence = 2
    while candidate.exists():
        candidate = root / f"{stem} ({sequence}){suffix}"
        sequence += 1
    return candidate


def save_stream(
    directory: str | Path,
    filename: str,
    writer: Callable[[BinaryIO], None],
) -> Path:
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError("快捷保存路径不是文件夹")
    fd, temporary_name = tempfile.mkstemp(prefix=".shiyin-quick-save-", suffix=".part", dir=str(root))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as target:
            writer(target)
            target.flush()
            os.fsync(target.fileno())
        with _FINALIZE_LOCK:
            destination = unique_destination(root, filename)
            os.replace(temporary, destination)
        return destination
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise
