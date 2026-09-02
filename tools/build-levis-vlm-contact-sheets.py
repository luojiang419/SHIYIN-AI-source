from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent / "输出" / "李维斯广告风格分析"
SAMPLE_ROOT = ROOT / "全部采样帧-5s"
SCENE_ROOT = ROOT / "镜头变化帧-去重"
OUT_ROOT = ROOT / "VLM全量联系图"
MANIFEST = ROOT / "VLM全量联系图清单.json"


def select_evenly(paths: list[Path], limit: int = 12) -> list[Path]:
    if len(paths) <= limit:
        return paths
    indexes = [round(index * (len(paths) - 1) / (limit - 1)) for index in range(limit)]
    return [paths[index] for index in indexes]


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for video_id in range(1, 42):
        sample = sorted(SAMPLE_ROOT.glob(f"video_{video_id:02d}_*.jpg"))
        scene = sorted(SCENE_ROOT.glob(f"video_{video_id:02d}_*.jpg"))
        # 5 秒序列提供全片覆盖，scene-detect 帧提供变化节点；去重后均匀抽样以控制 VLM 上下文。
        candidates = sorted({path.resolve() for path in [*sample, *scene]}, key=lambda path: path.name)
        selected = select_evenly(candidates)
        cell_w, cell_h = 420, 270
        sheet = Image.new("RGB", (cell_w * 4, cell_h * 3), (28, 28, 28))
        draw = ImageDraw.Draw(sheet)
        for index, path in enumerate(selected):
            try:
                with Image.open(path) as source:
                    image = source.convert("RGB")
                    image.thumbnail((cell_w - 8, cell_h - 28), Image.Resampling.LANCZOS)
                    x = (index % 4) * cell_w + (cell_w - image.width) // 2
                    y = (index // 4) * cell_h + 4
                    sheet.paste(image, (x, y))
                    draw.text(((index % 4) * cell_w + 5, (index // 4) * cell_h + cell_h - 21), path.stem[-18:], fill=(235, 235, 235))
            except Exception:
                continue
        target = OUT_ROOT / f"video_{video_id:02d}.jpg"
        sheet.save(target, "JPEG", quality=88, optimize=True)
        manifest.append({"video_id": f"{video_id:02d}", "candidate_count": len(candidates), "selected_count": len(selected), "file": str(target)})
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"videos": len(manifest), "sheets": len(list(OUT_ROOT.glob("*.jpg"))), "selected_frames": sum(item["selected_count"] for item in manifest)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
