from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


KLING_PACKAGES = {
    "china": "@klingai/cli-cn",
    "global": "@klingai/cli-global",
}
KLING_NPM_REGISTRY = "https://registry.npmjs.org"
_SAFE_ARGUMENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_WINDOWS_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
_SUCCESS_STATUSES = {
    "completed",
    "partial_completed",
    "succeed",
    "succeeded",
    "success",
    "done",
}
_FAILURE_STATUSES = {"failed", "cancelled", "canceled", "error"}


class KlingCliError(RuntimeError):
    def __init__(self, message: str, *, exit_code: int | None = None, raw_output: str = ""):
        super().__init__(message)
        self.exit_code = exit_code
        self.raw_output = raw_output


def default_kling_process_runner(
    executable: str,
    arguments: Sequence[str],
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    if os.name == "nt":
        kwargs["creationflags"] = int(kwargs.get("creationflags", 0)) | _WINDOWS_CREATE_NO_WINDOW
    return subprocess.run([executable, *arguments], **kwargs)


@dataclass(frozen=True)
class KlingCliEnvironment:
    node_path: str = ""
    npm_path: str = ""
    kling_path: str = ""
    entrypoint_path: str = ""
    version: str = ""
    error_message: str = ""

    @property
    def is_ready(self) -> bool:
        return not self.error_message and bool(self.executable)

    @property
    def executable(self) -> str:
        if os.name == "nt" and self.entrypoint_path:
            return self.node_path
        return self.kling_path

    @property
    def argument_prefix(self) -> list[str]:
        if os.name == "nt" and self.entrypoint_path:
            return [self.entrypoint_path]
        # 单元测试会在非 Windows 主机上构造 Windows 路径；只要显式提供入口，
        # 仍保持同一安全调用方式，避免退回 shell。
        if self.entrypoint_path and self.node_path:
            return [self.entrypoint_path]
        return []

    @property
    def use_shell(self) -> bool:
        return bool(os.name == "nt" and not self.entrypoint_path and self.kling_path.lower().endswith(".cmd"))


@dataclass
class KlingCliService:
    environment: KlingCliEnvironment
    runner: Callable[..., subprocess.CompletedProcess[Any]] = field(default_factory=lambda: default_kling_process_runner)
    sleeper: Callable[[float], None] = field(default_factory=lambda: time.sleep)
    poll_interval: float = 2.5

    def capabilities(self) -> dict[str, Any]:
        return parse_kling_capabilities(self._invoke_json(["who_am_i", "--quiet"], timeout=45))

    def account(self) -> dict[str, Any]:
        return _body(self._invoke_json(["account", "--quiet"], timeout=45))

    def generate(
        self,
        *,
        command: str,
        model: Mapping[str, Any],
        prompt: str,
        images: Sequence[str],
        parameters: Mapping[str, Any],
        videos: Sequence[str] = (),
        timeout_seconds: float = 900,
    ) -> dict[str, Any]:
        submitted = self.submit(
            command=command,
            model=model,
            prompt=prompt,
            images=images,
            videos=videos,
            parameters=parameters,
        )
        generation_id = submitted["generation_id"]
        credits_consumed = submitted.get("credits_consumed")
        deadline = time.monotonic() + max(1, timeout_seconds)
        last_payload: dict[str, Any] = submitted.get("raw") or {}
        while time.monotonic() < deadline:
            queried = self.query(
                generation_id,
                timeout=min(120, max(10, timeout_seconds)),
            )
            last_payload = queried.get("raw") or {}
            status = _text(queried.get("status")).lower()
            result_url = _text(queried.get("url"))
            if result_url and (not status or status in _SUCCESS_STATUSES):
                return {
                    "generation_id": generation_id,
                    "credits_consumed": credits_consumed,
                    "status": status or "completed",
                    "url": result_url,
                    "raw": last_payload,
                }
            if status in _SUCCESS_STATUSES:
                raise KlingCliError(
                    "可灵任务已完成，但响应中没有视频地址。",
                    raw_output=json.dumps(last_payload, ensure_ascii=False),
                )
            if status in _FAILURE_STATUSES:
                raise KlingCliError(
                    f"可灵视频生成失败：{queried.get('error') or status}",
                    raw_output=json.dumps(last_payload, ensure_ascii=False),
                )
            self.sleeper(self.poll_interval)
        raise KlingCliError(
            f"可灵视频任务轮询超时，可稍后使用 generationId {generation_id} 继续查询。",
            raw_output=json.dumps(last_payload, ensure_ascii=False),
        )

    def submit(
        self,
        *,
        command: str,
        model: Mapping[str, Any],
        prompt: str,
        images: Sequence[str],
        parameters: Mapping[str, Any],
        videos: Sequence[str] = (),
    ) -> dict[str, Any]:
        if command not in {"text_to_video", "image_to_video"}:
            raise KlingCliError(f"不支持的可灵视频命令：{command}")
        model_name = _text(model.get("model"))
        if not model_name:
            raise KlingCliError("提交可灵视频前必须选择动态返回的模型。")
        if command == "image_to_video" and not any(_text(value) for value in images):
            raise KlingCliError("可灵图生视频至少需要一张参考图。")
        if len(videos) > 1:
            raise KlingCliError("可灵当前一次只支持一个视频参考片段。")

        arguments = [command, "--quiet", "--model", model_name]
        if command == "image_to_video":
            for image in images:
                value = _text(image)
                if value:
                    arguments.extend(["--image", value])
        for video in videos:
            value = _text(video)
            if value:
                arguments.extend(["--video", value])

        specs = {
            _text(spec.get("name")): spec
            for spec in _maps(model.get("arguments"))
            if _text(spec.get("name")) not in {"", "prompt"}
        }
        for name, raw_value in parameters.items():
            if name not in specs or not _SAFE_ARGUMENT_NAME.fullmatch(name):
                continue
            value = _argument_text(raw_value)
            if not value:
                continue
            allowed_values = [_text(item) for item in specs[name].get("allowed_values", []) if _text(item)]
            if allowed_values and value not in allowed_values:
                raise KlingCliError(
                    f"可灵参数 {name} 的值 {value} 不在当前模型允许范围：{', '.join(allowed_values)}"
                )
            arguments.extend([f"--{name}", value])
        arguments.append(prompt.strip())

        submitted = _body(self._invoke_json(arguments, timeout=120))
        generation_id = _text(
            _find_value(submitted, ("generationId", "generation_id", "generationID"))
        )
        if not generation_id:
            raise KlingCliError(
                "可灵提交响应缺少 generationId，不能继续轮询。",
                raw_output=json.dumps(submitted, ensure_ascii=False),
            )
        credits_consumed = _find_value(submitted, ("creditsConsumed", "credits_consumed"))
        return {
            "generation_id": generation_id,
            "credits_consumed": credits_consumed,
            "status": "submitted",
            "raw": submitted,
        }

    def query(self, generation_id: str, *, timeout: float = 120) -> dict[str, Any]:
        clean_id = _text(generation_id)
        if not clean_id:
            raise KlingCliError("查询可灵视频任务前必须提供 generationId。")
        queried = _body(
            self._invoke_json(
                ["query_tasks", "--quiet", clean_id],
                timeout=max(10, min(120, timeout)),
            )
        )
        status = _text(
            _find_value(queried, ("taskStatus", "task_status", "status", "state"))
        ).lower()
        message = _text(
            _find_value(
                queried,
                ("errorMessage", "error_message", "message", "failReason"),
            )
        )
        return {
            "generation_id": clean_id,
            "status": status,
            "url": _result_url(queried),
            "error": message if status in _FAILURE_STATUSES else "",
            "raw": queried,
        }

    def _invoke_json(self, arguments: Sequence[str], *, timeout: float) -> dict[str, Any]:
        if not self.environment.is_ready:
            raise KlingCliError(self.environment.error_message or "可灵 CLI 尚未就绪。")
        command_arguments = [*self.environment.argument_prefix, *arguments]
        result = self.runner(
            self.environment.executable,
            command_arguments,
            capture_output=True,
            check=False,
            shell=self.environment.use_shell,
            timeout=timeout,
        )
        stdout = _decode_output(result.stdout).strip()
        stderr = _decode_output(result.stderr).strip()
        if result.returncode != 0:
            raise KlingCliError(
                stderr or "可灵 CLI 执行失败。",
                exit_code=result.returncode,
                raw_output=stdout,
            )
        payload = _decode_json(stdout)
        if payload.get("ok") is False:
            body = _body(payload)
            message = _text(_find_value(body, ("message", "error", "errorMessage")))
            raise KlingCliError(message or "可灵 CLI 返回失败状态。", raw_output=stdout)
        return payload


def resolve_kling_cli() -> KlingCliEnvironment:
    node_path = shutil.which("node") or _windows_program_file("node.exe")
    if not node_path:
        return KlingCliEnvironment(error_message="未检测到 Node.js，需要安装 Node.js 18 或更高版本。")
    node_version = _run_version(node_path)
    if _node_major(node_version) < 18:
        return KlingCliEnvironment(
            node_path=node_path,
            error_message=f"Node.js 版本过低，需要 18 或更高版本；当前为 {node_version or '未知'}。",
        )
    npm_path = shutil.which("npm.cmd" if os.name == "nt" else "npm") or _windows_program_file("npm.cmd")
    if not npm_path:
        return KlingCliEnvironment(node_path=node_path, error_message="未检测到 npm，无法安装或更新可灵 CLI。")
    kling_path = shutil.which("kling.cmd" if os.name == "nt" else "kling") or ""
    if not kling_path:
        kling_path = _npm_global_kling_candidate(npm_path)
    if not kling_path or not Path(kling_path).is_file():
        return KlingCliEnvironment(
            node_path=node_path,
            npm_path=npm_path,
            error_message="未检测到可灵 CLI，可选择账号区域后安装。",
        )
    entrypoint = _find_kling_entrypoint(kling_path) if os.name == "nt" else ""
    environment = KlingCliEnvironment(
        node_path=node_path,
        npm_path=npm_path,
        kling_path=kling_path,
        entrypoint_path=entrypoint,
    )
    if environment.use_shell:
        return KlingCliEnvironment(
            node_path=node_path,
            npm_path=npm_path,
            kling_path=kling_path,
            error_message="可灵 CLI 的 Node 入口文件缺失，请重新安装可灵 CLI。",
        )
    version = _run_command_version(environment)
    if not version:
        return KlingCliEnvironment(
            node_path=node_path,
            npm_path=npm_path,
            kling_path=kling_path,
            entrypoint_path=entrypoint,
            error_message="可灵 CLI 无法执行，请尝试重新安装。",
        )
    return KlingCliEnvironment(
        node_path=node_path,
        npm_path=npm_path,
        kling_path=kling_path,
        entrypoint_path=entrypoint,
        version=version,
    )


def install_kling_cli(region: str, npm_path: str = "") -> KlingCliEnvironment:
    package = KLING_PACKAGES.get(region)
    if not package:
        raise KlingCliError("可灵 CLI 区域必须是 china 或 global。")
    executable = npm_path or shutil.which("npm.cmd" if os.name == "nt" else "npm") or ""
    if not executable:
        raise KlingCliError("未检测到 npm，请先安装 Node.js 18 或更高版本。")
    result = default_kling_process_runner(
        executable,
        ["install", "--global", package, f"--registry={KLING_NPM_REGISTRY}"],
        capture_output=True,
        check=False,
        shell=False,
        timeout=600,
    )
    if result.returncode != 0:
        detail = _decode_output(result.stderr).strip() or _decode_output(result.stdout).strip()
        raise KlingCliError(f"安装可灵 CLI 失败：{detail or result.returncode}", exit_code=result.returncode)
    environment = resolve_kling_cli()
    if not environment.is_ready:
        raise KlingCliError(environment.error_message)
    return environment


def start_kling_login(environment: KlingCliEnvironment) -> int:
    if not environment.is_ready:
        raise KlingCliError(environment.error_message or "可灵 CLI 尚未就绪。")
    process = subprocess.Popen(
        [environment.executable, *environment.argument_prefix, "login"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        creationflags=_WINDOWS_CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    return process.pid


def _collect_video_element_tools(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            name = _text(item.get("name") or item.get("command") or item.get("id") or item.get("tool"))
            if name == "element_create":
                key = json.dumps(item, ensure_ascii=False, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    found.append(dict(item))
            for child in item.values():
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return found


def parse_kling_capabilities(payload: Mapping[str, Any]) -> dict[str, Any]:
    body = _body(payload)
    available = _map(body.get("availableModels") or body.get("available_models"))
    result: dict[str, list[dict[str, Any]]] = {}
    for command in ("text_to_video", "image_to_video"):
        group = _map(available.get(command))
        models = []
        for raw_model in _maps(group.get("models")):
            model_name = _text(raw_model.get("model"))
            if not model_name:
                continue
            arguments = []
            for raw_argument in _maps(raw_model.get("arguments")):
                name = _text(raw_argument.get("name"))
                if not name:
                    continue
                arguments.append(
                    {
                        "name": name,
                        "required": raw_argument.get("required") is True,
                        "default": _text(raw_argument.get("default")),
                        "allowed_values": [
                            _text(value)
                            for value in (
                                raw_argument.get("allowedValues")
                                or raw_argument.get("allowed_values")
                                or []
                            )
                            if _text(value)
                        ],
                        "description": _text(raw_argument.get("description")),
                    }
                )
            inputs = [
                {
                    "name": _text(raw_input.get("name")),
                    "required": raw_input.get("required") is True,
                    "description": _text(raw_input.get("description")),
                }
                for raw_input in _maps(raw_model.get("inputs"))
                if _text(raw_input.get("name"))
            ]
            models.append(
                {
                    "model": model_name,
                    "alias": _text(raw_model.get("alias")),
                    "description": _text(raw_model.get("description")),
                    "arguments": arguments,
                    "inputs": inputs,
                }
            )
        result[command] = models
    video_elements = _collect_video_element_tools(payload)
    # CLI 0.1.x exposes the element schema in tool_list but has no executable
    # element_create subcommand; keep this false until submit support exists.
    return {
        **result,
        "video_elements": video_elements,
        "video_reference_supported": False,
        "video_reference_message": (
            "当前可灵 CLI 能读取视频元素规范，但未提供 element_create 执行命令；"
            "请升级可灵 CLI 后再使用视频参考。"
        ),
    }


def _find_kling_entrypoint(kling_path: str) -> str:
    wrapper = Path(kling_path)
    candidates: list[Path] = []
    try:
        content = wrapper.read_text(encoding="utf-8", errors="ignore")
        match = re.search(r"%d[pP]0%[\\/]([^\"\r\n]+?\.js)", content)
        if match:
            candidates.append(wrapper.parent / Path(match.group(1).replace("\\", os.sep)))
    except OSError:
        pass
    for package in ("cli-cn", "cli-global", "cli"):
        candidates.append(wrapper.parent / "node_modules" / "@klingai" / package / "dist" / "cli.js")
    return next((str(path.resolve()) for path in candidates if path.is_file()), "")


def _npm_global_kling_candidate(npm_path: str) -> str:
    try:
        result = default_kling_process_runner(
            npm_path,
            ["prefix", "-g"],
            capture_output=True,
            check=False,
            shell=False,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    prefix = _decode_output(result.stdout).strip()
    if not prefix:
        return ""
    return str(Path(prefix) / ("kling.cmd" if os.name == "nt" else "bin/kling"))


def _run_command_version(environment: KlingCliEnvironment) -> str:
    try:
        result = default_kling_process_runner(
            environment.executable,
            [*environment.argument_prefix, "--version"],
            capture_output=True,
            check=False,
            shell=False,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return _decode_output(result.stdout).strip() if result.returncode == 0 else ""


def _run_version(executable: str) -> str:
    try:
        result = default_kling_process_runner(
            executable,
            ["--version"],
            capture_output=True,
            check=False,
            shell=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return _decode_output(result.stdout).strip() if result.returncode == 0 else ""


def _windows_program_file(filename: str) -> str:
    if os.name != "nt":
        return ""
    for root_name in ("ProgramFiles", "LOCALAPPDATA"):
        root = os.environ.get(root_name, "").strip()
        if not root:
            continue
        candidate = Path(root) / ("nodejs" if root_name == "ProgramFiles" else "Programs/nodejs") / filename
        if candidate.is_file():
            return str(candidate)
    return ""


def _node_major(version: str) -> int:
    match = re.search(r"v?(\d+)", version.strip())
    return int(match.group(1)) if match else 0


def _decode_json(output: str) -> dict[str, Any]:
    if not output:
        raise KlingCliError("可灵 CLI 未返回 JSON。")
    candidates = [output, *reversed([line.strip() for line in output.splitlines() if line.strip()])]
    for candidate in candidates:
        try:
            decoded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return decoded
    raise KlingCliError("无法解析可灵 CLI JSON。", raw_output=output)


def _decode_output(value: Any) -> str:
    if isinstance(value, str):
        return value
    if not isinstance(value, (bytes, bytearray)):
        return str(value or "")
    for encoding in ("utf-8", "mbcs" if os.name == "nt" else "latin-1"):
        try:
            return bytes(value).decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return bytes(value).decode("latin-1", errors="replace")


def _body(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _map(payload.get("body") or payload.get("data") or payload)


def _map(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _maps(value: Any) -> list[dict[str, Any]]:
    return [_map(item) for item in value] if isinstance(value, list) else []


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _argument_text(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return _text(value)


def _find_value(value: Any, keys: Sequence[str]) -> Any:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value:
                return value[key]
        for child in value.values():
            found = _find_value(child, keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_value(child, keys)
            if found is not None:
                return found
    return None


def _result_url(payload: Mapping[str, Any]) -> str:
    works = _find_value(payload, ("works", "results", "outputs"))
    if isinstance(works, list):
        for work in works:
            if not isinstance(work, Mapping):
                continue
            url = _text(
                work.get("urlWithoutWatermark")
                or work.get("url_without_watermark")
                or work.get("url")
                or work.get("videoUrl")
                or work.get("video_url")
            )
            if url:
                return url
    return _text(
        _find_value(
            payload,
            (
                "urlWithoutWatermark",
                "url_without_watermark",
                "resultUrl",
                "result_url",
                "videoUrl",
                "video_url",
            ),
        )
    )
