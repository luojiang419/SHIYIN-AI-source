from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_keys_from_markdown(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    current_url = ""
    keys: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line.lower().startswith("url") and ":" in line:
            current_url = line.split(":", 1)[1].strip().lower()
        if not line.lower().startswith("key") or ":" not in line:
            continue
        value = line.split(":", 1)[1].strip()
        if "shiying" in current_url and value:
            keys.setdefault("API_PROVIDER_SHIYING_KEY", value)
    return keys


def wait_for_task(client, task_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/ecommerce/tasks/{task_id}")
        response.raise_for_status()
        last = response.json()
        if last.get("status") not in {"queued", "running"}:
            return last
        time.sleep(3)
    raise TimeoutError(f"李维斯 Lookbook 真实任务等待超时：{task_id}，最后状态 {last.get('status')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="真实 API 验证李维斯广告 Lookbook 自适应预设")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "输出" / "李维斯广告风格分析" / "测试组图-20260902"))
    parser.add_argument("--api-key-file", default=str(PROJECT_ROOT / "api文档" / "api key.md"))
    parser.add_argument("--provider", default="shiying")
    parser.add_argument("--model", default="gemini-3-pro-image-preview")
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_images = [PROJECT_ROOT / "测试" / "模特.png", PROJECT_ROOT / "测试" / "场景.jpeg"]
    for path in source_images:
        if not path.is_file():
            raise FileNotFoundError(path)

    for name, value in load_keys_from_markdown(Path(args.api_key_file)).items():
        os.environ.setdefault(name, value)
    os.environ.setdefault("CANVAS_DESKTOP_TOKEN", "levis-lookbook-real")
    os.environ.setdefault("CANVAS_RUNTIME_MODE", "desktop")
    os.environ["CANVAS_DWPOSE_AUTO_DOWNLOAD"] = "0"
    os.environ["CANVAS_DEPTH_AUTO_DOWNLOAD"] = "0"

    report: dict = {
        "status": "running",
        "style_id": "levis-adaptive-campaign",
        "provider": args.provider,
        "model": args.model,
        "source_images": [str(path) for path in source_images],
        "count": 4,
    }
    started = time.time()
    try:
        with tempfile.TemporaryDirectory(prefix="levis-lookbook-real-data-") as data_dir:
            os.environ["CANVAS_DATA_DIR"] = data_dir
            from fastapi.testclient import TestClient
            import main as canvas_main

            with TestClient(canvas_main.app, client=("127.0.0.1", 50000)) as client:
                bootstrap = client.get("/api/auth/bootstrap?token=levis-lookbook-real", follow_redirects=False)
                if bootstrap.status_code != 303:
                    raise RuntimeError(f"测试会话鉴权失败：HTTP {bootstrap.status_code}")
                client.cookies.update(bootstrap.cookies)

                files = []
                handles = []
                try:
                    for path in source_images:
                        handle = path.open("rb")
                        handles.append(handle)
                        files.append(("files", (path.name, handle, "image/png" if path.suffix.lower() == ".png" else "image/jpeg")))
                    upload = client.post("/api/ai/upload", files=files)
                    upload.raise_for_status()
                finally:
                    for handle in handles:
                        handle.close()
                uploaded = upload.json().get("files") or []
                if len(uploaded) != 2:
                    raise RuntimeError(f"参考图上传数量异常：{len(uploaded)}")

                inputs = [
                    {**uploaded[0], "role": "subject", "reference_type": "subject", "reference_id": "model", "label": "人物", "lookbook_role": "人物", "instruction": "保留人物身份、体态、发型、现有针织衫、牛仔裤、鞋子和包。"},
                    {**uploaded[1], "role": "scene", "reference_type": "scene", "reference_id": "scene", "label": "场景", "lookbook_role": "场景", "instruction": "保留绿色报刊亭、树木、海报、杂志架、地面和原有日光关系。"},
                ]
                from canvas_core.ecommerce import build_prompt

                options = {
                    "prompt_policy": "lookbook",
                    "instruction": "把同一位人物和同一处报刊亭改编成一组原创丹宁广告照片，保留真实街景，不复制任何参考广告内容。",
                    "lookbook_count": 4,
                    "lookbook_style": {"id": "levis-adaptive-campaign", "name": "李维斯广告·环境自适应纪实"},
                    "lookbook_search": False,
                    "lookbook_quality_gate": False,
                }
                prompt = build_prompt("universal", inputs, options)
                snapshot = {"count": 4, "prompt": prompt, "options": options}
                generation_prompts = canvas_main.lookbook_generation_prompts(snapshot)
                batch = asyncio.run(canvas_main.execute_ai_image_batch(
                    prompt=prompt,
                    provider_id=args.provider,
                    model=args.model,
                    size="4:5",
                    quality="high",
                    references=inputs,
                    count=4,
                    prefix="levis_",
                    allow_edit_endpoint_fallback=False,
                    semantic_mask=True,
                    prompts=generation_prompts,
                ))
                report.update({
                    "execution_mode": "direct_batch",
                    "prompt": prompt,
                    "generation_prompts": generation_prompts,
                    "error": "",
                })
                images = batch.get("images") or []
                if len(images) != 4:
                    raise RuntimeError(f"生成图数量异常：{len(images)}")
                copied = []
                for index, url in enumerate(images, 1):
                    source = canvas_main.output_file_from_url(url)
                    if not source or not Path(source).is_file():
                        raise RuntimeError(f"生成图未保存到本地媒体目录：{url}")
                    target = output_dir / f"levis_adaptive_{index:02d}{Path(source).suffix.lower()}"
                    shutil.copy2(source, target)
                    with Image.open(target) as image:
                        copied.append({"path": str(target), "size": f"{image.width}x{image.height}"})
                report["generated_images"] = copied
                report["status"] = "ok"
    except Exception as exc:
        report.update({"status": "failed", "error": str(exc)})
        raise
    finally:
        report["elapsed_seconds"] = round(time.time() - started, 3)
        (output_dir / "测试报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if report.get("prompt"):
            (output_dir / "最终提示词.txt").write_text(str(report["prompt"]), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
