"""服装主导的 Lookbook 两阶段创作契约；不包含网络或任务存储。"""
from __future__ import annotations

import json
import re
from typing import Any

STORY_VERSION = "lookbook-editorial-story-v2"
REFERENCE_LIMIT = 14  # 与现有图片路由及通用参考契约一致；解析不能静默截为12张。

STORY_SYSTEM = """你是 Lookbook 时尚创意总监。这是第一次独立会话，只综合参考图片并确定故事与立意，下一次会话才编写生图分镜。
优先级：用户明确要求 > 服装/指定商品的视觉中心 > 人物身份与自然穿着 > 连续生活情境 > 摄影表达 > 辅助道具。
Lookbook是穿着的人有生活、服装自然成为视觉中心，不是道具主导的短片。先读廓形、面料、剪裁、露肤/开口、层次、搭配与适合的气质，再设计让这些特点自然显现的情境。
人物可以有赴约、等待、相遇、同行等生活目的，但不要套用固定故事。要有具体情境、行动动机、互动/发现/选择和情绪变化；拒绝“站立→转头→微笑”的空动作串。事件强度适度，优雅自然；不靠抢救物件、劳动、事故、追赶道具或凭空巨大布景制造戏剧。
服装展示价值按整组分配，不要求每格证明剪裁或展示完整衣服。脸部表情、手指触摸面料的亲密特写、环境中的身体关系都可以独立成图。未指定商品时以人物现有完整造型为主，指定商品时给该商品合理的关键细节和廓形覆盖，其余画面仍可表现人。
核心创作任务：根据场景扩展电影感时尚多角度画面，包含有情绪的表情、手摸服装的触感特写和真正切换的摄影角度。先从这张图独有的空间、光线、材质与人物气质提炼一个视觉吸引点，再给一个简洁开放的情境。没有生活剧情也可以是时尚肖像组照，不硬编赴约或试穿故事。
禁止默认“整理腰线→试走→停步→回身→正面站定”、开拍准备、确认穿着、九次确认等检查式叙事。不要把保守延展衣服背面解释成保守构图；可以近拍、俯拍、偏心、前景切入并保留有意裁切。棚拍也要有表情温差和身体线条，不能默认全程沉静。根据具体图选择情绪，不把全程微笑当作新模板。
按输入角色逐图综合：人物图锁身份与可见衣着，不锁原姿势/摄影机位/背景；只有明确场景参考锁地点结构，仍不锁相机位置。商品图锁商品结构，材质图锁纹理，姿态/版式参考只控制对应层。没有单独场景图时可从人物图环境自然延展相邻空间，不要求每幅都带原背景。
把可见事实与创作扩展分开。白衣的露腰、系带、两件式结构不可误读为完整连衣裙；不明确的结构/背面只能保守推断，不杜撰品牌、性能或私人人物关系。能力未知相机不可假设能回放影像。
故事必须简短连续（建议150–300中文字符）；用户已有情景/完整故事时忠实保留目的、顺序和立意，仅补服装与摄影执行空间。用户明确改衣/改场景时优先遵从。
摄影意图只写摄影方向，不预先排定逐格焦段、顺序和角度菜单；把镜头设计空间留给第二阶段。相邻同主体视点变化至少30°，不是画面倾斜或同机位变焦裁切；真实换机位应在背景透视、可见身体面和前景关系上成立。触感细节插入可不比较方位角。有行动轴时保持局部180°连续。独立输出1张且未要求拼格时才只设计一个瞬间；一张多宫格仍包含多个不同瞬间。
参数与所选风格保持用户优先；settings只建议未明确的值，不让故事中的镜头数字覆盖用户交付数量。无需联网；不要输出生图长提示词。
只返回严格JSON（所有图片逐一列reference_index，不遗漏）：
{"title":"","story":"","intent":"","wardrobe":{"target":"整体造型或指定商品","visible_features":[""],"coverage":[""]},"reference_facts":[{"reference_index":1,"facts":"","preserve":"","not_locked":""}],"creative_extensions":[""],"beats":[{"event":"","motivation":"","garment_value":""}],"camera_intent":"","settings":{"count":4,"aspect_ratio":"16:9","resolution":"2k","quality":"high"},"auto_decision":{"selected_style_id":"仅自动风格时选择给定ID","rationale":"","art_direction":""}}
输出前自查：情节是否自然、服装是否始终是视觉主体、有没有凭空道具抢戏、是否保留原衣物结构、是否给不同机位留出空间。"""

