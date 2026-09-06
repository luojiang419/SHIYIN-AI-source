from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from worker.depth_controls import DepthControls, apply_depth_controls, normalize_relative_depth
    from worker.models import MODEL_PROFILES, get_profile, infer_depths, model_status
else:
    from .depth_controls import DepthControls, apply_depth_controls, normalize_relative_depth
    from .models import MODEL_PROFILES, get_profile, infer_depths, model_status


LAB_ROOT = Path(__file__).resolve().parents[1]


def emit(event_type: str, **payload: Any) -> None:
    print(json.dumps({"type": event_type, **payload}, ensure_ascii=False), flush=True)


def progress(percent: int, message: str) -> None:
    emit("progress", percent=max(0, min(100, int(percent))), message=message)


def find_binary(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise FileNotFoundError(f"未找到 {name}，请先安装 FFmpeg 并加入 PATH")
    return value


def _hidden_process_kwargs() -> dict[str, Any]:
    if os.name != "nt":
        return {}
    return {"creationflags": 0x08000000}


def probe_video(path: Path) -> dict[str, Any]:
    command = [
        find_binary("ffprobe"),
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", **_hidden_process_kwargs())
    if completed.returncode != 0:
        raise RuntimeError(f"FFprobe 无法读取视频：{completed.stderr.strip()}")
    data = json.loads(completed.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise ValueError("输入文件没有视频轨道")
    stream = streams[0]

    def fraction(value: str | None) -> float:
        if not value or value in {"0/0", "N/A"}:
            return 0.0
        numerator, _, denominator = value.partition("/")
        return float(numerator) / max(float(denominator or 1), 1e-9)

    fps = fraction(stream.get("avg_frame_rate")) or fraction(stream.get("r_frame_rate"))
    duration = float(stream.get("duration") or data.get("format", {}).get("duration") or 0)
    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": fps,
        "duration": duration,
        "frameCount": int(stream.get("nb_frames") or round(duration * fps) or 0),
    }


def _scaled_size(width: int, height: int, max_resolution: int) -> tuple[int, int]:
    scale = min(1.0, max_resolution / max(width, height))
    output_width = max(2, int(round(width * scale / 2.0)) * 2)
    output_height = max(2, int(round(height * scale / 2.0)) * 2)
    return output_width, output_height


def read_video_frames(
    path: Path,
    target_fps: float,
    max_frames: int,
    max_resolution: int,
) -> tuple[np.ndarray, float, dict[str, Any]]:
    info = probe_video(path)
    fps = float(target_fps if target_fps > 0 else info["fps"])
    if info["fps"] > 0:
        fps = min(fps, float(info["fps"]))
    fps = max(fps, 1.0)
    width, height = _scaled_size(info["width"], info["height"], max_resolution)
    command = [
        find_binary("ffmpeg"),
        "-v",
        "error",
        "-i",
        str(path),
        "-an",
        "-sn",
        "-vf",
        f"fps={fps:.8f},scale={width}:{height}:flags=lanczos",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
    ]
    if max_frames > 0:
        command.extend(["-frames:v", str(max_frames)])
    command.append("pipe:1")
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_hidden_process_kwargs())
    frame_bytes = width * height * 3
    frames: list[np.ndarray] = []
    assert process.stdout is not None
    while True:
        raw = process.stdout.read(frame_bytes)
        if not raw:
            break
        if len(raw) != frame_bytes:
            process.kill()
            raise RuntimeError("视频解码得到不完整帧")
        frames.append(np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3).copy())
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"FFmpeg 视频解码失败：{stderr.strip()}")
    if not frames:
        raise ValueError("输入视频没有可解码帧")
    info.update({"processedWidth": width, "processedHeight": height, "processedFps": fps, "processedFrames": len(frames)})
    return np.stack(frames, axis=0), fps, info


