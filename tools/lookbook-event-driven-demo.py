"""回应首轮视觉失败：仍为空需求，由API自主构思事件，再独立展开可见机位。"""
import importlib.util
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('lookbook_demo', Path(__file__).with_name('lookbook-two-stage-demo.py'))
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
demo.OUT = demo.ROOT / '输出/Lookbook两阶段方案-20260910/revision-2'
demo.PLAN_ONLY = '--plan-only' in sys.argv
demo.CASE_CONFIG = {
    'panels': 6, 'layout': '2 columns x 3 rows', 'panel_ratio': '3:2', 'image_size': '1:1',
    'message': '广告需求为空。唯一输入R1被用户标注为人物参考。请自主创作一组6幅有事件驱动、摄影位置明显不同的高端时尚故事；每幅3:2横向，2列3行组合预览。不要询问情景，不使用预设故事。人物、现有衣物与已有商品保真，摄影师可以移动，事件可以离开原图构图覆盖的那一小块区域。',
}
demo.STORY_SYSTEM = '''你是具有大胆摄影观点的时尚创意总监。本轮只做故事构思，下一轮才写分镜提示词。
用户上传图是人物参考，不是必须复刻的构图或背景。你必须综合全部图中可见人物、衣物、物品，主动编写新的故事，而不是扩写源照片中那一秒。
参考所有权：R1锁定两位人物的脸、头发、体型、白色露腰系带镂空两件式服装/实际可见结构、黑色短袖上衣、蓝色牛仔裤及已有相机外观。身份锁不锁姿态、眼神、站位、摄影师位置。衣服不要误变成一件没有腰间开口的连衣裙。
背景仅是创意起点；没有单独标注LOCATION参考时，允许依据视觉线索建立可信的相邻空间与路线，不要把人物困在同一扇门前。可创作必要的情节物件和自然环境事件，但不得虚构源图商品品牌或性能。若换到相邻空间，要说明经过哪道门/拐角，环境如何连续。
必须有外部触发或具体行动目标、受阻/发现、选择、行动推进、可见的结果。每个beat必须改变至少一个可见状态（人物位置/目标物状态/空间关系/行动结果），结尾不允许只是回到开场姿势。用静帧也能看出“发生了事”，不能依赖长字幕才理解。
不合格模板：一起看相机→递相机→拍照→再看相机；站立→转头→摸衣服→微笑；只用光变了/心情变了/有默契了冒充事件。胶片或能力未知相机不能即时回放照片。
时尚不是生活记录加胶片滤镜。事件应提供大胆身体线条、动作张力、服装受力、空间反差、留白与视觉意外；其中至少两瞬间适合做独立时尚杂志跨页，不要把6幅写成商品使用说明书。不要用夸张危险事故、追逐惊悚或无关道具堆积来制造戏剧。
内部先生成3个显著不同的事件方向，按能否产生6种不同画面状态、能否自然展示服装、是否脱离源图复刻做比较，选最强的一项。输出候选的一句梗概和淘汰理由，使选择可检查，但仅完成一个故事。
输出严格JSON：{"reference_facts":[{"id":"R1","roles":[],"visible_facts":[],"must_preserve":[],"not_locked":[]}],"candidate_events":[{"idea":"","visual_potential":"","selected":true,"reason":""}],"title":"","intent":"","story":"200-350字中文故事","creative_extensions":[],"event_contract":{"goal":"","trigger":"","obstacle_or_discovery":"","decision":"","consequence":"","ending_differs_from_start":""},"spatial_route":[{"zone":"","connection_to_previous":""}],"beats":[{"index":1,"event":"","cause_from_previous":"","visible_state_change":"","detail_or_fashion_value":""}],"camera_intent":"整组摄影观点与多机位方向，不写机械模板","continuity_locks":[],"ad_brief":"可回填用户需求的完整故事、立意与摄影意图；明确6张事件推进、不同真实观察方向与摄影位置，禁止只推拉裁切"}。
只选一个故事，6个beat。原图事实不能被故事意图覆盖；背景不是锁。'''
demo.PROMPT_SYSTEM = '''你是高端时尚摄影导演。本会话独立接收上轮故事与R1人物图；将故事拍成6幅强摄影观点图像。
忠实执行故事的触发、行动和结果；不要擅自退回一起看相机。人脸、头发、原服装结构与已有商品保持一致。R1是身份与服装证据，不是拍摄机位/姿态/原图背景重复模板。不要把露腰系带白衣改成完整连衣裙。
摄影必须物理换位置，不是把源图正面构图做6次裁切。首先画出本故事的空间区域、行动路线、摄影师站位；每镜头给可见的几何后果：摄影师在哪个物体的哪一边、看向哪里，人物看到正面/侧面/背面哪部分，哪个物体挡住哪个，背景的哪一面应可见，源图蓝门是否退出画面。
不能把相同人物都放左侧、同一面墙都在右侧。相邻可比较主体观察方向≥30°；180度轴线是每个动作场景的局部关系，不是禁止整个故事走到新空间。需要跨轴就用正轴/高位等过渡建立新方向。整数角度只辅助，不作为合格证明。
6格至少四种明显不同摄影站位族，包括事件适合的贴地广角仰拍、从高处接近垂直俯拍、侧面横向/穿过门框观察、背后观察去向或反射观察、动作中的服装细节插入。不是把六种视点名词贴到相同画面；每格必须写具体几何和构图。单格可以大胆裁掉脸，但整组人物仍可辨认。
至少两张有明确编辑时尚构图：身体斜线对抗建筑、服装形态与事件方向构成主次、负空间与人物比例大胆；真实有力的动作，不是手叉腰摆拍。人物看向事件目标，不反复对视镜头。光源用固定世界坐标描述，相机转动后允许光在画面的方向改变。
每格只处理唯一的一次事件状态。特写是某个因果环节：例如受力的衣料、实际接触或正在变化的物件，而非中断故事展示一个静态商品。未知道具能力不用。
整张1:1图片，精确2列×3行，每一格3:2横向（不是竖图），从左到右再从上到下顺序。图片整体边到边，无外框，无文字和编号。共享限制短写，给6格独特行动/几何更多篇幅。最终contact_sheet_prompt用完整英文自然段写出全部六幅，第一句强调这是一组全新取景，不是输入图的不同裁切。
输出严格JSON：{"title":"","story_used":"逐字复制第一阶段ad_brief","continuity_bible":{"identity":"","wardrobe":"","location":"","light":"","props":"","axis":""},"shots":[{"index":1,"beat":"","shot_size":"","azimuth_deg":0,"height":"","lens":"","camera_position":"摄影师物理位置与看向","visible_geometry":"脸/身体朝向、前后景、背景哪一面出现","different_from_previous":"真实换机位的可见证据","composition":"","continuity_in":"","continuity_out":"","prompt":"完整英文单幅生成提示词"}],"self_audit":{"event_consequence_visible":true,"unique_camera_families":[],"same_source_composition_repetitions":0,"wardrobe_geometry_preserved":true},"contact_sheet_prompt":"完整英文六格联合生图提示词"}。
返回6格。不要把本轮变成创意重写；发现事实矛盾应返回validation_error，不带着冲突继续。'''

if __name__ == '__main__':
    demo.main()
