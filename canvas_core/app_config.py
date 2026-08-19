from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any


DEFAULT_CLOSE_BEHAVIOR = "ask_on_close"
CLOSE_BEHAVIORS = frozenset({DEFAULT_CLOSE_BEHAVIOR, "minimize_to_tray", "exit"})
DEFAULT_GENERATED_OUTPUT_DIR = ""
DEFAULT_TOPAZ_VIDEO_INSTALL_DIR = ""
_CONFIG_LOCK = RLock()


def _config_path(data_root: str | Path) -> Path:
    return Path(data_root) / "config" / "app.json"


def read_app_config(data_root: str | Path) -> dict[str, Any]:
    path = _config_path(data_root)
    with _CONFIG_LOCK:
        if not path.exists():
            return {
                "close_behavior": DEFAULT_CLOSE_BEHAVIOR,
                "generated_output_dir": DEFAULT_GENERATED_OUTPUT_DIR,
                "topaz_video_install_dir": DEFAULT_TOPAZ_VIDEO_INSTALL_DIR,
            }
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"无法读取软件设置：{exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("软件设置必须是 JSON 对象")
        behavior = str(value.get("close_behavior") or DEFAULT_CLOSE_BEHAVIOR)
        value["close_behavior"] = behavior if behavior in CLOSE_BEHAVIORS else DEFAULT_CLOSE_BEHAVIOR
        value["generated_output_dir"] = str(value.get("generated_output_dir") or "").strip()
        value["topaz_video_install_dir"] = str(value.get("topaz_video_install_dir") or "").strip()
        return value


def update_app_settings(
    data_root: str | Path,
    *,
    close_behavior: str | None = None,
    generated_output_dir: str | None = None,
    topaz_video_install_dir: str | None = None,
) -> dict[str, Any]:
    if close_behavior is None and generated_output_dir is None and topaz_video_install_dir is None:
        raise ValueError("没有可保存的软件设置")
    path = _config_path(data_root)
    with _CONFIG_LOCK:
        value = read_app_config(data_root)
        if close_behavior is not None:
            behavior = str(close_behavior or "").strip()
            if behavior not in CLOSE_BEHAVIORS:
                raise ValueError("关闭软件行为必须是 ask_on_close、minimize_to_tray 或 exit")
            value["close_behavior"] = behavior
        if generated_output_dir is not None:
            directory = str(generated_output_dir or "").strip()
            if directory and not Path(directory).expanduser().is_absolute():
                raise ValueError("生成图片保存目录必须是绝对路径")
            value["generated_output_dir"] = directory
        if topaz_video_install_dir is not None:
            directory = str(topaz_video_install_dir or "").strip()
            if directory and not Path(directory).expanduser().is_absolute():
                raise ValueError("Topaz Video AI 安装目录必须是绝对路径")
            value["topaz_video_install_dir"] = directory
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return value


def update_close_behavior(data_root: str | Path, close_behavior: str) -> dict[str, Any]:
    return update_app_settings(data_root, close_behavior=close_behavior)
