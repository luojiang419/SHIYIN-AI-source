"""Browser playback proxy for uploaded video; the source stays untouched for editing."""

import json
import os
import subprocess
from pathlib import Path

from canvas_core.video_clip import resolve_video_clip_tools


VIDEO_EXTENSIONS = {
    ".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".flv",
    ".mxf", ".mts", ".m2ts", ".ts", ".mpg", ".mpeg", ".wmv", ".vob", ".3gp",
}


def browser_playback_proxy(source: str, destination: str) -> bool:
    """Return whether a separate MP4 proxy was generated for this source."""
    tools = resolve_video_clip_tools()
    if not tools.ffprobe:
        if Path(source).suffix.lower() in {".mp4", ".m4v", ".webm"}:
            return False
        raise RuntimeError("未检测到 FFprobe，无法识别专业视频编码")
    probe = subprocess.run(
        [tools.ffprobe, "-v", "error", "-show_streams", "-of", "json", source],
        capture_output=True, text=True, timeout=120, check=False,
    )
    if probe.returncode:
        raise ValueError("无法识别视频格式或文件已损坏")
    streams = json.loads(probe.stdout).get("streams") or []
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    if not video:
        raise ValueError("文件不包含可解码的视频轨道")
    suffix = Path(source).suffix.lower()
    video_codec = video.get("codec_name")
    audio_codec = audio.get("codec_name") if audio else None
    pixel_format = video.get("pix_fmt")
    native_mp4 = suffix in {".mp4", ".m4v"} and video_codec == "h264" and pixel_format in {"yuv420p", "yuvj420p"} and audio_codec in {None, "aac", "mp3"}
    native_webm = suffix == ".webm" and video_codec in {"vp8", "vp9", "av1"} and pixel_format == "yuv420p" and audio_codec in {None, "opus", "vorbis"}
    if native_mp4 or native_webm:
        return False
    if not tools.ffmpeg:
        raise RuntimeError("未检测到 FFmpeg，无法为该视频生成浏览器播放版本")
    temporary = destination + ".tmp.mp4"
    command = [
        tools.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source,
        "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", temporary,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode or not os.path.getsize(temporary):
            raise RuntimeError((result.stderr or "视频转码失败")[-500:])
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return True
