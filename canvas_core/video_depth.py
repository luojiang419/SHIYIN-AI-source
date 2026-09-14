from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from pathlib import Path
from typing import Any, Callable


class VideoDepthUnavailable(RuntimeError):
    pass


class VideoDepthTaskService:
    """Run the validated video-depth worker without coupling it to FastAPI."""

    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self.lab_root = self.project_root / "tools" / "video-depth-lab"
        self.worker = self.lab_root / "worker" / "main.py"
        self.python = self.lab_root / "runtime" / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        self.deployment = self.lab_root / "runtime" / "deployment.json"
        self._tasks: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        details: dict[str, Any] = {}
        if self.deployment.is_file():
            try:
                details = json.loads(self.deployment.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                details = {}
        models = {str(item.get("key")): item for item in details.get("models", []) if isinstance(item, dict)}
        model = models.get("vda_base_fp16_relative", {})
        ready = self.python.is_file() and self.worker.is_file() and bool(model.get("ready"))
        return {
            "ready": ready,
            "model": "vda_base_fp16_relative",
            "label": "Video Depth Anything Base · FP16 · Relative",
            "message": "深度视频模型已就绪" if ready else "请先运行 tools/video-depth-lab/setup.ps1 部署深度视频组件",
            "gpu": details.get("gpu", ""),
        }

    def create(self, input_path: str | Path, output_root: str | Path, url_for_path: Callable[[str], str | None]) -> dict[str, Any]:
        state = self.status()
        if not state["ready"]:
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
        command = [
            str(self.python), str(self.worker), "infer",
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
                cwd=self.lab_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=flags,
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
