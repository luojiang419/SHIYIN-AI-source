from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ENVIRONMENTS = [
    ("clear_day", "晴天午后室外：太阳从画面左前方斜射，树叶投影清晰但阴影侧由天空反射打开，空气透明，暖色高光与自然蓝色丹宁保持分离。情绪帧中她左手拿着刚买的折叠报纸，听见街对面熟人叫她，认出对方后嘴角刚开始松开。"),
    ("overcast", "阴天室外：厚云层提供宽而偏冷的天光，投影边缘柔软，低对比但保留报刊亭绿色、人物皮肤和牛仔织纹，中性安静而有生活气。情绪帧中她左手拿折叠报纸，听到自行车铃后停步判断来车方向，神情专注警觉。"),
    ("wet_after_rain", "雨后室外：地面、棚布和金属边缘有真实湿润反射与少量水珠，灰蓝环境光从上方漫射，人物衣发略带潮湿重量。情绪帧中她左手拿折叠报纸，听见雨声重新变密，身体前倾准备快步离开，神情克制而决断。"),
    ("interior_window", "报刊亭遮棚与售货窗口的半室内环境：从窗口一侧进入方向性冷日光，同时混合原有遮棚暗部和实景反射，空间内部可读。情绪帧中她左手拿折叠报纸，正听售货员说话，身体探向窗口，眼神好奇而专注。"),
    ("blue_hour_practical", "蓝调时刻至入夜：保留报刊亭和街道几何，天空环境偏冷，窗口、街灯和车辆提供少量暖色实景光，人物脸部与牛仔材质仍然可读。情绪帧中她左手拿折叠报纸，听到路边车辆刹车后半转身确认方向，呼吸短暂停住，神情警觉。"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="真实验证李维斯广告预设环境矩阵")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT / "输出" / "李维斯广告风格分析" / "环境矩阵-20260902"))
    parser.add_argument("--api-key-file", default=str(PROJECT_ROOT / "api文档" / "api key.md"))
    parser.add_argument("--provider", default="shiying")
    parser.add_argument("--model", default="gemini-3-pro-image-preview")
    parser.add_argument("--only", default="", help="只运行指定环境 ID，逗号分隔")
    parser.add_argument("--timeout", type=float, default=240.0, help="每张图片最大等待秒数")
    parser.add_argument("--replace-shots", default="", help="强制替换逗号分隔的镜头编号")
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_images = [PROJECT_ROOT / "测试" / "模特.png", PROJECT_ROOT / "测试" / "场景.jpeg"]
    for path in source_images:
        if not path.is_file():
            raise FileNotFoundError(path)
    key_path = Path(args.api_key_file)
    current_url = ""
    for line in key_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        lower = line.strip().lower()
        if lower.startswith("url") and ":" in line:
            current_url = line.split(":", 1)[1].strip().lower()
        if lower.startswith("key") and ":" in line and "shiying" in current_url:
            os.environ.setdefault("API_PROVIDER_SHIYING_KEY", line.split(":", 1)[1].strip())
    os.environ["CANVAS_DWPOSE_AUTO_DOWNLOAD"] = "0"
    os.environ["CANVAS_DEPTH_AUTO_DOWNLOAD"] = "0"
    os.environ.setdefault("CANVAS_DESKTOP_TOKEN", "levis-environment-matrix-real")
    os.environ.setdefault("CANVAS_RUNTIME_MODE", "desktop")
    report_path = output_dir / "环境矩阵测试报告.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["status"] = "running"
    else:
        report = {"status": "running", "style_id": "levis-adaptive-campaign", "environment_count": len(ENVIRONMENTS), "images_per_environment": 4, "groups": []}
    only = {item.strip() for item in str(args.only or "").split(",") if item.strip()}
    replace_shots = {int(item.strip()) for item in str(args.replace_shots or "").split(",") if item.strip().isdigit()}
    with tempfile.TemporaryDirectory(prefix="levis-environment-matrix-") as data_dir:
        os.environ["CANVAS_DATA_DIR"] = data_dir
        from fastapi.testclient import TestClient
        import main as canvas_main
        from canvas_core.ecommerce import build_prompt
        with TestClient(canvas_main.app, client=("127.0.0.1", 50001)) as client:
            bootstrap = client.get("/api/auth/bootstrap?token=levis-environment-matrix-real", follow_redirects=False)
            if bootstrap.status_code != 303:
                raise RuntimeError(f"测试会话鉴权失败：HTTP {bootstrap.status_code}")
            client.cookies.update(bootstrap.cookies)
            files, handles = [], []
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
            inputs = [
                {**uploaded[0], "role": "subject", "reference_type": "subject", "reference_id": "model", "label": "人物", "lookbook_role": "人物", "instruction": "保留人物身份、发型、现有针织衫、牛仔裤、鞋子和包。"},
                {**uploaded[1], "role": "scene", "reference_type": "scene", "reference_id": "scene", "label": "场景", "lookbook_role": "场景", "instruction": "保留绿色报刊亭、树木、海报、杂志架、地面和建筑几何。允许仅按测试条件改变天气、时间和现场曝光。"},
            ]
            for environment_id, condition in ENVIRONMENTS:
                if only and environment_id not in only:
                    continue
                options = {
                    "prompt_policy": "lookbook",
                    "instruction": f"{condition} 生成四张同一系列原创丹宁广告照片，人物要处于正在做事的状态，四张分别承担环境建立、动作经过、情绪停顿、材质接触。",
                    "lookbook_count": 4,
                    "lookbook_style": {"id": "levis-adaptive-campaign", "name": "李维斯广告·环境自适应纪实"},
                    "lookbook_search": False,
                    "lookbook_quality_gate": False,
                }
                prompt = build_prompt("universal", inputs, options)
                prompts = canvas_main.lookbook_generation_prompts({"count": 4, "prompt": prompt, "options": options})
                existing_group = next((item for item in report["groups"] if item.get("id") == environment_id), {})
                copied = list(existing_group.get("images") or [])
                for index, shot_prompt in enumerate(prompts, 1):
                    if index in replace_shots:
                        copied = [item for item in copied if int(item.get("shot_index") or 0) != index]
                    if any(int(item.get("shot_index") or 0) == index and Path(str(item.get("path") or "")).is_file() for item in copied):
                        continue
                    async def generate_single():
                        return await asyncio.wait_for(
                            canvas_main.execute_ai_image_batch(prompt=shot_prompt, provider_id=args.provider, model=args.model, size="4:5", quality="high", references=inputs, count=1, prefix=f"levis_{environment_id}_{index:02d}_", allow_edit_endpoint_fallback=False, semantic_mask=True),
                            timeout=max(30.0, args.timeout),
                        )
                    try:
                        batch = asyncio.run(generate_single())
                    except Exception as exc:
                        existing_group = next((item for item in report["groups"] if item.get("id") == environment_id), {})
                        failures = list(existing_group.get("failures") or [])
                        failures.append({"shot_index": index, "error": str(exc)[:500] or type(exc).__name__})
                        report["groups"] = [item for item in report["groups"] if item.get("id") != environment_id]
                        report["groups"].append({"id": environment_id, "condition": condition, "prompt": prompt, "images": copied[:], "failures": failures})
                        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                        continue
                    for url in batch.get("images") or []:
                        source = canvas_main.output_file_from_url(url)
                        target = output_dir / environment_id / f"{environment_id}_{index:02d}{Path(source).suffix.lower()}"
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, target)
                        with Image.open(target) as image:
                            copied.append({"path": str(target), "size": f"{image.width}x{image.height}", "shot_index": index})
                    report["groups"] = [item for item in report["groups"] if item.get("id") != environment_id]
                    report["groups"].append({"id": environment_id, "condition": condition, "prompt": prompt, "images": copied[:]})
                    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["status"] = "ok" if all(len(next((group.get("images") or [] for group in report["groups"] if group.get("id") == environment_id), [])) == 4 for environment_id, _ in ENVIRONMENTS) else "partial"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
