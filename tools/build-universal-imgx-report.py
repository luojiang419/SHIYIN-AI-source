"""将 imgx 原生 manifest、原图和逐张审阅整理为中文 HTML 论述报告。"""
import argparse
from datetime import datetime
import html
import json
from pathlib import Path
import shutil


def esc(value):
    return html.escape(str(value), quote=True)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case_dir')
    args = parser.parse_args()
    case = Path(args.case_dir).resolve()
    review = load(case/'review.json')
    items, manifests = [], []
    for manifest_path in sorted(case.glob('*/manifest.json')):
        manifest = load(manifest_path)
        spec = load(case/(manifest_path.parent.name+'.json'))
        if manifest['mode'] != 'image-to-image' or manifest['model'] != 'gemini-3-pro-image-preview':
            raise ValueError(f'非本轮指定图生图配置：{manifest_path}')
        if [str(Path(p).resolve()) for p in manifest['referenceImages']] != spec['references']:
            raise ValueError(f'参考图顺序不一致：{manifest_path}')
        manifests.append(manifest)
        for result in manifest['results']:
            for img in ([result] if result.get('status') == 'succeeded' and result.get('file') else []):
                file=Path(img['file'])
                relative=file.relative_to(case).as_posix()
                evidence=review['images'].get(relative,{'title':relative,'verdict':'未审阅','discussion':'没有人工审阅记录，不能认定合格。'})
                fabric_path=manifest_path.parent/'fabric-depth-audit.json'
                fabric=load(fabric_path) if fabric_path.exists() else None
                final=Path(fabric['result']['images'][0]).relative_to(case).as_posix() if fabric else relative
                items.append(dict(file=relative,final=final,fabric=fabric,manifest=manifest_path.relative_to(case).as_posix(),spec=spec,**evidence))
    def picture(src,title):
        return f'<button class="photo" data-image="{esc(src)}" data-caption="{esc(title)}"><img loading="lazy" src="{esc(src)}" alt="{esc(title)}"></button>'
    sources=[('模特身份与身体','D:/data/图片/选用/B/XSY_9373.JPG'),('完整裤装：后侧版型','D:/data/图片/服装参考 (2).jpg'),('腰头与面料细节','D:/data/图片/腰头细节.jpg'),('动作与朝向','C:/Users/jiang/Desktop/人物形象/动作.png'),('庄园、汽车与碎石路','C:/Users/jiang/Desktop/西部小镇/【西部小镇WildWestTown】场景/page-004_img-004.jpeg')]
    (case/'references').mkdir(exist_ok=True)
    reference_cards=[]
    for i,(title,path) in enumerate(sources,1):
        target=case/'references'/f'{i}{Path(path).suffix.lower()}'
        if not target.exists(): shutil.copy2(path,target)
        relative=target.relative_to(case).as_posix()
        reference_cards.append(f'<figure>{picture(relative,title)}<figcaption>{i:02} / {title}</figcaption></figure>')
    cards=[]
    for item in items:
        title=item['title']
        rows=''.join(f'<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>' for k,v in item.get('checks',{}).items())
        prompts=''.join(f'<pre>{esc(p)}</pre>' for p in item['spec']['prompts'])
        fabric_note=''
        if item['fabric']:
            steps=item['fabric']['result']['fabric_enhancement']
            fabric_note=f'<details><summary>共用面料后处理审计</summary><pre>{esc(json.dumps(steps,ensure_ascii=False,indent=2))}</pre><button data-image="{esc(item["file"])}" data-caption="{esc(title)} · imgx 原始图">查看增强前原图</button></details>'
        cards.append(f'''<article data-type="{esc(item.get('type','other'))}">{picture(item['final'],title)}<div class="cardbody"><p class="eyebrow">IMGX / GEMINI 3 PRO IMAGE / 4K</p><h3>{esc(title)}</h3><span class="verdict">{esc(item['verdict'])}</span><p>{esc(item['discussion'])}</p><table class="checks">{rows}</table>{fabric_note}<div class="links"><a href="{esc(item['final'])}" download>下载最终原尺寸</a><a href="{esc(item['file'])}" download>imgx 原始图</a><a href="{esc(item['manifest'])}">原生 manifest</a></div><details><summary>提示词与参考图顺序</summary><ol>{''.join('<li>'+esc(Path(p).name)+'</li>' for p in item['spec']['references'])}</ol>{prompts}</details></div></article>''')
    total=sum(m['totalJobs'] for m in manifests)
    succeeded=sum(m['succeeded'] for m in manifests)
    failed=sum(m['failed'] for m in manifests)
    verification=review.get('verification',{})
    records=''.join(f'<tr><td>{esc(m["startedAt"])}</td><td>{m["totalJobs"]}</td><td>{m["concurrency"]}</td><td>{m["succeeded"]} / {m["failed"]}</td><td>{esc(m["finishedAt"])}</td></tr>' for m in manifests)
    body=f'''
<header><nav><a href="#findings">核心结论</a><a href="#ownership">参考分工</a><a href="#pipeline">链路论述</a><a href="#gallery">样张复核</a><a href="#acceptance">验收与验证</a></nav><div class="hero"><div><p class="eyebrow">SHIYIN AI · REAL IMAGE VALIDATION</p><h1>面料要可信，<br>人物要属于现场。</h1><p class="lead">全能模式 · 标准产品图与 Lookbook<br>imgx 专项实测与生成链路论述报告</p><p class="muted">2026-09-20 / 任务 197 / 按用户指定重新验证</p></div><aside><span>本轮只使用 IMGX</span><p>{esc(review['headline'])}</p><small>模型：gemini-3-pro-image-preview<br>比例 2:3 · 请求分辨率 4K · 每提示词 1 张</small></aside></div></header>
<main><section id="findings"><div class="sectionhead"><span>01 / FINDINGS</span><h2>先给结论，再展示证据</h2></div><div class="stats"><div><b>{total}</b><span>imgx 生成任务</span></div><div><b>{succeeded} / {failed}</b><span>成功 / 失败</span></div><div><b>4K</b><span>统一请求分辨率</span></div><div><b>原生输出</b><span>未叠加应用面料增强</span></div></div>
<p>{esc(review['summary'])}</p><p class="callout">用户明确要求全部使用 imgx，认为此前 GPT Image 2 的面料表现不足。因此本轮重新开始，GPT Image 2 样张不进入最终候选。历史样张仍保留在上一案例目录，但不能与本轮混算通过率。</p><div class="columns"><div class="panel"><h3>标准产品图要解决的事</h3><p>在保留指定模特、服装版型、面料与细节的前提下复刻动作，并让人物自然处于指定场景。本轮同时保留单阶段对照和“两阶段动作底图＋局部换装”，用于判断商品参考是否干扰姿势。</p></div><div class="panel"><h3>Lookbook 要解决的事</h3><p>同样锁定身份与商品，但允许创意动作和机位。创意不能改变扣数、后袋、腰耳、面料尺度或裤型，也不能通过遮挡关键部位来回避保真检查。</p></div></div></section>
<section id="ownership"><div class="sectionhead"><span>02 / REFERENCE OWNERSHIP</span><h2>不是叠加五张图，而是分配五种权责</h2></div><div class="references">{''.join(reference_cards)}</div><div class="tablewrap"><table><thead><tr><th>输入</th><th>它决定什么</th><th>它不能覆盖什么</th></tr></thead><tbody><tr><td>模特</td><td>身体比例、默认身份、短发；未替换的背心和鞋</td><td>新裤子的颜色、版型与纹样；目标动作和场景</td></tr><tr><td>完整商品</td><td>高腰、宽直裤腿、裤长、后袋、结构线与固有色</td><td>模特身份、动作、原场景</td></tr><tr><td>局部细节</td><td>所属商品后腰的双扣、双腰耳、皮牌、育克、缝线与细斜纹</td><td>把背面部件贴到正面；把放大图纹理尺度复制到整条裤子</td></tr><tr><td>动作＋深度</td><td>头部转向、抱臂、关节、重心、交叉脚及遮挡</td><td>牛仔服、栅栏、原穿着者；旧衣轮廓覆盖新裤型</td></tr><tr><td>场景</td><td>建筑、汽车、地面、空间、光照与拍摄位置</td><td>人物身份；把商品任意染色或强制全画面锐利</td></tr></tbody></table></div><p>这组素材的商品图与局部细节都来自后侧，而动作图主要展示前侧。标准图看不到后腰时，应保持不可见，不能把皮牌和后袋移到正面假装还原。Lookbook 可选择后侧机位验证这些特征。当前没有独立的人脸替换参考，也没有正面商品参考，这两项不能由本次样张证明。</p></section>
<section id="pipeline"><div class="sectionhead"><span>03 / WHY THE PIPELINE MATTERS</span><h2>先隔离冲突，再谈细节与摄影</h2></div><div class="flow"><div><b>参考分工</b><small>角色、细节绑定、原尺寸输入</small></div><i>→</i><div><b>动作与场景底图</b><small>模特＋动作＋实际深度＋环境</small></div><i>→</i><div><b>商品局部编辑</b><small>仅替换指定商品，继承底图</small></div><i>→</i><div><b>逐项复核</b><small>结构、纹理、动作与光学层次</small></div></div>
<h3>多参考图的主要矛盾：每张图里都有不该迁移的东西</h3><p>模特图有原动作和棚拍光，裤装图有另一个人的身体及转身姿态，动作图又带着牛仔服和栅栏。原链路同时提出“保留底图”和“更换场景”，加剧了属性冲突。现在通过明确所有权，并在标准图中先解出人物、姿势和环境底图，再单独换商品，降低服装参考穿着者造成的转背与朝向污染。</p>
<h3>深度图是有效的辅助证据，但当前不是逐关节硬控制</h3><p>本轮复用同一动作原图已完成 quality 推理的人物深度文件，不伪造深度、不更换固定模型。imgx 将深度作为有明确角色说明的图像参考输入；这不同于接入逐关节约束求解器。深度能补充体积与遮挡，却不能单独保证视线、手指、头部转角及脚落点完全一致。因此必须检查成图，而不是看到深度调用成功就判定动作合格。</p>
<h3>“同一 SKU”约束固有色，“同一现场”决定它被如何照亮</h3><p>如果把商品照片的白平衡、亮度和阴影一并冻结，人物换进新场景后仍像棚拍贴纸。新的摄影规则保留固有色、材质、纹样和设计，同时根据真实站位重算天空光、地面反射、局部阴影及高光。动作底图阶段就决定这个光场，换装阶段继承，避免人物与环境各自一套照明。</p>
<h3>主体清楚与背景退焦可以同时成立</h3><p>脸与关键衣片处于主体焦平面，远处汽车、窗格、树木随着距离渐进变柔；不是用抠图蒙版给背景统一模糊。提示词中的焦段与光圈属于视觉意图，不是相机测量值。评估时检查头发边缘、透明鞋面、近地面与远景的连续变化，而不是只问“有没有虚化”。</p>
<h3>面料需要尺度与结构证据，不能用锐度代替还原</h3><p>微观斜纹、缝线、金属扣和版型属于不同层级。斜纹必须细密、连续并随曲面透视变化，不能变成粗绳、灯芯绒或锐化条带。双扣和腰耳的数量及相对位置属于结构问题，不会因为纹理更清楚就自动正确。本轮直接查看 imgx 原生输出，避免额外锐化或应用增强掩盖模型本身的材质表现。</p>
<p class="callout">并发执行的是独立样张：标准单阶段、动作底图、Lookbook 不同编排可以同时生成。标准商品编辑依赖已经完成并审阅的底图，必须顺序执行。并发不改变参考图顺序，也不能跳过这个依赖。</p></section>
<section id="gallery"><div class="sectionhead"><span>04 / IMAGE EVIDENCE</span><h2>逐张看：画面成立，不等于所有细节都成立</h2></div><p>点击图片可切换原尺寸查看，卡片附原生 manifest、参考图顺序与实际提示词。中间底图明确标注，不计作最终商品成图。所有评语是本次人工视觉复核，不是模型自评。</p><div class="filters"><button data-filter="all" aria-pressed="true">全部</button><button data-filter="standard" aria-pressed="false">标准产品图</button><button data-filter="lookbook" aria-pressed="false">Lookbook</button><button data-filter="anchor" aria-pressed="false">中间底图</button></div><div class="gallery">{''.join(cards)}</div></section>
<section id="acceptance"><div class="sectionhead"><span>05 / ACCEPTANCE & VERIFICATION</span><h2>报告结论由哪些证据支撑</h2></div><div class="tablewrap"><table><thead><tr><th>验收维度</th><th>当前结论</th></tr></thead><tbody>{''.join('<tr><td>'+esc(k)+'</td><td>'+esc(v)+'</td></tr>' for k,v in review['acceptance'].items())}</tbody></table></div>
<div class="columns"><div class="panel"><h3>工程回归</h3><p>五组 Python 回归：194 passed / 2 failed。失败项是独立 Lookbook 计数优先级和平台默认列表，与前序任务的既有失败相同。Python 编译与前端 JS 语法检查通过，素材坞在 1689 / 1000 / 800px 的布局检查通过。</p></div><div class="panel"><h3>界面实测</h3><p>浅色与深色弹窗均有两个选项；Escape 可关闭；两种风格切换并刷新后均保持选择。390px 窄屏弹窗无横向溢出。本轮 imgx 是提示词与素材的直接生成实验，不冒充应用完整 HTTP 链路回归。</p></div></div>
<p><b>分析服务边界：</b>前序应用实测的逐图分析服务返回 502 后按角色说明继续。本轮 imgx 直接使用保存的提示词、人工明确的朝向及后腰说明和原始图片，不依赖该分析服务；这不表示分析服务已经恢复，也不把人工证据称为自动识别。</p><p><b>适用范围：</b>同一组素材、少量样本、未固定随机种子。可以证明这些文件对应的行为与视觉问题，不能给出总体成功率、宣称最高质量或保证每一张商品完全还原。最终是否采用具体成图，应结合卡片里的保留意见。</p>
<div class="tablewrap"><table><thead><tr><th>开始时间（UTC）</th><th>任务数</th><th>组内并发</th><th>成功 / 失败</th><th>完成时间（UTC）</th></tr></thead><tbody>{records}</tbody></table></div>
<p>{esc(verification.get('cache',''))}</p><p>{esc(verification.get('git','分支 feat/universal-product-lookbook；未发布热更新或构建全量安装包。'))}</p><details><summary>复现与交付文件</summary><pre>python tools/prepare-universal-imgx-validation.py --case-dir 案例/全能双风格/imgx-20260920
&amp; tools/run-universal-imgx-job.ps1 -JobFile 案例/全能双风格/imgx-20260920/lookbook.json
python tools/build-universal-imgx-report.py 案例/全能双风格/imgx-20260920</pre><p>重新生图会调用已配置的真实服务。请复制任务规格到新目录以避免覆盖证据。HTML 使用同目录原图，移动或分享时携带整个案例目录。没有把密钥写入规格、报告或 manifest。</p><a href="review.json">逐张审阅记录</a> · <a href="validation-plan.json">本轮实验设计</a> · <a href="manifest.json">汇总 manifest</a></details></section></main>
<footer>真实文件与人工审阅 · 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')} · 用户指定 imgx 专项验证</footer>
<dialog id="viewer"><div class="viewerbar"><strong id="caption"></strong><button id="zoom">原尺寸 / 适应窗口</button><a id="download" download>下载</a><button id="close">关闭 ×</button></div><div class="viewport"><img id="large" alt=""></div></dialog>'''
    css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f2efe7;color:#27332b;font:16px/1.9 system-ui,"Microsoft YaHei",sans-serif}header{background:#193c30;color:#f8f4e8}nav{max-width:1400px;margin:auto;padding:20px 36px;display:flex;gap:28px;border-bottom:1px solid #ffffff25}nav a{color:#e3e9dd;text-decoration:none;font-size:13px;white-space:nowrap}.hero{max-width:1400px;margin:auto;padding:68px 36px 76px;display:grid;grid-template-columns:1.5fr 1fr;gap:70px;align-items:center}h1{font-size:clamp(36px,4.5vw,62px);line-height:1.3;letter-spacing:-1px;margin:18px 0}.lead{font-size:19px;color:#d4dfd0}.eyebrow{font-size:10px;letter-spacing:2px}.muted{font-size:12px;color:#b5cbb7}aside{padding:30px;background:#ffffff0b;border:1px solid #ffffff35}aside>span{font-size:11px;letter-spacing:2px;color:#dcc698}aside p{font-size:23px}aside small{color:#c4d2c0}main{max-width:1400px;margin:auto;padding:0 36px}section{padding:56px 0;border-bottom:1px solid #d1d9cc;scroll-margin-top:16px}.sectionhead>span{font-size:11px;color:#758772;letter-spacing:2px}h2{font-size:31px;line-height:1.5;margin:8px 0 28px}h3{font-size:20px;line-height:1.6;margin:24px 0 10px}p{max-width:1120px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin:30px 0}.stats div{border-left:2px solid #aabca3;padding-left:20px}.stats b{font-size:35px;font-weight:500;display:block}.stats span{font-size:12px;color:#6f7e6b}.columns{display:grid;grid-template-columns:1fr 1fr;gap:24px}.panel{padding:25px;background:#fffdf7;border:1px solid #d8dfd0}.panel h3{margin-top:0}.callout{padding:22px 26px;border-left:3px solid #ac864a;background:#e8e2d4}.references{display:grid;grid-template-columns:repeat(5,1fr);gap:15px}figure{margin:0}figcaption{font-size:12px;line-height:1.7;padding-top:10px}.photo{padding:0;border:0;background:#e5e4db;width:100%;display:block;cursor:zoom-in}.photo img{display:block;width:100%;height:530px;object-fit:contain}.references img{height:260px}.tablewrap{overflow:auto;margin:26px 0}table{border-collapse:collapse;width:100%;font-size:13px}.tablewrap table{min-width:680px}th{text-align:left;background:#e2e9db}th,td{padding:14px;border-bottom:1px solid #d6ddce;vertical-align:top}.flow{display:flex;gap:15px;align-items:center;padding:25px;background:#e1e9db}.flow>div{flex:1}.flow b,.flow small{display:block}.flow small{font-size:12px;color:#65795f}.flow i{font-style:normal}.filters{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}button{font:inherit}.filters button{border:1px solid #a8b99f;background:transparent;border-radius:25px;padding:8px 20px;cursor:pointer;font-size:13px}.filters [aria-pressed=true]{background:#284f39;color:#fff}.gallery{display:grid;grid-template-columns:repeat(2,1fr);gap:26px}.gallery article{background:#fffdf6;border:1px solid #d8dece;min-width:0}.gallery article[hidden]{display:none}.cardbody{padding:22px 28px}.cardbody h3{margin-top:6px}.cardbody p{font-size:14px}.verdict{font-size:12px;background:#eae0cb;color:#78572b;padding:6px 10px;display:inline-block}.checks th{width:25%;font-weight:400}.checks td,.checks th{padding:9px 10px;font-size:12px}.links{display:flex;gap:20px;margin:18px 0}a{color:#356440}.links a,details{font-size:12px}summary{cursor:pointer;font-size:13px;color:#466b43}pre{font:12px/1.8 monospace;white-space:pre-wrap;overflow-wrap:anywhere;padding:18px;background:#e9edde;max-height:460px;overflow:auto}footer{max-width:1400px;margin:auto;padding:30px 36px;font-size:12px;color:#75806f}dialog{width:96vw;height:95vh;max-width:none;border:0;padding:0;background:#17271c;color:white}dialog::backdrop{background:#000d}.viewerbar{display:flex;gap:12px;align-items:center;padding:12px 18px}.viewerbar strong{flex:1;font-size:13px}.viewerbar button,.viewerbar a{font-size:12px;padding:6px 12px;border:0;background:#35513b;color:white;cursor:pointer}.viewport{height:calc(100% - 64px);overflow:auto;display:flex}.viewport img{display:block;max-width:100%;max-height:100%;object-fit:contain;margin:auto}.viewport img.full{max-width:none;max-height:none}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #b68c4b;outline-offset:3px}@media(max-width:960px){.hero{grid-template-columns:1fr;gap:25px}.references{grid-template-columns:repeat(3,1fr)}.flow{flex-wrap:wrap}.flow>div{min-width:38%}.flow i{display:none}}@media(max-width:600px){nav{padding:16px 20px;gap:18px;overflow:auto}.hero{padding:36px 20px}.hero aside p{font-size:20px}main{padding:0 20px}h2{font-size:25px}.stats{grid-template-columns:1fr 1fr}.stats b{font-size:29px}.columns,.gallery{grid-template-columns:1fr}.references{grid-template-columns:1fr 1fr}.references img{height:220px}.photo img{height:auto;max-height:800px}.cardbody{padding:20px}section{padding:38px 0}.viewerbar{flex-wrap:wrap}.viewerbar strong{width:100%;flex:auto}.viewport{height:calc(100% - 108px)}}@media print{nav,.filters,dialog{display:none}.gallery article[hidden]{display:block}.photo img{height:260px}.gallery article,.panel{break-inside:avoid}body,header{background:white;color:#203928}.hero aside,.hero .lead,.hero .muted{color:#203928}}'''
    js='''const viewer=document.querySelector('#viewer'),large=document.querySelector('#large');let opener;document.querySelectorAll('[data-image]').forEach(b=>b.onclick=()=>{opener=b;large.src=b.dataset.image;large.alt=b.dataset.caption;document.querySelector('#caption').textContent=b.dataset.caption;document.querySelector('#download').href=b.dataset.image;large.classList.remove('full');viewer.showModal()});document.querySelector('#close').onclick=()=>viewer.close();document.querySelector('#zoom').onclick=()=>large.classList.toggle('full');viewer.addEventListener('close',()=>opener?.focus());document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{document.querySelectorAll('.gallery article').forEach(c=>c.hidden=b.dataset.filter!=='all'&&c.dataset.type!==b.dataset.filter);document.querySelectorAll('[data-filter]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)))});'''
    css += (Path(__file__).with_name('training-report-theme.css').read_text(encoding='utf-8') + '''
body{overflow-wrap:anywhere;transition:background .2s,color .2s}header nav{border-bottom-color:var(--line)}header nav a{color:var(--ink)}.hero{grid-template-columns:1.5fr 1fr}.hero .lead,.hero .muted{color:var(--muted)}.hero aside{background:var(--card);border-color:var(--line);color:var(--ink)}.hero aside>span,.sectionhead>span{color:var(--green)}.hero aside small,.stats span,.flow small,figcaption,footer{color:var(--muted)}section{border-bottom-color:var(--line)}.stats div{border-left-color:var(--soft)}.panel,.gallery article{background:var(--card);border-color:var(--line)}.callout{border-left-color:var(--green);background:var(--panel);color:var(--ink)}.photo{background:var(--panel)}table{background:var(--card)}th{background:var(--soft);color:var(--ink)}th,td{border-bottom-color:var(--line)}.flow{background:var(--panel)}.filters button{border-color:var(--line);background:var(--control);color:var(--ink)}.filters [aria-pressed=true]{background:var(--accent);color:var(--contrast)}.verdict{background:var(--soft);color:var(--ink)}a,summary{color:var(--green)}pre{background:var(--panel);color:var(--ink);border:1px solid var(--line)}.theme-toggle{margin-left:auto;border:1px solid var(--line);border-radius:7px;padding:7px 12px;background:var(--control);color:var(--ink);white-space:nowrap}.checks{table-layout:fixed}td,th,li,small{overflow-wrap:anywhere}.columns>*{min-width:0}.cardbody{overflow-wrap:anywhere}h1{letter-spacing:0}@media(max-width:600px){.theme-toggle{margin-left:0}}''')
    js += '''const themeToggle=document.getElementById('themeToggle'),themeMedia=matchMedia('(prefers-color-scheme:dark)');let savedTheme;try{savedTheme=localStorage.getItem('shiyin-training-theme')}catch{}let manualTheme=savedTheme==='dark'||savedTheme==='light';function setTheme(value){document.documentElement.dataset.theme=value;themeToggle.textContent=value==='dark'?'浅色模式':'暗色模式';themeToggle.setAttribute('aria-pressed',String(value==='dark'))}setTheme(manualTheme?savedTheme:(themeMedia.matches?'dark':'light'));themeToggle.onclick=()=>{const next=document.documentElement.dataset.theme==='dark'?'light':'dark';manualTheme=true;setTheme(next);try{localStorage.setItem('shiyin-training-theme',next)}catch{}};themeMedia.addEventListener?.('change',event=>{if(!manualTheme)setTheme(event.matches?'dark':'light')});'''
    body=body.replace('<b>原生输出</b><span>未叠加应用面料增强</span>','<b>复用现有链路</b><span>编译器＋深度＋面料后处理</span>')
    body=body.replace('本轮直接查看 imgx 原生输出，避免额外锐化或应用增强掩盖模型本身的材质表现。','本轮同时保留 imgx 原始图与应用现有面料还原结果。后处理直接调用 main.apply_fabric_enhancement 和 canvas_core.fabric_enhancement.enhance_fabric_image，不另造纹理算法。')
    body=body.replace('工程回归</h3><p>五组','工程回归</h3><p>最新复用相关测试 136 项通过。此前五组')
    body=body.replace('</nav>','<button class="theme-toggle" id="themeToggle" type="button" aria-label="切换明暗主题" aria-pressed="false">切换主题</button></nav>',1)
    body=body.replace('此前五组 Python 回归：194 passed / 2 failed。','最新电商回归：138 passed / 2 failed。')
    metrics=[]
    for folder in ['reuse-standard','reuse-lookbook','integrated-standard']:
        metric_path=case/folder/'pixel-depth-verification.json'
        if metric_path.exists():
            m=load(metric_path)
            metrics.append(f'<tr><td>{esc(folder)}</td><td>{m["changed_pixels"]:,}</td><td>{m["mask_pixels"]:,}</td><td>{m["outside_mask_changed"]}</td></tr>')
    body=body.replace('<p><b>分析服务边界：</b>', '<div class="tablewrap"><table><tr><th>输出自身深度＋既有面料算法</th><th>实际变化像素</th><th>掩膜像素</th><th>掩膜外变化</th></tr>'+''.join(metrics)+'</table></div><p>像素检查只验证处理范围；自动掩膜本身是否精确对应商品，仍需视觉检查。</p><p><b>分析服务边界：</b>')
    insertion='''<section id="reuse"><div class="sectionhead"><span>04A / REUSE, NOT REIMPLEMENTATION</span><h2>真正复用的四个环节</h2></div><div class="tablewrap"><table><tr><th>现有能力</th><th>本次适配</th></tr><tr><td>一键复刻 / 批量换款编译器</td><td>标准单款商品编辑调用 pose-replicate.v3.5.base-wardrobe.depth.zh-CN，保留成熟材质、款式、深度分工。多商品或数字图号等不兼容场景保留原分支。</td></tr><tr><td>人物深度组件</td><td>对实际生成底图重新推理，避免用原动作图深度冒充底图对应关系；面料还原使用最终输出自身的深度。</td></tr><tr><td>逐款绑定细节</td><td>按 detail_target_id 选择对应面料；绑定细节存在时，不再对同一商品重复叠加整衣纹理。</td></tr><tr><td>共用面料还原与回退</td><td>使用原有采样、自动衣片掩膜和高频迁移算法；保留原图、掩膜像素数及处理状态。深度不可用时回退保守定位，后处理失败不丢失图片。</td></tr></table></div><p>仅靠把一键复刻的大模板整段搬过来，仍会发生动作偏离；复用需要保留它的输入契约。本轮把成熟的基础换装放到已经确定动作与场景的底图之后，而不是要求一次请求同时解决所有冲突。</p><p>以下为 420×420 原像素局部裁切，无重采样、无增强对比图的额外锐化。参考与结果未配准，不能作为同尺度误差测量。对照说明原算法能恢复可见织纹，同时也暴露保守掩膜对暗部的漏选，不能把“applied”当成全裤验收。</p><div class="references">'''
    for file,title in [('reference.png','原始面料参考'),('reuse-lookbook-original.png','Lookbook：imgx 原图'),('reuse-lookbook-enhanced.png','Lookbook：既有面料还原'),('reuse-standard-enhanced.png','标准旧候选：暗部漏选边界')]:
        if (case/'texture-inspection'/file).exists():
            insertion+=f'<figure>{picture("texture-inspection/"+file,title)}<figcaption>{title}</figcaption></figure>'
    insertion+='</div></section>'
    body=body.replace('<section id="acceptance">',insertion+'<section id="acceptance">')
    body = (body
        .replace('SHIYIN AI', 'SHIYING AI')
        .replace('SHIYIN-AI', 'SHIYING-AI'))
    theme_boot="<script>try{const theme=localStorage.getItem('shiyin-training-theme');if(theme==='dark'||theme==='light')document.documentElement.dataset.theme=theme}catch{}</script>"
    document=f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>全能模式 imgx 实测论述报告</title><style>{css}</style>{theme_boot}</head><body>{body}<script>{js}</script></body></html>'
    (case/'实测论述报告.html').write_text(document,encoding='utf-8')
    (case/'manifest.json').write_text(json.dumps({'provider':'shiying','transport':'imgx','model':'gemini-3-pro-image-preview','mode':'image-to-image','succeeded':succeeded,'failed':failed,'totalJobs':total,'manifests':[p.relative_to(case).as_posix() for p in sorted(case.glob('*/manifest.json'))],'images':items},ensure_ascii=False,indent=2),encoding='utf-8')
    print(case/'实测论述报告.html')


if __name__=='__main__':
    main()
