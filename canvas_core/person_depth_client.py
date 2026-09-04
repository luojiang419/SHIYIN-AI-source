from __future__ import annotations

import json
import os
import queue
import subprocess
import tempfile
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .person_depth_components import PersonDepthComponentManager, PersonDepthComponentUnavailable


PERSON_DEPTH_PROTOCOL_VERSION = 1


@dataclass(frozen=True)
class PersonDepthResult:
    content: bytes
    width: int
    height: int
    bit_depth: int


class PersonDepthWorkerError(RuntimeError):
    pass


class PersonDepthWorkerClient:
    """Serialize requests through one persistent external worker process."""

    def __init__(self, component_manager: PersonDepthComponentManager, *, timeout: float = 600.0) -> None:
        self.component_manager = component_manager
        self.timeout = float(timeout)
        self._lock = threading.RLock()
        self._process: Optional[subprocess.Popen[str]] = None
        self._responses: queue.Queue[dict[str, object]] = queue.Queue()
        self._reader: Optional[threading.Thread] = None
        self._stderr_lines: queue.Queue[str] = queue.Queue(maxsize=100)

    def close(self) -> None:
        with self._lock:
            process = self._process
            self._process = None
            if process and process.poll() is None:
                try:
                    assert process.stdin is not None
                    process.stdin.write(json.dumps({"op": "shutdown"}) + "\n")
                    process.stdin.flush()
                    process.wait(timeout=3)
                except Exception:  # noqa: BLE001
                    process.kill()

    def _start(self) -> None:
        if self._process and self._process.poll() is None:
            return
        command = [*self.component_manager.worker_command(), "--stdio"]
        root = self.component_manager.installation_path()
        if root is None:
            raise PersonDepthComponentUnavailable("高精度人物深度组件尚未就绪")
        self._responses = queue.Queue()
        self._stderr_lines = queue.Queue(maxsize=100)
        environment = os.environ.copy()
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8"
        self._process = subprocess.Popen(
            command,
            cwd=str(root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=environment,
        )
        self._reader = threading.Thread(target=self._read_stdout, name="person-depth-worker-reader", daemon=True)
        self._reader.start()
        threading.Thread(target=self._read_stderr, name="person-depth-worker-stderr", daemon=True).start()
        hello = self._request({"op": "hello"}, start=False, timeout=60.0)
        if int(hello.get("protocol_version") or 0) != PERSON_DEPTH_PROTOCOL_VERSION:
            self.close()
            raise PersonDepthWorkerError("高精度人物深度 worker 协议版本不匹配")

    def _read_stdout(self) -> None:
        process = self._process
        if not process or not process.stdout:
            return
        for line in process.stdout:
            try:
                payload = json.loads(line)
                if isinstance(payload, dict):
                    self._responses.put(payload)
            except ValueError:
                continue

    def _read_stderr(self) -> None:
        process = self._process
        if not process or not process.stderr:
            return
        for line in process.stderr:
            clean = line.strip()
            if not clean:
                continue
            if self._stderr_lines.full():
                try:
                    self._stderr_lines.get_nowait()
                except queue.Empty:
                    pass
            self._stderr_lines.put_nowait(clean)

    def _stderr_detail(self) -> str:
        lines: list[str] = []
        while True:
            try:
                lines.append(self._stderr_lines.get_nowait())
            except queue.Empty:
                break
        return " | ".join(lines[-8:])

    def _request(
        self,
        payload: dict[str, object],
        *,
        start: bool = True,
        timeout: Optional[float] = None,
    ) -> dict[str, object]:
        if start:
            self._start()
        process = self._process
        if not process or process.poll() is not None or not process.stdin:
            raise PersonDepthWorkerError("高精度人物深度 worker 未运行")
        request_id = str(payload.get("id") or uuid.uuid4().hex)
        payload["id"] = request_id
        process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        process.stdin.flush()
        wait_seconds = float(timeout if timeout is not None else self.timeout)
        try:
            while True:
                response = self._responses.get(timeout=wait_seconds)
                if str(response.get("id") or "") != request_id:
                    continue
                if not response.get("ok"):
                    raise PersonDepthWorkerError(str(response.get("error") or "高精度人物深度推理失败"))
                return response
        except queue.Empty as exc:
            detail = self._stderr_detail()
            self.close()
            message = "高精度人物深度 worker 响应超时"
            if detail:
                message += f"：{detail}"
            raise PersonDepthWorkerError(message) from exc

    def estimate(self, content: bytes, *, bit_depth: int = 8) -> PersonDepthResult:
        if bit_depth not in {8, 16}:
            raise ValueError("高精度人物深度输出位深只支持 8 或 16")
        with self._lock, tempfile.TemporaryDirectory(prefix="shiyin-person-depth-") as temp_root:
            root = Path(temp_root)
            input_path = root / "input.png"
            output_path = root / "depth.png"
            input_path.write_bytes(content)
            response = self._request(
                {
                    "op": "estimate",
                    "input": str(input_path),
                    "output": str(output_path),
                    "bit_depth": bit_depth,
                }
            )
            if not output_path.is_file():
                raise PersonDepthWorkerError("高精度人物深度 worker 未生成输出文件")
            result = output_path.read_bytes()
            if not result:
                raise PersonDepthWorkerError("高精度人物深度 worker 输出为空")
            return PersonDepthResult(
                content=result,
                width=int(response.get("width") or 0),
                height=int(response.get("height") or 0),
                bit_depth=int(response.get("bit_depth") or bit_depth),
            )
