from __future__ import annotations

import json
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parent.parent / "输出" / "李维斯广告风格分析" / "环境矩阵-20260902"
REPORT_PATH = ROOT / "环境矩阵测试报告.json"
OUTPUT_PATH = ROOT / "环境矩阵数值指标.json"


def metrics(path: Path) -> dict:
    with Image.open(path) as image:
        rgb_image = image.convert("RGB")
        rgb = np.asarray(rgb_image, dtype=np.float32) / 255.0
        luma = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
        blurred = np.asarray(rgb_image.filter(ImageFilter.GaussianBlur(radius=1.1)), dtype=np.float32) / 255.0
        residual = rgb - blurred
        maximum = rgb.max(axis=2)
        minimum = rgb.min(axis=2)
        saturation = np.zeros_like(maximum)
        np.divide(maximum - minimum, maximum, out=saturation, where=maximum > 1e-6)
        percentiles = np.percentile(luma, [1, 50, 99])
        return {
            "path": str(path),
            "width": rgb_image.width,
            "height": rgb_image.height,
            "p1": round(float(percentiles[0]), 4),
            "p50": round(float(percentiles[1]), 4),
            "p99": round(float(percentiles[2]), 4),
            "dark_ratio_lt_0_08": round(float((luma < 0.08).mean()), 4),
            "highlight_ratio_gt_0_95": round(float((luma > 0.95).mean()), 4),
            "mean_saturation": round(float(saturation.mean()), 4),
            "high_frequency_residual_std": round(float(residual.std()), 5),
            "mean_rgb": [round(float(value), 4) for value in rgb.reshape(-1, 3).mean(axis=0)],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="统计李维斯环境矩阵数值指标")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report_path = root / "环境矩阵测试报告.json"
    output_path = root / "环境矩阵数值指标.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    groups = []
    for group in report.get("groups") or []:
        images = [metrics(Path(item["path"])) for item in group.get("images") or [] if Path(item.get("path") or "").is_file()]
        summary = {}
        for field in ("p1", "p50", "p99", "dark_ratio_lt_0_08", "highlight_ratio_gt_0_95", "mean_saturation", "high_frequency_residual_std"):
            values = [item[field] for item in images]
            summary[field] = {"min": round(min(values), 5), "mean": round(sum(values) / len(values), 5), "max": round(max(values), 5)} if values else {}
        groups.append({"id": group.get("id"), "condition": group.get("condition"), "image_count": len(images), "summary": summary, "images": images})
    output = {"status": "ok" if len(groups) == 5 and all(group["image_count"] == 4 for group in groups) else "partial", "groups": groups}
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": output["status"], "groups": len(groups), "images": sum(group["image_count"] for group in groups)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
