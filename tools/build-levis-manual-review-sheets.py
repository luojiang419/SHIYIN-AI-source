"""为李维斯参考视频生成原尺寸人工复核联系图。

该脚本只做可视化排版，不调用任何视觉模型，也不对画面做语义筛选。
每个格子尽量保留源帧的原始像素尺寸，避免把缩略图误当作证据。
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent / "输出" / "李维斯广告风格分析"
SAMPLE_ROOT = ROOT / "全部采样帧-5s"
SCENE_ROOT = ROOT / "镜头变化帧-去重"
OUT_ROOT = ROOT / "人工高清复核联系图"
MANIFEST = ROOT / "人工高清复核联系图清单.json"


def select_evenly(paths: list[Path], limit: int = 12) -> list[Path]:
    """按时间排序均匀取样；不改变原始帧，只限制一张联系图的格数。"""
    if len(paths) <= limit:
        return paths
    indexes = [round(index * (len(paths) - 1) / (limit - 1)) for index in range(limit)]
    return [paths[index] for index in indexes]


def load_font(size: int):
    for name in ("segoeui.ttf", "msyh.ttc", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []
    # 720x406 是当前抽帧的原始尺寸；联系图单格不缩小，右侧/底部仅增加标签。
    cell_w, cell_h, label_h, header_h, gap = 720, 406, 42, 38, 8
    title_font = load_font(26)
    label_font = load_font(18)

    for video_id in range(1, 42):
        sample = sorted(SAMPLE_ROOT.glob(f"video_{video_id:02d}_*.jpg"))
        scene = sorted(SCENE_ROOT.glob(f"video_{video_id:02d}_*.jpg"))
        candidates = sorted({path.resolve() for path in [*sample, *scene]}, key=lambda path: path.name)
        selected = select_evenly(candidates)
        rows = max(1, (len(selected) + 3) // 4)
        sheet = Image.new("RGB", (cell_w * 4 + gap * 5, header_h + (cell_h + label_h) * rows + gap * (rows + 1)), (20, 20, 20))
        draw = ImageDraw.Draw(sheet)
        for index, path in enumerate(selected):
            col, row = index % 4, index // 4
            x = gap + col * (cell_w + gap)
            y = header_h + gap + row * (cell_h + label_h + gap)
            with Image.open(path) as source:
                image = source.convert("RGB")
                if image.size != (cell_w, cell_h):
                    # 只允许等比缩小，不对低分辨率素材做虚假放大。
                    image.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
                paste_x = x + (cell_w - image.width) // 2
                paste_y = y + (cell_h - image.height) // 2
                sheet.paste(image, (paste_x, paste_y))
            draw.rectangle((x, y + cell_h, x + cell_w, y + cell_h + label_h), fill=(32, 32, 32))
            draw.text((x + 8, y + cell_h + 9), f"{index + 1:02d}  {path.name}", fill=(240, 240, 240), font=label_font)
        # 标题使用 ASCII，避免运行环境缺少中文字体时渲染成方框；帧文件名仍保留完整证据编号。
        draw.text((gap, 5), f"video_{video_id:02d} | ORIGINAL-RES EVIDENCE | {len(selected)}/{len(candidates)}", fill=(255, 220, 120), font=title_font)
        target = OUT_ROOT / f"video_{video_id:02d}.jpg"
        sheet.save(target, "JPEG", quality=96, subsampling=0, optimize=False)
        manifest.append({
            "video_id": f"{video_id:02d}",
            "candidate_count": len(candidates),
            "selected_count": len(selected),
            "source_dimensions": [cell_w, cell_h],
            "sheet_dimensions": list(sheet.size),
            "file": str(target.resolve()),
            "source_files": [str(path) for path in selected],
        })

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"videos": len(manifest), "sheets": len(list(OUT_ROOT.glob("*.jpg"))), "selected_frames": sum(item["selected_count"] for item in manifest)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
