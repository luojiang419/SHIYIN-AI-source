from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any


DEFAULT_CLOSE_BEHAVIOR = "ask_on_close"
CLOSE_BEHAVIORS = frozenset({DEFAULT_CLOSE_BEHAVIOR, "minimize_to_tray", "exit"})
DEFAULT_GENERATED_OUTPUT_DIR = ""
DEFAULT_QUICK_SAVE_MODE = "manual"
QUICK_SAVE_MODES = frozenset({DEFAULT_QUICK_SAVE_MODE, "silent"})
DEFAULT_QUICK_SAVE_DIR = ""
DEFAULT_TOPAZ_VIDEO_INSTALL_DIR = ""
DEFAULT_SHORTCUT_BINDINGS: dict[str, str] = {}
_CONFIG_LOCK = RLock()


def _normalize_shortcut_bindings(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("快捷键设置必须是对象")
    if len(value) > 200:
        raise ValueError("快捷键设置数量不能超过 200 项")
    result: dict[str, str] = {}
    for raw_action, raw_binding in value.items():
        action = str(raw_action or "").strip()
        if not action or len(action) > 80 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for ch in action):
            raise ValueError("快捷键动作标识不合法")
        if not isinstance(raw_binding, str):
            raise ValueError(f"快捷键 {action} 必须是字符串")
        binding = raw_binding.strip()
        if len(binding) > 64:
            raise ValueError(f"快捷键 {action} 过长")
        result[action] = binding
    return result


def _config_path(data_root: str | Path) -> Path:
    return Path(data_root) / "config" / "app.json"


def read_app_config(data_root: str | Path) -> dict[str, Any]:
    path = _config_path(data_root)
    with _CONFIG_LOCK:
        if not path.exists():
            return {
                "close_behavior": DEFAULT_CLOSE_BEHAVIOR,
                "generated_output_dir": DEFAULT_GENERATED_OUTPUT_DIR,
                "quick_save_mode": DEFAULT_QUICK_SAVE_MODE,
                "quick_save_dir": DEFAULT_QUICK_SAVE_DIR,
                "topaz_video_install_dir": DEFAULT_TOPAZ_VIDEO_INSTALL_DIR,
                "shortcut_bindings": DEFAULT_SHORTCUT_BINDINGS.copy(),
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
        quick_save_mode = str(value.get("quick_save_mode") or DEFAULT_QUICK_SAVE_MODE).strip()
        value["quick_save_mode"] = quick_save_mode if quick_save_mode in QUICK_SAVE_MODES else DEFAULT_QUICK_SAVE_MODE
        value["quick_save_dir"] = str(value.get("quick_save_dir") or "").strip()
        if value["quick_save_mode"] == "silent" and not value["quick_save_dir"]:
            value["quick_save_mode"] = DEFAULT_QUICK_SAVE_MODE
        value["topaz_video_install_dir"] = str(value.get("topaz_video_install_dir") or "").strip()
        value["shortcut_bindings"] = _normalize_shortcut_bindings(value.get("shortcut_bindings"))
        return value


def update_app_settings(
    data_root: str | Path,
    *,
    close_behavior: str | None = None,
    generated_output_dir: str | None = None,
    quick_save_mode: str | None = None,
    quick_save_dir: str | None = None,
    topaz_video_install_dir: str | None = None,
    shortcut_bindings: dict[str, str] | None = None,
) -> dict[str, Any]:
    if close_behavior is None and generated_output_dir is None and quick_save_mode is None and quick_save_dir is None and topaz_video_install_dir is None and shortcut_bindings is None:
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
        if quick_save_mode is not None:
            mode = str(quick_save_mode or "").strip()
            if mode not in QUICK_SAVE_MODES:
                raise ValueError("快捷保存模式必须是 manual 或 silent")
            value["quick_save_mode"] = mode
        if quick_save_dir is not None:
            directory = str(quick_save_dir or "").strip()
            if directory and not Path(directory).expanduser().is_absolute():
                raise ValueError("快捷保存目录必须是绝对路径")
            value["quick_save_dir"] = directory
        if value["quick_save_mode"] == "silent" and not value["quick_save_dir"]:
            raise ValueError("启用静默保存前必须选择快捷保存目录")
        if topaz_video_install_dir is not None:
            directory = str(topaz_video_install_dir or "").strip()
            if directory and not Path(directory).expanduser().is_absolute():
                raise ValueError("Topaz Video AI 安装目录必须是绝对路径")
            value["topaz_video_install_dir"] = directory
        if shortcut_bindings is not None:
            value["shortcut_bindings"] = _normalize_shortcut_bindings(shortcut_bindings)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return value


def update_close_behavior(data_root: str | Path, close_behavior: str) -> dict[str, Any]:
    return update_app_settings(data_root, close_behavior=close_behavior)
