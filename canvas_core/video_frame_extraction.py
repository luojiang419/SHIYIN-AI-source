"""视频抽帧核心能力。

该模块只负责 FFmpeg/FFprobe 交互和文件产物，不依赖 FastAPI，便于桌面端和
后台任务复用，也便于在没有启动服务时做单元测试。
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .video_clip import VideoClipError, VideoClipTools, parse_video_probe, resolve_video_clip_tools


class VideoFrameExtractionError(VideoClipError):
    """视频抽帧失败。"""


STRATEGIES: tuple[dict[str, Any], ...] = (
    {
        "value": "sceneAndInterval",
        "label": "场景变化 + 固定间隔",
        "description": "优先保留场景切换，同时限制相邻帧的最小时间间隔。",
    },
    {
        "value": "intervalOnly",
        "label": "固定时间间隔",
        "description": "按固定秒数抽帧，适合快速浏览视频节奏。",
    },
    {
        "value": "perFrame",
        "label": "逐帧抽取",
        "description": "输出视频中的每一帧，适合短视频或精确分析。",
    },
    {
        "value": "highFidelity",
        "label": "高保真间隔",
        "description": "按固定秒数抽取并使用更高 PNG 质量。",
    },
)
STRATEGY_VALUES = frozenset(item["value"] for item in STRATEGIES)
DEFAULT_STRATEGY = "sceneAndInterval"
DEFAULT_INTERVAL_SECONDS = 1.0
DEFAULT_SCENE_THRESHOLD = 0.30
DEFAULT_MAX_FRAMES = 300
MAX_MAX_FRAMES = 2000

_WINDOWS_CREATE_NO_WINDOW = 0x08000000
_SHOWINFO_RE = re.compile(r"showinfo.*?\bn:\s*(?P<index>\d+).*?pts_time:(?P<timestamp>-?(?:\d+(?:\.\d*)?|\.\d+))")


@dataclass(frozen=True)
class VideoFrameExtractionRequest:
    source: str | Path
    output_directory: str | Path
    strategy: str = DEFAULT_STRATEGY
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS
    scene_threshold: float = DEFAULT_SCENE_THRESHOLD
    max_frames: int = DEFAULT_MAX_FRAMES
    run_id: str = ""


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _safe_component(value: str, label: str) -> str:
    clean = str(value or "").strip()
    if not clean or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for ch in clean):
        raise VideoFrameExtractionError(f"{label}无效。")
    return clean


def validate_extraction_options(
    strategy: str = DEFAULT_STRATEGY,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    scene_threshold: float = DEFAULT_SCENE_THRESHOLD,
    max_frames: int = DEFAULT_MAX_FRAMES,
) -> dict[str, Any]:
    selected = str(strategy or DEFAULT_STRATEGY).strip()
    if selected not in STRATEGY_VALUES:
        raise VideoFrameExtractionError("不支持的视频抽帧方法。")
    interval = _finite(interval_seconds, -1)
    if interval <= 0 or interval > 3600:
        raise VideoFrameExtractionError("抽帧间隔必须在 0 到 3600 秒之间。")
    threshold = _finite(scene_threshold, -1)
    if threshold < 0 or threshold > 1:
        raise VideoFrameExtractionError("场景变化阈值必须在 0 到 1 之间。")
    try:
        frame_limit = int(max_frames)
    except (TypeError, ValueError) as exc:
        raise VideoFrameExtractionError("最大抽帧数量无效。") from exc
    if frame_limit < 1 or frame_limit > MAX_MAX_FRAMES:
        raise VideoFrameExtractionError(f"最大抽帧数量必须在 1 到 {MAX_MAX_FRAMES} 之间。")
    return {
        "strategy": selected,
        "interval_seconds": interval,
        "scene_threshold": threshold,
        "max_frames": frame_limit,
    }


def parse_video_probe_payload(payload: str | Mapping[str, Any]) -> dict[str, Any]:
    """解析 ffprobe 输出，并补充适合前端展示的字段。"""
    metadata = parse_video_probe(payload)
    metadata["frame_rate"] = metadata.get("fps", 0.0)
    metadata["duration_ms"] = int(round(float(metadata.get("duration", 0.0)) * 1000))
    metadata["display_size"] = f"{metadata['width']}×{metadata['height']}"
    return metadata


def probe_video_frames(
    path: str | Path,
    tools: VideoClipTools | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """读取视频元数据；独立命名以避免和视频剪辑接口耦合。"""
    source = Path(path)
    if not source.is_file():
        raise VideoFrameExtractionError("源视频文件不存在。")
    resolved = tools or resolve_video_clip_tools()
    if not resolved.ffprobe:
        raise VideoFrameExtractionError("未检测到 ffprobe，请安装 FFmpeg 或配置 SHIYIN_FFPROBE_PATH。")
    result = runner(
        [resolved.ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=60,
        creationflags=_WINDOWS_CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        raise VideoFrameExtractionError((result.stderr or "无法读取视频信息。").strip())
    try:
        return parse_video_probe_payload(result.stdout)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise VideoFrameExtractionError("无法解析视频信息。") from exc


def build_video_frame_command(
    tools: VideoClipTools,
    source: str | Path,
    output_pattern: str | Path,
    *,
    strategy: str = DEFAULT_STRATEGY,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    scene_threshold: float = DEFAULT_SCENE_THRESHOLD,
    max_frames: int = DEFAULT_MAX_FRAMES,
) -> list[str]:
    options = validate_extraction_options(strategy, interval_seconds, scene_threshold, max_frames)
    if not tools.ffmpeg:
        raise VideoFrameExtractionError("未检测到 ffmpeg，请安装 FFmpeg 或配置 SHIYIN_FFMPEG_PATH。")
    selected = options["strategy"]
    interval = options["interval_seconds"]
    threshold = options["scene_threshold"]
    if selected == "sceneAndInterval":
        video_filter = f"select=eq(n\\,0)+gt(scene\\,{threshold:.6f})+gte(t-prev_selected_t\\,{interval:.6f}),showinfo"
        quality = "2"
        vfr = "vfr"
    elif selected == "perFrame":
        video_filter = "showinfo"
        quality = "2"
        vfr = "vfr"
    else:
        video_filter = f"fps=1/{interval:.6f},showinfo"
        quality = "1" if selected == "highFidelity" else "2"
        vfr = "0"
    return [
        tools.ffmpeg,
        "-hide_banner", "-nostdin", "-y",
        "-i", str(source),
        "-map", "0:v:0",
        "-vf", video_filter,
        "-frames:v", str(options["max_frames"]),
        "-fps_mode", vfr,
        "-c:v", "png",
        "-compression_level", "0" if selected == "highFidelity" else "3",
        "-q:v", quality,
        str(output_pattern),
    ]


def parse_showinfo_timestamps(text: str) -> list[dict[str, Any]]:
    """从 FFmpeg showinfo 日志中提取顺序帧号和时间戳。"""
    parsed: list[dict[str, Any]] = []
    for match in _SHOWINFO_RE.finditer(str(text or "")):
        timestamp = _finite(match.group("timestamp"), -1)
        if timestamp < 0:
            continue
        parsed.append({"source_index": int(match.group("index")), "timestamp": timestamp})
    return parsed


def _output_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("frame_*.png"), key=lambda item: item.name)


def canvas_video_frame_directory(media_generated_root: str | Path, canvas_id: str, run_id: str) -> Path:
    """返回并校验画布抽帧产物目录，防止通过 ID 穿越到媒体根目录之外。"""
    root = Path(media_generated_root).resolve()
    canvas_component = _safe_component(canvas_id, "画布 ID")
    run_component = _safe_component(run_id, "抽帧运行 ID")
    target = (root / "canvases" / canvas_component / "video-frames" / run_component).resolve()
    if root not in target.parents:
        raise VideoFrameExtractionError("画布视频抽帧目录无效。")
    return target


def extract_video_frames(
    request: VideoFrameExtractionRequest,
    *,
    tools: VideoClipTools | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """同步执行抽帧并返回产物；调用方应放入线程或进程任务。"""
    source = Path(request.source).resolve()
    if not source.is_file():
        raise VideoFrameExtractionError("源视频文件不存在。")
    options = validate_extraction_options(
        request.strategy,
        request.interval_seconds,
        request.scene_threshold,
        request.max_frames,
    )
    output_directory = Path(request.output_directory).resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    run_id = _safe_component(request.run_id, "抽帧运行 ID") if request.run_id else f"extract_{uuid.uuid4().hex}"
    pattern = output_directory / "frame_%06d.png"
    command = build_video_frame_command(tools or resolve_video_clip_tools(), source, pattern, **options)
    try:
        result = runner(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=max(120.0, float(options["max_frames"]) * max(1.0, options["interval_seconds"]) * 4.0),
            creationflags=_WINDOWS_CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoFrameExtractionError("视频抽帧超时。") from exc
    files = _output_files(output_directory)
    if result.returncode != 0 or not files:
        message = (result.stderr or result.stdout or "视频抽帧失败。").strip()
        for path in files:
            path.unlink(missing_ok=True)
        raise VideoFrameExtractionError(message[-1200:])
    timestamps = parse_showinfo_timestamps(f"{result.stderr or ''}\n{result.stdout or ''}")
    frames: list[dict[str, Any]] = []
    for index, path in enumerate(files[: options["max_frames"]]):
        item = timestamps[index] if index < len(timestamps) else {}
        frames.append(
            {
                "index": index,
                "source_index": item.get("source_index", index),
                "timestamp": float(item.get("timestamp", 0.0)),
                "timestamp_ms": int(round(float(item.get("timestamp", 0.0)) * 1000)),
                "path": str(path),
                "size": path.stat().st_size,
            }
        )
    return {
        "run_id": run_id,
        "strategy": options["strategy"],
        "interval_seconds": options["interval_seconds"],
        "scene_threshold": options["scene_threshold"],
        "frame_count": len(frames),
        "frames": frames,
        "output_directory": str(output_directory),
    }


__all__ = [
    "DEFAULT_INTERVAL_SECONDS",
    "DEFAULT_MAX_FRAMES",
    "DEFAULT_SCENE_THRESHOLD",
    "DEFAULT_STRATEGY",
    "MAX_MAX_FRAMES",
    "STRATEGIES",
    "VideoFrameExtractionError",
    "VideoFrameExtractionRequest",
    "build_video_frame_command",
    "canvas_video_frame_directory",
    "extract_video_frames",
    "parse_showinfo_timestamps",
    "parse_video_probe_payload",
    "probe_video_frames",
    "validate_extraction_options",
]
