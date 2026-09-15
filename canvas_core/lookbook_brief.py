"""服装主导的 Lookbook 两阶段创作契约；不包含网络或任务存储。"""
from __future__ import annotations

import json
import re
from typing import Any

STORY_VERSION = "lookbook-editorial-story-v2"
DIRECTING_REVISION = "editorial-default-workflow-v2"
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
指定卖什么就围绕什么创作：用户主推牛仔裤时，wardrobe.focus_mode必须为product，target必须指向参考图的牛仔裤，不能回退成整体造型或黑色上衣。服装细节的触碰也应落在主推商品。人物表情可以服务广告态度，但不能用一堆脸部和上衣特写占掉牛仔裤的主视觉。
摄影表达默认具有时尚编辑张力，不默认35/50/85mm轮换。允许近距离广角、超广角、鱼眼、贴地仰拍、俯冲视角与强烈透视。用户明确要求广角/鱼眼时将其写进摄影意图；安静表情不等于保守机位。透视可以夸张，商品本身的真实版型和结构不能被替换。
节点开启大胆时尚时，即使用户只说“主推牛仔裤”或不写需求，也默认规划高张力摄影；无需用户重复填写广角关键词。不要固定同一套动作或每次强加鱼眼。只有用户明确限制镜头/透视/构图时，才在camera_constraints返回restrained与对应原文quote；仅表情安静、优雅不能作为收敛摄影的理由。
只返回严格JSON（所有图片逐一列reference_index，不遗漏）：
{"title":"","story":"","intent":"","wardrobe":{"focus_mode":"product或outfit","target":"整体造型或用户明确主推的商品","visible_features":[""],"coverage":[""]},"reference_facts":[{"reference_index":1,"facts":"","preserve":"","not_locked":""}],"creative_extensions":[""],"beats":[{"event":"","motivation":"","garment_value":""}],"camera_intent":"","camera_constraints":{"mode":"bold或restrained","quote":"用户明确摄影限制原文，没有则空"},"settings":{"count":4,"aspect_ratio":"16:9","resolution":"2k","quality":"high"},"auto_decision":{"selected_style_id":"仅自动风格时选择给定ID","rationale":"","art_direction":""}}
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

OPTICS_DIRECTION = """FASHION OPTICS AND PRODUCT DIRECTION:
Choose actual optics, proximity and viewpoint, not a menu of conventional focal lengths. Unless the user requests restraint, fashion editorial may use 14–24mm rectilinear wide/ultra-wide close to the foreground, full-frame 8–16mm fisheye, floor-level upward views, overhead proximity, diagonal body geometry and strong near/far size contrast. Mix these with tactile details; do not make every frame the same effect.
A focal-length label alone is insufficient: every camera must declare lens_mm, projection (rectilinear or fisheye), distance_m to the emphasized foreground, height_m, and perspective_effect describing visible scale/convergence/curvature. A wide lens used far away is still a conventional image. Fisheye means visible optical curvature and expanded foreground, filling the rectangular photograph without a circular black vignette unless requested. Tilt belongs inside a level grid.
Honor explicitly requested wide and fisheye lenses: a wide-angle campaign needs at least one third of its shots at 24mm or wider and within 1.5m of the emphasized foreground; a fisheye request needs at least one fisheye shot. Preserve a restrained or no-distortion request. Facial emotion, camera intensity and body amplitude are independent.
If the user names a product, at least two thirds of frames must visually prioritize that product, with product_emphasis=dominant. Product_focus and product_visibility describe what draws the eye and the visible evidence; supporting garments and the face may support attitude but must not displace the product. For jeans, use the actual denim volume, waistband, pockets, stitching, knee folds and hems as compositional geometry. Place denim near the lens, let legs form strong diagonals or depth planes, touch the denim rather than an unrelated top. At least one view must establish the actual trouser silhouette. Do not invent seams, stretch the garment into another cut, enlarge footwear into the advertised subject, or confuse optical foreshortening with changing the product.
"""

