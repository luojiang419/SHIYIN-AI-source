"""一次真实两阶段 Lookbook 实验；只读安装版配置，不修改产品流程。"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '输出' / 'Lookbook两阶段方案-20260910'
INSTALLED = Path('D:/Program Files/SHIYIN AI/data')
sys.path.insert(0, str(ROOT))

STORY_SYSTEM = '''你是高端时尚广告的故事创意总监。此会话只完成综合看图与短故事策划，不输出生图提示词。
输入图片是视觉事实来源，用户文字为空也必须主动从图片发展具体、有因果、可拍摄的连续微故事。
逐图区分身份、服装/商品、道具、场景；综合图片之间关系。保留所有人物身份与现有衣着、可见产品结构。
仅人物图时以其姿态、目光、衣着或已有互动为延展起点；有商品/道具时让它参与事件，不凭空虚构品牌和性能。
将可见事实与创作扩展分开。避免编造私人身份、关系与人格；故事人物关系只能明确作为虚构设定。
故事有目标、触发、动作、反应、结果，4张能呈现，不强行加入大戏剧和无关人物地点。
必须写明不得全部同机位，围绕同一行动轴设计多机位，相邻主体镜头机位方位变化至少30度（不是画面倾斜30度或只裁切放大），保持180度轴线连续；细节插入镜头可不直接比较主体方位角，但说明空间联系。
构图达到顶级时尚编辑摄影意图：不对称层次、负空间、前景遮挡、具有目的的视角，至少一幅可独立作为广告主视觉。
适当特写展现实际衣料、穿着或道具细节，并让细节与动作有因果联系。用户数量、比例、衣着和场景约束优先。
仅输出严格JSON：{"reference_facts":[{"id":"R1","roles":[],"visible_facts":[],"must_preserve":[]}],"creative_extensions":[],"title":"","intent":"","story":"中文150-280字连续故事","beats":[{"index":1,"event":"","cause_from_previous":"","detail_or_fashion_value":""}],"camera_intent":"","continuity_locks":[],"ad_brief":"可直接回填广告需求的完整中文文本，包含标题、故事、立意、摄影要求，不要JSON或生图长提示词"}。'''

PROMPT_SYSTEM = '''你是高端时尚摄影执行导演和提示词作者。这是独立第二阶段会话。
第一阶段故事已确定；忠实执行提供的完整广告需求，不重写故事主旨，不把连续事件替换成四个摆拍。
再次观察全部原始图片以锁定身份、衣着、道具、地点。输出恰好4张按时间连续的镜头设计；最终仅生成一张2行2列的四格联合预览，每个格子3:4，整体3:4。四格顺序左上、右上、左下、右下。
相邻主体镜头应在行动轴同侧改变真实机位至少30度，不能仅改变焦距或让画面倾斜。使用镜头方位角0至180度与机位高度描述；细节插入无需强行满足主体方位差但必须匹配动作、手和服装状态。
至少一幅带环境的主视觉、一幅服装/商品/道具动作特写。明确同一人物拿相机的手、相机朝向、背带、彼此视线和动作状态的连续变化。
源图中的物品如果是胶片相机不要虚构数码回放屏；品牌不确定则不添加logo。镜头不同但同一物理光源不随相机旋转。
摄影是有层次的真实时尚影像，自然肤质，奶油白与浅青色环境，服装保真，避免塑料皮肤与四幅同景别。
仅输出严格JSON：{"title":"","story_used":"完整复述收到的广告需求原文，不缩写","continuity_bible":{"identity":"","wardrobe":"","location":"","light":"","props":"","axis":""},"shots":[{"index":1,"beat":"","shot_size":"","azimuth_deg":20,"height":"","lens":"","composition":"","continuity_in":"","continuity_out":"","prompt":"该格完整英文生图提示词"}],"contact_sheet_prompt":"可直接发给图片API的完整英文提示词，包含共享身份与连续性锁、四格各自事件/机位/细节、2x2布局及每格3:4，禁止文字标题/标签/外框。不得只是引用上面的字段。"}。'''


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


async def run(app, providers, report):
    route = app.configured_ecommerce_vision_route()
    if not route:
        raise RuntimeError('no_configured_vision_route')
    image_provider = next(p for p in providers if p['id'] == 'shiying')
    model = 'gemini-3-pro-image-preview'
    if model not in image_provider.get('image_models', []):
        raise RuntimeError('image_model_not_configured')
    source = INSTALLED / 'media/generated/SHIYIN-001150-20260909.png'
    shutil.copy2(source, OUT / 'reference.png')
    reference = 'data:image/png;base64,' + base64.b64encode(source.read_bytes()).decode('ascii')
    report.update(vision_provider=route['provider_id'], vision_model=route['model'],
                  image_provider='shiying', image_model=model,
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  input_brief='', source_task='ecommerce_f33ca39199894008bb6ea4d302ab4acb',
                  source_file=source.name, layout='2x2', panels=4, panel_ratio='3:4',
                  method='两次独立多模态 LLM 请求，一次四格图片生成；无单阶段对照；非生产链路验收')
    save('results.json', report)
    for stage, system in [('story', STORY_SYSTEM), ('prompts', PROMPT_SYSTEM)]:
        existing = OUT / f'{stage}-response.json'
        if existing.exists():
            data = json.loads(existing.read_text(encoding='utf-8'))['parsed']
        else:
            message = ('广告需求：（空）。综合唯一输入图中的全部人物、服装、相机与环境线索，策划连续4张时尚故事。保持源图衣着，采用真实环境光，四格预览，每格3:4。' if stage == 'story' else
                       '已完成的第一阶段广告需求（冻结原文）：\n' + story['ad_brief'] + '\n第一阶段完整结构：\n' + json.dumps(story, ensure_ascii=False))
            save(f'{stage}-request.json', {'system_prompt':system,'message':message,'images':['reference.png'], 'messages':[], 'web_search':False, 'provider':route['provider_id'],'model':route['model']})
            started = time.perf_counter()
            result = await asyncio.wait_for(app.canvas_llm(app.CanvasLLMRequest(
                system_prompt=system, message=message, provider=route['provider_id'], model=route['model'],
                images=[reference], image_labels=['R1：人物参考；观察图中全部人物及其衣着、道具和可见环境'], web_search=False, retry_524=0,
            )), timeout=480)
            raw = str(result.get('text') or '')
            data = app._parse_lookbook_json(raw)
            if not data:
                raise RuntimeError(f'{stage}_invalid_json')
            report['stages'][stage] = {'status':'succeeded','elapsed_s':round(time.perf_counter()-started,3),'response_chars':len(raw)}
            save(f'{stage}-response.json', {'text':raw,'parsed':data})
            save('results.json', report)
        if stage == 'story':
            story = data
            if not isinstance(story.get('ad_brief'),str) or not story['ad_brief'].strip():
                raise RuntimeError('empty_ad_brief')
        else:
            prompts = data
    if len(prompts.get('shots',[])) != 4 or not prompts.get('contact_sheet_prompt'):
        raise RuntimeError('invalid_shots')
    report['story_handoff_exact'] = prompts.get('story_used') == story['ad_brief']
    if not (OUT / 'contact-sheet.png').exists():
        started = time.perf_counter()
        save('image-request.json', {'provider':'shiying','model':model,'size':'3:4','quality':'high','count':1,'references':['reference.png'],'prompt':prompts['contact_sheet_prompt']})
        batch = await asyncio.wait_for(app.execute_ai_image_batch(
            prompt=prompts['contact_sheet_prompt'],provider_id='shiying',model=model,size='3:4',quality='high',
            references=[{'url':reference,'kind':'image','role':'subject'}],count=1,prefix='lookbook_demo_',
            allow_edit_endpoint_fallback=False,semantic_mask=True,
        ), timeout=600)
        urls = batch.get('images') or []
        if len(urls) != 1:
            raise RuntimeError('invalid_image_count')
        file = app.output_file_from_url(urls[0])
        if not file or not Path(file).is_file():
            raise RuntimeError('missing_image_file')
        shutil.copy2(file,OUT / 'contact-sheet.png')
        from PIL import Image
        with Image.open(OUT / 'contact-sheet.png') as im:
            dimensions = list(im.size)
        report['stages']['image'] = {'status':'succeeded','elapsed_s':round(time.perf_counter()-started,3),'dimensions':dimensions,'images':1,'panels':4}
    report['status']='succeeded'
    save('results.json',report)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    old = OUT / 'results.json'
    report = json.loads(old.read_text(encoding='utf-8')) if old.exists() else {'status':'running','started_at':time.strftime('%Y-%m-%d %H:%M:%S'),'stages':{}}
    if report.get('status')=='succeeded':
        print('Existing successful case retained; no API calls.')
        return
    runtime = ROOT / '.codex-artifacts/lookbook-two-stage-runtime'
    runtime.mkdir(parents=True,exist_ok=True)
    os.environ.update(CANVAS_DATA_DIR=str(runtime / 'data'),CANVAS_PORTABLE_ROOT=str(runtime),CANVAS_APP_ROOT=str(ROOT),
                      CANVAS_DWPOSE_AUTO_DOWNLOAD='0',CANVAS_DEPTH_AUTO_DOWNLOAD='0')
    from canvas_core.secrets import DpapiProtector
    with sqlite3.connect((INSTALLED / 'database/canvas.db').as_uri()+'?mode=ro',uri=True) as db:
        providers = [json.loads(r[0]) for r in db.execute('SELECT payload_json FROM providers ORDER BY sort_order,id')]
        providers = [p for p in providers if p.get('id') in {'ecommerce-vision','shiying'}]
        for p in providers:
            key_name='API_PROVIDER_'+p['id'].upper().replace('-','_')+'_KEY'
            row=db.execute('SELECT encrypted_value FROM secret_values WHERE key=?',(key_name,)).fetchone()
            if row is None:
                raise RuntimeError('missing_saved_credential')
            os.environ[key_name]=DpapiProtector().unprotect(bytes(row[0]))
    try:
        # 不保存底层调试日志，它可能含请求头或完整多模态载荷。
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            import main as app
            app.ADMIN_DATABASE.save_providers(providers)
            asyncio.run(run(app, providers, report))
    except Exception as exc:
        report.update(status='failed',error_type=type(exc).__name__)
        save('results.json',report)
    finally:
        for p in providers:
            os.environ.pop('API_PROVIDER_'+p['id'].upper().replace('-','_')+'_KEY',None)
    print(json.dumps(report,ensure_ascii=True,indent=2))
    if report['status']!='succeeded':
        raise SystemExit(1)


if __name__=='__main__':
    main()
