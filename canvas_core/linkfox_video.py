"""LinkFox 图转视频技能适配器。

该模块只负责节点参数规范化、底层 skill 脚本选择、子进程调用和结果转存。
它不把 LinkFox 的临时远程 URL暴露给画布，也不把 API Key写入节点数据。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping


class LinkFoxVideoError(ValueError):
    """可直接展示给用户的 LinkFox 参数或调用错误。"""


MODEL_ALIASES = {
    "seedance2.0": "seedance2.0",
    "seedance2.0fast": "seedance2.0fast",
    "seed": "seedance2.0",
    "seed_fast": "seedance2.0fast",
    "可灵omni": "可灵Omni",
    "kling": "可灵Omni",
    "happyhorse": "HappyHorse",
    "happy_horse": "HappyHorse",
    "海螺": "海螺2.3",
    "hailuo": "海螺2.3",
    "wan": "wan2.6",
    "wan2.6": "wan2.6",
    "可灵2.6": "可灵2.6",
}

REFERENCE_MULTI_MODELS = {"seedance2.0", "seedance2.0fast", "可灵Omni", "HappyHorse"}
REFERENCE_SINGLE_MODELS = {"海螺2.3", "wan2.6"}
FIRST_LAST_MODELS = {"seedance2.0", "seedance2.0fast", "可灵2.6"}

MODEL_SPECS: dict[str, dict[str, Any]] = {
    "seedance2.0": {
        "durations": (5, 10, 15), "resolutions": ("480p", "720p", "1080p"),
        "ratios": ("16:9", "9:16", "adaptive"), "voice": "optional", "max_images": 9,
    },
    "seedance2.0fast": {
        "durations": (5, 10, 15), "resolutions": ("480p", "720p"),
        "ratios": ("16:9", "9:16"), "voice": "optional", "max_images": 9,
    },
    "可灵Omni": {
        "durations": (5, 10, 15), "resolutions": ("720p", "1080p"),
        "ratios": ("16:9", "9:16", "1:1"), "voice": "fixed_false", "max_images": 7,
    },
    "HappyHorse": {
        "durations": (5, 10, 15), "resolutions": ("720p", "1080p"),
        "ratios": ("16:9", "9:16"), "voice": "fixed_true", "max_images": 9,
    },
    "海螺2.3": {
        "durations": (6, 10), "resolutions": ("768p", "1080p"),
        "ratios": (), "voice": "fixed_false", "max_images": 1,
    },
    "wan2.6": {
        "durations": (5, 10, 15), "resolutions": (),
        "ratios": (), "voice": "optional", "max_images": 1,
    },
    "可灵2.6": {
        "durations": (5, 10), "resolutions": ("720p", "1080p"),
        "ratios": ("adaptive",), "voice": "optional", "max_images": 2,
    },
}


def available_models(mode: str = "reference") -> list[dict[str, Any]]:
    """返回前端可直接消费的模型和参数矩阵。"""
    selected = FIRST_LAST_MODELS if mode == "first_last_frame" else (REFERENCE_MULTI_MODELS | REFERENCE_SINGLE_MODELS)
    return [{"id": name, **MODEL_SPECS[name]} for name in MODEL_SPECS if name in selected]


def _canonical_model(value: Any) -> str:
    raw = str(value or "").strip()
    if raw in MODEL_SPECS:
        return raw
    return MODEL_ALIASES.get(raw.lower(), "")


def _http_url(value: Any, label: str) -> str:
    url = str(value or "").strip()
    if not re.match(r"^https?://[^\s]+$", url, re.IGNORECASE):
        raise LinkFoxVideoError(f"{label}必须是可访问的 HTTP(S) 图片 URL；画布本地路径需要先上传到公网地址")
    return url


def normalize_request(raw: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    """规范化节点参数并返回 (skill_json, single|multi)。"""
    data = dict(raw or {})
    if str(data.get("entry") or "") != "img2video":
        raise LinkFoxVideoError("LinkFox 视频节点入口必须为 img2video")
    mode = str(data.get("mode") or "").strip().lower()
    if mode in {"single", "multi_reference", "reference_image"}:
        mode = "reference"
    if mode not in {"reference", "first_last_frame"}:
        mode = "first_last_frame" if data.get("lastFrameImageUrl") else "reference"

    model = _canonical_model(data.get("videoType") or data.get("model"))
    if not model:
        raise LinkFoxVideoError("请选择 LinkFox 视频模型")
    if mode == "first_last_frame" and model not in FIRST_LAST_MODELS:
        raise LinkFoxVideoError(f"模型“{model}”不支持首尾帧模式")
    if mode == "reference" and model not in (REFERENCE_MULTI_MODELS | REFERENCE_SINGLE_MODELS):
        raise LinkFoxVideoError(f"模型“{model}”不支持参考图模式")

    image_list = data.get("imageList") if isinstance(data.get("imageList"), list) else []
    image_url = str(data.get("imageUrl") or "").strip()
    if image_url and image_url not in image_list:
        image_list = [image_url, *image_list]
    image_list = [_http_url(url, f"第{index + 1}张参考图") for index, url in enumerate(image_list) if str(url or "").strip()]
    if not image_list and image_url:
        image_list = [_http_url(image_url, "首帧图片")]
    if not image_list:
        raise LinkFoxVideoError("请至少连接一张图片或填写图片 URL")

    spec = MODEL_SPECS[model]
    if len(image_list) > int(spec["max_images"]):
        raise LinkFoxVideoError(f"模型“{model}”最多支持 {spec['max_images']} 张图片")
    if mode == "reference" and model in REFERENCE_SINGLE_MODELS and len(image_list) != 1:
        raise LinkFoxVideoError(f"模型“{model}”的参考图模式只支持 1 张图片")

    duration = int(data.get("videoTime") or data.get("duration") or 5)
    if duration not in spec["durations"]:
        raise LinkFoxVideoError(f"模型“{model}”不支持 {duration} 秒，请从 {list(spec['durations'])} 中选择")
    resolution = str(data.get("resolution") or "").strip()
    if spec["resolutions"] and resolution and resolution not in spec["resolutions"]:
        raise LinkFoxVideoError(f"模型“{model}”不支持分辨率 {resolution}")
    ratio = str(data.get("aspectRatio") or "").strip()
    if ratio in {"default", "默认", "按模型"}:
        ratio = ""
    if spec["ratios"] and ratio and ratio not in spec["ratios"]:
        raise LinkFoxVideoError(f"模型“{model}”不支持比例 {ratio}")
    if model == "wan2.6" and ratio:
        raise LinkFoxVideoError("wan2.6 不支持显式视频比例")

    voice = bool(data.get("voice", True))
    if spec["voice"] == "fixed_false":
        voice = False
    elif spec["voice"] == "fixed_true":
        voice = True
    last_frame = str(data.get("lastFrameImageUrl") or "").strip()
    if last_frame:
        last_frame = _http_url(last_frame, "尾帧图片")
    if mode == "first_last_frame" and model == "可灵2.6" and last_frame and not (resolution == "1080p" and not voice):
        raise LinkFoxVideoError("可灵2.6 只有 1080p 且关闭声音时才允许传尾帧")

    prompt = str(data.get("prompt") or "").strip()
    if len(prompt) > 2000:
        raise LinkFoxVideoError("提示词不能超过 2000 个字符")
    payload: dict[str, Any] = {
        "entry": "img2video",
        "mode": mode,
        "videoType": model,
        "videoTime": duration,
        "prompt": prompt,
        "promptOptimizer": bool(data.get("promptOptimizer", False)),
        "isPro": bool(data.get("isPro", False)),
        "voice": voice,
        "camera": "multi" if str(data.get("camera") or "single").lower() == "multi" else "single",
    }
    if ratio:
        payload["aspectRatio"] = ratio
    if resolution:
        payload["resolution"] = resolution
    if mode == "reference" and model in REFERENCE_MULTI_MODELS:
        payload["imageList"] = image_list
    else:
        payload["imageUrl"] = image_list[0]
        if last_frame:
            payload["lastFrameImageUrl"] = last_frame
    return payload, "multi" if mode == "reference" and model in REFERENCE_MULTI_MODELS else "single"


def _skill_path(project_root: Path, kind: str) -> Path:
    base = project_root / "skills" / "linkfox-expert-aigc-videogen-image-to-video" / "skills"
    folder = "linkfox-aigc-videogen-multi" if kind == "multi" else "linkfox-aigc-videogen"
    filename = "aigc_videogen_multi.py" if kind == "multi" else "aigc_videogen.py"
    path = base / folder / "scripts" / filename
    if not path.is_file():
        raise LinkFoxVideoError(f"未找到已安装的 LinkFox 底层技能脚本：{path}")
    return path


def _parse_saved_paths(stdout: str) -> list[str]:
    match = re.search(r"Saved full response:\s*(\[[\s\S]*?\])", stdout or "")
    if not match:
        return []
    try:
        values = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return [str(value) for value in values if isinstance(value, str) and value]


def run_skill(raw: Mapping[str, Any], *, project_root: str | Path, output_dir: str | Path, timeout: int = 1300) -> dict[str, Any]:
    """调用已安装的 LinkFox 底层 skill，并将视频转存为画布输出 URL所需的文件。"""
    if not (os.environ.get("LINKFOX_AGENT_API_KEY") or os.environ.get("LINKFOXAGENT_API_KEY")):
        raise LinkFoxVideoError("未配置 LINKFOX_AGENT_API_KEY，请先在环境中设置 LinkFox API Key")
    payload, kind = normalize_request(raw)
    root = Path(project_root).resolve()
    script = _skill_path(root, kind)
    environment = os.environ.copy()
    command = [sys.executable, str(script), json.dumps(payload, ensure_ascii=False)]
    try:
        result = subprocess.run(command, cwd=str(root), env=environment, capture_output=True, text=True, timeout=max(30, int(timeout)))
    except subprocess.TimeoutExpired as exc:
        raise LinkFoxVideoError(f"LinkFox 视频生成超时（已等待 {timeout} 秒）") from exc
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    paths = _parse_saved_paths(stdout)
    if result.returncode != 0 or not paths:
        detail = (stdout + "\n" + stderr).strip()
        # 技能失败时可能把完整响应落盘；只提取错误字段，不把 traceback 透传到前端。
        saved_json = re.search(r"Saved full response:\s*([^\s(]+\.json)", detail)
        if saved_json:
            try:
                body = json.loads(Path(saved_json.group(1)).read_text(encoding="utf-8"))
                detail = str(body.get("errorMsg") or body.get("errmsg") or body.get("error") or body.get("msg") or body.get("status") or detail)
            except Exception:
                pass
        raise LinkFoxVideoError(detail[-800:] or "LinkFox 视频生成失败")

    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    stamp = int(time.time() * 1000)
    for index, source in enumerate(paths):
        source_path = Path(source).expanduser()
        if not source_path.is_file():
            continue
        target = destination / f"linkfox_{stamp}_{index + 1}{source_path.suffix.lower() or '.mp4'}"
        shutil.copy2(source_path, target)
        copied.append(str(target))
    if not copied:
        raise LinkFoxVideoError("LinkFox 已返回结果，但本地视频文件不存在")
    return {"paths": copied, "payload": payload, "kind": kind, "stdout": stdout[-2000:]}


__all__ = ["LinkFoxVideoError", "MODEL_SPECS", "available_models", "normalize_request", "run_skill"]
