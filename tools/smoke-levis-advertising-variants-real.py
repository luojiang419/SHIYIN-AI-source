"""真实验证李维斯广告的标准/高调亮色/黑白三种变体。

每个风格固定一个场景小情景，并以四次独立 ``count=1`` 请求生成：环境建立、
动作经过、自信停顿、材质收束。输出报告保存每张 prompt、尺寸和文件路径，便于
人工按组判断风格连续性与演员动作生命力。
"""

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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STYLES = {
    "standard-advertising": "标准广告·均衡电影质感",
    "levis-high-key-color": "李维斯广告·高调亮色主题",
    "levis-black-white": "李维斯广告·黑白纪实",
}
SCENARIO = (
    "同一组四张照片发生在用户提供的绿色地铁站服务信息亭：人物刚买完一份折叠报纸，"
    "听见站台另一侧朋友叫她，边走出信息亭边回头确认来人，最后停在杂志架旁整理牛仔袖口。"
    "动作要由这个连续的小任务驱动，人物自信、洒脱、自由但不摆拍；保留绿色圆柱、红色列车、"
    "站牌、海报、杂志架、地面和建筑几何，不添加无来源棚拍道具。"
)
SHOT_CARDS = (
    {"role": "环境建立", "camera": "腰平宽环境纪实视角", "action": "人物从报刊亭遮棚迈出，左手拿折叠报纸，步伐自然有方向", "gaze": "视线投向街角声音，不看镜头"},
    {"role": "动作经过", "camera": "人际距离斜侧中景", "action": "人物边走边回头确认朋友位置，报纸和包随步伐产生轻微惯性", "gaze": "眼睛跟随街角目标，肩髋与脚步形成反向平衡"},
    {"role": "自信停顿", "camera": "带前景遮挡的三分之四移动近景", "action": "人物听清招呼后仍处于转身或迈步末端，一手压住报纸/包带，准备回应", "gaze": "视线追随画外朋友，肩膀和下巴保持运动方向，不直视镜头", "performance": "一只脚保留行进方向，重心完成转移；禁止静态美姿和无目的摸脸/头发"},
    {"role": "材质收束", "camera": "手部、袖口、报纸和杂志架的触觉特写", "action": "一只手压住报纸，另一只手整理牛仔袖口后重新握紧纸张", "gaze": "面部可不入画", "performance": "展示织纹、车线、折痕、手指压力和接触阴影"},
)


def read_shiying_key(path: Path) -> None:
    if not path.is_file():
        return
    current_url = ""
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        lower = line.strip().lower()
        if "平台" in line and "shiying" in lower:
            current_url = "shiying"
        elif lower.startswith("url") and (":" in line or "：" in line):
            current_url = line.replace("：", ":", 1).split(":", 1)[1].strip().lower()
        if lower.startswith("key") and (":" in line or "：" in line) and "shiying" in current_url:
            os.environ.setdefault("API_PROVIDER_SHIYING_KEY", line.replace("：", ":", 1).split(":", 1)[1].strip())


