"""只读核验真实软件输出与模型原图，裁片和差异图不参与生成。"""
import json
import sqlite3
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '案例/批量复刻培训-20260920/evidence'
DATA = Path('D:/Program Files/SHIYIN AI/data')
FINAL = '/assets/output/fabric_0c419eb12a2e4b5c89dd04913deab09e.png'


def main():
    with sqlite3.connect((DATA / 'database/canvas.db').as_uri() + '?mode=ro', uri=True) as conn:
        record = next(p for (raw,) in conn.execute('SELECT payload_json FROM generation_history')
                      if FINAL in (p := json.loads(raw)).get('images', []))
    original = record['original_images'][0]
    box = (1500, 850, 2050, 1250)
    images = [Image.open(DATA / 'media/generated' / Path(url).name).convert('RGB')
              for url in (original, FINAL)]
    assert images[0].size == images[1].size
    crops = [im.crop(box) for im in images]
    for im, name in zip(crops, ('button-model-original.png', 'button-software-final.png')):
        im.save(OUT / name)
    pair = Image.new('RGB', (1100, 400))
    for i, im in enumerate(crops):
        pair.paste(im, (550*i, 0))
    pair.save(OUT / 'button-before-after.png')
    a, b = [np.asarray(im).astype('int16') for im in crops]
    changed = np.any(a != b, axis=2)
    Image.fromarray((changed*255).astype('uint8')).save(OUT / 'button-changed-mask.png')
    # 人工观察后选取的验证框，仅测量，不能用于构造增强掩膜。
    regions = {'button_upper_cloth': (210, 38, 50, 30),
               'adjacent_waist_cloth': (355, 60, 100, 60),
               'right_button_center': (305, 80, 20, 20)}
    metrics = {}
    for name, (x, y, w, h) in regions.items():
        delta = (b-a)[y:y+h, x:x+w]
        metrics[name] = {'crop_xywh': [x, y, w, h],
                         'changed_fraction': float(np.mean(np.any(delta != 0, axis=2))),
                         'mean_absolute_channel_difference': float(np.abs(delta).mean())}
    audit = {'original': original, 'final': FINAL, 'crop_xyxy': box,
             'enhancement': record.get('fabric_enhancement'), 'regions': metrics,
             'interpretation': '黑色表示最终像素与模型原图完全相同，并非软件内部掩膜；白色表示发生变化。纽扣上方布面存在未增强区域，相邻布面被增强，原图本已偏软。',
             'verdict': '未通过纹理连续性验收；未修改软件或重新生图。'}
    (OUT / 'button-coverage-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == '__main__':
    main()