DEFAULT_BOLD_DIRECTION = """DEFAULT BOLD EDITORIAL IS ACTIVE:
Make the visual tension unmistakable, not slight, gentle or merely a conventional low-angle full-body picture. At least one third of the sequence must put the primary subject/product within 0.7m of a 24mm-or-wider lens. Move the photographer close enough that foreground shape dominates and the rest of the body recedes dramatically. Use intentional crop, opposing diagonals, deep foreshortening, floor-near or plunging views. Do not stand back to fit the whole body in every photograph. Keep one readable product silhouette across the series, not a full-body quota. Other shots provide tactile or emotional contrast. A label such as 21mm without strong visible near/far scale fails this direction. Preserve exact reference construction, not its catalog framing.
"""


def product_direction(options: dict) -> dict:
    wardrobe = (options.get("lookbook_story") or {}).get("wardrobe") or {}
    if wardrobe.get("focus_mode") != "product":
        return {}
    return {"focus_mode": "product", "target": wardrobe.get("target"),
            "immutable_features": wardrobe.get("visible_features") or [],
            "coverage": wardrobe.get("coverage") or [],
            "priority": "Advertise THIS product. Most panels make it the compositional protagonist; expressions and other clothes support it."}


def requested_optics(options: dict) -> set[str]:
    # 只识别明确正向要求；创意选型仍交给看过参考图的模型。
    text = str(options.get("instruction") or "")
    choices = set()
    for clause in re.split(r"[，,。;；\n]|但是|但|而是|\bbut\b", text, flags=re.I):
        for name, pattern in (("fisheye", r"鱼眼|fish[ -]?eye"), ("wide", r"广角|wide[ -]?angle")):
            for match in re.finditer(pattern, clause, re.I):
                prefix = clause[max(0, match.start()-24):match.start()]
                if not re.search(r"不要|不用|禁止|不使用|避免|无畸变|without|\bno\b", prefix, re.I):
                    choices.add(name)
    return choices


def workflow_defaults(options: dict) -> dict:
    result = dict(options)
    for key in ("lookbook_bold_editorial", "lookbook_quality_gate", "lookbook_auto_repair"):
        result.setdefault(key, True)
    result.setdefault("lookbook_max_retries", 1)
    return result


def effective_optics(options: dict) -> set[str]:
    choices = requested_optics(options)
    if bold_direction_active(options):
        choices.add("wide")
    return choices