EXECUTION_RULES = """WARDROBE-FIRST LOOKBOOK EXECUTION — EDITORIAL FREEDOM:
The user's explicit intent and reference facts are authoritative. The AI-written story is a creative proposal, not a mandatory pose list. Preserve its setting and mood, but replace repetitive fitting/walking/turning coverage with stronger photographic moments. Never replace an explicit user story with another plot.
Direct a fashion photograph, not a fit inspection. Wardrobe fidelity is a SERIES continuity constraint, not a requirement to show all construction in every frame. Allow expressive face portraits and intimate hand-on-fabric details alongside silhouette images. Separate expression, body gesture and camera intensity. Choose emotions from this scene, not uniformly blank faces or a compulsory smile.
Start with the specific reference's space, light, texture and attitude. An editorial portrait session can be enough; do not invent errands, rescue props or a forced dramatic twist. Never default to adjusting the waistband, walking, turning and a final frontal stance.
References own only their assigned roles: a person reference does not own the original camera position, pose or background; a separately assigned scene reference owns architecture and spatial facts, not framing. Preserve visible garment openings, ties, separate pieces, hems and fabric; never simplify the outfit into a different garment.
Each shot must name wardrobe_focus (what garment feature is revealed), wardrobe_visibility (how it stays readable), camera.position (physical photographer location and look direction), and camera.visible_geometry (body side seen, foreground overlap, background plane or spatial evidence of a new viewpoint). Adjacent comparable subject views should change observation direction at least 30 degrees, while maintaining the local action axis. Cropping, zooming or Dutch tilt alone does not count as changing position.
Across a multi-view series create a visible rhythm of subject scale, near/far perspective, body geometry and emotional temperature. Give a readable face a specific gaze, eyelid/mouth response and feeling; give tactile details the exact finger contact and fabric response. These roles have no fixed order. A detail without a face needs no invented facial expression. Use foreground depth or intentional crop when the scene supports it. Adjacent comparable subject views change physical observation direction by at least 30 degrees; a tactile insert is exempt. Derive light from stable world-space sources, not the same camera-relative light direction in every shot.
PERFORMANCE AUDIT: unless the user explicitly asks for a uniformly neutral mood, do not describe every face as calm, restrained, serene or relaxed. Design visibly different emotional states and at least one unmistakably expressive face; writing 'almost smiling' on an otherwise blank face is insufficient. A quiet studio can contain an amused response, a private smile, curiosity or an intense direct gaze, selected from its specific mood. Body geometry also changes: repeatedly standing with one leg bent and one hand near the waist fails even if the camera moves. Do not equate sophistication with absence of expression.
Judge visual variety from visible geometry, not angle numbers or a model self-score. User count, aspect ratio, layout and explicit art direction remain authoritative.
"""


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"Lookbook 故事缺少有效的 {name} 或超过长度限制")
    return value.strip()


