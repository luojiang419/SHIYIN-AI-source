from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable


class VideoDepthUnavailable(RuntimeError):
    pass


def smoke_video_depth_runtime(command: list[str], component_root: Path) -> None:
    env = os.environ.copy()
    runtime_root = component_root / "runtime"
    env["SHIYIN_VIDEO_DEPTH_SOURCE_ROOT"] = str(runtime_root / "sources")
    env["PATH"] = str(runtime_root / "bin") + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [*command, "status"], cwd=component_root, env=env, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "深度视频运行时验证失败").strip()
        raise VideoDepthUnavailable(detail[-1200:])
    events = []
    for line in result.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    status = next((item.get("result") for item in events if item.get("type") == "result"), None)
    if not isinstance(status, dict) or not status.get("runtimeReady", True):
        raise VideoDepthUnavailable("深度视频运行时自检未通过")


class VideoDepthTaskService:
    """Run the validated video-depth worker without coupling it to FastAPI."""

    def __init__(
        self, project_root: str | Path, model_manager: Any = None,
        bug_reporter: Any = None, runtime_manager: Any = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.model_manager = model_manager
        self.bug_reporter = bug_reporter
        self.runtime_manager = runtime_manager
        self.lab_root = self.project_root / "tools" / "video-depth-lab"
        self.worker = self.lab_root / "worker" / "main.py"
        self.python = self.lab_root / "runtime" / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        self.deployment = self.lab_root / "runtime" / "deployment.json"
        self.packaged_runtime = self.project_root / "runtime" / "video-depth"
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()

    def _source_runtime(self) -> dict[str, Any] | None:
        details: dict[str, Any] = {}
        if self.deployment.is_file():
            try:
                details = json.loads(self.deployment.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                details = {}
        models = {str(item.get("key")): item for item in details.get("models", []) if isinstance(item, dict)}
        model = models.get("vda_base_fp16_relative", {})
        ready = self.python.is_file() and self.worker.is_file() and bool(model.get("ready"))
        if not ready:
            return None
        return {"mode": "source", "command": [str(self.python), str(self.worker)], "cwd": self.lab_root, "env": None, "modelReady": True}

    def _packaged_runtime(self) -> dict[str, Any] | None:
        managed = self.runtime_manager.installation_path() if self.runtime_manager else None
        runtime_root = managed / "runtime" if managed else self.packaged_runtime
        worker = runtime_root / "video-depth-worker" / "video-depth-worker.exe"
        sources = runtime_root / "sources"
        tools = runtime_root / "bin"
        if not worker.is_file() or not (sources / "video-depth-anything" / "video_depth_anything" / "video_depth.py").is_file():
            return None
        installation = self.model_manager.installation_path() if self.model_manager else None
        model_root = installation / "models" if installation else None
        env = os.environ.copy()
        env["SHIYIN_VIDEO_DEPTH_SOURCE_ROOT"] = str(sources)
        if model_root:
            env["SHIYIN_VIDEO_DEPTH_MODEL_ROOT"] = str(model_root)
        env["PATH"] = str(tools) + os.pathsep + env.get("PATH", "")
        return {
            "mode": "managed" if managed else "packaged",
            "command": [str(worker)], "cwd": runtime_root, "env": env,
            "modelReady": bool(model_root),
        }

    def _runtime(self) -> dict[str, Any] | None:
        return self._source_runtime() or self._packaged_runtime()

    def status(self) -> dict[str, Any]:
        runtime = self._runtime()
        model_status = self.model_manager.public_status() if self.model_manager else {}
        runtime_status = self.runtime_manager.public_status() if self.runtime_manager else {}
        ready = bool(runtime and (runtime["modelReady"] or model_status.get("ready")))
        message = "深度视频模型已就绪" if ready else (
            str(model_status.get("message") or "深度视频模型将在首次生成时自动下载")
            if runtime else str(runtime_status.get("message") or "深度视频运行时将在首次生成时自动安装")
        )
        return {
            "ready": ready,
            "runtimeReady": bool(runtime),
            "installAvailable": bool(model_status.get("install_available")) and bool(
                runtime or runtime_status.get("install_available")
            ),
            "progress": runtime_status.get("progress", model_status.get("progress", 1 if ready else 0)),
            "runtimeVariant": runtime_status.get("selected_variant", "bundled" if runtime else ""),
            "model": "vda_base_fp16_relative",
            "label": "Video Depth Anything Base · FP16 · Relative",
            "message": message,
        }

    def create(self, input_path: str | Path, output_root: str | Path, url_for_path: Callable[[str], str | None], user_id: str = 'admin') -> dict[str, Any]:
        state = self.status()
        if not state["runtimeReady"] and not state["installAvailable"]:
            raise VideoDepthUnavailable(state["message"])
        source = Path(input_path).resolve()
        if not source.is_file():
            raise FileNotFoundError("输入视频不存在")
        task_id = uuid.uuid4().hex
        output_dir = Path(output_root).resolve() / f"depth_video_{task_id}"
        task = {
            "id": task_id,
            "status": "queued",
            "progress": 0,
            "message": "任务已排队",
            "inputName": source.name,
            "outputUrl": "",
            "outputName": "depth-preview.mp4",
            "error": "",
            "userId": user_id,
        }
        with self._lock:
            self._tasks[task_id] = task
        threading.Thread(
            target=self._run,
            args=(task_id, source, output_dir, url_for_path),
            name=f"video-depth-{task_id[:8]}",
            daemon=True,
        ).start()
        return dict(task)

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self._tasks.get(str(task_id))
            return dict(task) if task else None

    def _update(self, task_id: str, **patch: Any) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(patch)

    def _run(self, task_id: str, source: Path, output_dir: Path, url_for_path: Callable[[str], str | None]) -> None:
        self._update(task_id, status="queued", progress=0, message="等待其他深度视频任务完成")
        with self._run_lock:
            self._run_worker(task_id, source, output_dir, url_for_path)

    def _run_worker(self, task_id: str, source: Path, output_dir: Path, url_for_path: Callable[[str], str | None]) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        runtime = self._runtime()
        if not runtime:
            self._ensure_runtime(task_id)
            runtime = self._runtime()
            if not runtime:
                self._update(task_id, status="failed", error="深度视频运行时安装后仍不可用", message="深度视频运行时安装失败")
                return
        if not runtime["modelReady"]:
            self._ensure_model(task_id)
            runtime = self._packaged_runtime()
            if not runtime or not runtime["modelReady"]:
                self._update(task_id, status="failed", error="深度视频模型安装后仍不可用", message="深度视频模型安装失败")
                return
        command = [
            *runtime["command"], "infer",
            "--model", "vda_base_fp16_relative",
            "--input", str(source),
            "--output-dir", str(output_dir),
            "--input-size", "322",
            "--target-fps", "-1",
            "--max-frames", "-1",
            "--max-resolution", "-1",
            "--params-json", "{}",
        ]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self._update(task_id, status="running", progress=1, message="正在启动深度视频模型")
        try:
            process = subprocess.Popen(
                command,
                cwd=runtime["cwd"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
                env=runtime["env"],
            )
            result: dict[str, Any] | None = None
            assert process.stdout is not None
            for line in process.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "progress":
                    self._update(task_id, progress=max(1, min(99, int(event.get("percent") or 0))), message=str(event.get("message") or "正在生成深度视频"))
                elif event.get("type") == "result":
                    result = event.get("result") if isinstance(event.get("result"), dict) else {}
                elif event.get("type") == "error":
                    raise RuntimeError(str(event.get("error") or "深度视频生成失败"))
            stderr = process.stderr.read() if process.stderr else ""
            code = process.wait()
            if code != 0:
                raise RuntimeError(stderr.strip().splitlines()[-1] if stderr.strip() else f"深度视频 worker 退出码 {code}")
            output_path = Path(str((result or {}).get("outputVideoPath") or output_dir / "depth-preview.mp4")).resolve()
            output_url = url_for_path(str(output_path))
            if not output_path.is_file() or not output_url:
                raise RuntimeError("深度视频已生成，但无法注册输出文件")
            input_meta = (result or {}).get("input") or {}
            self._update(
                task_id,
                status="done",
                progress=100,
                message="深度视频已生成",
                outputUrl=output_url,
                outputName=output_path.name,
                width=int(input_meta.get("processedWidth") or input_meta.get("width") or 0),
                height=int(input_meta.get("processedHeight") or input_meta.get("height") or 0),
                fps=float(input_meta.get("processedFps") or input_meta.get("fps") or 0),
                frameCount=int(input_meta.get("processedFrames") or input_meta.get("frameCount") or 0),
            )
        except BaseException as error:
            self._update(task_id, status="failed", error=str(error)[:1000], message=str(error)[:240])
            if self.bug_reporter:
                from canvas_core.bug_reporter import gpu_diagnostics
                worker_status = {}
                try:
                    diagnostic = subprocess.run([*runtime['command'], 'status'], cwd=runtime['cwd'],
                        env=runtime['env'], capture_output=True, text=True, timeout=8,
                        creationflags=flags)
                    for line in diagnostic.stdout.splitlines():
                        event = json.loads(line)
                        if event.get('type') == 'result':
                            worker_status = {key: event['result'].get(key) for key in (
                                'torchVersion', 'cudaVersion', 'cudaArchitectures',
                                'gpu', 'gpuComputeCapability', 'cudaAvailable')}
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    pass
                self.bug_reporter.report('error', '深度视频生成失败', {
                    'taskId': task_id, 'error': str(error)[:3000],
                    'runtimeMode': runtime['mode'], 'workerStderr': stderr[-6000:] if 'stderr' in locals() else '',
                    'gpu': gpu_diagnostics(), 'worker': worker_status, 'inputSuffix': source.suffix,
                }, user_id=self.get(task_id).get('userId', 'admin'))

    def _ensure_model(self, task_id: str) -> None:
        if not self.model_manager:
            raise VideoDepthUnavailable("深度视频模型管理器不可用")
        status = self.model_manager.public_status()
        if status.get("ready"):
            return
        if not status.get("install_available"):
            raise VideoDepthUnavailable(str(status.get("message") or "深度视频模型暂不可下载"))
        self.model_manager.start_background()
        while True:
            status = self.model_manager.public_status()
            state = str(status.get("state") or "")
            progress = float(status.get("progress") or 0)
            self._update(task_id, status="running", progress=min(18, max(1, int(progress * 18))), message=str(status.get("message") or "正在安装深度视频模型"))
            if status.get("ready"):
                return
            if state in {"failed", "unavailable"}:
                raise VideoDepthUnavailable(str(status.get("message") or "深度视频模型安装失败"))
            time.sleep(0.5)

    def _ensure_runtime(self, task_id: str) -> None:
        if not self.runtime_manager:
            raise VideoDepthUnavailable("深度视频运行时管理器不可用")
        status = self.runtime_manager.public_status()
        if status.get("ready"):
            return
        if not status.get("install_available"):
            raise VideoDepthUnavailable(str(status.get("message") or "深度视频运行时暂不可下载"))
        self.runtime_manager.start_background()
        while True:
            status = self.runtime_manager.public_status()
            state = str(status.get("state") or "")
            progress = float(status.get("progress") or 0)
            self._update(
                task_id, status="running", progress=min(12, max(1, int(progress * 12))),
                message=str(status.get("message") or "正在安装深度视频运行时"),
            )
            if status.get("ready"):
                return
            if state in {"failed", "unavailable"}:
                raise VideoDepthUnavailable(str(status.get("message") or "深度视频运行时安装失败"))
            time.sleep(0.5)
