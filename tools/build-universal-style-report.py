"""从真实实测文件生成本地可放大的验证报告，不把接口成功等同于视觉合格。"""
from pathlib import Path
import argparse
import html
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case_dir')
    args = parser.parse_args()
    case = Path(args.case_dir).resolve()
    notes = {
        'round-1-lookbook': '未通过：动作过于贴近参考，后腰银扣错误出现在正面。',
        'round-2-standard_product': '未通过严格动作验收：人物、场景、裤色与织纹成立，但头朝向反转、弯膝不足。',
        'round-2-lookbook': '后侧展示成立；后袋与织纹可见，皮牌被手臂遮挡，腰头相对位置仍需核对。',
        'round-3-standard_product': '弯膝改善，但头仍看向镜头，部分后腰扣误到正面。',
        'round-3-lookbook': '后腰可见度改善；皮牌、扣位与双腰耳仍未严格对应，不能视为 SKU 级验收通过。',
        'round-4-standard_product': '失败样张：出现长发、转背和场景漂移；没有选为推荐样张。',
        'round-4-lookbook': '人物与后侧展示成立；腰头部件位置和皮牌文字仍有偏差。',
        'round-5-standard_product': '未通过：底图已保留头部朝右与弯膝，但通用合成提示词在第二阶段又将人物转成背面。已据此改为专用局部编辑提示词，并让底图原尺寸无损传输。',
        'round-6-standard_product': '修正后的正式两阶段链路；最终视觉结论见验收记录，不能仅凭接口成功认定保真通过。',
        'mature-baseline': '批量复刻完整模板对照：仍有头部反向、动作简化，不能单靠模板替换解决。',
        'two-stage-anchor': '两阶段对照的动作底图：头朝右、肩髋倾斜、弯膝和交叉脚明显改善。此图是中间产物。',
        'two-stage-product': '两阶段对照的商品局部编辑：保留动作与场景；面料及不可见正面结构仍需按证据核对。',
    }
    cards = []
    for prefix, note in notes.items():
        files = sorted(case.glob(prefix + '-result-*')) if prefix.startswith('round-') else [p for p in case.glob(prefix + '.*') if p.suffix.lower() in {'.jpg','.png'}]
        for file in files:
            task_file=case/(prefix+'-task.json')
            metadata=''
            if task_file.is_file():
                task=json.loads(task_file.read_text(encoding='utf-8'))
                metadata=f"接口状态：{task.get('status')} · 人物深度：{(task.get('pose_depth') or {}).get('status','—')} · 两阶段：{(task.get('pose_anchor') or {}).get('status','—')}"
            cards.append(f'<article><button class="photo" onclick="openImage(this)"><img loading="lazy" src="{html.escape(file.name)}" alt="{html.escape(prefix)}"></button><h2>{html.escape(prefix)}</h2><small>{html.escape(metadata)}</small><p>{html.escape(note)}</p><a href="{html.escape(file.name)}" download>下载原尺寸</a></article>')
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全能双风格实测报告</title><style>
body{margin:0;background:#eeeae2;color:#252722;font:15px/1.8 system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:38px 24px}h1{font-size:32px;line-height:1.3}header{max-width:920px;margin-bottom:32px}header p{color:#55594e}.tag{color:#7b5436;letter-spacing:2px;font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:22px}article{background:#fffcf7;border:1px solid #dcd5c8;border-radius:16px;padding:15px}h2{font-size:15px;overflow-wrap:anywhere}small{color:#737769}.photo{border:0;padding:0;background:transparent;width:100%;cursor:zoom-in}.photo img{width:100%;height:500px;object-fit:contain;background:#e5e3dc}a{color:#65552e}dialog{width:94vw;height:92vh;padding:0;border:0;background:#181a17;color:white}dialog::backdrop{background:#000c}dialog nav{position:sticky;top:0;background:#181a17;padding:10px;display:flex;gap:15px;align-items:center;z-index:2}dialog button{padding:8px 15px;border:0;border-radius:6px;cursor:pointer}dialog .view{overflow:auto;height:calc(100% - 65px)}dialog img{display:block;max-width:100%;max-height:100%;margin:auto}dialog img.full{max-width:none;max-height:none}
</style><main><header><div class="tag">REFERENCE OWNERSHIP / REAL GENERATION TESTS</div><h1>全能模式 · 标准产品图与 Lookbook</h1><p>同一组用户素材的真实生成对照。标准产品图先锁定模特身份、动作与场景，再局部换装；Lookbook 锁定产品与身份，在摄影和动作上创作。点击样张可切换原尺寸检查织纹、扣位与皮牌。</p><p><b>验收边界：</b>裤子和腰头参考为后侧视角，动作参考主要展示前侧。不能把后侧部件贴到正面充当“还原”，也不能用缺失的正面证据保证完整结构正确。失败样张如实保留。逐图分析上游在测试时返回 502，实际生成使用类型约束、原图与人工补充证据。</p></header><section class="grid">'''+''.join(cards)+'''</section></main><dialog id="viewer"><nav><button onclick="viewer.close()">关闭</button><button onclick="large.classList.toggle('full')">适合窗口 / 原尺寸</button><span id="caption"></span></nav><div class="view"><img id="large"></div></dialog><script>function openImage(button){const image=button.querySelector('img');large.src=image.src;large.alt=image.alt;large.className='';caption.textContent=image.alt;viewer.showModal()}</script></html>'''
    (case/'实测报告.html').write_text(document,encoding='utf-8')
    print(case/'实测报告.html')


if __name__=='__main__':
    main()
