from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_ROOT = ROOT / "输出" / "李维斯广告风格分析"
SOURCES = (
    ANALYSIS_ROOT / "本地视觉模型解析结果-v2.json",
    ANALYSIS_ROOT / "本地视觉模型解析结果-retry.json",
    ANALYSIS_ROOT / "本地视觉模型解析结果-retry-single.json",
    ANALYSIS_ROOT / "本地视觉模型解析结果-retry-fields.json",
    ANALYSIS_ROOT / "本地视觉模型解析结果-retry-11-12.json",
)
OUTPUT = ANALYSIS_ROOT / "本地视觉模型解析结果-汇总.json"


def main() -> int:
    videos: dict[str, dict] = {}
    patterns: list[str] = []
    uncertainties: list[str] = []
    source_files = []
    for path in SOURCES:
        if not path.is_file():
            continue
        source_files.append(str(path))
        payload = json.loads(path.read_text(encoding="utf-8"))
        for batch in payload.get("batches") or []:
            analysis = batch.get("analysis") or {}
            for item in analysis.get("videos") or []:
                if not isinstance(item, dict) or not str(item.get("video_id") or "").strip():
                    continue
                video_id = str(item["video_id"]).zfill(2)
                videos[video_id] = {**item, "source": path.name}
            patterns.extend(str(item).strip() for item in analysis.get("batch_patterns") or [] if str(item).strip())
            uncertainties.extend(str(item).strip() for item in analysis.get("uncertainties") or [] if str(item).strip())

    # 第 23 条在本地模型连续响应为空/截断时，保留其 reasoning 中明确给出的可见证据，
    # 并显式标注为 fallback，避免把推断伪装成结构化模型输出。
    videos.setdefault("23", {
        "video_id": "23",
        "environment": "outdoor/mixed",
        "weather": "festive lighting conditions",
        "time": "night/evening",
        "lighting": "warm overhead string lights, soft ambient",
        "palette": "teal accents against warm yellow ambient",
        "camera": "wide angle, eye level, capturing crowd",
        "emotion_action": "dancing and celebrating with joy",
        "set_material": "wooden pallets, fabric flags, string lights",
        "grooming": "casual wear, varied headwear",
        "transferable_method": "Warm string lights and cool accents for festive wide shots",
        "source": "本地视觉模型 reasoning fallback",
    })
    result = {
        "status": "ok" if len(videos) == 41 else "partial",
        "video_count": len(videos),
        "frame_count": 123,
        "model": "qwen3.5-9b-vlm",
        "endpoint": "http://127.0.0.1:1234",
        "source_files": source_files,
        "videos": [videos[key] for key in sorted(videos)],
        "batch_patterns": list(dict.fromkeys(patterns)),
        "uncertainties": list(dict.fromkeys(uncertainties)),
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "videos": result["video_count"], "frames": result["frame_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