async def generate_one(canvas_main, prompt: str, inputs, provider: str, model: str, prefix: str):
    return await asyncio.wait_for(
        canvas_main.execute_ai_image_batch(
            prompt=prompt,
            provider_id=provider,
            model=model,
            size="4:5",
            quality="high",
            references=inputs,
            count=1,
            prefix=prefix,
            allow_edit_endpoint_fallback=False,
            semantic_mask=True,
        ),
        timeout=240,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="真实验证李维斯广告三种色彩变体")
    parser.add_argument("--output-dir", default=str(ROOT / "输出" / "李维斯广告风格分析" / "色彩变体场景验证-20260902"))
    parser.add_argument("--api-key-file", default=str(ROOT / "api文档" / "api key.md"))
    parser.add_argument("--provider", default="shiying")
    parser.add_argument("--model", default="gemini-3-pro-image-preview")
    parser.add_argument("--styles", default=",".join(STYLES), help="逗号分隔的风格 ID")
    parser.add_argument("--shots", default="1,2,3,4", help="只生成指定镜头编号，默认 1,2,3,4")
    args = parser.parse_args()
    read_shiying_key(Path(args.api_key_file))
    os.environ.setdefault("CANVAS_DWPOSE_AUTO_DOWNLOAD", "0")
    os.environ.setdefault("CANVAS_DEPTH_AUTO_DOWNLOAD", "0")
    os.environ.setdefault("CANVAS_DESKTOP_TOKEN", "levis-advertising-variants-real")
    os.environ.setdefault("CANVAS_RUNTIME_MODE", "desktop")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    model_candidates = sorted((ROOT / "测试" / "模特").glob("*"))
    model_path = next((item for item in model_candidates if item.suffix.lower() in {".jpg", ".jpeg", ".png"}), None)
    source_images = [model_path or ROOT / "测试" / "模特" / "XSY_9373.JPG", ROOT / "测试" / "场景" / "page-014_img-006.jpeg"]
    for path in source_images:
        if not path.is_file():
            raise FileNotFoundError(path)
    selected = [item.strip() for item in str(args.styles).split(",") if item.strip()]
    unknown = [item for item in selected if item not in STYLES]
    if unknown:
        raise ValueError(f"未知风格 ID: {unknown}")
    selected_shots = sorted({int(item.strip()) for item in str(args.shots).split(",") if item.strip().isdigit() and 1 <= int(item.strip()) <= 4})
    if not selected_shots:
        raise ValueError("--shots 至少需要一个 1-4 的镜头编号")
    report_path = output_dir / "色彩变体场景验证报告.json"
    report = {"status": "running", "scenario": SCENARIO, "requested_shots": selected_shots, "images_per_style": len(selected_shots), "styles": []}
    with tempfile.TemporaryDirectory(prefix="levis-advertising-variants-") as data_dir:
        os.environ["CANVAS_DATA_DIR"] = data_dir
        import main as canvas_main
        from canvas_core.ecommerce import build_prompt

        input_root = Path(os.fspath(canvas_main.OUTPUT_INPUT_DIR))
        input_root.mkdir(parents=True, exist_ok=True)
        uploaded = []
        for path in source_images:
            target = input_root / f"variant_{path.name}"
            shutil.copy2(path, target)
            uploaded.append({"url": f"/assets/input/{target.name}", "path": str(target)})
        inputs = [
            {**uploaded[0], "role": "subject", "reference_type": "subject", "reference_id": "model", "label": "人物", "lookbook_role": "人物", "instruction": "锁定人物身份、脸、发型、身体比例和可见配饰。"},
            {**uploaded[1], "role": "scene", "reference_type": "scene", "reference_id": "scene", "label": "场景", "lookbook_role": "场景", "instruction": "锁定绿色报刊亭、树木、海报、杂志架、地面和建筑几何。"},
        ]
        for style_id in selected:
            options = {
                "prompt_policy": "lookbook",
                "instruction": SCENARIO,
                "lookbook_count": 4,
                "lookbook_style": {"id": style_id, "name": STYLES[style_id]},
                "lookbook_search": False,
            }
            base = build_prompt("universal", inputs, options)
            prompts = canvas_main.lookbook_generation_prompts({"count": 4, "prompt": base, "options": options})
            style_report = {"id": style_id, "name": STYLES[style_id], "scenario": SCENARIO, "images": [], "failures": []}
            for index, shot in enumerate(prompts, 1):
                if index not in selected_shots:
                    continue
                # 将简短卡片显式附在 prompt 末尾，避免四张图只共享抽象风格而没有叙事节拍。
                shot_prompt = shot + " SCENE STORY SHOT CARD: " + json.dumps(SHOT_CARDS[index - 1], ensure_ascii=False, separators=(",", ":"))
                try:
                    batch = asyncio.run(generate_one(canvas_main, shot_prompt, inputs, args.provider, args.model, f"{style_id}_{index:02d}_"))
                    # 直接调用 execute_ai_image_batch 不会经过任务层 finish，这里显式应用预设后处理。
                    batch = canvas_main.apply_lookbook_film_finish(batch, {"options": options})
                    for url in batch.get("images") or []:
                        source = canvas_main.output_file_from_url(url)
                        target = output_dir / style_id / f"{style_id}_{index:02d}{Path(source).suffix.lower()}"
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, target)
                        with Image.open(target) as image:
                            style_report["images"].append({"shot_index": index, "path": str(target), "size": f"{image.width}x{image.height}", "prompt": shot_prompt})
                except Exception as exc:
                    style_report["failures"].append({"shot_index": index, "error": str(exc)[:500]})
                report["styles"] = [item for item in report["styles"] if item.get("id") != style_id] + [style_report]
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["status"] = "ok" if all(len(item.get("images") or []) == len(selected_shots) and not item.get("failures") for item in report["styles"]) else "partial"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
