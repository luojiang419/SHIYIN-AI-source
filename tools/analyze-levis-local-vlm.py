from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path

import httpx


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def image_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def extract_json(text: str) -> dict:
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


def request_batch(client: httpx.Client, endpoint: str, key: str, model: str, groups: list[tuple[str, list[Path]]]) -> dict:
    content: list[dict] = [{
        "type": "text",
        "text": (
            "你是广告片视觉研究员。下面每组图属于同一条视频，标签中的 video_id 和 start/mid/end 是唯一编号。"
            "只根据画面可见证据，概括可迁移的方法，不要复述品牌名、人物姓名、Logo 或文案，不要猜测不可见信息。每个字段尽量控制在 30 字以内。"
            "请对每条视频分别输出：环境 interior/exterior/mixed、天气、时间、主光源方向与软硬、色彩关系、摄影机/构图、"
            "人物情绪与动作、置景/材质、妆发，以及一句可迁移方法。最后输出本批次共同规律。"
            "严格输出 JSON，不要 Markdown，结构为："
            '{"videos":[{"video_id":"01","environment":"","weather":"","time":"","lighting":"",'
            '"palette":"","camera":"","emotion_action":"","set_material":"","grooming":"","transferable_method":""}],'
            '"batch_patterns":[""],"uncertainties":[""]}'
        ),
    }]
    for video_id, frames in groups:
        content.append({"type": "text", "text": f"\n视频 {video_id} 的三帧证据："})
        for slot, path in zip(("start", "mid", "end"), frames):
            content.append({"type": "text", "text": f"视频 {video_id} / {slot}"})
            content.append({"type": "image_url", "image_url": {"url": image_data_url(path)}})
    response = client.post(
        endpoint.rstrip("/") + "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "只输出严格 JSON。事实优先，证据不足就写空字符串或 uncertainty。"},
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
    text = (
        message.get("content")
        or message.get("reasoning_content")
        or message.get("reasoning")
        or payload.get("output_text")
        or ""
    )
    if isinstance(text, list):
        text = "".join(str(item.get("text") or "") for item in text if isinstance(item, dict))
    return extract_json(str(text))


def main() -> int:
    parser = argparse.ArgumentParser(description="使用本地视觉模型批量解析李维斯参考视频证据帧")
    parser.add_argument("--endpoint", default=os.getenv("LEVIS_LOCAL_VISION_ENDPOINT", "http://127.0.0.1:1234"))
    parser.add_argument("--model", default="qwen3.5-9b-vlm")
    parser.add_argument("--frames", default=str(PROJECT_ROOT / "输出" / "李维斯广告风格分析" / "全部关键帧"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "输出" / "李维斯广告风格分析" / "本地视觉模型解析结果.json"))
    parser.add_argument("--batch-videos", type=int, default=2)
    parser.add_argument("--only", default="", help="只解析逗号分隔的视频编号，例如 01,02,41")
    parser.add_argument("--single-frame", action="store_true", help="每条视频只提交中点帧，适合多图响应不稳定时重试")
    args = parser.parse_args()
    key = os.getenv("LEVIS_LOCAL_VISION_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少 LEVIS_LOCAL_VISION_KEY；密钥只应通过当前进程环境变量传入")
    frame_root = Path(args.frames).resolve()
    output_path = Path(args.output).resolve()
    groups: list[tuple[str, list[Path]]] = []
    for video_id in range(1, 42):
        frames = [frame_root / f"video_{video_id:02d}_{slot}.jpg" for slot in ("start", "mid", "end")]
        if all(path.is_file() for path in frames):
            groups.append((f"{video_id:02d}", frames))
    if len(groups) != 41:
        raise RuntimeError(f"证据帧不完整：找到 {len(groups)}/41 条视频")
    only = {item.strip().zfill(2) for item in str(args.only or "").split(",") if item.strip()}
    if only:
        groups = [group for group in groups if group[0] in only]
        if len(groups) != len(only):
            raise RuntimeError(f"指定视频编号不存在：{sorted(only - {group[0] for group in groups})}")
    if args.single_frame:
        groups = [(video_id, [frames[1]]) for video_id, frames in groups]

    result = {
        "status": "running",
        "endpoint": args.endpoint,
        "model": args.model,
        "video_count": len(groups),
        "frame_count": len(groups) * 3,
        "batches": [],
    }
    started = time.time()
    with httpx.Client() as client:
        for offset in range(0, len(groups), max(1, args.batch_videos)):
            batch = groups[offset : offset + max(1, args.batch_videos)]
            batch_ids = [item[0] for item in batch]
            print(f"解析视频 {batch_ids[0]}-{batch_ids[-1]} ...", flush=True)
            try:
                parsed = request_batch(client, args.endpoint, key, args.model, batch)
                result["batches"].append({"video_ids": batch_ids, "analysis": parsed})
            except Exception as exc:
                result["batches"].append({"video_ids": batch_ids, "error": str(exc)[:500]})
            output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["status"] = "ok" if all("analysis" in item for item in result["batches"]) else "partial"
    result["elapsed_seconds"] = round(time.time() - started, 3)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "batches": len(result["batches"]), "elapsed_seconds": result["elapsed_seconds"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
