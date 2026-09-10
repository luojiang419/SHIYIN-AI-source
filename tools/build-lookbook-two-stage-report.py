"""将已保存的真实 API 证据嵌入单文件 HTML；不发起任何 API 请求。"""
from __future__ import annotations

import base64
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '输出/Lookbook两阶段方案-20260910'


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def esc(value):
    return html.escape(str(value), quote=True)


def block(value):
    return '<pre>' + esc(json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value) + '</pre>'


def data_image(name):
    return 'data:image/png;base64,' + base64.b64encode((OUT / name).read_bytes()).decode('ascii')


def details(title, value):
    return '<details><summary>' + esc(title) + '</summary>' + block(value) + '</details>'


def main():
    report = read('results.json')
    story = read('story-response.json')['parsed']
    plan = read('prompts-response.json')['parsed']
    req1, req2 = read('story-request.json'), read('prompts-request.json')
    image_request = read('image-request.json')
    assert report['status'] == 'succeeded'
    assert req1['messages'] == [] and req2['messages'] == []
    assert story['ad_brief'] in req2['message']
    assert req1['images'] == req2['images'] == ['reference.png']
    assert plan['story_used'] == story['ad_brief']
    assert len(plan['shots']) == 4
    image_url, ref_url = data_image('contact-sheet.png'), data_image('reference.png')
    total = sum(item['elapsed_s'] for item in report['stages'].values())
    parts = [f'''<div class="meta"><div><strong>2 + 1</strong><span>LLM 请求 + 图片请求（逻辑调用）</span></div><div><strong>{total:.1f}s</strong><span>三个客户端阶段累计耗时</span></div><div><strong>1 → 4</strong><span>一张参考 → 四格联合预览</span></div><div><strong>896 × 1200</strong><span>实际返回整图像素</span></div></div>
    <div class="grid"><figure class="figure reference"><img src="{ref_url}" alt="真实输入参考：两位人物在蓝绿色百叶门前查看复古相机"><figcaption>原始参考：{esc(report['source_file'])}。来自最近一次 Lookbook 任务。点击可放大；输入的广告需求为空，预览数量与比例由测试脚本设定，不是故事提示。</figcaption></figure><div class="card"><span class="tag">真实输入条件</span><h3>只有一张人物图，没有故事文字</h3><p>同图包含两位人物、白色系带镂空衣物、黑色上衣与牛仔裤、银黑色相机、百叶门、墙面和栏杆。模型必须综合这些线索，而不是只描述人物外观。</p><p><b>解析平台：</b>{esc(report['vision_provider'])}<br><b>解析模型：</b>{esc(report['vision_model'])}<br><b>生图平台：</b>{esc(report['image_provider'])}<br><b>生图模型：</b>{esc(report['image_model'])}</p><p>两次请求均重新附原图、角色标签，messages 为空，web_search=false。配置取自安装版已有设置，凭据仅在进程内存中使用。当前实验没有中途人工改写 API 返回后再生图。</p><p class="caption">本案例四格联合预览采用技能的 contact-sheet-first 方法；没有为本报告另外生成四张独立图片。</p></div></div>''']
    parts.append(f'<h3 style="margin-top:32px">第一阶段返回：{esc(story["title"])}</h3><p>{esc(story["intent"])}</p><div class="story">{esc(story["ad_brief"])}</div><p class="caption">以上为 API 返回原文，保留了“回看 / 确认成片”等问题用语；展示不是人工优化后的版本。</p>')
    parts.append('<table><thead><tr><th>情节</th><th>真实返回的事件</th><th>前后因果 / 时尚表达</th></tr></thead><tbody>')
    for beat in story['beats']:
        parts.append(f'<tr><td>{esc(beat["index"])}</td><td>{esc(beat["event"])}</td><td>{esc(beat["cause_from_previous"])}<br>{esc(beat["detail_or_fashion_value"])}</td></tr>')
    parts.append('</tbody></table><h3>第二阶段返回：机位与镜头规划</h3><p>完整故事交接比对通过：第二次请求包含第一轮 ad_brief 原文，返回 story_used 与它逐字一致。不过，“原文一致”只证明交接没有丢文本，不能证明全部动作已经正确执行。</p><table><thead><tr><th>镜头</th><th>规划机位 / 景别</th><th>动作与构图</th></tr></thead><tbody>')
    for shot in plan['shots']:
        parts.append(f'<tr><td>{esc(shot["index"])}</td><td>{esc(shot["azimuth_deg"])}° · {esc(shot["shot_size"])}<br>{esc(shot["height"])}<br>{esc(shot["lens"])}</td><td>{esc(shot["beat"])}<br>{esc(shot["composition"])}</td></tr>')
    parts.append(f'</tbody></table><p class="caption">35° / 70° / 115° / 165° 是模型写下的规划值；不是对实际生成图片测得的机位角度。</p><figure class="figure sheet"><img src="{image_url}" alt="真实API生成四格：共同查看相机、手部交接特写、越肩拍摄、再次共同查看"><figcaption>一次真实图片 API 返回的完整四格图，保持原始结果，不修图、不替换失败区域。点击放大。整体实际比例约0.747，接近请求3:4；四格等分局部约448×600。</figcaption></figure>')
    labels = [('0% 0%','01 · 开场','双人查看相机，身份与环境保持较好，但构图与输入照片接近。'),('100% 0%','02 · 细节','相机、手部和服装局部得到展示；景别差异清楚。'),('0% 100%','03 · 拍摄','明显越肩视角，人物正在拍另一人，事件关系最清楚。'),('100% 100%','04 · 收束','回到共同低头的画面；首尾仍近似同机位，未兑现规划的165°背肩机位。')]
    parts.append('<div class="scene-grid">')
    for position,title,description in labels:
        parts.append(f'<div><div class="crop" role="img" aria-label="{esc(title)}对应原图四分之一局部" style="background-position:{position}"></div><b>{esc(title)}</b><p>{esc(description)}</p></div>')
    parts.append('</div><p class="caption">四个局部来自同一完整原图的 CSS 展示窗口，并非独立 API 成片。</p>')
    parts.append('''<h3 style="margin-top:32px">视觉与语义复查：链路成功，质量仅部分达标</h3>
    <table><thead><tr><th>检查项</th><th>观察结果</th><th>判定</th></tr></thead><tbody>
    <tr><td>自动扩展故事</td><td>从同一张图发展为共同查看 → 交接 → 拍摄 → 再次查看，形成具体事件，而非四个孤立姿势。</td><td class="check">有故事结构</td></tr>
    <tr><td>景别与拍摄视点</td><td>第二格明显手部近景，第三格明显越肩环境镜头；首尾两格仍为相近正面双人构图。</td><td class="warn">部分达标；多机位未完全兑现</td></tr>
    <tr><td>故事物理可行性</td><td>第一轮原始 story 写“屏幕里的斑驳光影”，ad_brief 要求即时回看/确认成片。源图没有证明存在可回放屏幕；第二轮将相机定义为胶片机并禁用屏幕，却保留了刚曝光即可确认影像的情节。</td><td class="warn">未通过；原文冻结不能放大事实错误</td></tr>
    <tr><td>人物与服装</td><td>两人发色、肤色、黑上衣与蓝牛仔整体延续。白衣原图有明显腰部开口与系带，模型概括成“连衣裙”；第三格背部结构与开口延续不足，存在服装结构漂移风险。</td><td class="warn">大体一致，关键结构仍需更强约束</td></tr>
    <tr><td>道具与动作</td><td>交接和持机拍摄可读，相机外形大体连续；第二格交接瞬间不能仅凭单帧确定谁释放、谁握持，第四格持机关系不够明确。</td><td class="warn">可读但不精确</td></tr>
    <tr><td>场景、光线与质感</td><td>百叶门、浅墙、栏杆与日光贯穿四格，肤色和织物质感较自然。提示词同时写固定光源和“camera-right rear in all four panels”，坐标语义矛盾，未做光线几何测量。</td><td class="warn">视觉较统一；世界坐标描述需修正</td></tr>
    <tr><td>顶级时尚构图</td><td>第三格有前景遮挡与层次，第二格有触感细节；首尾仍偏安全生活方式构图，尚不足以宣称全组达到顶级广告标准。</td><td class="warn">有改善方向，未完全达标</td></tr>
    </tbody></table>
    <div class="note"><b>实测反推的方案修订：</b>故事进入“冻结”前，必须校验道具能力与可见服装结构，未知能力采用保守动作。本案应把“回看成片”改为“共同检查相机/注意现实衣料光影 → 交接 → 拍摄 → 放下相机交换目光”，不虚构胶片机即时回放。此修订是人工分析建议，未另行调用 API 或用它替换已展示原始结果。</div>
    <div class="grid"><div class="card"><h3>把语义检查放进第一阶段</h3><p>要求返回“可见事实 / 创作扩展 / 不确定能力”三组信息，并在同轮输出前检查。若第二阶段发现能力冲突，应返回明确 validation_error，允许修订故事并重新显示版本；不要暗改故事还标记为完全继承。结构检查可本地执行，复杂语义无法保证仅靠规则检测。</p></div><div class="card"><h3>把机位要求落实到画面</h3><p>将165°写成可观察的“从金发人物肩后看到深发人物侧面，金发背部占前景，百叶门移至另一侧背景”等几何结果。用位置、朝向和遮挡一起约束，复查时仍以实图为准。光源使用相对百叶门/墙面的世界位置，而非四镜头都写相机右侧。</p></div></div>''')
    parts.append('<h3 style="margin-top:32px">调用记录与完整证据</h3><table><thead><tr><th>阶段</th><th>客户端耗时</th><th>结果</th></tr></thead><tbody>')
    for key, title in [('story','API 1 · 故事'),('prompts','API 2 · 提示词'),('image','图片 API · 四格预览')]:
        item=report['stages'][key]
        desc = f'{item["response_chars"]} 字符返回' if 'response_chars' in item else '1 张图片 / 4 个画面'
        parts.append(f'<tr><td>{title}</td><td>{item["elapsed_s"]:.3f} 秒</td><td>{esc(desc)} · 成功</td></tr>')
    parts.append('</tbody></table><p class="caption">耗时为脚本每阶段开始至返回/保存的客户端观测，不是模型纯推理时间。逻辑调用数不代表代理内部绝无重试。LLM retry_524=0；未获取可核对账单，不提供虚构 token 用量或金额。</p>')
    parts.append(details('查看 API 1 · 完整请求（图片以本报告文件名标识）',req1))
    parts.append(details('查看 API 1 · 原始响应全文',read('story-response.json')['text']))
    parts.append(details('查看 API 2 · 完整独立会话请求',req2))
    parts.append(details('查看 API 2 · 原始响应全文 / 四张独立提示词',read('prompts-response.json')['text']))
    parts.append(details('查看实际发给图片 API 的完整最终提示词与参数',image_request))
    parts.append(details('查看耗时、模型、输入哈希与案例元数据',report))
    parts.append(f'<p class="caption">输出图片 SHA-256：<code>{hashlib.sha256((OUT / "contact-sheet.png").read_bytes()).hexdigest()}</code></p>')
    template = (ROOT/'tools/lookbook-two-stage-report.html').read_text(encoding='utf-8')
    result = template.replace('@@CASE@@',''.join(parts)).replace('@@BRIEF_JSON@@',json.dumps(story['ad_brief'],ensure_ascii=False).replace('<','\\u003c'))
    assert '@@CASE@@' not in result and '@@BRIEF_JSON@@' not in result
    target=OUT/'Lookbook两阶段故事设计与实测报告.html'
    target.write_text(result,encoding='utf-8')
    print(json.dumps({'report':str(target),'bytes':target.stat().st_size,'handoff_exact':True,'api_status':report['status'],'visual_acceptance':'partial'},ensure_ascii=True))


if __name__=='__main__':
    main()
