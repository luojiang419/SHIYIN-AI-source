"""生成同一商品区域的色彩可信度离线报告。"""
import argparse
import json
from pathlib import Path
import sys

from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from canvas_core.color_fidelity import crop_rgb, inspect_color_fidelity


def parse_box(value):
    parts = [int(part.strip()) for part in value.split(',')]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError('ROI 格式为 x,y,width,height')
    return parts


def load(path):
    with Image.open(path) as image:
        return np.asarray(image.convert('RGB'))


def save_crop(image, path):
    Image.fromarray(image).save(path, 'PNG')


def main():
    parser = argparse.ArgumentParser(description='商品复刻色彩可信度检查')
    parser.add_argument('--reference', required=True)
    parser.add_argument('--generated', required=True)
    parser.add_argument('--reference-roi', type=parse_box, required=True)
    parser.add_argument('--generated-roi', type=parse_box, required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    reference = crop_rgb(load(args.reference), args.reference_roi)
    generated = crop_rgb(load(args.generated), args.generated_roi)
    save_crop(reference, output / 'reference-100pct.png')
    save_crop(generated, output / 'generated-100pct.png')
    report = inspect_color_fidelity(reference, generated).as_dict()
    report.update({'reference': str(Path(args.reference)), 'generated': str(Path(args.generated)),
                   'reference_roi': args.reference_roi, 'generated_roi': args.generated_roi})
    (output / 'color-fidelity.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    metrics = ''.join(f'<tr><th>{key}</th><td>{value}</td></tr>' for key, value in report.items() if key not in {'reference', 'generated', 'reference_roi', 'generated_roi'})
    (output / 'index.html').write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>商品色彩可信度检查</title><style>body{{margin:0;background:#f5f1e8;color:#202722;font:16px/1.6 system-ui,"Microsoft YaHei",sans-serif}}main{{max-width:1280px;margin:auto;padding:38px 24px}}h1{{margin:0}}.note{{color:#5b655d;max-width:880px}}.result{{padding:16px 20px;background:#fff;border-left:5px solid #7c442d}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}figure{{margin:0;background:white;padding:14px}}img{{display:block;width:100%;height:auto;image-rendering:auto}}figcaption{{padding-top:8px}}table{{border-collapse:collapse;background:#fff;width:100%;max-width:760px}}th,td{{padding:10px 14px;border-bottom:1px solid #ded8cd;text-align:left}}th{{width:42%}}@media(max-width:700px){{.pair{{grid-template-columns:1fr}}main{{padding:22px 14px}}}}</style><main><h1>商品复刻色彩可信度检查</h1><p class="note">两图均按原始像素裁切。原始色差反映用户看到的结果；归一后指标仅扣除整体曝光/色温偏移，用于判断商品本身的色相和饱和度是否接近，不能代替实物色卡或人工质检。</p><p class="result"><b>{report['confidence']}</b></p><div class="pair"><figure><img src="reference-100pct.png"><figcaption>参考商品区域 · 100% 原始像素</figcaption></figure><figure><img src="generated-100pct.png"><figcaption>复刻结果区域 · 100% 原始像素</figcaption></figure></div><h2>可审计指标</h2><table>{metrics}</table><p class="note">ROI：参考 {args.reference_roi}；复刻 {args.generated_roi}。</p></main></html>''', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
