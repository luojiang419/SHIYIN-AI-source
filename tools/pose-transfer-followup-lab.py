"""任务222：保留认可基线，复测稳定性及去裤脚轮廓的关节深度代理。"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import cv2
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = ROOT / '.codex-artifacts/pose-transfer-222/depth-fit-exact-three-20260928'
OUT = BASE / 'followup'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def ab_report():
    """两版固定对照：A=07、B=08；原候选页独立存档。"""
    template = ROOT / 'tools/pose-transfer-ab-compare.html'
    (BASE/'compare.html').write_text(template.read_text(encoding='utf-8'), encoding='utf-8')


def report(main):
    rows = [
        ('A','动作参考','pose.jpg','仅提供动作。'),
        ('B','产品主视角','source.jpg','原产品版型、颜色、口袋与拼缝依据。'),
        ('B侧','产品侧视角','source_view_1.jpg','核对侧缝、后袋和膝下外扩。'),
        ('01','原流程','baseline.png','动作接近，但深色牛仔及棕靴明显受 A 影响。'),
        ('02','分离提示·原样','separated.png','上一轮候选；浅蓝、斜缝和凉鞋。'),
        ('03','仅深度·原样','depth_only.png','上一轮候选；保留用于与复测、新方案比较。'),
        ('04','生成式中间深度','body_depth.png','上一轮候选；中间深度仍有旧衣外形。'),
        ('05','脚口比例提示','flare_ratio.png','上一轮候选；对比例提示的响应有限。'),
        ('06','分离提示·复测','followup/separated-repeat.png','同输入同提示词复测；颜色明显变深，存在波动。'),
        ('07','仅深度·复测','followup/depth-only-repeat.png','同输入同提示词复测；颜色、鞋更接近原样。'),
        ('08','关节深度·标准','followup/proxy-regular.png','移除下肢旧衣外缘；裤脚较舒展，前脚朝向更偏正面。'),
        ('09','关节深度·较细','followup/proxy-slim.png','保留交叉腿，但膝部位置、前脚与上衣边缘有变化。'),
    ]
    def infer(path):
        im = Image.open(path).convert('RGB').resize((800,1000), Image.Resampling.LANCZOS)
        result = main.render_dwpose_image(im)
        if result.people != 1:
            raise ValueError('关节评估要求检测到单人：'+str(path))
        return result.keypoints[0], result.scores[0]
    target, target_scores = infer(BASE/'pose.jpg')
    entries = []
    for identifier, title, file, note in rows:
        item = {'id':identifier, 'title':title, 'file':file, 'note':note}
        if identifier.isdigit():
            points, scores = infer(BASE/file)
            valid = (target_scores[:18]>.25)&(scores[:18]>.25)
            distances = np.linalg.norm((points[:18]-target[:18])/np.array([800,1000]), axis=1)
            item['joints'] = int(valid.sum())
            item['pose_error'] = round(float(distances[valid].mean()), 5) if valid.any() else None
        entries.append(item)
    save_json(OUT/'comparison.json', {'user_selection':None, 'candidates':entries,
        'limitation':'关节偏差不是服装质量评分；新条件是局部下肢代理，并非真实人体重建。'})
    old_page = BASE/'compare-first-five.html'
    if not old_page.exists():
        old_page.write_bytes((BASE/'compare.html').read_bytes())
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>动作迁移 · 最终候选对比</title><style>
*{box-sizing:border-box}body{margin:0;background:#f4f5f7;color:#182431;font:15px/1.6 system-ui,"Microsoft YaHei",sans-serif}header,main{max-width:1500px;margin:auto;padding:24px}header{padding-bottom:6px}h1{margin:0;font-size:30px}p{margin:8px 0}.muted{color:#5b6875}.notice{background:#e6f1ee;border-left:4px solid #247b63;padding:10px 16px}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0}button,select,a.btn{font:inherit;background:white;border:1px solid #c8d1d9;border-radius:7px;padding:8px 13px;color:inherit;cursor:pointer}button.active{background:#173f56;color:white}.pair{display:grid;grid-template-columns:1fr 1fr;gap:18px}.pane{background:white;padding:16px;border-radius:12px;min-width:0}select{width:100%}canvas{display:block;width:100%;height:min(68vh,760px);background:#edf0f3;margin-top:12px}.note{min-height:56px;font-size:14px}.links{display:flex;justify-content:space-between;gap:8px}a{color:#206086}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.card{background:white;border-radius:10px;padding:12px}.card img{width:100%;height:250px;object-fit:contain;background:#edf0f3}.card h3{font-size:16px;margin:8px 0}.card p{font-size:13px;min-height:45px}.card button{font-size:13px;padding:6px 10px}.badge{font-size:13px;color:#66717c}.source{display:flex;gap:16px}.source img{height:220px;max-width:100%;object-fit:contain}.source>div{flex:1;background:white;padding:12px;border-radius:10px}details{margin:24px 0}summary{cursor:pointer;font-weight:600}h2{margin-top:28px} @media(max-width:800px){header,main{padding:14px}.cards{grid-template-columns:repeat(2,1fr)}canvas{height:48vh}.pane{padding:8px}.pair{gap:8px}h1{font-size:23px}}
</style><header><h1>动作迁移 · 最终候选对比</h1><p class="muted">保留上一轮全部结果，新增 4 张真实生成。点选任意两张，比较动作、版型和局部细节。</p><p class="notice">已记录你的反馈：当前效果已不错。01–05 为上一轮，06–09 为本轮；最终采用哪一版由你决定，尚未替换正式页面。</p></header><main>
<div class="toolbar" id="regions"><button data-region="all" class="active">整图</button><button data-region="waist">腰头 / 口袋</button><button data-region="seam">大腿 / 斜缝</button><button data-region="hem">裤脚 / 鞋</button><button id="swap">交换左右</button></div>
<p class="muted">局部按画面位置放大，未做物理尺寸标定；点击“原尺寸”可查看完整文件。</p>
<div class="pair"><section class="pane"><select aria-label="左侧候选" id="left"></select><canvas id="leftCanvas" width="900" height="1000"></canvas><p class="note" id="leftNote"></p><div class="links"><a id="leftOriginal" target="_blank">原尺寸 ↗</a><span class="badge" id="leftMetric"></span></div></section><section class="pane"><select aria-label="右侧候选" id="right"></select><canvas id="rightCanvas" width="900" height="1000"></canvas><p class="note" id="rightNote"></p><div class="links"><a id="rightOriginal" target="_blank">原尺寸 ↗</a><span class="badge" id="rightMetric"></span></div></section></div>
<h2>全部候选</h2><p class="muted">建议优先比较 03 / 07（原方案复测）与 08（新深度）。关节偏差只衡量动作，不用于自动决定商品效果。</p><div class="cards" id="cards"></div>
<details><summary>查看三张原始参考</summary><div class="source" id="sources"></div></details>
<details><summary>查看本轮深度条件及实验记录</summary><p>新深度仅替换下肢裤腿和鞋的轮廓，上半身沿用原深度。两种粗细是实验参数，不是真实人体测量。</p><div class="source"><div><img src="depth.png"><p>原始深度</p></div><div><img src="followup/proxy-1.00.png"><p>下肢代理·标准</p></div><div><img src="followup/proxy-0.80.png"><p>下肢代理·较细</p></div></div><p><a href="followup/comparison.json">关节评估记录</a> · <a href="accepted-baseline-manifest.json">原候选保留清单</a> · <a href="compare-first-five.html">上一轮对照页存档</a></p></details>
<p class="muted">两轮同条件样本仅用于观察波动，不构成稳定成功率证明。最终选择后再接入页面。</p></main>
<script>const entries=__ENTRIES__;let region='all';const boxes={all:[0,0,1,1],waist:[.28,.06,.47,.28],seam:[.34,.25,.40,.34],hem:[.28,.64,.50,.36]};const images=new Map();
function imageFor(file){if(!images.has(file))images.set(file,new Promise((resolve,reject)=>{const i=new Image();i.onload=()=>resolve(i);i.onerror=reject;i.src=file}));return images.get(file)}
async function paint(side){const selected=document.getElementById(side).value,item=entries.find(x=>x.id===selected);document.getElementById(side+'Note').textContent=item.note;document.getElementById(side+'Original').href=item.file;document.getElementById(side+'Metric').textContent=item.pose_error==null?'参考原图':`关节偏差 ${item.pose_error.toFixed(5)} · ${item.joints}点`;const canvas=document.getElementById(side+'Canvas'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,900,1000);try{const image=await imageFor(item.file);if(document.getElementById(side).value!==selected)return;const [x,y,w,h]=boxes[region],sw=image.width*w,sh=image.height*h,s=Math.min(900/sw,1000/sh);ctx.drawImage(image,image.width*x,image.height*y,sw,sh,(900-sw*s)/2,(1000-sh*s)/2,sw*s,sh*s)}catch{ctx.fillText('图片载入失败，请打开原尺寸文件',30,50)}}
for(const side of ['left','right']){const select=document.getElementById(side);for(const item of entries)select.add(new Option(item.id+' · '+item.title,item.id));select.value=side==='left'?'03':'08';select.onchange=()=>paint(side);paint(side)}
for(const button of document.querySelectorAll('[data-region]'))button.onclick=()=>{region=button.dataset.region;document.querySelectorAll('[data-region]').forEach(b=>b.classList.toggle('active',b===button));paint('left');paint('right')};document.getElementById('swap').onclick=()=>{const l=document.getElementById('left'),r=document.getElementById('right');[l.value,r.value]=[r.value,l.value];paint('left');paint('right')};
for(const item of entries.filter(x=>/^\\d+$/.test(x.id))){const card=document.createElement('article');card.className='card';card.innerHTML=`<a href="${item.file}" target="_blank"><img loading="lazy" src="${item.file}" alt="${item.id} ${item.title}"></a><h3>${item.id} · ${item.title}</h3><p>${item.note}</p>`;for(const side of ['left','right']){const b=document.createElement('button');b.textContent=side==='left'?'放到左侧':'放到右侧';b.onclick=()=>{document.getElementById(side).value=item.id;paint(side);document.getElementById('regions').scrollIntoView({behavior:'smooth'})};card.append(b)}document.getElementById('cards').append(card)}
for(const item of entries.slice(0,3)){const el=document.createElement('div');el.innerHTML=`<a href="${item.file}" target="_blank"><img loading="lazy" src="${item.file}" alt="${item.title}"></a><p>${item.title}</p>`;document.getElementById('sources').append(el)}
</script></html>'''
    (BASE/'compare-all-candidates.html').write_text(html.replace('__ENTRIES__', json.dumps(entries,ensure_ascii=False)), encoding='utf-8')
    ab_report()
    print(json.dumps(entries,ensure_ascii=False), flush=True)


def proxy_depth(main, scale):
    """只替换下肢服装外缘；半径为实验代理参数，并非实测人体尺寸。"""
    im = Image.open(BASE / 'pose.jpg').convert('RGB').resize((800, 1000))
    result = main.render_dwpose_image(im)
    if result.people != 1:
        raise ValueError('动作图必须检测到单人')
    xy, confidence = result.keypoints[0], result.scores[0]
    if np.any(confidence[[8, 9, 10, 11, 12, 13, 18, 21]] < .25):
        raise ValueError('下肢关键点不足，不能构造代理')
    original = np.asarray(Image.open(BASE / 'depth.png').convert('L').resize((800, 1000)), dtype=float)
    yy, xx = np.mgrid[:1000, :800]
    rendered = np.zeros_like(original)

    def capsule(a, b, ra, rb, za, zb):
        delta = b - a
        t = np.clip(((xx-a[0])*delta[0] + (yy-a[1])*delta[1]) / max(float(delta @ delta), 1), 0, 1)
        distance = np.hypot(xx-a[0]-t*delta[0], yy-a[1]-t*delta[1])
        radius = (ra + t*(rb-ra)) * scale
        cross = np.sqrt(np.clip(1-(distance / np.maximum(radius, 1))**2, 0, 1))
        values = za + t*(zb-za) - 28*(1-cross)
        # 较大深度值覆盖较小值，固定前后关系。
        np.maximum(rendered, np.where(distance <= radius, values, 0), out=rendered)

    limbs = []
    for hip, knee, ankle, toe in [(8, 9, 10, 21), (11, 12, 13, 18)]:
        h, k, a, f = xy[[hip, knee, ankle, toe]]
        z = float(original[round(k[1]), round(k[0])])
        calf = k*.6+a*.4
        capsule(h, k, 51, 27, z, z)
        capsule(k, calf, 27, 30, z, z)
        capsule(calf, a, 30, 15, z, z+6)
        capsule(a, f, 15, 12, z+6, z+9)
        limbs.append({'indices':[hip,knee,ankle,toe], 'xy':xy[[hip,knee,ankle,toe]].tolist(), 'depth':z})
    # 上部保留原动作手/躯干深度；在膝上完成下肢代理替换。
    transition = np.clip((yy-320)/130, 0, 1)
    def signed_distance(mask):
        return cv2.distanceTransform(mask.astype('uint8'), cv2.DIST_L2, 5) - cv2.distanceTransform((~mask).astype('uint8'), cv2.DIST_L2, 5)
    old_mask, new_mask = original > 8, rendered > 0
    contour = signed_distance(old_mask)*(1-transition) + signed_distance(new_mask)*transition
    # 在两个前景之间插值轮廓，避免把旧裤腿半透明地留在代理旁边。
    old_values = np.where(old_mask, original, rendered)
    new_values = np.where(new_mask, rendered, original)
    composite = np.where(contour > 0, old_values*(1-transition) + new_values*transition, 0)
    path = OUT / f'proxy-{scale:.2f}.png'
    Image.fromarray(np.clip(composite, 0, 255).astype('uint8')).save(path)
    save_json(path.with_suffix('.json'), {'kind':'case_specific_lower_limb_proxy_not_true_body_reconstruction',
              'scale':scale, 'pose_sha256':digest(BASE/'pose.jpg'), 'depth_sha256':digest(BASE/'depth.png'),
              'limbs':limbs, 'transition_y':[320,450], 'image_size':[800,1000]})
    return path


async def generate(main, name, template, control=None):
    destination = OUT / f'{name}.png'
    if destination.exists():
        raise ValueError(f'拒绝覆盖已保存候选：{destination}')
    previous = json.loads((BASE/f'{template}-request.json').read_text(encoding='utf-8'))
    prompt = previous['prompt']
    references, audit_refs = [], []
    for item in previous['references']:
        path = Path(item['path'])
        if digest(path) != item['sha256']:
            raise ValueError('基线输入发生变化：'+str(path))
        if control and item['role'] == 'control_map':
            path = control
        mime = 'image/png' if path.suffix == '.png' else 'image/jpeg'
        references.append({'role':item['role'], 'name':path.name,
            'garment_design_owner':item['role']=='source',
            'url':f'data:{mime};base64,'+base64.b64encode(path.read_bytes()).decode()})
        audit_refs.append({'role':item['role'],'path':str(path),'sha256':digest(path)})
    if control:
        prompt += (' Image 2 uses smooth tapered lower-limb proxy geometry at the original joint positions. '
                   'It intentionally has no trouser hem or boot shape. Treat it as the body inside the garment, '
                   'and independently drape the exact B product from Images 1 and 3 over it. '
                   'Do not make B trousers as thin as these internal proxy legs. Preserve B original flared silhouette.')
    audit = {'round':name,'template':template,'prompt':prompt,'model':previous['model'],
             'size':previous['size'],'references':audit_refs}
    save_json(OUT/f'{name}-request.json', audit)
    print('Generating '+name, flush=True)
    start = time.monotonic()
    try:
        response, _ = await main.generate_gemini_provider_image(prompt, audit['size'], audit['model'],
            reference_images=references, provider=main.get_api_provider_exact('shiying'))
        if response.get('type') != 'b64':
            raise ValueError('返回内容不是内嵌图片')
        destination.write_bytes(base64.b64decode(response['value']))
        with Image.open(destination) as image:
            dimensions = image.size
        save_json(OUT/f'{name}-result.json', {'status':'succeeded','elapsed_s':time.monotonic()-start,
                  'path':str(destination),'sha256':digest(destination),'dimensions':dimensions})
        print('Saved '+name, flush=True)
    except Exception as error:
        save_json(OUT/f'{name}-result.json', {'status':'failed','error_type':type(error).__name__})
        print('Failed '+name+': '+type(error).__name__, flush=True)
        raise


async def run(mode):
    if mode == 'ab':
        ab_report()
        return
    import main
    OUT.mkdir(parents=True, exist_ok=True)
    if mode == 'report':
        report(main)
        return
    if mode == 'prepare':
        for scale in [1., .8]:
            print(proxy_depth(main, scale))
        return
    if mode == 'repeat':
        jobs = [generate(main,'separated-repeat','separated'), generate(main,'depth-only-repeat','depth_only')]
    else:
        paths = [OUT/f'proxy-{scale:.2f}.png' for scale in [1., .8]]
        if not all(path.exists() for path in paths):
            raise ValueError('先 prepare 并检查代理深度图')
        jobs = [generate(main,'proxy-regular','depth_only',paths[0]), generate(main,'proxy-slim','depth_only',paths[1])]
    outcomes = await asyncio.gather(*jobs, return_exceptions=True)
    if any(isinstance(result, Exception) for result in outcomes):
        raise RuntimeError('部分实验失败，已保存成功结果和失败类型')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare','repeat','proxy','report','ab'])
    asyncio.run(run(parser.parse_args().mode))
