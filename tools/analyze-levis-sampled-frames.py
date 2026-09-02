from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parent.parent / "输出" / "李维斯广告风格分析"
FRAME_ROOT = ROOT / "全部采样帧-5s"
OUTPUT = ROOT / "全量5秒采样逐帧数值证据.json"
NAME_RE = re.compile(r"video_(\d{2})_(\d{4})\.jpg$")


def dominant_colors(image: Image.Image, count: int = 3) -> list[dict]:
    reduced = image.convert("RGB").resize((96, 54), Image.Resampling.BILINEAR)
    quantized = reduced.quantize(colors=count, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    color_counts = sorted(quantized.getcolors() or [], reverse=True)
    total = max(1, sum(amount for amount, _ in color_counts))
    result = []
    for amount, index in color_counts[:count]:
        rgb = palette[index * 3 : index * 3 + 3]
        result.append({"hex": "#" + "".join(f"{value:02X}" for value in rgb), "ratio": round(amount / total, 4)})
    return result


def analyze(path: Path) -> dict:
    match = NAME_RE.match(path.name)
    if not match:
        raise ValueError(path.name)
    video_id, sample_index = match.groups()
    with Image.open(path) as source:
        image = source.convert("RGB")
        small = image.resize((320, max(1, round(image.height * 320 / image.width))), Image.Resampling.BILINEAR)
        rgb = np.asarray(small, dtype=np.float32) / 255.0
        luma = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        blurred = np.asarray(small.filter(ImageFilter.GaussianBlur(radius=1.1)), dtype=np.float32) / 255.0
        maximum = rgb.max(axis=2)
        minimum = rgb.min(axis=2)
        saturation = np.zeros_like(maximum)
        np.divide(maximum - minimum, maximum, out=saturation, where=maximum > 1e-6)
        p1, p50, p99 = np.percentile(luma, [1, 50, 99])
        return {
            "video_id": video_id,
            "sample_index": int(sample_index),
            "approx_time_seconds": (int(sample_index) - 1) * 5,
            "file": str(path),
            "width": image.width,
            "height": image.height,
            "p1": round(float(p1), 4),
            "p50": round(float(p50), 4),
            "p99": round(float(p99), 4),
            "dark_ratio_lt_0_08": round(float((luma < 0.08).mean()), 4),
            "highlight_ratio_gt_0_95": round(float((luma > 0.95).mean()), 4),
            "mean_saturation": round(float(saturation.mean()), 4),
            "high_frequency_residual_std": round(float((rgb - blurred).std()), 5),
            "dominant_colors": dominant_colors(small),
        }


def main() -> int:
    items = [analyze(path) for path in sorted(FRAME_ROOT.glob("video_*.jpg"))]
    by_video = []
    for video_id in sorted({item["video_id"] for item in items}):
        frames = [item for item in items if item["video_id"] == video_id]
        by_video.append({
            "video_id": video_id,
            "frame_count": len(frames),
            "approx_covered_seconds": frames[-1]["approx_time_seconds"] if frames else 0,
            "p50_range": [min(item["p50"] for item in frames), max(item["p50"] for item in frames)] if frames else [],
            "frames": frames,
        })
    result = {"status": "ok" if len(items) == 976 and len(by_video) == 41 else "partial", "sampling_interval_seconds": 5, "frame_count": len(items), "video_count": len(by_video), "videos": by_video}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "frames": len(items), "videos": len(by_video)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
