from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parent.parent
MATRIX_ROOT = ROOT / "输出" / "李维斯广告风格分析" / "环境矩阵-后处理-20260902"
OUTPUT = MATRIX_ROOT / "本地视觉模型验收.json"
MODEL_IMAGE = ROOT / "测试" / "模特.png"
SCENE_IMAGE = ROOT / "测试" / "场景.jpeg"


def data_url(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


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


def review_group(client: httpx.Client, key: str, group_id: str, paths: list[Path]) -> dict:
    content = [
        {"type": "text", "text": (
            "你是严格的时尚广告终审。图1是人物身份/原服装，图2是场景，图3-6是同一环境组的四张输出。"
            "只依据可见事实，分别检查：人物身份和原服装、场景几何、天气/时间光线、肤色和色彩一致性、"
            "人物是否正在做事、视线/手指/重心是否有因果、是否仍像电商摆拍、丹宁/针织/皮肤/发丝细节、"
            "颗粒是否形成脏点或吞噬细节、四张镜头职责是否不同。评分必须严格。"
            "输出 JSON，不要 Markdown："
            '{"group_id":"","scores":{"identity":0,"wardrobe":0,"scene":0,"environment_light":0,"color":0,'
            '"human_vitality":0,"action_causality":0,"material_detail":0,"grain":0,"series_consistency":0},'
            '"frame_findings":[{"frame":1,"role":"","strengths":[""],"failures":[""]}],'
            '"overall":"达成|基本达成|部分达成|未达成","must_fix":[""],"summary":""}'
        )},
        {"type": "text", "text": "图1 人物参考"},
        {"type": "image_url", "image_url": {"url": data_url(MODEL_IMAGE)}},
        {"type": "text", "text": "图2 场景参考"},
        {"type": "image_url", "image_url": {"url": data_url(SCENE_IMAGE)}},
    ]
    for index, path in enumerate(paths, 1):
        content.append({"type": "text", "text": f"图{index + 2} 输出帧 {index}"})
        content.append({"type": "image_url", "image_url": {"url": data_url(path)}})
    response = client.post(
        "http://127.0.0.1:1234/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "qwen3.5-9b-vlm", "messages": [{"role": "system", "content": "只输出严格 JSON，评分范围 0-100。"}, {"role": "user", "content": content}], "temperature": 0.1, "max_tokens": 1800},
        timeout=300,
    )
    response.raise_for_status()
    payload = response.json()
    message = ((payload.get("choices") or [{}])[0].get("message") or {})
    text = message.get("content") or message.get("reasoning_content") or message.get("reasoning") or ""
    if isinstance(text, list):
        text = "".join(str(item.get("text") or item.get("content") or "") for item in text if isinstance(item, dict))
    result = parse_json(str(text))
    result.setdefault("group_id", group_id)
    return result


def main() -> int:
    key = os.getenv("LEVIS_LOCAL_VISION_KEY", "").strip()
    if not key:
        raise RuntimeError("缺少 LEVIS_LOCAL_VISION_KEY")
    report = json.loads((MATRIX_ROOT / "环境矩阵测试报告.json").read_text(encoding="utf-8"))
    result = {"status": "running", "model": "qwen3.5-9b-vlm", "endpoint": "http://127.0.0.1:1234", "groups": []}
    started = time.time()
    with httpx.Client() as client:
        for group in report.get("groups") or []:
            group_id = str(group.get("id") or "")
            paths = [Path(item["path"]) for item in sorted(group.get("images") or [], key=lambda item: int(item.get("shot_index") or 0))]
            print(f"验收 {group_id} ...", flush=True)
            try:
                review = review_group(client, key, group_id, paths)
                result["groups"].append({"id": group_id, "review": review})
            except Exception as exc:
                result["groups"].append({"id": group_id, "error": str(exc)[:500]})
            OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["status"] = "ok" if len(result["groups"]) == 5 and all(item.get("review", {}).get("scores") for item in result["groups"]) else "partial"
    result["elapsed_seconds"] = round(time.time() - started, 3)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "groups": len(result["groups"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
