"""任务222：PA-321动作与P605深蓝牛仔的独立A/B复验。"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('followup', ROOT/'tools/pose-transfer-followup-lab.py')
LAB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAB)
LAB.BASE = ROOT/'.codex-artifacts/pose-transfer-222/pa321-p605-20260928'
LAB.OUT = LAB.BASE/'results'
SOURCES = {
    'pose': Path('//192.168.0.188/^0^ Lookbook Store/PA 裤子 Pants/301-400/PA-321/PA-321-41.jpg'),
    'source': Path('//192.168.0.188/摄影/100拍摄/人台图/LC78/LC7876670/LC7876670-P605/XSY_2796.jpg'),
    'source_view_1': Path('//192.168.0.188/摄影/100拍摄/人台图/LC78/LC7876670/LC7876670-P605/XSY_2771.jpg'),
}
PROMPT = (
    'Create one realistic fashion product photo. Image 1 is the FRONT THREE-QUARTER view and Image 3 is the SIDE view '
    'of the SAME dark blue B jeans. They exclusively own the product and outfit: dark indigo washed denim, original '
    'waistband and rise, silver waist button, curved front pockets and coin pocket, ochre topstitching, rear patch pocket '
    'with original shape, diagonal thigh panel seams, fitted thighs and knees with broad flared floor-length hems. '
    'Keep the exact actual B construction, color, wash and material from these photographs, plus B white crop top and '
    'blue open-toe low-heel sandals. Do not transplant back pockets onto the front or duplicate side seams. '
    'Image 2 is registered depth of a DIFFERENT person and provides ONLY the target pose, camera direction and crop. '
    'Recreate its SIDE-ON stance facing screen-right, torso and pelvis orientation, asymmetric knee bend, staggered feet, '
    'arm positions and hand position near the upper torso. Read the new joint positions and overlap from this depth. '
    'Do not use the standing front-facing pose from B product references. Do not reuse a front-view crossed-leg pose. '
    'Keep the original depth crop with the head outside the frame, and keep both complete feet in frame. '
    'The depth is body geometry, NOT the garment boundary. Retain B full-length flared trousers around these joints '
    'even though the pose subject has bare lower legs. Cover legs with B denim to the correct original full length; '
    'do not create shorts, a skirt, exposed calves or tight leggings. Let original B flare extend outside the depth legs. '
    'Do not copy the pose subject dress, lace, handbag, jewelry or high heels. Keep B plain studio background and lighting. '
    'Only change pose and physically necessary draping/occlusion; keep B product design and fine construction intact. '
    'Output a single photograph without diagrams, labels or extra views.'
)


def report(main):
    from PIL import Image
    def infer(path):
        result = main.render_dwpose_image(Image.open(path).convert('RGB').resize((800,1000),Image.Resampling.LANCZOS))
        if result.people != 1:
            raise ValueError('关节评估要求检测到单人')
        return result.keypoints[0],result.scores[0]
    target,confidence = infer(LAB.BASE/'pose.jpg')
    rows=[]
    for name in ['A-original-depth','B-new-depth']:
        path=LAB.OUT/(name+'.png')
        points,scores=infer(path)
        valid=(confidence[:18]>.25)&(scores[:18]>.25)
        error=np.linalg.norm((points[:18]-target[:18])/np.array([800,1000]),axis=1)
        rows.append({'name':name,'visible_joints':int(valid.sum()),
                     'mean':float(error[valid].mean()) if valid.any() else None,'sha256':LAB.digest(path)})
    LAB.save_json(LAB.BASE/'pose-metrics.json',rows)
    html=(ROOT/'tools/pose-transfer-ab-compare.html').read_text(encoding='utf-8')
    for old,new in [
        ('动作迁移 · A / B 两版对比','PA-321 新动作 · A / B 两版对比'),
        ('只看这两版：A 与 B','新动作 PA-321：A / B 实测'),
        ('两张为此前真实成图，本次没有重新生成或修图。','两张均为本轮新素材真实生成，产品为 LC7876670-P605 深蓝牛仔。'),
        ('followup/depth-only-repeat.png','results/A-original-depth.png'),
        ('followup/proxy-regular.png','results/B-new-depth.png'),
        (' · 原编号 07',''),(' · 原编号 08',''),
        ('前脚更朝画面左侧，动作更接近参考；裤脚相对收一些。','保留深蓝裤、斜缝、后袋和凉鞋；双手在身前，但构图、身体朝向和腿位仍有偏移。'),
        ('裤脚看起来更舒展；前脚更朝正面，腿部姿态略有变化。','保留深蓝产品和屈膝趋势；一只手变为下垂，未准确复现参考手位。'),
        ('整体效果确实接近，主要差别在脚尖方向、裤脚展开和腿部位置。','本轮重点比较侧身屈膝动作，以及深蓝产品的裤脚、拼缝和口袋。'),
        ('<p class="archive">其他实验已移出本页，需要回查时可打开 <a href="compare-all-candidates.html">全部实验存档</a>。</p>',
         '<details><summary>查看本轮三张输入与深度</summary><p>动作参考原图为385×550，按其可见姿势测试；不补造脸部。</p><div style="display:flex;gap:16px;flex-wrap:wrap">'+
         ''.join(f'<a href="{file}" target="_blank"><img src="{file}" style="height:260px;max-width:100%;object-fit:contain"><p>{label}</p></a>' for file,label in [('pose.jpg','图1 · 动作'),('source_view_1.jpg','图2 · 产品侧面'),('source.jpg','图3 · 产品正侧'),('depth.png','原深度'),('results/proxy-1.00.png','新下肢深度')])+
         '</div></details><p class="archive"><a href="pose-metrics.json">关节记录</a> · <a href="../depth-fit-exact-three-20260928/compare.html">上一组三图的A/B对照</a></p>'),
    ]:
        if old not in html:
            raise ValueError('对照模板已变化，缺少：'+old)
        html=html.replace(old,new)
    (LAB.BASE/'compare.html').write_text(html,encoding='utf-8')
    print(json.dumps(rows),flush=True)


async def run(mode):
    import main
    from PIL import Image
    LAB.OUT.mkdir(parents=True, exist_ok=True)
    if mode == 'report':
        report(main)
        return
    if mode == 'prepare':
        for role, source in SOURCES.items():
            dest = LAB.BASE/(role+'.jpg')
            if dest.exists() and LAB.digest(dest) != LAB.digest(source):
                raise ValueError('已保存输入与新输入不同，拒绝覆盖')
            if not dest.exists():
                dest.write_bytes(source.read_bytes())
        depth = LAB.BASE/'depth.png'
        if not depth.exists():
            content, tier = await main.render_universal_person_depth(str(LAB.BASE/'pose.jpg'))
            depth.write_bytes(content)
            LAB.save_json(LAB.BASE/'depth-audit.json', {'tier':tier,'source_sha256':LAB.digest(LAB.BASE/'pose.jpg')})
        im = Image.open(LAB.BASE/'pose.jpg').convert('RGB').resize((800,1000))
        keypoints = main.render_dwpose_image(im)
        LAB.save_json(LAB.BASE/'pose-keypoints.json', {'people':keypoints.people,'xy':keypoints.keypoints.tolist(),
                       'scores':keypoints.scores.tolist(),'original_size':Image.open(LAB.BASE/'pose.jpg').size})
        print('Keypoints saved', flush=True)
        LAB.proxy_depth(main, 1.)
        paths = [(LAB.BASE/'source.jpg','source'),(depth,'control_map'),(LAB.BASE/'source_view_1.jpg','source_view_1')]
        LAB.save_json(LAB.BASE/'case-request.json', {'model':'gemini-3-pro-image-preview','size':'3000x4000',
                      'prompt':PROMPT,'references':[{'role':r,'path':str(p),'sha256':LAB.digest(p)} for p,r in paths]})
        print('Prepared '+str(LAB.BASE), flush=True)
    elif mode == 'generate':
        results = await asyncio.gather(LAB.generate(main,'A-original-depth','case'),
            LAB.generate(main,'B-new-depth','case',LAB.OUT/'proxy-1.00.png'),return_exceptions=True)
        if any(isinstance(item,Exception) for item in results):
            raise RuntimeError('存在生成失败，见结果记录')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['prepare','generate','report'])
    asyncio.run(run(parser.parse_args().mode))
