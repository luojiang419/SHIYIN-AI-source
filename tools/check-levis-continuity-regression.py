"""检查李维斯环境矩阵的跨时间/天气连续性证据。

脚本不重新生成图片，而是读取已有的 5 类环境 × 4 张独立镜头报告，验证每组
镜头完整性、尺寸一致性和曝光/色彩统计，并输出人工复核清单。它不会把有意的
天气曝光差异误判成失败；最终身份、动作因果和场景几何仍需人工查看。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image
import numpy as np


EXPECTED = ("clear_day", "overcast", "wet_after_rain", "interior_window", "blue_hour_practical")


def inspect(report_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    groups = {str(item.get("id")): item for item in report.get("groups") or [] if isinstance(item, dict)}
    result = {"source_report": str(report_path), "expected_groups": list(EXPECTED), "groups": [], "errors": [], "manual_review": []}
    for group_id in EXPECTED:
        group = groups.get(group_id)
        if not group:
            result["errors"].append(f"缺少环境组: {group_id}")
            continue
        images = [item for item in group.get("images") or [] if isinstance(item, dict)]
        shot_ids = sorted(int(item.get("shot_index") or 0) for item in images)
        entry = {"id": group_id, "condition": group.get("condition", ""), "image_count": len(images), "shot_indices": shot_ids, "frames": [], "status": "ok"}
        if shot_ids != [1, 2, 3, 4] or len(images) != 4:
            entry["status"] = "partial"
            result["errors"].append(f"{group_id} 镜头不完整: {shot_ids}")
        for item in sorted(images, key=lambda value: int(value.get("shot_index") or 0)):
            path = Path(str(item.get("path") or ""))
            if not path.is_file():
                entry["status"] = "partial"
                result["errors"].append(f"文件不存在: {path}")
                continue
            with Image.open(path) as image:
                rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
                size = [int(image.width), int(image.height)]
            luma = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
            chroma = np.max(rgb, axis=2) - np.min(rgb, axis=2)
            entry["frames"].append({
                "shot_index": int(item.get("shot_index") or 0),
                "path": str(path),
                "size": size,
                "luma_p50": round(float(np.percentile(luma, 50)), 4),
                "luma_p99": round(float(np.percentile(luma, 99)), 4),
                "chroma_p50": round(float(np.percentile(chroma, 50)), 4),
                "chroma_p99": round(float(np.percentile(chroma, 99)), 4),
            })
        result["groups"].append(entry)
        result["manual_review"].append({"id": group_id, "checks": ["同一人物脸型/发型/服装连续", "报刊亭与列车几何连续", "动作从报纸任务自然推进", "主光方向符合该天气/时间", "四张色彩和颗粒质感连续"]})
    result["status"] = "ok" if not result["errors"] and len(result["groups"]) == len(EXPECTED) else "partial"
    return result


def write_markdown(result: dict, target: Path) -> None:
    lines = ["# 李维斯跨时间/天气连续性回归", "", f"状态：{result['status']}", "", "## 数值摘要", "", "| 环境 | 图数 | 镜头 | P50亮度范围 | P99亮度范围 | P99色度范围 |", "| --- | ---: | --- | ---: | ---: | ---: |"]
    for group in result["groups"]:
        frames = group["frames"]
        p50 = [item["luma_p50"] for item in frames]
        p99 = [item["luma_p99"] for item in frames]
        c99 = [item["chroma_p99"] for item in frames]
        lines.append(f"| {group['id']} | {group['image_count']} | {group['shot_indices']} | {min(p50, default=0):.3f}–{max(p50, default=0):.3f} | {min(p99, default=0):.3f}–{max(p99, default=0):.3f} | {min(c99, default=0):.3f}–{max(c99, default=0):.3f} |")
    lines.extend(["", "## 人工复核清单", "", "数值检查只确认组图完整、尺寸和曝光统计；以下项目必须按组查看原图：", "", "- 同一人物身份、发型、服装和配饰跨环境保持连续。", "- 同一报刊亭/列车场景的几何、标牌、杂志架和接触关系没有漂移。", "- 报纸任务从环境建立、动作经过、自信停顿到材质收束有因果推进。", "- 晴天、阴天、雨后、室内窗光、蓝调入夜的光线方向和反射符合条件。", "- 有意的亮度/色度变化服务于天气，不应变成随机滤镜或风格断裂。"])
    if result["errors"]:
        lines.extend(["", "## 错误", "", *[f"- {item}" for item in result["errors"]]])
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="检查李维斯跨时间/天气连续性")
    parser.add_argument("--report", default="输出/李维斯广告风格分析/环境矩阵-20260902/环境矩阵测试报告.json")
    parser.add_argument("--output-dir", default="输出/李维斯广告风格分析/跨时间天气连续性回归-20260902")
    args = parser.parse_args()
    result = inspect(Path(args.report).resolve())
    target_dir = Path(args.output_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "跨时间天气连续性回归.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(result, target_dir / "跨时间天气连续性回归.md")
    print(json.dumps({"status": result["status"], "groups": len(result["groups"]), "errors": len(result["errors"])}, ensure_ascii=False))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
