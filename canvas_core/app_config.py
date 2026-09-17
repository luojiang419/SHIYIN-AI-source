from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any


DEFAULT_CLOSE_BEHAVIOR = "ask_on_close"
CLOSE_BEHAVIORS = frozenset({DEFAULT_CLOSE_BEHAVIOR, "minimize_to_tray", "exit"})
DEFAULT_GENERATED_OUTPUT_DIR = ""
DEFAULT_BATCH_OUTFIT_OUTPUT_DIR = ""
DEFAULT_QUICK_SAVE_MODE = "manual"
QUICK_SAVE_MODES = frozenset({DEFAULT_QUICK_SAVE_MODE, "silent"})
DEFAULT_QUICK_SAVE_DIR = ""
DEFAULT_TOPAZ_VIDEO_INSTALL_DIR = ""
DEFAULT_DEPTH_MAP_MODE = "person"
DEPTH_MAP_MODES = frozenset({DEFAULT_DEPTH_MAP_MODE, "professional"})
DEFAULT_DEPTH_MAP_CONTROLS: dict[str, Any] = {
    "farPoint": 0,
    "nearPoint": 100,
    "midtone": 0,
    "contrast": 100,
    "brightness": 0,
    "smooth": 0,
    "invert": False,
}
DEFAULT_SHORTCUT_BINDINGS: dict[str, str] = {}
DEFAULT_PERSON_DEPTH_LAN_SERVER_ENABLED = False
DEFAULT_PERSON_DEPTH_LAN_HOST = "192.168.0.24"
DEFAULT_PERSON_DEPTH_LAN_PORT = 3011
DEFAULT_PERSON_DEPTH_LAN_SOURCE = "http://192.168.0.24:3011"
_CONFIG_LOCK = RLock()