def bold_direction_active(options: dict) -> bool:
    if options.get("lookbook_bold_editorial") is not True:
        return False
    text = str(options.get("instruction") or "")
    constraint = (options.get("lookbook_story") or {}).get("camera_constraints") or {}
    quote = str(constraint.get("quote") or "").strip()
    explicit_restraint = (constraint.get("mode") == "restrained" and quote and quote in text
                          and re.search(r"镜头|摄影|机位|焦段|透视|构图|广角|鱼眼|mm|lens|camera|perspective", quote, re.I)
                          and not re.search(r"(?:不要|拒绝|避免|不用).{0,8}(?:常规|普通|保守|克制)", quote))
    no_wide = re.search(r"(?:不要|不用|不使用|禁止|避免|without|\bno\b)[^，,。;；\n]{0,12}(?:广角|wide[ -]?angle)", text, re.I)
    fixed_lens = re.search(r"(?:只|仅|only)[^，,。;；\n]{0,12}\d+\s*mm", text, re.I)
    return not bool(explicit_restraint or no_wide or fixed_lens)


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
    focus_mode = wardrobe.get("focus_mode", "outfit")
    if focus_mode not in {"product", "outfit"}:
        raise ValueError("Lookbook wardrobe.focus_mode必须为product或outfit")
    result["wardrobe"]["focus_mode"] = focus_mode
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
    constraints = data.get("camera_constraints")
    if isinstance(constraints, dict) and constraints.get("mode") in {"bold", "restrained"}:
        result["camera_constraints"] = {"mode": constraints["mode"], "quote": str(constraints.get("quote") or "")[:500]}
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
            + EXECUTION_RULES + "\n" + OPTICS_DIRECTION
            + ("\n" + DEFAULT_BOLD_DIRECTION if bold_direction_active(options) else "")
            + "\n本次必须落实的镜头类型：" + json.dumps(sorted(effective_optics(options)), ensure_ascii=False)
            + "。大胆时尚是节点默认摄影策略，与用户选择的色彩风格分别执行；用户明确摄影限制优先。"
            + "\n明确主推商品：" + json.dumps(product_direction(options), ensure_ascii=False)
            + "\n用户原始要求（优先）：" + str(options.get("instruction") or "（空）")
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
    optics = effective_optics(options)
    if optics:
        wide_count = fisheye_count = 0
        for shot in shots:
            camera = shot["camera"]
            try:
                lens = float(camera["lens_mm"])
                distance = float(camera["distance_m"])
                height = float(camera["height_m"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("明确要求广角/鱼眼时，每格必须给出数字lens_mm、distance_m和height_m") from exc
            if not 0 < lens <= 2000 or not 0 < distance <= 1000 or not -100 <= height <= 1000:
                raise ValueError("Lookbook 光学参数超出有效范围")
            projection = camera.get("projection")
            if projection not in {"rectilinear", "fisheye"}:
                raise ValueError("镜头projection必须为rectilinear或fisheye")
            _text(camera.get("perspective_effect"), "camera.perspective_effect", 1500)
            wide_count += lens <= 24 and distance <= (0.7 if bold_direction_active(options) else 1.5)
            fisheye_count += projection == "fisheye"
        if "wide" in optics and wide_count < max(1, (len(shots)+2)//3):
            raise ValueError("本次摄影策略要求广角张力，但近距离广角镜头不足三分之一；默认大胆摄影须24mm以内且距主角前景不超过0.7m。请真正靠近并允许裁切，不能只写低机位")
        if "fisheye" in optics and not fisheye_count:
            raise ValueError("用户明确要求鱼眼，但没有fisheye镜头；请规划真实鱼眼投影与可见曲率")
    product = product_direction(options)
    if product:
        dominant = 0
        for shot in shots:
            _text(shot.get("product_focus"), "product_focus", 1500)
            _text(shot.get("product_visibility"), "product_visibility", 1500)
            if shot.get("product_emphasis") not in {"dominant", "supporting", "none"}:
                raise ValueError("指定主推商品时，每格必须声明product_emphasis")
            dominant += shot["product_emphasis"] == "dominant"
        if dominant < (2*len(shots)+2)//3:
            raise ValueError("主推商品未成为至少三分之二镜头的构图主体；减少无关脸部/上衣展示")
    return [{**card, "lookbook_story_version": STORY_VERSION, "product_direction": product,
             "bold_editorial": bold_direction_active(options)} for card in cards]


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
    focus_fields = ("product_focus", "product_visibility", "product_emphasis") if shot.get("product_emphasis") else ("wardrobe_focus", "wardrobe_visibility")
    fields = ("action_chain", "micro_expression", "weight_and_contact", "camera", "composition", "lighting", *focus_fields)
    visual = {key: shot[key] for key in fields if shot.get(key)}
    if isinstance(visual.get("camera"), dict):
        camera = visual["camera"]
        visual["camera"] = {k: camera[k] for k in ("lens_mm", "projection", "distance_m", "height_m", "perspective_effect",
                                                  "shot_size", "position", "visible_geometry", "tilt") if camera.get(k) is not None}
    return json.dumps(visual, ensure_ascii=False, separators=(",", ":"))


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
                  "camera_intensity", "performance_amplitude", "camera_policy",
                  "palette", "lighting", "physical_light", "photographic_surface")
    world = {k: bible[k] for k in world_keys if bible.get(k)} if isinstance(bible, dict) else bible
    product = card.get("product_direction") or {}
    if product and isinstance(world, dict):
        world.pop("product_direction", None)
        world.pop("products", None)
    product_lock = ("\nADVERTISED PRODUCT — PRIMARY COMPOSITION AUTHORITY: " + json.dumps(product, ensure_ascii=False)
                    + "\nMake this product, not supporting clothes, portraits or footwear, the visual protagonist in the assigned dominant panels. "
                    "Use its shape and material as the foreground geometry; preserve its real construction under optical perspective. "
                    if product else "")
    columns = int(layout.get("columns") or 1)
    panel_text = "\n".join(
        f"PANEL {i} — ROW {(i-1)//columns+1}, COLUMN {(i-1)%columns+1}: {photographic_shot(panel)}"
        for i, panel in enumerate(panels, 1)) if layout.get("explicit") else "PANEL 1: " + photographic_shot(panels[0])
    layout_map = ("\nGRID MAP (positions only, never print numbers): " + " / ".join(
        "[" + " | ".join(str(row*columns+col+1) for col in range(columns)) + "]" for row in range(int(layout.get("rows") or 1)))
        if layout.get("explicit") else "")
    return (delivery + layout_map
            + ("\n" + DEFAULT_BOLD_DIRECTION if card.get("bold_editorial") else "")
            + "\nPhotograph cinematic fashion moments from the reference setting: expressive faces, intimate hand-on-fabric contact, and genuinely different camera viewpoints. "
            "WARDROBE-FIRST means preserve the outfit across the series, not show every detail in every frame. "
            "Execute the expressive portraits and intentional crops. Avoid repetitive neutral standing poses. "
            "Adjacent comparable subject views change physical observation direction by at least 30 degrees; zoom or crop alone does not count. "
            "Execute lens_mm, projection, distance_m, height_m and perspective_effect visibly. Wide/ultra-wide shots require strong foreground scale and near/far depth, not distant flat coverage. Fisheye is FULL-FRAME: optical curvature cropped edge-to-edge to fill its rectangular cell, no black circular mask. "
            + product_lock
            + "\nUSER INTENT AND SETTING: " + brief
            + "\nREFERENCE ROLES: " + json.dumps(labels, ensure_ascii=False)
            + "\nSHARED VISUAL FACTS AND LIGHT: " + json.dumps(world, ensure_ascii=False)
            + "\n" + panel_text
            + "\nFINAL LAYOUT: " + delivery
            + "Every photograph keeps the assigned cell aspect ratio, even when a full-body view is planned. Never rearrange cells to fit a standing model.")


def editorial_planning_message(snapshot: dict, layout: dict) -> str:
    """新版导演使用简短独立契约，不再叠加历史电商/剧情分镜模板。"""
    options = snapshot.get("options") or {}
    panel = {"index": 1, "beat": "摄影瞬间", "story_purpose": "画面吸引点",
             "continuity_in": "", "continuity_out": "", "action_chain": "",
             "micro_expression": "", "weight_and_contact": "", "wardrobe_focus": "",
             "wardrobe_visibility": "", "composition": "", "lighting": "",
             "product_focus": "", "product_visibility": "", "product_emphasis": "dominant或supporting或none",
             "camera": {"lens_mm": "数字", "projection": "rectilinear或fisheye", "distance_m": "数字", "height_m": "数字",
                        "perspective_effect": "可见透视效果", "shot_size": "", "position": "", "visible_geometry": ""}}
    output = {**panel, "panel_cards": [panel]} if layout.get("explicit") and int(layout.get("panel_count") or 1) > 1 else panel
    schema = {"logline": "", "campaign_bible": {"identity": "", "wardrobe": "", "location": "",
              "product_direction": product_direction(options), "camera_policy": "", "camera_intensity": "1至5",
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
用户明确主推商品时，检查商品是否真正占据大多数格子的视觉重心，不能仅凭“模特穿着这条裤子”判通过。牛仔裤广告中，大量脸、上衣或鞋子主图挤占裤子主视觉应判弱。
用户要求广角/鱼眼张力时，观察实际近大远小、透视汇聚、贴地或俯冲位置、鱼眼的可见曲率；全是常规平视/常规透视即判弱，不能因为提示词写了14mm就通过。有意光学畸变不等于服装改版或背景漂移，保持身份和结构即可；不把张力纠正成平拍。
用户原始要求是约束，自动计划中的动作建议不是额外用户命令。若实际触碰部位、站姿或构图变化仍然符合用户目标且形成好照片，不因偏离自动建议而判弱；把视觉效果、情绪和多样性置于计划逐字服从之前。
逐格观察，不把计划里的角度或自评分当作证据。指出重复的具体格号：动作与身体线条是否雷同、脸是否统一呆滞、是否只是同机位裁切、是否全为平视远景、触碰是否真实、有无清晰的摄影主次与表情温差。
检查参考事实、身份、服装与空间连续性。不要为增加新意更换衣服、人物或地点。修复只针对弱格，保留已经成立的表情、裁切与机位。用户明确要求的克制/棚景优先，不因缺少剧情或街景而判弱。
"""
