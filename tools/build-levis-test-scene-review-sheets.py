from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "输出" / "李维斯广告风格分析" / "测试场景全量回归-20260902"
TARGET = ROOT / "输出" / "李维斯广告风格分析" / "测试场景全量复核板-20260902"


def main() -> int:
    TARGET.mkdir(parents=True, exist_ok=True)
    report = json.loads((SOURCE / "多场景互动生成报告.json").read_text(encoding="utf-8"))
    manifest = []
    for scene in report.get("scenes") or []:
        scene_id = str(scene.get("id") or "")
        paths = [Path(item["path"]) for item in sorted(scene.get("images") or [], key=lambda item: int(item.get("shot_index") or 0))]
        if len(paths) != 4 or not all(path.is_file() for path in paths):
            continue
        with Image.open(paths[0]) as sample:
            cell_w, cell_h = sample.size
        sheet = Image.new("RGB", (cell_w * 2, cell_h * 2 + 40), (20, 20, 20))
        draw = ImageDraw.Draw(sheet)
        draw.text((8, 8), f"{scene_id} | 4 original-resolution shots", fill=(255, 220, 120))
        for index, path in enumerate(paths):
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
                x = (index % 2) * cell_w + (cell_w - image.width) // 2
                y = 40 + (index // 2) * cell_h + (cell_h - image.height) // 2
                sheet.paste(image, (x, y))
        output = TARGET / f"{scene_id}.jpg"
        sheet.save(output, "JPEG", quality=96, subsampling=0)
        manifest.append({"id": scene_id, "file": str(output.resolve()), "size": list(sheet.size), "source_count": 4})
    (TARGET / "复核板清单.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "sheets": len(manifest), "shots": sum(item["source_count"] for item in manifest)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