def _normalize_depth_map_controls(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, dict) else {}
    ranges = {
        "farPoint": (0, 99),
        "nearPoint": (1, 100),
        "midtone": (-100, 100),
        "contrast": (0, 300),
        "brightness": (-100, 100),
        "smooth": (0, 50),
    }
    result: dict[str, Any] = {}
    for key, (minimum, maximum) in ranges.items():
        raw = source.get(key, DEFAULT_DEPTH_MAP_CONTROLS[key])
        if isinstance(raw, bool):
            raw = int(raw)
        try:
            number = int(round(float(raw)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"深度图参数 {key} 必须是数字") from exc
        result[key] = max(minimum, min(maximum, number))
    result["invert"] = bool(source.get("invert", DEFAULT_DEPTH_MAP_CONTROLS["invert"]))
    if result["nearPoint"] <= result["farPoint"]:
        result["nearPoint"] = min(100, result["farPoint"] + 1)
    if result["nearPoint"] <= result["farPoint"]:
        result["farPoint"] = max(0, result["nearPoint"] - 1)
    return result


def _normalize_canvas_arrange_spacing(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 240 or int(value) != value:
        raise ValueError("自动整理间距必须是 0～240 之间的整数")
    return int(value)


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


def _desktop_lan_source(data_root: str | Path) -> str:
    try:
        settings = json.loads((Path(data_root) / "config" / "update.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_PERSON_DEPTH_LAN_SOURCE
    if not isinstance(settings, dict):
        return DEFAULT_PERSON_DEPTH_LAN_SOURCE
    if settings.get("lanUpdateEnabled") is False:
        return ""
    source = str(settings.get("lanUpdateUrl") or "").strip().rstrip("/")
    return source if source.startswith("http://") else DEFAULT_PERSON_DEPTH_LAN_SOURCE


def _component_lan_source(data_root: str | Path, value: object) -> str:
    source = str(value or "").strip().rstrip("/")
    if source and source != DEFAULT_PERSON_DEPTH_LAN_SOURCE:
        return source
    return _desktop_lan_source(data_root)


def read_app_config(data_root: str | Path) -> dict[str, Any]:
    path = _config_path(data_root)
    with _CONFIG_LOCK:
        if not path.exists():
            return {
                "close_behavior": DEFAULT_CLOSE_BEHAVIOR,
                "generated_output_dir": DEFAULT_GENERATED_OUTPUT_DIR,
                "batch_outfit_output_dir": DEFAULT_BATCH_OUTFIT_OUTPUT_DIR,
                "quick_save_mode": DEFAULT_QUICK_SAVE_MODE,
                "quick_save_dir": DEFAULT_QUICK_SAVE_DIR,
                "topaz_video_install_dir": DEFAULT_TOPAZ_VIDEO_INSTALL_DIR,
                "depth_map_mode": DEFAULT_DEPTH_MAP_MODE,
                "depth_map_controls": DEFAULT_DEPTH_MAP_CONTROLS.copy(),
                "shortcut_bindings": DEFAULT_SHORTCUT_BINDINGS.copy(),
                "person_depth_lan_server_enabled": DEFAULT_PERSON_DEPTH_LAN_SERVER_ENABLED,
                "person_depth_lan_host": DEFAULT_PERSON_DEPTH_LAN_HOST,
                "person_depth_lan_port": DEFAULT_PERSON_DEPTH_LAN_PORT,
                "person_depth_lan_source": _desktop_lan_source(data_root),
                "canvas_arrange_spacing": 56,
                "canvas_group_arrange_spacing": 28,
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
        value["batch_outfit_output_dir"] = str(value.get("batch_outfit_output_dir") or "").strip()
        quick_save_mode = str(value.get("quick_save_mode") or DEFAULT_QUICK_SAVE_MODE).strip()
        value["quick_save_mode"] = quick_save_mode if quick_save_mode in QUICK_SAVE_MODES else DEFAULT_QUICK_SAVE_MODE
        value["quick_save_dir"] = str(value.get("quick_save_dir") or "").strip()
        if value["quick_save_mode"] == "silent" and not value["quick_save_dir"]:
            value["quick_save_mode"] = DEFAULT_QUICK_SAVE_MODE
        value["topaz_video_install_dir"] = str(value.get("topaz_video_install_dir") or "").strip()
        depth_map_mode = str(value.get("depth_map_mode") or DEFAULT_DEPTH_MAP_MODE).strip()
        value["depth_map_mode"] = depth_map_mode if depth_map_mode in DEPTH_MAP_MODES else DEFAULT_DEPTH_MAP_MODE
        value["depth_map_controls"] = _normalize_depth_map_controls(value.get("depth_map_controls"))
        value["shortcut_bindings"] = _normalize_shortcut_bindings(value.get("shortcut_bindings"))
        value["person_depth_lan_server_enabled"] = bool(value.get("person_depth_lan_server_enabled", False))
        value["person_depth_lan_host"] = str(value.get("person_depth_lan_host") or DEFAULT_PERSON_DEPTH_LAN_HOST).strip()
        try:
            value["person_depth_lan_port"] = int(value.get("person_depth_lan_port") or DEFAULT_PERSON_DEPTH_LAN_PORT)
        except (TypeError, ValueError):
            value["person_depth_lan_port"] = DEFAULT_PERSON_DEPTH_LAN_PORT
        value["person_depth_lan_source"] = _component_lan_source(data_root, value.get("person_depth_lan_source"))
        for key, default in (("canvas_arrange_spacing", 56), ("canvas_group_arrange_spacing", 28)):
            try:
                value[key] = _normalize_canvas_arrange_spacing(value.get(key, default))
            except ValueError:
                value[key] = default
        return value


def update_app_settings(
    data_root: str | Path,
    *,
    close_behavior: str | None = None,
    generated_output_dir: str | None = None,
    batch_outfit_output_dir: str | None = None,
    quick_save_mode: str | None = None,
    quick_save_dir: str | None = None,
    topaz_video_install_dir: str | None = None,
    depth_map_mode: str | None = None,
    depth_map_controls: dict[str, Any] | None = None,
    shortcut_bindings: dict[str, str] | None = None,
    canvas_arrange_spacing: int | None = None,
    canvas_group_arrange_spacing: int | None = None,
    person_depth_lan_server_enabled: bool | None = None,
    person_depth_lan_host: str | None = None,
    person_depth_lan_port: int | None = None,
    person_depth_lan_source: str | None = None,
) -> dict[str, Any]:
    if close_behavior is None and generated_output_dir is None and batch_outfit_output_dir is None and quick_save_mode is None and quick_save_dir is None and topaz_video_install_dir is None and depth_map_mode is None and depth_map_controls is None and shortcut_bindings is None and canvas_arrange_spacing is None and canvas_group_arrange_spacing is None and person_depth_lan_server_enabled is None and person_depth_lan_host is None and person_depth_lan_port is None and person_depth_lan_source is None:
        raise ValueError("没有可保存的软件设置")
    path = _config_path(data_root)
    with _CONFIG_LOCK:
        value = read_app_config(data_root)
        stored_source = (
            json.loads(path.read_text(encoding="utf-8")).get("person_depth_lan_source", DEFAULT_PERSON_DEPTH_LAN_SOURCE)
            if path.exists() else DEFAULT_PERSON_DEPTH_LAN_SOURCE
        )
        value["person_depth_lan_source"] = stored_source
        if canvas_group_arrange_spacing is not None:
            value["canvas_group_arrange_spacing"] = _normalize_canvas_arrange_spacing(canvas_group_arrange_spacing)
        if canvas_arrange_spacing is not None:
            value["canvas_arrange_spacing"] = _normalize_canvas_arrange_spacing(canvas_arrange_spacing)
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
        if batch_outfit_output_dir is not None:
            directory = str(batch_outfit_output_dir or "").strip()
            if directory and not Path(directory).expanduser().is_absolute():
                raise ValueError("批量换款保存目录必须是绝对路径")
            value["batch_outfit_output_dir"] = directory
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
        if depth_map_mode is not None:
            mode = str(depth_map_mode or "").strip()
            if mode not in DEPTH_MAP_MODES:
                raise ValueError("深度图处理模式必须是 person 或 professional")
            value["depth_map_mode"] = mode
        if depth_map_controls is not None:
            value["depth_map_controls"] = _normalize_depth_map_controls(depth_map_controls)
        if shortcut_bindings is not None:
            value["shortcut_bindings"] = _normalize_shortcut_bindings(shortcut_bindings)
        if person_depth_lan_server_enabled is not None:
            value["person_depth_lan_server_enabled"] = bool(person_depth_lan_server_enabled)
        if person_depth_lan_host is not None:
            host = str(person_depth_lan_host or "").strip()
            if not host or len(host) > 255:
                raise ValueError("局域网服务器地址无效")
            value["person_depth_lan_host"] = host
        if person_depth_lan_port is not None:
            port = int(person_depth_lan_port)
            if not 1024 <= port <= 65535:
                raise ValueError("局域网服务器端口必须为 1024～65535")
            value["person_depth_lan_port"] = port
        if person_depth_lan_source is not None:
            source = str(person_depth_lan_source).strip().rstrip("/")
            if source and not source.startswith("http://"):
                raise ValueError("局域网下载地址必须使用 http://")
            value["person_depth_lan_source"] = source
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        return read_app_config(data_root)


def update_close_behavior(data_root: str | Path, close_behavior: str) -> dict[str, Any]:
    return update_app_settings(data_root, close_behavior=close_behavior)