def encode_gray_video(frames: np.ndarray, fps: float, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    height, width = frames.shape[1:3]
    command = [
        find_binary("ffmpeg"),
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-s:v",
        f"{width}x{height}",
        "-r",
        f"{fps:.8f}",
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "15",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, **_hidden_process_kwargs())
    assert process.stdin is not None
    try:
        for frame in np.asarray(frames, dtype=np.uint8):
            process.stdin.write(np.ascontiguousarray(frame).tobytes())
        process.stdin.close()
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        return_code = process.wait()
    except BaseException:
        process.kill()
        process.wait()
        raise
    if return_code != 0:
        raise RuntimeError(f"FFmpeg 深度视频编码失败：{stderr.strip()}")


def run_infer(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"输入视频不存在：{input_path}")
    profile = get_profile(args.model)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    progress(5, "正在读取视频信息")
    frames, fps, video_info = read_video_frames(input_path, args.target_fps, args.max_frames, args.max_resolution)
    progress(20, f"已解码 {len(frames)} 帧，准备加载模型")
    depths, gpu_memory = infer_depths(LAB_ROOT, profile.key, frames, fps, args.input_size, progress)
    if depths.shape[0] != frames.shape[0]:
        raise RuntimeError(f"模型输出帧数 {depths.shape[0]} 与输入帧数 {frames.shape[0]} 不一致")
    progress(82, "正在归一化 Relative Depth")
    normalized, normalization = normalize_relative_depth(depths)
    raw_path = output_dir / "depth-relative-normalized.npz"
    np.savez_compressed(raw_path, depths=normalized.astype(np.float16), fps=np.float32(fps))
    controls = DepthControls.from_mapping(json.loads(args.params_json))
    video_path = output_dir / "depth-preview.mp4"
    progress(88, "正在应用深度参数并编码 H.264")
    encode_gray_video(apply_depth_controls(normalized, controls), fps, video_path)
    elapsed = time.perf_counter() - started
    metadata = {
        "schema": "shiyin.video-depth-lab/v1",
        "createdAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input": {"path": str(input_path), "name": input_path.name, **video_info},
        "model": {
            "key": profile.key,
            "label": profile.label,
            "encoder": profile.encoder,
            "precision": profile.precision,
            "depthType": profile.depth_type,
            "inputSize": args.input_size,
            "inferLen": profile.infer_len,
            "overlap": profile.overlap,
            "keyframes": list(profile.keyframes),
            "interpLen": profile.interp_len,
            "licenseNotice": profile.license_notice,
            "sourceRevision": profile.source_revision,
            "checkpointSha256": profile.checkpoint_sha256,
            "inferenceSeed": 0,
        },
        "parameters": controls.as_camel_dict(),
        "normalization": normalization,
        "gpuMemory": gpu_memory,
        "elapsedSeconds": round(elapsed, 3),
        "rawDepthPath": str(raw_path),
        "outputVideoPath": str(video_path),
    }
    metadata_path = output_dir / "run-metadata.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    progress(100, "深度视频已生成")
    return {**metadata, "metadataPath": str(metadata_path), "outputDirectory": str(output_dir)}


def run_postprocess(args: argparse.Namespace) -> dict[str, Any]:
    raw_path = Path(args.raw).resolve()
    if not raw_path.is_file():
        raise FileNotFoundError(f"原始深度数据不存在：{raw_path}")
    payload = np.load(raw_path)
    depths = np.asarray(payload["depths"], dtype=np.float32)
    fps = float(payload["fps"])
    controls = DepthControls.from_mapping(json.loads(args.params_json))
    output = Path(args.output).resolve()
    progress(20, "正在应用深度参数")
    encode_gray_video(apply_depth_controls(depths, controls), fps, output)
    progress(100, "参数预览视频已更新")
    return {"outputVideoPath": str(output), "parameters": controls.as_camel_dict(), "fps": fps}


def run_status() -> dict[str, Any]:
    import torch

    ffmpeg = shutil.which("ffmpeg")
    models = model_status(LAB_ROOT)
    return {
        "ready": bool(ffmpeg and torch.cuda.is_available() and all(row["ready"] for row in models)),
        "python": sys.executable,
        "pythonVersion": sys.version.split()[0],
        "torchVersion": torch.__version__,
        "cudaAvailable": torch.cuda.is_available(),
        "cudaVersion": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
        "gpuMemoryBytes": torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else 0,
        "ffmpeg": ffmpeg or "",
        "models": models,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SHIYIN 视频深度统一推理 worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")

    infer = subparsers.add_parser("infer")
    infer.add_argument("--model", choices=sorted(MODEL_PROFILES), required=True)
    infer.add_argument("--input", required=True)
    infer.add_argument("--output-dir", required=True)
    infer.add_argument("--input-size", type=int, required=True)
    infer.add_argument("--target-fps", type=float, default=12.0)
    infer.add_argument("--max-frames", type=int, default=48)
    infer.add_argument("--max-resolution", type=int, default=960)
    infer.add_argument("--params-json", default="{}")

    post = subparsers.add_parser("postprocess")
    post.add_argument("--raw", required=True)
    post.add_argument("--output", required=True)
    post.add_argument("--params-json", default="{}")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "status":
            result = run_status()
        elif args.command == "infer":
            result = run_infer(args)
        else:
            result = run_postprocess(args)
        emit("result", result=result)
        return 0
    except BaseException as error:
        emit("error", error=str(error), errorType=type(error).__name__)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