def normalize_story(data: Any, reference_count: int) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Lookbook 故事必须是对象")
    result = {key: _text(data.get(key), key, limit) for key, limit in
              (("title", 160), ("story", 1800), ("intent", 800), ("camera_intent", 1600))}
    wardrobe = data.get("wardrobe")
    if not isinstance(wardrobe, dict):
        raise ValueError("Lookbook 故事缺少服装展示方案")
    result["wardrobe"] = {"target": _text(wardrobe.get("target"), "wardrobe.target", 500)}
    for field in ("visible_features", "coverage"):
        values = wardrobe.get(field)
        if not isinstance(values, list) or not 1 <= len(values) <= 20:
            raise ValueError(f"Lookbook 故事缺少 wardrobe.{field}")
        result["wardrobe"][field] = [_text(v, field, 500) for v in values]
    references = data.get("reference_facts")
    if not isinstance(references, list) or len(references) != reference_count:
        raise ValueError("Lookbook 故事未综合全部参考图，已停止生成")
    result["reference_facts"] = []
    for index, ref in enumerate(references, 1):
        if not isinstance(ref, dict) or ref.get("reference_index") != index:
            raise ValueError("Lookbook 故事参考图映射不完整")
        result["reference_facts"].append({"reference_index": index, **{
            key: _text(ref.get(key), key, 1500) for key in ("facts", "preserve", "not_locked")}})
    beats = data.get("beats")
    if not isinstance(beats, list) or not 1 <= len(beats) <= 20:
        raise ValueError("Lookbook 故事需要1–20个简要情节或摄影瞬间")
    result["beats"] = []
    for beat in beats:
        if not isinstance(beat, dict):
            raise ValueError("Lookbook 情节格式无效")
        result["beats"].append({key: _text(beat.get(key), key, 700)
                                for key in ("event", "motivation", "garment_value")})
    extensions = data.get("creative_extensions", [])
    if not isinstance(extensions, list) or len(extensions) > 12:
        raise ValueError("Lookbook 创作扩展格式无效")
    result["creative_extensions"] = [_text(v, "creative_extensions", 800) for v in extensions]
    result["ad_brief"] = (f"《{result['title']}》\n\n故事：{result['story']}\n\n立意：{result['intent']}"
                          f"\n\n服装展示：{'；'.join(result['wardrobe']['coverage'])}"
                          f"\n\n摄影意图：{result['camera_intent']}")
    if len(result["ad_brief"]) > 6000:
        raise ValueError("Lookbook 广告需求过长，请精简故事与摄影意图")
    result["version"] = STORY_VERSION
    return result


def effective_brief(options: dict) -> str:
    story = options.get("lookbook_story")
    if isinstance(story, dict) and story.get("version") == STORY_VERSION:
        return str(story.get("ad_brief") or "")
    return str(options.get("instruction") or "")


def story_handoff(options: dict) -> str:
    story = options.get("lookbook_story")
    if not isinstance(story, dict) or story.get("version") != STORY_VERSION:
        return ""
    return ("\n第二次独立会话：第一轮故事提供情境与事实依据；保留用户意图，允许重新导演其中雷同的自动动作建议。\n"
            + EXECUTION_RULES + "\n用户原始要求（优先）：" + str(options.get("instruction") or "（空）")
            + "\n已完成故事与服装展示依据：" + json.dumps(story, ensure_ascii=False))


def validate_story_shots(cards: list[dict], options: dict) -> list[dict]:
    if not story_handoff(options):
        return cards
    layout = options.get("lookbook_layout_intent") or {}
    expected = int(layout.get("panel_count") or 1) if layout.get("explicit") else 1
    for card in cards:
        panels = card.get("panel_cards")
        if expected > 1 and (not isinstance(panels, list) or len(panels) != expected):
            raise ValueError(f"Lookbook 拼图必须逐格规划 {expected} 个 panel_cards，不能重复整张镜头")
        if panels:
            if not isinstance(panels, list) or len(panels) != expected:
                raise ValueError("Lookbook 分格数量与版式不一致")
            for index, panel in enumerate(panels, 1):
                if not isinstance(panel, dict) or panel.get("index") != index:
                    raise ValueError("Lookbook 分格编号必须连续")
                for key in ("action_chain", "micro_expression", "composition"):
                    _text(panel.get(key), f"panel.{key}", 1800)
    positions = set()
    shots = [panel for card in cards for panel in (card.get("panel_cards") or [card])]
    for shot in shots:
        _text(shot.get("wardrobe_focus"), "shot.wardrobe_focus", 1200)
        _text(shot.get("wardrobe_visibility"), "shot.wardrobe_visibility", 1200)
        camera = shot.get("camera")
        if not isinstance(camera, dict):
            raise ValueError("Lookbook 镜头缺少真实机位")
        positions.add(_text(camera.get("position"), "camera.position", 1200))
        _text(camera.get("visible_geometry"), "camera.visible_geometry", 1200)
    if len(positions) < min(3, len(shots)):
        raise ValueError("Lookbook 镜头重复同一机位，请重新规划服装展示视点")
    # 只拦截可证明的复制，不用自评分或角度数字宣称视觉多样性。
    def canonical(value):
        return re.sub(r"[\W_\d]+", "", str(value or "").lower())

    signatures = set()
    for shot in shots:
        if not all(shot.get(key) for key in ("action_chain", "micro_expression", "composition")):
            continue  # 旧版独立镜头兼容；新拼格必填项在上面检查。
        signature = tuple(canonical(shot[key]) for key in ("action_chain", "micro_expression", "composition"))
        if signature in signatures:
            raise ValueError("Lookbook 出现重复动作、表情与构图组合；仅改机位编号不算新镜头")
        signatures.add(signature)
    return [{**card, "lookbook_story_version": STORY_VERSION} for card in cards]


