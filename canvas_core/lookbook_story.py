"""Lookbook 故事广告模式的确定性参数与分镜契约。

本模块只负责不应交给 LLM 猜测的设置归一化，以及后台 agent 使用的
shot card 结构校验/提示词编译。故事理解和视觉规划仍由 main.py 的
CanvasLLM 链路负责。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


LOOKBOOK_STORY_MODE = "story-campaign"
LOOKBOOK_MAX_COUNT = 20
LOOKBOOK_DEFAULTS = {
    "count": 4,
    "aspect_ratio": "16:9",
    "resolution": "2k",
    "quality": "high",
}
LOOKBOOK_ASPECT_RATIOS = {"1:1", "2:3", "3:4", "4:3", "4:5", "9:16", "16:9"}
LOOKBOOK_RESOLUTIONS = {"1k", "2k", "4k"}
LOOKBOOK_QUALITIES = {"auto", "medium", "high"}
LOOKBOOK_SINGLE_FRAME_MODE = "single-frame"
LOOKBOOK_EDITORIAL_LAYOUT_MODE = "editorial-layout"

_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}

_LOOKBOOK_LAYOUT_PATTERN = re.compile(
    r"(?P<layout>"
    r"(?:\d{1,2}|[一二三四五六七八九十百]+)\s*(?:宫格|格(?:拼图|拼贴|排版))"
    r"|(?:四格|六格|九格|多格)\s*(?:拼图|拼贴|排版)?"
    r"|拼图|拼贴|照片墙|联系表|contact\s*sheet|collage|split[-\s]?screen"
    r"|(?:杂志|画册|海报|editorial|magazine)\s*(?:排版|版式|layout)"
    r"|(?:排版|版式)\s*(?:拼图|拼贴|组合|设计|样式|页面)"
    r")",
    flags=re.IGNORECASE,
)
_LOOKBOOK_LAYOUT_NEGATION = re.compile(r"(?:不要|禁止|避免|无需|不需要|拒绝|不能|不得|严禁|no|without)", re.IGNORECASE)
_LOOKBOOK_LAYOUT_POSITIVE = re.compile(r"(?:生成|制作|创作|需要|采用|使用|请|做成|呈现|要求|make|create|use)", re.IGNORECASE)


def chinese_number(value: str) -> Optional[int]:
    """解析常见中文整数，如“二十”“十二”“两张”。"""
    text = str(value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if not all(char in _CN_DIGITS or char in _CN_UNITS for char in text):
        return None
    total = 0
    section = 0
    number = 0
    for char in text:
        if char in _CN_DIGITS:
            number = _CN_DIGITS[char]
            continue
        unit = _CN_UNITS[char]
        if number == 0:
            number = 1
        section += number * unit
        number = 0
    return total + section + number


def _setting(value: Any, source: str, confidence: str = "explicit") -> Dict[str, Any]:
    return {"value": value, "source": source, "confidence": confidence}


def parse_lookbook_layout_intent(text: str) -> Dict[str, Any]:
    """只在用户明确要求排版/拼图时授权多画面画布。

    诸如“不要九宫格”这样的负向要求不会误触发授权。未命中时始终采用
    单幅 full-bleed 输出，避免模型把系列数量误解为单张图片里的格子数。
    """
    raw = str(text or "").strip()
    matches = []
    for match in _LOOKBOOK_LAYOUT_PATTERN.finditer(raw):
        clause_start = max(raw.rfind(mark, 0, match.start()) for mark in "，。！？,.;；\n") + 1
        prefix = raw[clause_start : match.start()]
        last_negation = list(_LOOKBOOK_LAYOUT_NEGATION.finditer(prefix))
        last_positive = list(_LOOKBOOK_LAYOUT_POSITIVE.finditer(prefix))
        if last_negation and (not last_positive or last_negation[-1].start() > last_positive[-1].start()):
            continue
        matches.append(match)
    if not matches:
        return {
            "mode": LOOKBOOK_SINGLE_FRAME_MODE,
            "explicit": False,
            "source": "",
            "specification": "",
        }
    match = matches[-1]
    source = raw[match.start() : match.end()].strip()
    return {
        "mode": LOOKBOOK_EDITORIAL_LAYOUT_MODE,
        "explicit": True,
        "source": source,
        "specification": source[:120],
    }


def parse_explicit_lookbook_settings(text: str) -> Dict[str, Any]:
    """从用户文本中提取高置信度的生成设置。

    只提取明确字段，不负责理解故事，也不把 LLM 的猜测当作参数。
    返回值中的 ``explicit`` 记录字段来源，便于前端解释和审计。
    """
    raw = str(text or "").strip()
    explicit: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []

    count_matches = list(
        re.finditer(
            r"(?P<value>\d{1,3}|[零〇一二两三四五六七八九十百千]+)\s*"
            r"(?P<unit>张|幅|帧|张图|个镜头|个画面|镜头|画面)",
            raw,
            flags=re.IGNORECASE,
        )
    )
    if count_matches:
        match = count_matches[-1]
        count = chinese_number(match.group("value"))
        if count is not None:
            explicit["count"] = _setting(count, raw[match.start() : match.end()])

    ratio_match = None
    for ratio_match in re.finditer(r"(?P<w>\d{1,2})\s*[:：比/]\s*(?P<h>\d{1,2})", raw):
        pass
    if ratio_match:
        ratio = f"{ratio_match.group('w')}:{ratio_match.group('h')}"
        if ratio in LOOKBOOK_ASPECT_RATIOS:
            explicit["aspect_ratio"] = _setting(ratio, raw[ratio_match.start() : ratio_match.end()])
        else:
            warnings.append(f"文本中的画幅 {ratio} 暂不支持")
    elif re.search(r"竖屏|竖版|手机屏", raw):
        explicit["aspect_ratio"] = _setting("9:16", "竖屏")
    elif re.search(r"横屏|横版|宽屏", raw):
        explicit["aspect_ratio"] = _setting("16:9", "横屏")
    elif re.search(r"方形|正方形", raw):
        explicit["aspect_ratio"] = _setting("1:1", "方形")

    resolution_matches = list(re.finditer(r"(?P<value>[124])\s*[kK](?:分辨率|画质)?", raw))
    if resolution_matches:
        match = resolution_matches[-1]
        resolution = f"{match.group('value')}k"
        explicit["resolution"] = _setting(resolution, raw[match.start() : match.end()])
    elif re.search(r"超清|超高清|顶级分辨率", raw):
        explicit["resolution"] = _setting("4k", "超清")
    elif re.search(r"高清|高分辨率", raw):
        explicit["resolution"] = _setting("2k", "高清")

    if re.search(r"快速出图|快速生成|低质量|草图", raw):
        explicit["quality"] = _setting("medium", "快速出图")
    elif re.search(r"高质量|最高质量|精细出图|顶级画质", raw):
        explicit["quality"] = _setting("high", "高质量")
    elif re.search(r"自动质量|质量自动", raw):
        explicit["quality"] = _setting("auto", "自动质量")

    return {
        "raw": raw,
        "explicit": explicit,
        "values": {key: item["value"] for key, item in explicit.items()},
        "warnings": warnings,
        "layout_intent": parse_lookbook_layout_intent(raw),
    }


def normalize_ai_lookbook_settings(value: Any) -> Dict[str, Any]:
    """归一化 AI 对未明确生成参数的理解结果。"""
    if not isinstance(value, dict):
        return {}
    source = value.get("settings") if isinstance(value.get("settings"), dict) else value
    normalized: Dict[str, Any] = {}
    count = source.get("count")
    try:
        count = int(count) if count not in (None, "") else None
    except (TypeError, ValueError):
        count = None
    if count is not None and 1 <= count <= LOOKBOOK_MAX_COUNT:
        normalized["count"] = count

    ratio = str(source.get("aspect_ratio") or source.get("aspect") or "").strip().lower()
    ratio = ratio.replace("：", ":").replace("比", ":").replace("/", ":")
    if ratio in {"横版", "横屏", "电影宽幅", "宽屏"}:
        ratio = "16:9"
    elif ratio in {"竖版", "竖屏", "手机屏", "社媒竖版"}:
        ratio = "9:16"
    elif ratio in {"方形", "正方形"}:
        ratio = "1:1"
    if ratio in LOOKBOOK_ASPECT_RATIOS:
        normalized["aspect_ratio"] = ratio

    resolution = str(source.get("resolution") or source.get("res") or "").strip().lower()
    if resolution in {"高清", "高分辨率", "hd"}:
        resolution = "2k"
    elif resolution in {"超清", "超高清", "uhd", "顶级"}:
        resolution = "4k"
    match = re.search(r"([124])\s*k", resolution)
    if match:
        resolution = f"{match.group(1)}k"
    if resolution in LOOKBOOK_RESOLUTIONS:
        normalized["resolution"] = resolution

    quality = str(source.get("quality") or "").strip().lower()
    if quality in {"快速", "快速出图", "草图", "draft", "standard"}:
        quality = "medium"
    elif quality in {"高质量", "最高", "精细", "premium", "best"}:
        quality = "high"
    elif quality in LOOKBOOK_QUALITIES:
        normalized["quality"] = quality
    if quality in LOOKBOOK_QUALITIES:
        normalized["quality"] = quality
    if source.get("delivery_type"):
        normalized["delivery_type"] = str(source["delivery_type"]).strip()[:80]
    if source.get("rationale"):
        normalized["rationale"] = str(source["rationale"]).strip()[:800]
    try:
        if source.get("confidence") is not None:
            normalized["confidence"] = max(0.0, min(1.0, float(source["confidence"])))
    except (TypeError, ValueError):
        pass
    return normalized


def resolve_lookbook_settings(
    text: str,
    node_settings: Optional[Dict[str, Any]] = None,
    manual_overrides: Optional[Dict[str, Any]] = None,
    ai_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """按“手动控件 > 文本明确值 > AI 理解值 > 节点默认值”合并设置。"""
    parsed = parse_explicit_lookbook_settings(text)
    ai_values = normalize_ai_lookbook_settings(ai_settings)
    node = dict(LOOKBOOK_DEFAULTS)
    node.update(node_settings or {})
    manual = dict(manual_overrides or {})
    values: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    warnings = list(parsed["warnings"])
    for key, default in LOOKBOOK_DEFAULTS.items():
        if key in manual and manual[key] not in (None, ""):
            value, source = manual[key], "manual"
        elif key in parsed["values"]:
            value, source = parsed["values"][key], "brief"
        elif key in ai_values:
            value, source = ai_values[key], "ai"
        else:
            value, source = node.get(key, default), "node"
        values[key] = value
        sources[key] = source

    try:
        values["count"] = int(values["count"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Lookbook 生成数量必须是整数") from exc
    if not 1 <= values["count"] <= LOOKBOOK_MAX_COUNT:
        raise ValueError(f"故事 Lookbook 生成数量必须是 1 到 {LOOKBOOK_MAX_COUNT}")
    values["aspect_ratio"] = str(values["aspect_ratio"] or "").strip().lower().replace("：", ":")
    if values["aspect_ratio"] not in LOOKBOOK_ASPECT_RATIOS:
        raise ValueError("Lookbook 画幅不支持")
    values["resolution"] = str(values["resolution"] or "").strip().lower()
    if values["resolution"] not in LOOKBOOK_RESOLUTIONS:
        raise ValueError("Lookbook 分辨率只能是 1k、2k 或 4k")
    values["quality"] = str(values["quality"] or "").strip().lower()
    if values["quality"] not in LOOKBOOK_QUALITIES:
        raise ValueError("Lookbook 质量只能是 auto、medium 或 high")
    if values["count"] > 8:
        warnings.append("超过 8 张时将按单镜头任务受控并发生成，并保持镜头顺序")
    return {
        "values": values,
        "sources": sources,
        "warnings": warnings,
        "parsed": parsed,
        "ai": ai_values,
        "layout_intent": parsed["layout_intent"],
    }


SHOT_CARD_REQUIRED_FIELDS = ("index", "beat", "story_purpose", "continuity_in", "continuity_out")


def normalize_lookbook_shot_cards(value: Any, count: int) -> List[Dict[str, Any]]:
    """校验并标准化 AI 返回的分镜卡，禁止数量或序号静默漂移。"""
    try:
        expected = int(count)
    except (TypeError, ValueError) as exc:
        raise ValueError("分镜数量无效") from exc
    if not 1 <= expected <= LOOKBOOK_MAX_COUNT:
        raise ValueError(f"分镜数量必须是 1 到 {LOOKBOOK_MAX_COUNT}")
    if not isinstance(value, list) or len(value) != expected:
        actual = len(value) if isinstance(value, list) else 0
        raise ValueError(f"AI 分镜数量不一致：要求 {expected} 张，实际 {actual} 张")
    cards: List[Dict[str, Any]] = []
    for position, item in enumerate(value, 1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {position} 张分镜不是对象")
        card = dict(item)
        try:
            index = int(card.get("index", position))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"第 {position} 张分镜序号无效") from exc
        if index != position:
            raise ValueError(f"分镜序号必须连续：第 {position} 张收到 {index}")
        for field in SHOT_CARD_REQUIRED_FIELDS[1:]:
            if not str(card.get(field) or "").strip():
                raise ValueError(f"第 {position} 张分镜缺少 {field}")
        card["index"] = index
        card["beat"] = str(card["beat"]).strip()
        card["story_purpose"] = str(card["story_purpose"]).strip()
        card["continuity_in"] = str(card["continuity_in"]).strip()
        card["continuity_out"] = str(card["continuity_out"]).strip()
        card["reference_ids"] = [str(item) for item in card.get("reference_ids") or [] if str(item).strip()]
        cards.append(card)
    return cards


def build_lookbook_shot_prompt(
    brief: str,
    bible: Any,
    card: Dict[str, Any],
    reference_labels: Optional[Iterable[str]] = None,
) -> str:
    """把全局视觉圣经和当前分镜卡编译成图片请求。"""
    index = int(card.get("index") or 1)
    layout_intent = parse_lookbook_layout_intent(brief)
    references = " ".join(str(item).strip() for item in (reference_labels or []) if str(item).strip())
    bible_text = str(bible or "")
    if isinstance(bible, (dict, list)):
        import json

        bible_text = json.dumps(bible, ensure_ascii=False, separators=(",", ":"))
    raw_brief = str(brief or "").strip()
    if layout_intent["explicit"]:
        output_lock = (
            "EXPLICIT EDITORIAL-LAYOUT AUTHORIZATION: the user explicitly requested an arranged multi-image composition. "
            f"Execute only the requested layout specification ({layout_intent['specification']}) and make it feel art-directed for a top-tier fashion magazine: "
            "precise visual hierarchy, intentional rhythm and scale contrast, coherent gutters/crops, disciplined negative space, seamless color continuity and publication-grade finishing. "
            "Every panel must advance the same narrative beat; never create a random collage, generic template, contact-sheet dump, repeated near-duplicates or ecommerce catalog tiles. "
        )
        story_text = raw_brief
    else:
        output_lock = (
            "SINGLE-FRAME HARD STOP: render exactly one standalone full-bleed fashion editorial photograph on the final canvas. "
            "The requested series quantity is fulfilled by separate API calls; never visualize that quantity by dividing this canvas. "
            "Do not create a contact sheet, diptych, triptych, grid, collage, split screen, storyboard layout, border, gutter or multiple panels. "
        )
        story_text = re.sub(
            r"(?:生成|制作|创作|输出|做)?\s*(?:\d{1,3}|[零〇一二两三四五六七八九十百千]+)\s*(?:张图?|幅|帧|个镜头|个画面|镜头|画面)",
            "",
            raw_brief,
            flags=re.IGNORECASE,
        ).strip(" ，,。;；") or raw_brief
    return (
        output_lock
        + f"This is story frame {index}; execute only its assigned narrative beat and never add unrelated series frames. "
        f"USER STORY (narrative content only): {story_text}\n"
        f"GLOBAL LOOKBOOK BIBLE: {bible_text}\n"
        "CURRENT SHOT CARD: "
        + _compact_card(card)
        + "\nCONTINUITY RULE: preserve the incoming state, execute the current decisive action, and leave the outgoing state for the next frame. "
        + (f"REFERENCE LABELS: {references}\n" if references else "")
        + "Preserve identity, wardrobe, product geometry, scene architecture and readable brand marks from the supplied references. "
        "Create a consequential observed moment with character objective, tension or emotional change, not a posed ecommerce listing. "
        "Reject white-seamless catalog staging, centered SKU presentation, mannequin gestures, hands-on-hips posing, stock smiles and decorative props without story function. "
        "Use motivated camera/light choices and do not add unrelated people, products, text or watermarks."
    )


def _compact_card(card: Dict[str, Any]) -> str:
    import json

    allowed = {
        key: card.get(key)
        for key in (
            "index",
            "beat",
            "story_purpose",
            "time_position",
            "location",
            "subjects",
            "wardrobe_state",
            "prop_state",
            "camera",
            "composition",
            "lighting",
            "continuity_in",
            "continuity_out",
            "reference_ids",
        )
        if card.get(key) not in (None, "", [], {})
    }
    return json.dumps(allowed, ensure_ascii=False, separators=(",", ":"))
