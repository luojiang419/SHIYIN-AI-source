from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


class VideoClipError(RuntimeError):
    pass


_WINDOWS_CREATE_NO_WINDOW = 0x08000000
_RESOLUTION_LIMITS = {
    "1080p": (1920, 1080),
    "720p": (1280, 720),
}


@dataclass(frozen=True)
class VideoClipTools:
    ffmpeg: str
    ffprobe: str

    @property
    def ready(self) -> bool:
        return bool(self.ffmpeg and self.ffprobe)


def _safe_id(value: str, label: str) -> str:
    clean = str(value or "").strip()
    if not clean or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in clean):
        raise VideoClipError(f"{label}无效。")
    return clean


def resolve_video_clip_tools(environ: Mapping[str, str] | None = None) -> VideoClipTools:
    env = os.environ if environ is None else environ
    configured_ffmpeg = str(env.get("SHIYIN_FFMPEG_PATH") or "").strip()
    configured_ffprobe = str(env.get("SHIYIN_FFPROBE_PATH") or "").strip()
    ffmpeg = configured_ffmpeg if configured_ffmpeg and Path(configured_ffmpeg).is_file() else (shutil.which("ffmpeg") or "")
    ffprobe = configured_ffprobe if configured_ffprobe and Path(configured_ffprobe).is_file() else (shutil.which("ffprobe") or "")
    return VideoClipTools(ffmpeg=ffmpeg, ffprobe=ffprobe)


def _finite_number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _frame_rate(value: Any) -> float:
    text = str(value or "").strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        divisor = _finite_number(denominator)
        return _finite_number(numerator) / divisor if divisor else 0.0
    return _finite_number(text)