def panel_planning_rules(layout: dict) -> str:
    if not layout.get("explicit") or int(layout.get("panel_count") or 1) <= 1:
        return ""
    return (
        f"\n逐格执行契约：每个 shot_card 必须额外包含恰好 {int(layout['panel_count'])} 个 panel_cards。"
        "每格 index 从1连续编号，其余字段使用下述单镜头结构（无需嵌套panel_cards）。外层仅为摘要，内层是生图权威。"
        "每格都写 action_chain、micro_expression、wardrobe_focus、wardrobe_visibility、composition、lighting 和 camera。"
        "每个字段用一句可见的拍摄决定，不重复全局规则、上一格故事、禁令或服装清单；面部不可见时micro_expression明确写不可见。"
        "camera 必须有 shot_size、position、visible_geometry；写出摄影师在哪里及画面能看见的透视证据。"
        "在整组自由安排有情绪的脸部近景、手摸衣料的触感细节、身体与环境的主视觉；用户有明确限制时按用户要求调整。"
        "用表情、景别、身体线条与空间关系共同形成差异，不按固定顺序排动作。只换镜头编号、焦段或方位数值不能通过去重检查。"
    )


def photographic_shot(shot: dict) -> str:
    """只编译该画面可执行的视觉信息，不把过程状态和叙事解释灌入图片模型。"""
    fields = ("action_chain", "micro_expression", "weight_and_contact", "camera",
              "composition", "lighting", "wardrobe_focus", "wardrobe_visibility")
    return json.dumps({key: shot[key] for key in fields if shot.get(key)}, ensure_ascii=False, separators=(",", ":"))


def generation_brief(options: dict) -> str:
    story = options.get("lookbook_story") or {}
    if story.get("version") != STORY_VERSION:
        return effective_brief(options)
    return ("用户要求：" + str(options.get("instruction") or "依据参考发挥")
            + "\n《" + story["title"] + "》情境：" + story["story"] + "\n意图：" + story["intent"])


def editorial_generation_prompt(brief: str, bible: Any, card: dict, labels: list, layout: dict) -> str:
    panels = card.get("panel_cards") or [card]
    if layout.get("explicit"):
        delivery = (f"Create ONE image: a strict {layout.get('rows')} rows x {layout.get('columns')} columns grid, "
                    f"exactly {len(panels)} equal rectangular photographs, each {layout.get('cell_aspect_ratio')} aspect ratio. "
                    f"{layout.get('gap_prompt')}. Read left to right, top to bottom. "
                    "Straight aligned separators; no spanning cells, inset pictures, overlaps, text or outer margin. ")
    else:
        delivery = "SINGLE-FRAME HARD STOP: ONE full-bleed photograph, no grid, border or text. "
    world_keys = ("identity", "appearance", "wardrobe", "products", "product_direction", "location", "environment",
                  "palette", "lighting", "physical_light", "photographic_surface")
    world = {k: bible[k] for k in world_keys if bible.get(k)} if isinstance(bible, dict) else bible
    return (delivery
            + "\nPhotograph cinematic fashion moments from the reference setting: expressive faces, intimate hand-on-fabric contact, and genuinely different camera viewpoints. "
            "WARDROBE-FIRST means preserve the outfit across the series, not show every detail in every frame. "
            "Execute the expressive portraits and intentional crops. Avoid repetitive neutral standing poses. "
            "Adjacent comparable subject views change physical observation direction by at least 30 degrees; zoom or crop alone does not count. "
            + "\nUSER INTENT AND SETTING: " + brief
            + "\nREFERENCE ROLES: " + json.dumps(labels, ensure_ascii=False)
            + "\nSHARED VISUAL FACTS AND LIGHT: " + json.dumps(world, ensure_ascii=False)
            + "\n" + "\n".join(f"PANEL {i}: {photographic_shot(panel)}" for i, panel in enumerate(panels, 1))
            + "\nDeliver precisely the layout specified above. Each panel is one distinct photographic moment; no alternate inset or collage layout.")


