"""复用第二轮真实故事，仅重做第二阶段摄影导演；所有额外调用独立记录。"""
import importlib.util
import json
from pathlib import Path
import shutil

spec=importlib.util.spec_from_file_location('event_demo',Path(__file__).with_name('lookbook-event-driven-demo.py'))
event=importlib.util.module_from_spec(spec)
spec.loader.exec_module(event)
demo=event.demo
previous=demo.OUT
demo.OUT=demo.ROOT/'输出/Lookbook两阶段方案-20260910/revision-3'
demo.OUT.mkdir(parents=True,exist_ok=True)
for name in ('story-request.json','story-response.json'):
    if not (demo.OUT/name).exists():
        shutil.copy2(previous/name,demo.OUT/name)
if not (demo.OUT/'results.json').exists():
    prior=json.loads((previous/'results.json').read_text(encoding='utf-8'))
    record={'status':'running','stages':{'story':prior['stages']['story']},
            'story_reused_from':'revision-2; no new story API call',
            'purpose':'second-stage editorial direction refinement after visual review rejected generic documentary execution'}
    (demo.OUT/'results.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')

demo.PROMPT_SYSTEM += '''
追加导演审查：上次按同一故事生成的结果已经被判定为普通生活记录，虽然换了实际地点，却没有时尚摄影。这次必须升级摄影表达，不能只把动作拍清楚。故事、服装和布面事件不变。
最高优先执行以下编辑摄影原则：
1. 不是居民晾床单的纪实照片。人物的动作幅度、身体线条和光影关系需要时尚摄影的有意识编排：逆风扭身、重心偏移、手臂与腰线形成互相对抗的斜线、布面张力和衣料受力真实；动作必须来自当前事件，禁止无理由手叉腰站直。
2. 摄影机敢于靠近并离轴。至少两格是强视觉主图；宁可有意裁掉头顶/半个身体，也不要每格居中全身+完整建筑的保险构图。不要每格曝光、主体占比、地平线位置都相同。
3. 用有力量的18-24mm近地透视建立布面与前景肢体的尺度反差；与85-100mm的触感/侧面局部、真正俯视的几何图交替。广角不是站远把所有东西拍进去；相机必须贴近前景动作，人物主体靠近镜头，背景保持真实透视。
4. 光线属于同一阵天气变化：开始真实硬侧光与深门洞阴影，进入阵雨后冷天光和湿地反射；强调物理塑形、真实皮肤和乳白布面分层，不要柔光电商曝光、米色房产摄影、HDR抬亮一切或塑料光泽。不能用泛泛“cinematic fashion realism”代替具体摄影决定。
5. 一格一个决定性瞬间。开场突出逆风抓布的一瞬；受阻镜头突出身体与拉力相反的对角；释放挂带镜头用真正顶视的手、衣料和物件关系；楼梯图用靠近镜头的跨步与飞布透视，不是远远站在楼梯口；拱门图强调有意的巨大负空间、逆光薄布和人体剪影轮廓；终局从帆下近地看帆面接近镜头的大斜线，两人在不同深度放松张力，是事件结束后的身体变化，不是站定留念。
6. 即使拿掉剧情说明，每格仍应作为有强图形组织的时尚影像成立。不要拍成旅游、家居劳动、地产、温馨广告。人物仍是原图两人，现有露腰白衣和黑衣牛仔保真。
最终contact_sheet_prompt至少2200英文字符，把以上摄影决定具体分配到每个panel，不要最后又压缩成六句“站在哪里拍”。输出结构与6镜头数量不变。所有共有身份规则只短写，重点预算给动作几何、负空间、透视和世界光源。
'''

if __name__=='__main__':
    demo.main()
