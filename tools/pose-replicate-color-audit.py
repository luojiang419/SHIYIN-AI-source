"""本例衣片局部颜色诊断；只测量/拼接，不对生成图做任何调色。"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1] / '输出/一键复刻服装保真-20260911'
REFERENCE_BOXES = [(0.25, 0.30, 0.47, 0.48), (0.65, 0.32, 0.80, 0.52)]
TARGET_BOXES = [(0.34, 0.36, 0.50, 0.50), (0.60, 0.37, 0.70, 0.52)]
CASES = [
    ('服装参考', 'garment.png', REFERENCE_BOXES),
    ('上一版 v3.2', 'attempt-2/result.png', TARGET_BOXES),
    ('v3.3 Gemini', 'attempt-3-color/result.png', TARGET_BOXES),
    ('v3.3 GPT Image 2', 'attempt-4-gpt-color/result.png', TARGET_BOXES),
    ('GPT + 图2色样', 'attempt-5-color-samples/result.png', TARGET_BOXES),
    ('上一版局部校色', 'attempt-6-color-only/result.png', TARGET_BOXES),
]


def main():
    report = {'method': '手动选取左右两块衣片，按各区域L*第65至90百分位抽样较亮底色，第10至35百分位抽样深纹样；sRGB转CIELAB D65，报告中位数。',
              'limitations': '不同姿势与光照下的非配准区域，只用于诊断偏色；没有标定色卡，不代表商品色差合格证，也不对整体颜色作自动通过判断。',
              'cases': []}
    panels = []
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 27)
    for label, name, boxes in CASES:
        if not (ROOT / name).exists():
            continue
        with Image.open(ROOT / name) as source:
            source = source.convert('RGB')
            record = {'label': label, 'file': name, 'regions': []}
            panel = Image.new('RGB', (550, 640), '#f4f3f0')
            draw = ImageDraw.Draw(panel)
            draw.text((275, 30), label, font=font, fill='#222222', anchor='mm')
            for index, box in enumerate(boxes):
                pixel_box = tuple(round(value * (source.width if i % 2 == 0 else source.height)) for i, value in enumerate(box))
                crop = source.crop(pixel_box)
                lab = cv2.cvtColor(np.asarray(crop).astype(np.float32) / 255, cv2.COLOR_RGB2LAB).reshape(-1, 3)
                regions = {'normalized_box': box, 'pixel_box': pixel_box}
                for key, low, high in [('ground', 65, 90), ('pattern', 10, 35)]:
                    selected = (lab[:, 0] >= np.percentile(lab[:, 0], low)) & (lab[:, 0] <= np.percentile(lab[:, 0], high))
                    regions[key + '_median_lab'] = np.median(lab[selected], axis=0).round(2).tolist()
                record['regions'].append(regions)
                crop.thumbnail((510, 215), Image.Resampling.LANCZOS)
                y = 70 + index * 280
                panel.paste(crop, ((550-crop.width)//2, y))
                values = regions['ground_median_lab']
                draw.text((275, y+240), f"底色 L* {values[0]:.1f}  a* {values[1]:.1f}  b* {values[2]:.1f}", font=font, fill='#222222', anchor='mm')
            report['cases'].append(record)
            panels.append(panel)
    (ROOT / '颜色局部抽样.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    comparison = Image.new('RGB', (550*len(panels), 640), '#f4f3f0')
    for index, panel in enumerate(panels):
        comparison.paste(panel, (550*index, 0))
    comparison.save(ROOT / '颜色局部对照.jpg', quality=96, subsampling=0)
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