def editorial_planning_message(snapshot: dict, layout: dict) -> str:
    """新版导演使用简短独立契约，不再叠加历史电商/剧情分镜模板。"""
    options = snapshot.get("options") or {}
    panel = {"index": 1, "beat": "摄影瞬间", "story_purpose": "画面吸引点",
             "continuity_in": "", "continuity_out": "", "action_chain": "",
             "micro_expression": "", "weight_and_contact": "", "wardrobe_focus": "",
             "wardrobe_visibility": "", "composition": "", "lighting": "",
             "camera": {"shot_size": "", "position": "", "visible_geometry": ""}}
    output = {**panel, "panel_cards": [panel]} if layout.get("explicit") and int(layout.get("panel_count") or 1) > 1 else panel
    schema = {"logline": "", "campaign_bible": {"identity": "", "wardrobe": "", "location": "",
              "palette": "", "lighting": "", "photographic_surface": ""}, "shot_cards": [output]}
    return (
        "根据提供的参考图和情境，扩展电影感时尚摄影画面。先构图，再让人物在画面中活起来。只返回JSON。\n"
        "这组画面要让人想看人物的情绪与衣料的触感，不是逐项检查穿着。允许有意识的编辑摄影姿态与亲密人像。"
        "多镜头时让脸有可辨的情绪变化：具体写出眼睛、嘴角、视线和呼吸的可见变化，不把‘沉静、克制、平静、放松’换词写满全组。"
        "按情境选择表情强度，不要求每格微笑；脸部不可见的细节格明确说明。手摸服装要看清指尖压力和衣料受力。"
        "景别需要有冲突与节奏，摄影师要真正靠近：清晰的脸部近景、触感局部、身体与场景关系；不要全是相同人物占比的远景。"
        "相邻可比人物视点按30度规则实际换位，写出背景平面和身体可见面的变化证据；细节插入不用机械计算角度。"
        "从这张图的场景、光线和衣物找到自己的构图，不照抄固定镜头顺序，不凭空添人物或布景。"
        "风格决定光色和摄影气质，用户指定版式/情绪优先于预设中的固定四张、禁止拼格或动作示例。"
        f"\n交付恰好{int(snapshot.get('count') or 1)}个shot_cards。"
        + panel_planning_rules(layout)
        + "\n每字段一句短而明确的视觉描述；公共规则仅在campaign_bible写一次。"
        + "\n用户原始需求：" + str(options.get("instruction") or "空，依据图片发挥")
        + "\n第一轮情境（自动动作可重新导演）：" + effective_brief(options)
        + "\n选定风格：" + json.dumps(options.get("lookbook_style") or {}, ensure_ascii=False)
        + "\n版式：" + json.dumps(layout, ensure_ascii=False)
        + "\n可选研究：" + str(options.get("search_context") or "")[:3000]
        + "\nJSON结构：" + json.dumps(schema, ensure_ascii=False)
    )


EDITORIAL_QA = """Lookbook 编辑摄影终审：服装保真按整组覆盖检查，允许表情近景、手摸衣料特写、局部裁切和有意摆姿；不要求每格完整展示服装或发生剧情转折。
用户原始要求是约束，自动计划中的动作建议不是额外用户命令。若实际触碰部位、站姿或构图变化仍然符合用户目标且形成好照片，不因偏离自动建议而判弱；把视觉效果、情绪和多样性置于计划逐字服从之前。
逐格观察，不把计划里的角度或自评分当作证据。指出重复的具体格号：动作与身体线条是否雷同、脸是否统一呆滞、是否只是同机位裁切、是否全为平视远景、触碰是否真实、有无清晰的摄影主次与表情温差。
检查参考事实、身份、服装与空间连续性。不要为增加新意更换衣服、人物或地点。修复只针对弱格，保留已经成立的表情、裁切与机位。用户明确要求的克制/棚景优先，不因缺少剧情或街景而判弱。
"""
