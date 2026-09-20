"""通过真实 HTTP 全能任务验证双风格；隔离数据，复用本机已安装深度组件。"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import time

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-dir", required=True)
    parser.add_argument("--port", type=int, default=8897)
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--provider", default="shiying")
    parser.add_argument("--model", default="gemini-3-pro-image-preview")
    parser.add_argument("--resolution", default="4k")
    parser.add_argument("--styles", nargs="+", default=["standard_product", "lookbook"])
    parser.add_argument("--serve-only", action="store_true")
    args = parser.parse_args()
    case = Path(args.case_dir).resolve()
    case.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location("universal_smoke", ROOT / "tools/smoke-ecommerce-universal-real.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    for key, value in helper.load_keys_from_markdown(ROOT / "api文档/api key.md").items():
        os.environ.setdefault(key, value)
    runtime_name = 'universal-style-runtime' if args.port == 8897 else f'universal-style-runtime-{args.port}'
    os.environ["CANVAS_DATA_DIR"] = str(ROOT / ".codex-tmp" / runtime_name)
    os.environ["CANVAS_RUNTIME_MODE"] = "desktop"
    os.environ["CANVAS_DESKTOP_TOKEN"] = "universal-style-local-check"
    os.environ["CANVAS_DWPOSE_AUTO_DOWNLOAD"] = "0"
    import main as app
    from canvas_core.depth_models import DepthModelManager
    from canvas_core.person_depth_components import PersonDepthComponentManager
    from canvas_core.person_depth_client import PersonDepthWorkerClient
    app.DEPTH_MODEL_MANAGER = DepthModelManager(ROOT / "data/system/models/depth")
    app.PERSON_DEPTH_COMPONENT_MANAGER = PersonDepthComponentManager(ROOT / "data/system/components/person-depth")
    app.PERSON_DEPTH_WORKER = PersonDepthWorkerClient(app.PERSON_DEPTH_COMPONENT_MANAGER)
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app.app, host="127.0.0.1", port=args.port, log_level="warning"))
    if args.serve_only:
        server.run()
        return
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(300):
        if server.started:
            break
        time.sleep(.1)
    session = requests.Session()
    base = f"http://127.0.0.1:{args.port}"
    response = session.get(base + "/api/auth/bootstrap?token=universal-style-local-check", allow_redirects=False)
    assert response.status_code == 303, response.status_code
    sources = [
        ("subject", "模特身体与身份", r"D:\data\图片\选用\B\XSY_9373.JPG", "只提供人物身份、身体、发型；保留黑色背心与鞋子，不保留原裤子的白色斑点。"),
        ("lower_garment", "棕色长裤版型", r"D:\data\图片\服装参考 (2).jpg", "精确保留高腰、宽直裤腿、裤长、后袋及裤腿结构；这是后侧视图。"),
        ("detail", "后腰结构与斜纹面料细节", r"D:\data\图片\腰头细节.jpg", "仅绑定棕色长裤，保留细密斜纹、双银扣调节袢、后腰皮牌和缝线；这些是后侧结构，禁止移到正面。"),
        ("pose", "交叉手臂与交叉腿动作", r"C:\Users\jiang\Desktop\人物形象\动作.png", "标准产品图精确复刻手臂、重心、腿和头部方向，不能借用牛仔服或白色栅栏。"),
        ("scene", "庄园与复古汽车场景", r"C:\Users\jiang\Desktop\西部小镇\【西部小镇WildWestTown】场景\page-004_img-004.jpeg", "保留建筑、树木、碎石路与复古汽车，人物合理融入真实空间。"),
    ]
    inputs = []
    for role, label, path, instruction in sources:
        with open(path, "rb") as handle:
            response = session.post(base + "/api/ai/upload", files=[("files", (Path(path).name, handle, "image/png" if path.endswith("png") else "image/jpeg"))], timeout=120)
        response.raise_for_status()
        item = response.json()["files"][0]
        inputs.append({**item, "role": role, "reference_type": role, "reference_id": role, "label": label, "instruction": instruction, **({"detail_target_id": "lower_garment"} if role == "detail" else {})})
    (case / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    for style in args.styles:
        if args.round >= 4:
            for item in inputs:
                if item['reference_type'] == 'pose':
                    item['instruction'] = '按画面左右：脸与鼻尖朝画面右，视线偏右上；身体向画面左微倾。画面左腿直立承重，画面右膝向右外展弯曲、小腿斜向左，交叉脚在画面左下触地，不抬高悬空。胸前抱臂，保持原手臂交叠顺序。不要看镜头。仅迁移动作。'
                elif item['reference_type'] == 'detail':
                    item['instruction'] = '仅绑定棕裤后侧：侧后腰调节袢与两枚银扣、腰头原位置的双腰耳、橙棕矩形皮牌luvamia、后育克与五角后贴袋。保留这些部件沿腰头的先后位置及缝线，不镜像、不重排、不增删；后腰细节不得出现在正面。面料为细密连续斜纹，不是绒面。'
        instruction = ""
        if args.round == 2 and style == "lookbook":
            instruction = "采用后侧三分之四视角的全身时装摄影，让模特回头望向镜头，在庄园碎石路上迈步，清楚展示裤子后腰、双银扣调节袢、皮牌、后袋与宽直裤型。自然光下棕色斜纹面料必须清晰，保持衣服原设计。"
        payload = {"operation": "universal", "mode": "standard", "provider_id": args.provider, "model": args.model, "aspect_ratio": "2:3", "resolution": args.resolution, "quality": "high", "count": 1, "inputs": inputs, "options": {"generation_style": style, "instruction": instruction}}
        prefix = case / f"round-{args.round}-{style}"
        Path(str(prefix) + "-request.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        response = session.post(base + "/api/ecommerce/tasks", json=payload, timeout=120)
        response.raise_for_status()
        task_id = response.json()["id"]
        print(f"SUBMITTED {style} {task_id}", flush=True)
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            response = session.get(base + f"/api/ecommerce/tasks/{task_id}", timeout=60)
            response.raise_for_status()
            task = response.json()
            if task.get("status") not in {"queued", "running"}:
                break
            time.sleep(3)
        Path(str(prefix) + "-task.json").write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"FINISHED {style} {task.get('status')} {task.get('error') or ''}", flush=True)
        urls = [("result", url) for url in (task.get("result") or {}).get("images", [])]
        urls += [("original", url) for url in (task.get("result") or {}).get("original_images", [])]
        if (task.get("pose_depth") or {}).get("url"):
            urls.append(("depth", task["pose_depth"]["url"]))
        if (task.get("pose_anchor") or {}).get("url"):
            urls.append(("anchor", task["pose_anchor"]["url"]))
        for index, (kind, url) in enumerate(urls):
            media = session.get(base + url, timeout=120)
            media.raise_for_status()
            ext = ".png" if media.content.startswith(b"\x89PNG") else ".jpg"
            output = Path(str(prefix) + f"-{kind}-{index}{ext}")
            output.write_bytes(media.content)
            print(f"SAVED {output}", flush=True)
    server.should_exit = True
    thread.join(timeout=15)


if __name__ == "__main__":
    main()
