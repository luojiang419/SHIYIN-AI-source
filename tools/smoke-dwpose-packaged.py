from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_NAMES = ("yolox_l.onnx", "dw-ll_ucoco_384.onnx")


def wait_for_health(base_url: str, process: subprocess.Popen, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"打包后端在健康检查前退出，代码 {process.returncode}")
        try:
            response = requests.get(f"{base_url}/api/health", timeout=1)
            if response.ok and response.json().get("status") == "ok":
                return
        except requests.RequestException:
            pass
        time.sleep(0.1)
    raise RuntimeError("打包后端健康检查超时")


def wait_for_models(session: requests.Session, base_url: str, timeout: float = 15 * 60) -> dict:
    deadline = time.monotonic() + timeout
    latest = {}
    while time.monotonic() < deadline:
        response = session.get(f"{base_url}/api/dwpose/status", timeout=10)
        if not response.ok:
            raise RuntimeError(f"DWPose 模型状态读取失败：HTTP {response.status_code}")
        latest = response.json()
        if latest.get("ready"):
            return latest
        if latest.get("state") == "failed":
            raise RuntimeError(str(latest.get("message") or "DWPose 模型下载失败"))
        time.sleep(0.5)
    raise RuntimeError(f"DWPose 模型准备超时：{latest}")


def link_models(source_root: Path, target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for name in MODEL_NAMES:
        source = source_root / name
        if not source.is_file():
            raise FileNotFoundError(f"DWPose 模型不存在：{source}")
        target = target_root / name
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)
    manifest = source_root / "manifest.json"
    if manifest.is_file():
        shutil.copy2(manifest, target_root / manifest.name)


def run_smoke(
    stage: Path,
    model_root: Path,
    input_image: Path,
    output: Path,
    port: int,
    *,
    download_models: bool,
) -> dict:
    stage = stage.resolve()
    backend = stage / "app" / "backend" / "canvas-backend" / "canvas-backend.exe"
    if not backend.is_file():
        raise FileNotFoundError(f"打包后端不存在：{backend}")
    if not input_image.is_file():
        raise FileNotFoundError(f"真实人物测试图不存在：{input_image}")
    build_root = PROJECT_ROOT / ".build"
    build_root.mkdir(parents=True, exist_ok=True)
    token = "dwpose-packaged-smoke-token"
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="dwpose-packaged-smoke-", dir=build_root) as temp:
        smoke_root = Path(temp)
        data_root = smoke_root / "data"
        if not download_models:
            link_models(model_root.resolve(), data_root / "system" / "models" / "dwpose")
        stdout_path = smoke_root / "stdout.log"
        stderr_path = smoke_root / "stderr.log"
        environment = dict(os.environ)
        environment["CANVAS_DWPOSE_AUTO_DOWNLOAD"] = "1" if download_models else "0"
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [
                    str(backend),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--data-dir",
                    str(data_root),
                    "--app-root",
                    str(stage / "app"),
                    "--portable-root",
                    str(stage),
                    "--desktop-token",
                    token,
                    "--runtime-mode",
                    "desktop",
                ],
                cwd=backend.parent,
                env=environment,
                stdout=stdout,
                stderr=stderr,
                creationflags=creation_flags,
            )
            try:
                wait_for_health(base_url, process)
                session = requests.Session()
                auth = session.get(
                    f"{base_url}/api/auth/bootstrap",
                    params={"token": token},
                    allow_redirects=False,
                    timeout=10,
                )
                if auth.status_code != 303:
                    raise RuntimeError(f"桌面鉴权失败：HTTP {auth.status_code}")
                model_started = time.perf_counter()
                model_status = wait_for_models(session, base_url) if download_models else {"source_label": "预置测试模型"}
                model_elapsed = time.perf_counter() - model_started
                started = time.perf_counter()
                with input_image.open("rb") as source:
                    response = session.post(
                        f"{base_url}/api/dwpose/detect",
                        files={"file": (input_image.name, source, "image/jpeg")},
                        timeout=120,
                    )
                elapsed = time.perf_counter() - started
                if response.status_code != 200:
                    raise RuntimeError(f"真实 DWPose 请求失败：HTTP {response.status_code} {response.text[:500]}")
                image = Image.open(io.BytesIO(response.content)).convert("RGB")
                people = int(response.headers.get("X-DWPose-People") or 0)
                if people < 1:
                    raise RuntimeError("真实人物图未检测到人物")
                if image.getbbox() is None:
                    raise RuntimeError("DWPose 返回了空白骨架图")
                if response.headers.get("X-DWPose-Width") != str(image.width):
                    raise RuntimeError("DWPose 输出宽度响应头不匹配")
                if response.headers.get("X-DWPose-Height") != str(image.height):
                    raise RuntimeError("DWPose 输出高度响应头不匹配")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(response.content)
                return {
                    "status": "ok",
                    "model_seconds": round(model_elapsed, 3),
                    "model_source": str(model_status.get("source_label") or ""),
                    "seconds": round(elapsed, 3),
                    "people": people,
                    "size": [image.width, image.height],
                    "bytes": len(response.content),
                    "output": str(output.resolve()),
                }
            except Exception as exc:
                stderr.flush()
                tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-3000:]
                if tail:
                    raise RuntimeError(f"{exc}\n打包后端日志末尾：\n{tail}") from exc
                raise
            finally:
                try:
                    requests.post(
                        f"{base_url}/api/runtime/shutdown",
                        headers={"X-Desktop-Token": token},
                        timeout=3,
                    )
                except requests.RequestException:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description="使用真实人物图验证 PyInstaller DWPose 后端")
    parser.add_argument("--stage", default=str(PROJECT_ROOT / "dist" / "installer-stage"))
    parser.add_argument("--model-root", default=str(PROJECT_ROOT / "data" / "system" / "models" / "dwpose"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=str(PROJECT_ROOT / ".build" / "dwpose-packaged-output.png"))
    parser.add_argument("--port", type=int, default=3127)
    parser.add_argument("--download-models", action="store_true")
    args = parser.parse_args()
    result = run_smoke(
        Path(args.stage),
        Path(args.model_root),
        Path(args.input),
        Path(args.output),
        args.port,
        download_models=args.download_models,
    )
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
