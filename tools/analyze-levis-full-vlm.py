from __future__ import annotations

import base64
import json
import os
import time
import argparse
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent
SHEET_ROOT = ROOT / "输出" / "李维斯广告风格分析" / "VLM全量联系图"
OUTPUT = ROOT / "输出" / "李维斯广告风格分析" / "本地视觉模型全量解析.json"


def data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def parse_json(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {"raw": raw}
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(raw[start : end + 1])
                return value if isinstance(value, dict) else {"raw": raw}
            except json.JSONDecodeError:
                pass
    return {"raw": raw}


def request_batch(client: httpx.Client, key: str, model: str, groups: list[tuple[str, Path]]) -> dict:
    content: list[dict] = [{
        "type": "text",
        "text": (
            "你是严格的广告片视觉研究员。每张联系图对应一条完整视频，图内按时间顺序排列了固定间隔帧与镜头变化候选帧，"
            "不是一张广告海报。请只依据可见证据，提取可迁移的方法，不复述品牌名、人物姓名、Logo、文案或具体地点。"
            "分别输出每条视频：环境类型、天气/时间（看不出就空）、黑白点、主光源方向/软硬/补光、色彩比例、摄影机/景别/剪辑节奏、"
            "人物情绪与动作、妆发、置景和材质、3条可迁移规则、3个关键时间节点。字段短而具体。"
            "严格输出 JSON，不要 Markdown："
            '{"videos":[{"video_id":"01","environment":"","weather":"","time":"",'
            '"black_white_points":"","lighting":"","palette":"","camera_editing":"",'
            '"emotion_action":"","grooming":"","set_material":"",'
            '"transferable_rules":["","",""],"key_moments":[{"position":"","evidence":"","use":""}]}],'
            '"cross_video_patterns":[""],"uncertainties":[""]}'
        ),
    }]
    for video_id, path in groups:
        content.append({"type": "text", "text": f"视频 {video_id} 全片联系图，按左到右、上到下阅读："})
        content.append({"type": "image_url", "image_url": {"url": data_url(path)}})
    response = client.post(
        "http://127.0.0.1:1234/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "只输出严格 JSON。每条视频必须有 video_id；证据不足写空字符串。"},
                {"role": "user", "content": content},
            ],
            "temperature": 0.1,
            "max_tokens": 2200,
        },
        timeout=300,
    )
    response.raise_for_status()
    payload = response.json()
    message = ((payload.get("choices") or [{}])[0].get("message") or {})
    text = message.get("content") or message.get("reasoning_content") or message.get("reasoning") or payload.get("output_text") or ""
    if isinstance(text, list):
        text = "".join(
            str(item.get("text") or item.get("content") or "")
            for item in text
            if isinstance(item, dict)
        )
    return parse_json(str(text))


def main() -> int:
    parser = argparse.ArgumentParser(description="使用本地视觉模型解析李维斯视频全量联系图")
    parser.add_argument("--only", default="", help="只解析逗号分隔的视频编号")
    parser.add_argument("--batch-videos", type=int, default=2)
    args = parser.parse_args()
    key = os.getenv("LEVIS_LOCAL_VISION_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少 LEVIS_LOCAL_VISION_KEY")
    model = os.getenv("LEVIS_LOCAL_VISION_MODEL", "qwen3.5-9b-vlm")
    groups = [(f"{index:02d}", SHEET_ROOT / f"video_{index:02d}.jpg") for index in range(1, 42)]
    if not all(path.is_file() for _, path in groups):
        raise RuntimeError("VLM 联系图不完整")
    only = {item.strip().zfill(2) for item in str(args.only or "").split(",") if item.strip()}
    if only:
        groups = [group for group in groups if group[0] in only]
    result = {"status": "running", "model": model, "endpoint": "http://127.0.0.1:1234", "video_count": 41, "contact_sheet_count": 41, "batches": []}
    started = time.time()
    with httpx.Client() as client:
        batch_size = max(1, int(args.batch_videos or 2))
        for offset in range(0, len(groups), batch_size):
            batch = groups[offset : offset + batch_size]
            ids = [item[0] for item in batch]
            print(f"全量解析视频 {ids[0]}-{ids[-1]} ...", flush=True)
            try:
                analysis = request_batch(client, key, model, batch)
                result["batches"].append({"video_ids": ids, "analysis": analysis})
            except Exception as exc:
                result["batches"].append({"video_ids": ids, "error": str(exc)[:500]})
            OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["status"] = "ok" if all("analysis" in item and item["analysis"].get("videos") for item in result["batches"]) else "partial"
    result["elapsed_seconds"] = round(time.time() - started, 3)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "batches": len(result["batches"]), "elapsed_seconds": result["elapsed_seconds"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