def parse_video_probe(payload: str | Mapping[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(payload) if isinstance(payload, str) else dict(payload)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise VideoClipError("无法解析视频信息。") from exc
    streams = data.get("streams") if isinstance(data.get("streams"), list) else []
    video = next((item for item in streams if isinstance(item, Mapping) and item.get("codec_type") == "video"), None)
    if not video:
        raise VideoClipError("文件中没有可用的视频轨道。")
    width = int(_finite_number(video.get("width")))
    height = int(_finite_number(video.get("height")))
    duration = _finite_number(video.get("duration")) or _finite_number((data.get("format") or {}).get("duration"))
    if width <= 0 or height <= 0 or duration <= 0:
        raise VideoClipError("视频缺少有效的分辨率或时长信息。")
    rotation = 0
    tags = video.get("tags") if isinstance(video.get("tags"), Mapping) else {}
    rotation = int(_finite_number(tags.get("rotate")))
    for side_data in video.get("side_data_list") or []:
        if isinstance(side_data, Mapping) and side_data.get("rotation") is not None:
            rotation = int(_finite_number(side_data.get("rotation")))
            break
    if abs(rotation) % 180 == 90:
        width, height = height, width
    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": _frame_rate(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "video_codec": str(video.get("codec_name") or ""),
        "audio": any(isinstance(item, Mapping) and item.get("codec_type") == "audio" for item in streams),
        "rotation": rotation,
        "size": int(_finite_number((data.get("format") or {}).get("size"))),
    }


def probe_video(path: str | Path, tools: VideoClipTools | None = None, runner: Callable[..., Any] = subprocess.run) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        raise VideoClipError("源视频文件不存在。")
    resolved = tools or resolve_video_clip_tools()
    if not resolved.ffprobe:
        raise VideoClipError("未检测到 ffprobe，请安装 FFmpeg 或配置 SHIYIN_FFPROBE_PATH。")
    result = runner(
        [
            resolved.ffprobe,
            "-v", "error",
            "-show_streams",
            "-show_format",
            "-of", "json",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=60,
        creationflags=_WINDOWS_CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        raise VideoClipError((result.stderr or "无法读取视频信息。").strip())
    return parse_video_probe(result.stdout)


def output_dimensions(width: int, height: int, resolution: str = "1080p") -> tuple[int, int]:
    if width <= 0 or height <= 0:
        raise VideoClipError("源视频分辨率无效。")
    preset = str(resolution or "1080p").strip().lower()
    if preset == "original":
        scale = 1.0
    elif preset in _RESOLUTION_LIMITS:
        long_limit, short_limit = _RESOLUTION_LIMITS[preset]
        long_edge, short_edge = max(width, height), min(width, height)
        scale = min(1.0, long_limit / long_edge, short_limit / short_edge)
    else:
        raise VideoClipError("截取分辨率仅支持 original、1080p 或 720p。")
    target_width = max(2, int(math.floor(width * scale / 2) * 2))
    target_height = max(2, int(math.floor(height * scale / 2) * 2))
    return target_width, target_height


def validate_clip_range(start: float, end: float, duration: float) -> tuple[float, float]:
    start_value = _finite_number(start, -1)
    end_value = _finite_number(end, -1)
    if start_value < 0 or end_value <= start_value:
        raise VideoClipError("截取出点必须晚于入点。")
    if duration <= 0 or end_value > duration + 0.05:
        raise VideoClipError("截取区间超出源视频时长。")
    return max(0.0, start_value), min(duration, end_value)


def build_video_clip_command(
    tools: VideoClipTools,
    source: str | Path,
    output: str | Path,
    *,
    start: float,
    end: float,
    width: int,
    height: int,
) -> list[str]:
    if not tools.ffmpeg:
        raise VideoClipError("未检测到 ffmpeg，请安装 FFmpeg 或配置 SHIYIN_FFMPEG_PATH。")
    return [
        tools.ffmpeg,
        "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", str(source),
        "-ss", f"{start:.6f}",
        "-t", f"{end - start:.6f}",
        "-map", "0:v:0", "-map", "0:a?",
        "-vf", f"scale={width}:{height}:flags=lanczos,setsar=1",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-avoid_negative_ts", "make_zero",
        str(output),
    ]


def canvas_clip_directory(media_generated_root: str | Path, canvas_id: str) -> Path:
    clean_canvas_id = _safe_id(canvas_id, "画布 ID")
    root = Path(media_generated_root).resolve()
    target = (root / "canvases" / clean_canvas_id / "video-clips").resolve()
    if root not in target.parents:
        raise VideoClipError("画布视频目录无效。")
    return target


def create_video_clip(
    source: str | Path,
    media_generated_root: str | Path,
    canvas_id: str,
    *,
    start: float,
    end: float,
    resolution: str = "1080p",
    tools: VideoClipTools | None = None,
    runner: Callable[..., Any] = subprocess.run,
    clip_id: str = "",
) -> dict[str, Any]:
    resolved = tools or resolve_video_clip_tools()
    metadata = probe_video(source, resolved, runner=runner)
    in_point, out_point = validate_clip_range(start, end, metadata["duration"])
    width, height = output_dimensions(metadata["width"], metadata["height"], resolution)
    clean_clip_id = _safe_id(clip_id, "片段 ID") if clip_id else f"clip_{uuid.uuid4().hex}"
    directory = canvas_clip_directory(media_generated_root, canvas_id)
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"{clean_clip_id}.mp4"
    partial = directory / f".{clean_clip_id}.{uuid.uuid4().hex}.partial.mp4"
    command = build_video_clip_command(
        resolved,
        source,
        partial,
        start=in_point,
        end=out_point,
        width=width,
        height=height,
    )
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=max(120.0, (out_point - in_point) * 12.0),
            creationflags=_WINDOWS_CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0 or not partial.is_file() or partial.stat().st_size <= 0:
            raise VideoClipError((result.stderr or "视频截取失败。").strip())
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)
    return {
        "clip_id": clean_clip_id,
        "path": str(output),
        "start": in_point,
        "end": out_point,
        "duration": out_point - in_point,
        "width": width,
        "height": height,
        "resolution": str(resolution or "1080p").lower(),
        "source": metadata,
        "size": output.stat().st_size,
    }


def delete_video_clip(media_generated_root: str | Path, canvas_id: str, clip_id: str) -> bool:
    clean_clip_id = _safe_id(clip_id, "片段 ID")
    directory = canvas_clip_directory(media_generated_root, canvas_id)
    target = (directory / f"{clean_clip_id}.mp4").resolve()
    if target.parent != directory:
        raise VideoClipError("片段文件路径无效。")
    existed = target.is_file()
    target.unlink(missing_ok=True)
    try:
        directory.rmdir()
        directory.parent.rmdir()
    except OSError:
        pass
    return existed


def purge_canvas_video_clips(media_generated_root: str | Path, canvas_id: str) -> bool:
    directory = canvas_clip_directory(media_generated_root, canvas_id).parent
    existed = directory.is_dir()
    if existed:
        shutil.rmtree(directory)
    return existed
