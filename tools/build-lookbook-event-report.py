"""将第二轮实际产物、可见机位与用户否决意见编入修订报告，无API调用。"""
import base64
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '输出/Lookbook两阶段方案-20260910'
CASE = OUT / 'revision-2'


def load(name):
    return json.loads((CASE/name).read_text(encoding='utf-8'))


def e(value):
    return html.escape(str(value),quote=True)


def image(path):
    return 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode('ascii')


def details(label,data):
    text = data if isinstance(data,str) else json.dumps(data,ensure_ascii=False,indent=2)
    return f'<details><summary>{e(label)}</summary><pre>{e(text)}</pre></details>'


def main():
    result=load('results.json')
    story=load('story-response.json')['parsed']
    plan=load('prompts-response.json')['parsed']
    review=load('visual-review.json')
    assert result['status']=='succeeded'
    assert story['ad_brief'] in load('prompts-request.json')['message']
    assert len(plan['shots'])==6
    reference=image(OUT/'reference.png')
    preview=image(CASE/'contact-sheet.png')
    failed=image(OUT/'contact-sheet.png')
    case=f'''<div class="note"><b>首轮案例已被用户否决，本报告撤回“部分达标”评价。</b>网络成功、JSON完整和写了角度数字都不能替代故事、换机位与时尚摄影验收。下方保留失败图，并展示重新设计后的真实API产物。</div>
    <div class="grid"><div><h3>首轮 / 不合格</h3><figure class="figure"><img src="{failed}" alt="用户否决的首轮四格，同一墙面前查看相机循环"><figcaption>首轮循环：看相机、交接、拍照、再看相机。没有足够的事件推动和画面变化，首尾构图近似，近景变化被误当作机位多样性。</figcaption></figure></div><div><h3>原始输入 / 未改变</h3><figure class="figure reference"><img src="{reference}" alt="原始人物参考，与首轮使用同一张图"><figcaption>仍使用同一张人物参考、同一套API配置，广告需求仍为空。改变的是系统创作方法、参考约束及交付镜头数量；这不是只改变一个变量的A/B实验。</figcaption></figure></div></div>
    <h3 style="margin-top:35px">第二轮：{e(story['title'])}</h3><p>{e(story['intent'])}</p><div class="story">{e(story['story'])}</div>
    <p class="caption">以上来自第一阶段API真实返回。故事未由助手手工代写；API根据空需求、自主候选事件比较生成。实验新增了创作与摄影方法约束。</p>'''
    case+='<h3 style="margin-top:30px">API第一轮：为什么选择这个事件</h3><table><thead><tr><th>候选</th><th>画面潜力与选择理由</th><th>结果</th></tr></thead><tbody>'
    for candidate in story.get('candidate_events',[]):
        case+=f'<tr><td>{e(candidate["idea"])}</td><td>{e(candidate.get("visual_potential",""))}<br>{e(candidate["reason"])}</td><td>{"选中" if candidate["selected"] else "未选"}</td></tr>'
    case+='</tbody></table><h3>事件不是几个动作词，而是状态改变</h3><div class="grid three">'
    for key,label in [('goal','人物目标'),('trigger','触发'),('obstacle_or_discovery','受阻 / 发现'),('decision','选择'),('consequence','后果'),('ending_differs_from_start','终点与起点不同')]:
        case+=f'<div class="card"><h3>{label}</h3><p>{e(story["event_contract"][key])}</p></div>'
    case+='</div><h3 style="margin-top:30px">实际生成结果：先看画面，再看文字</h3>'
    case+=f'<figure class="figure sheet" style="max-width:1000px"><img src="{preview}" alt="第二轮事件驱动六格真实API生成结果"><figcaption>2列×3行，依次左上→右上→中左→中右→左下→右下。一次图片API生成的完整原图，未修图；每格请求3:2横幅。点击可放大。原始返回尺寸：{e(result["stages"]["image"]["dimensions"])}。</figcaption></figure>'
    case+='<h3>每格实际画面复查</h3><table><thead><tr><th>镜头</th><th>API规划的事件 / 摄影师位置</th><th>实际观察（助手目视）</th></tr></thead><tbody>'
    for shot,observed in zip(plan['shots'],review['shots']):
        case+=f'<tr><td>{e(shot["index"])}</td><td>{e(shot["beat"])}<br><b>位置：</b>{e(shot["camera_position"])}<br><b>应见几何：</b>{e(shot["visible_geometry"])}</td><td>{e(observed["observation"])}<br><b>{e(observed["verdict"])}</b></td></tr>'
    case+='</tbody></table>'
    case+=f'<div class="note"><b>本轮判断：</b>{e(review["summary"])}<br><b>仍存在：</b>{e(review["limitations"])}<br>这些是助手的目视判断，不是用户已认可，也不是摄影机角度测量。</div>'
    case+='<h3>将方法写进产品，而不是只给案例加长提示词</h3><div class="grid"><div class="card"><h3>第一阶段新增约束</h3><p>reference_facts必须同时说明must_preserve和not_locked；人物参考不自动升级为场景或构图锁。event_contract必须有目标、触发、选择、后果；每个beat写visible_state_change。对比候选事件后选一项，避免默认重复参考图原有动作。</p></div><div class="card"><h3>第二阶段新增约束</h3><p>camera_position、visible_geometry、different_from_previous共同描述真实摄影位置。每张卡检查人物哪面可见、前景谁挡谁、背景哪面出现、地平线与透视。若全部仍是同面墙同侧人物，应重做摄影方案，不能只改焦距数字。</p></div></div>'
    case+='<h3 style="margin-top:30px">真实调用与回填文本</h3><table><thead><tr><th>阶段</th><th>平台 / 模型</th><th>客户端耗时</th></tr></thead><tbody>'
    for key,label in [('story','故事与候选'),('prompts','独立提示词会话'),('image','六格图生成')]:
        provider=result['image_provider'] if key=='image' else result['vision_provider']
        model=result['image_model'] if key=='image' else result['vision_model']
        case+=f'<tr><td>{label}</td><td>{e(provider)} / {e(model)}</td><td>{result["stages"][key]["elapsed_s"]:.3f} 秒</td></tr>'
    case+='</tbody></table><p>文本方案生成后先人工检查事件和机位可执行性，再用保存的第二阶段提示词发起图片API。人工检查没有更改API返回文字，两个解析阶段仍是独立会话。第二阶段曾失败一次（HTTPException，旧脚本仅记录类型，无法确认具体状态码与失败耗时），保留故事后重试成功；因此本轮实际有3次LLM调用尝试，表中仅列成功阶段耗时。额外人工检查时间不计入表内；没有采用第三次LLM作质量评分。</p>'
    case+=details('第一阶段：可回填的完整广告需求',story['ad_brief'])
    for name,label in [('story-request.json','API 1 完整请求'),('story-response.json','API 1 原始返回'),('prompts-request.json','API 2 完整独立会话请求'),('prompts-response.json','API 2 原始返回与6格提示词'),('image-request.json','实际图片API请求'),('results.json','完整运行元数据'),('visual-review.json','逐格人工复查记录')]:
        case+=details(label,load(name))
    template=(ROOT/'tools/lookbook-two-stage-report.html').read_text(encoding='utf-8')
    template=template.replace('先让照片有故事，<br>再让镜头有<em>观点。</em>','让事件改变人物，<br>让摄影师<em>真正移动。</em>')
    template=template.replace('方案评审稿','修订稿 · 首轮已否决')
    template=template.replace('真实案例：一张参考图，自动展开一组故事','重做案例：事件、空间与真实观察方向')
    template=template.replace('本次为一个案例：两次独立 LLM 会话 + 一次图片 API 返回的四格预览，不是四次独立成片测试。图片为真实生成结果，报告中的单格局部只是同一张结果的展示窗口。','第二轮重新执行两次独立LLM会话和一次六格图片生成。首轮失败样本保留作复盘；本轮没有用更多格数本身作为质量证据，每个镜头仍须检查可见的事件与机位差异。')
    template=template.replace('先让照片有故事','让事件改变人物')
    template=template.replace('提交四格预览生成','提交六格预览生成')
    template=template.replace('由隔离实验脚本执行，不能视为节点功能已经上线。','由隔离实验脚本执行，不能视为节点功能已经上线。首轮方案过度锁定背景与小动作，已据用户否决意见重新设计。')
    template=template.replace('“两次”指默认成功路径中的两次故事/提示词 LLM 请求','首轮失败证明：拆成两轮本身不能产生时尚感。需要同时建立事件合同、参考角色所有权和可见机位几何。“两次”指默认成功路径中的两次故事/提示词 LLM 请求')
    template=template.replace('四格预览与独立逐张生成存在一致性差异','联合预览与独立逐张生成存在一致性差异')
    template=template.replace('<div><span class="tag">修订稿 · 首轮已否决</span>', '<div><a href="#case" class="tag" style="text-decoration:none">直接查看重做结果 ↓</a><span class="tag">修订稿 · 首轮已否决</span>')
    content=template.replace('@@CASE@@',case).replace('@@BRIEF_JSON@@',json.dumps(story['ad_brief'],ensure_ascii=False).replace('<','\\u003c'))
    assert '@@CASE@@' not in content
    target=OUT/'Lookbook事件驱动重设计与实测报告.html'
    target.write_text(content,encoding='utf-8')
    print(json.dumps({'report':str(target),'bytes':target.stat().st_size,'review':review['summary']},ensure_ascii=True))


if __name__=='__main__':
    main()
