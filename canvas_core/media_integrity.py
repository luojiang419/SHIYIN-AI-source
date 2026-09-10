"""媒体内容契约：格式来自字节，文件名只提供展示提示。"""
from __future__ import annotations

import io
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image

IMAGE_FORMATS = {
    "PNG": (".png", "image/png"), "JPEG": (".jpg", "image/jpeg"),
    "WEBP": (".webp", "image/webp"), "GIF": (".gif", "image/gif"),
    "BMP": (".bmp", "image/bmp"), "TIFF": (".tiff", "image/tiff"),
    "AVIF": (".avif", "image/avif"),
}
MEDIA_EXTENSIONS = {ext for ext, _ in IMAGE_FORMATS.values()} | {
    ".jpeg", ".tif", ".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv",
    ".flv", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac",
}


def image_content_info(raw: bytes) -> tuple[str, str]:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            result = IMAGE_FORMATS.get(image.format)
            if not result:
                raise ValueError("不支持的图片格式")
            image.verify()
        # verify 不会解码 JPEG 像素；load 可拒绝截断的响应体。
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
        return result
    except (OSError, SyntaxError, ValueError) as exc:
        raise ValueError("上游返回的内容不是完整、有效的图片") from exc


def canonical_media_extension(value: str, fallback: str = ".png") -> str:
    ext = str(value or "").lower()
    if ext.endswith("_x"):
        ext = ext[:-2]
    ext = {".jpeg": ".jpg", ".tif": ".tiff"}.get(ext, ext)
    return ext if ext in MEDIA_EXTENSIONS else fallback


@lru_cache(maxsize=4096)
def _file_image_info(path: str, mtime_ns: int, size: int) -> tuple[str, str] | None:
    try:
        with Image.open(path) as image:
            return IMAGE_FORMATS.get(image.format)
    except (OSError, ValueError):
        return None


def file_image_info(path: str) -> tuple[str, str] | None:
    try:
        stat = os.stat(path)
        return _file_image_info(os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None


def atomic_write_bytes(path: str, raw: bytes) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".media-", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
