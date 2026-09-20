"""在本轮模型原图上重放修复后的软件增强，不重新生图，不覆盖失败证据。"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canvas_core.fabric_enhancement import read_rgb,material_patch,garment_mask,refine_garment_boundary,enhance_fabric_image
from PIL import Image
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'案例/批量复刻培训-20260920'
MEDIA=Path('D:/Program Files/SHIYIN AI/data/media')
results=[]
for key,original,control in [('b-node','SHIYIN-001401-20260920.jpg','ai_ref_7474c3e225c7.png'),('b-product','SHIYIN-001400-20260920.jpg','ai_ref_605b74eb05b2.png')]:
    src=MEDIA/'generated'/original;detail=OUT/'assets/b-detail.jpg';depth=MEDIA/'input'/control
    dest=OUT/'assets'/f'{key}-fixed.png'
    result=enhance_fabric_image(src,detail,dest,depth)
    assert result['status']=='applied',result
    base=read_rgb(src);fixed=read_rgb(dest)
    _,color=material_patch(read_rgb(detail))
    mask=refine_garment_boundary(base,garment_mask(base,color,np.asarray(Image.open(depth).convert('L'))))
    changed=np.any(base!=fixed,axis=2)
    assert not np.any(changed[mask==0])
    # 图像观察后固定的验证区域，不参与软件掩膜或图像修改。
    regions={'left_foot':(750,4150,1500,4520),'right_foot':(2100,4150,2580,4560)}
    if key == 'b-node':
        regions.update(left_ankle_shadow=(1185,4070,1215,4090),
                       right_ankle_shadow=(2165,4078,2190,4090))
    skin={name:int(changed[y0:y1,x0:x1].sum()) for name,(x0,y0,x1,y1) in regions.items()}
    assert not any(skin.values()),skin
    previous=read_rgb(OUT/'assets'/f'{key}-result.png')
    previous_changed=np.any(previous!=base,axis=2)
    old_skin={name:int(previous_changed[y0:y1,x0:x1].sum()) for name,(x0,y0,x1,y1) in regions.items()}
    Image.fromarray(mask).save(OUT/'evidence'/f'{key}-fixed-mask.png')
    box=(500,3850,2700,4608)
    Image.fromarray(fixed).crop(box).save(OUT/'evidence'/f'{key}-fixed-ankles.png')
    Image.fromarray(base).crop(box).save(OUT/'evidence'/f'{key}-original-ankles.png')
    overlay=base.copy();overlay[mask>0]=(overlay[mask>0]*.45+np.array([0,180,70])*.55).astype('uint8')
    Image.fromarray(overlay).crop(box).save(OUT/'evidence'/f'{key}-fixed-boundary.png')
    results.append(dict(case=key,original=original,result=f'assets/{key}-fixed.png',enhancement=result,outside_mask_changed=0,skin_boxes=regions,skin_box_changed=skin,previous_skin_box_changed=old_skin,total_changed=int(changed.sum()),method='重新执行修复后的软件面料增强；仅使用专属细节一次；未重新调用生图模型'))
(OUT/'evidence/boundary-fix-audit.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=True))
