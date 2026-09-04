"""Lookbook 故事广告模式的确定性参数与分镜契约。

本模块只负责不应交给 LLM 猜测的设置归一化，以及后台 agent 使用的
shot card 结构校验/提示词编译。故事理解和视觉规划仍由 main.py 的
CanvasLLM 链路负责。
"""

from __future__ import annotations

import re
import math
from typing import Any, Dict, Iterable, List, Optional


LOOKBOOK_STORY_MODE = "story-campaign"
LOOKBOOK_MAX_COUNT = 20
LOOKBOOK_DEFAULTS = {
    "count": 4,
    "aspect_ratio": "16:9",
    "resolution": "2k",
    "quality": "high",
}
LOOKBOOK_ASPECT_RATIOS = {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9"}
LOOKBOOK_RESOLUTIONS = {"1k", "2k", "4k"}
LOOKBOOK_QUALITIES = {"auto", "medium", "high"}
LOOKBOOK_SINGLE_FRAME_MODE = "single-frame"
LOOKBOOK_EDITORIAL_LAYOUT_MODE = "editorial-layout"
LOOKBOOK_LAYOUT_MAX_AXIS = 5
LOOKBOOK_LAYOUT_MAX_PANELS = 20
LOOKBOOK_LAYOUT_PRESETS = {
    "auto": (1, 1),
    "single-frame": (1, 1),
    "row-3": (1, 3),
    "column-3": (3, 1),
    "grid-2x2": (2, 2),
    "grid-3x3": (3, 3),
}
LOOKBOOK_LAYOUT_GAPS = {
    0: {"id": "none", "label": "无间距", "prompt": "zero internal gutters; adjacent panels touch directly"},
    1: {"id": "thin", "label": "窄间距", "prompt": "very thin, even internal gutters"},
    2: {"id": "standard", "label": "标准间距", "prompt": "moderate, consistent internal gutters"},
    3: {"id": "wide", "label": "宽间距", "prompt": "wide, deliberate editorial gutters"},
}
LOOKBOOK_OUTPUT_ASPECT_RATIOS = ("9:16", "2:3", "3:4", "1:1", "4:5", "5:4", "4:3", "3:2", "16:9", "21:9")

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


def normalize_lookbook_layout_selection(value: Any) -> Dict[str, Any]:
    """校验节点保存的布局选择；auto 继续允许从用户文案识别版式。"""
    raw = value if isinstance(value, dict) else {}
    preset_id = str(raw.get("preset_id") or raw.get("presetId") or "auto").strip().lower()
    if preset_id not in {*LOOKBOOK_LAYOUT_PRESETS, "custom"}:
        preset_id = "custom"
    preset = LOOKBOOK_LAYOUT_PRESETS.get(preset_id)
    try:
        rows = int(raw.get("rows") or (preset[0] if preset else 1))
        columns = int(raw.get("columns") or raw.get("cols") or (preset[1] if preset else 1))
        gap = int(raw.get("gap", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("Lookbook 布局行列或间距无效") from exc
    if preset:
        rows, columns = preset
    if not 1 <= rows <= LOOKBOOK_LAYOUT_MAX_AXIS or not 1 <= columns <= LOOKBOOK_LAYOUT_MAX_AXIS:
        raise ValueError(f"Lookbook 布局行列必须是 1 到 {LOOKBOOK_LAYOUT_MAX_AXIS}")
    panel_count = rows * columns
    if panel_count > LOOKBOOK_LAYOUT_MAX_PANELS:
        raise ValueError(f"Lookbook 单张拼图最多包含 {LOOKBOOK_LAYOUT_MAX_PANELS} 个画面")
    if gap not in LOOKBOOK_LAYOUT_GAPS:
        raise ValueError("Lookbook 图片间距只能是 0 到 3")
    return {
        "preset_id": preset_id,
        "rows": rows,
        "columns": columns,
        "panel_count": panel_count,
        "gap": gap,
        "gap_id": LOOKBOOK_LAYOUT_GAPS[gap]["id"],
        "gap_label": LOOKBOOK_LAYOUT_GAPS[gap]["label"],
    }


def _ratio_value(value: str) -> float:
    match = re.fullmatch(r"\s*(\d+)\s*:\s*(\d+)\s*", str(value or ""))
    if not match or int(match.group(2)) <= 0:
        return 1.0
    return int(match.group(1)) / int(match.group(2))


def lookbook_layout_output_aspect_ratio(cell_aspect_ratio: str, rows: int, columns: int) -> str:
    """把子画面比例和行列转换为图片 API 支持的最近最终画幅。"""
    target = _ratio_value(cell_aspect_ratio) * max(1, int(columns)) / max(1, int(rows))
    return min(
        LOOKBOOK_OUTPUT_ASPECT_RATIOS,
        key=lambda ratio: abs(math.log(max(target, 0.0001) / _ratio_value(ratio))),
    )


def _layout_grid_from_text(intent: Dict[str, Any]) -> Optional[tuple[int, int]]:
    source = str(intent.get("source") or intent.get("specification") or "")
    match = re.search(r"(\d{1,2}|[一二三四五六七八九十]+)\s*(?:宫格|格)", source)
    count = chinese_number(match.group(1)) if match else None
    known = {2: (1, 2), 3: (1, 3), 4: (2, 2), 6: (2, 3), 9: (3, 3), 12: (3, 4), 16: (4, 4), 20: (4, 5)}
    return known.get(count or 0)


def resolve_lookbook_layout_intent(
    text: str,
    selection: Any = None,
    cell_aspect_ratio: str = "16:9",
) -> Dict[str, Any]:
    """合并弹窗选择和自然语言版式，并补齐可执行的行列、间距和画幅。"""
    selected = normalize_lookbook_layout_selection(selection)
    preset_id = selected["preset_id"]
    if preset_id == "auto":
        intent = parse_lookbook_layout_intent(text)
        if not intent["explicit"]:
            return {**intent, "selection": selected, "cell_aspect_ratio": cell_aspect_ratio, "output_aspect_ratio": cell_aspect_ratio}
        inferred = _layout_grid_from_text(intent)
        if inferred:
            rows, columns = inferred
            selected = normalize_lookbook_layout_selection({"preset_id": "custom", "rows": rows, "columns": columns, "gap": selected["gap"]})
        else:
            return {**intent, "selection": selected, "cell_aspect_ratio": cell_aspect_ratio, "output_aspect_ratio": cell_aspect_ratio}
    elif preset_id == "single-frame":
        return {
            "mode": LOOKBOOK_SINGLE_FRAME_MODE,
            "explicit": False,
            "forced": True,
            "source": "layout-picker",
            "specification": "独立成片",
            "selection": selected,
            "cell_aspect_ratio": cell_aspect_ratio,
            "output_aspect_ratio": cell_aspect_ratio,
        }
    else:
        intent = {
            "mode": LOOKBOOK_EDITORIAL_LAYOUT_MODE,
            "explicit": True,
            "source": "layout-picker",
            "specification": f"{selected['rows']}x{selected['columns']} layout",
        }
    rows, columns = selected["rows"], selected["columns"]
    return {
        **intent,
        **selected,
        "selection": selected,
        "cell_aspect_ratio": cell_aspect_ratio,
        "output_aspect_ratio": lookbook_layout_output_aspect_ratio(cell_aspect_ratio, rows, columns),
        "reading_order": "left-to-right-top-to-bottom",
        "gap_prompt": LOOKBOOK_LAYOUT_GAPS[selected["gap"]]["prompt"],
        "specification": (
            f"{rows} rows x {columns} columns, exactly {selected['panel_count']} panels, "
            f"each panel targets {cell_aspect_ratio}, {selected['gap_label']}"
        ),
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
    """合并 Lookbook 设置。

    数量是故事交付的硬约束：只要用户在文本中明确写出数量，就优先于节点
    当前数量（包括旧版保存下来的 ``lookbook_manual_overrides.count``）。其余
    字段仍保持“手动控件 > 文本明确值 > AI 理解值 > 节点默认值”的兼容规则。
    """
    parsed = parse_explicit_lookbook_settings(text)
    ai_values = normalize_ai_lookbook_settings(ai_settings)
    node = dict(LOOKBOOK_DEFAULTS)
    node.update(node_settings or {})
    manual = dict(manual_overrides or {})
    values: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    warnings = list(parsed["warnings"])
    for key, default in LOOKBOOK_DEFAULTS.items():
        # 用户故事中的明确数量必须覆盖节点数量，避免节点曾经手动设为 1
        # 后，新的“生成 9 张”需求仍只提交一张。手动数量只作为文本未给出
        # 数量时的显式回退。
        if key == "count" and key in parsed["values"]:
            value, source = parsed["values"][key], "brief"
        elif key in manual and manual[key] not in (None, ""):
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
        subjects = card.get("subjects") if isinstance(card.get("subjects"), list) else []
        primary_subject = subjects[0] if subjects and isinstance(subjects[0], dict) else {}
        primary_action = str(primary_subject.get("action") or "").strip()
        primary_gaze = str(primary_subject.get("gaze") or "").strip()
        # 兼容旧快照，同时把表演字段显式带入逐镜头 prompt，避免模型退化成静态站姿。
        card["emotion_state"] = str(card.get("emotion_state") or "由当前事件触发的具体情绪，禁止统一微笑").strip()[:500]
        card["objective"] = str(card.get("objective") or card["story_purpose"]).strip()[:500]
        card["action_chain"] = str(
            card.get("action_chain")
            or f"承接：{card['continuity_in']}；执行：{primary_action or card['story_purpose']}；收束：{card['continuity_out']}"
        ).strip()[:900]
        card["micro_expression"] = str(
            card.get("micro_expression") or "视线先行，眼睑、嘴角、下颌或呼吸对事件产生一拍内的可见反应，避免无因果表情"
        ).strip()[:600]
        card["weight_and_contact"] = str(
            card.get("weight_and_contact")
            or f"至少一脚承重并产生真实接触，肩髋与动作方向形成自然不对称；{primary_gaze or '视线与动作目标保持一致'}，衣物/头发保留动作余势"
        ).strip()[:700]
        card["scene_region"] = str(
            card.get("scene_region")
            or card.get("location")
            or "从场景母图中选择能承载当前动作的真实可见区域"
        ).strip()[:700]
        card["scene_extension"] = str(
            card.get("scene_extension")
            or "只沿用场景母图可见的建筑结构、空间拓扑、材质、色彩、植被和光线，保守补全新机位露出的画外空间"
        ).strip()[:900]
        card["reference_ids"] = [str(item) for item in card.get("reference_ids") or [] if str(item).strip()]
        cards.append(card)
    return cards


def lookbook_shot_scale_contract(count: int) -> List[Dict[str, str]]:
    """为连续组图分配强制景别，避免场景参考把所有镜头吸成同一大全景。"""
    expected = max(1, min(LOOKBOOK_MAX_COUNT, int(count or 1)))
    if expected == 1:
        return [{
            "shot_size": "50mm environmental medium shot, frame the primary subject from knees or waist upward",
            "framing": "subject dominates the focal plane while enough environment remains to explain the event",
        }]
    opening = {
        "shot_size": "35mm environmental wide establishing shot",
        "framing": "the only wide master in the sequence; establish spatial geography and full-body blocking",
    }
    closing = {
        "shot_size": "50mm low-angle medium hero two-shot, knees-up",
        "framing": "resolve the relationship with both faces and body attitude readable; never widen back to a master shot",
    }
    interior = [
        {
            "shot_size": "50mm medium-full action shot, knees-to-head",
            "framing": "one primary performer owns the frame; background figures remain secondary and defocused",
        },
        {
            "shot_size": "65mm three-quarter medium portrait, thigh-up",
            "framing": "prioritize the second performer, torso rotation, hands and gaze; do not show the whole room",
        },
        {
            "shot_size": "50mm waist-up interactive two-shot",
            "framing": "both faces, joined action and eye-lines fill the frame; crop below the hips",
        },
        {
            "shot_size": "85mm tight action close-up, chest-up with hands entering frame",
            "framing": "capture decisive gesture, expression, fabric motion and contact; background becomes strong bokeh",
        },
        {
            "shot_size": "85mm tactile detail close-up",
            "framing": "show hands, material, footwear contact or another story-bearing detail without an environmental master",
        },
    ]
    return [opening, *[dict(interior[index % len(interior)]) for index in range(expected - 2)], closing]


def lookbook_story_rhythm_contract(count: int) -> List[Dict[str, Any]]:
    """把九宫格的“建立—转折—收束”规律扩展到任意 1～20 张。

    契约只规定每个位置承担的叙事功能和状态变化方向，不替用户编造具体
    情节。小数量使用专门结构；6 张以上按归一化位置分配，并把约 40%
    位置固定为事件转折锚点（9 张时恰好为第 4 张）。
    """
    expected = max(1, min(LOOKBOOK_MAX_COUNT, int(count or 1)))
    small_roles = {
        1: [("英雄收束", "在一个决定性瞬间同时交代人物目标、环境关系与产品价值", "进入动作高潮并停在仍有余势的完成状态")],
        2: [
            ("建立目标", "建立人物、环境、目标和初始状态", "明确下一张将发生的动作或事件"),
            ("结果收束", "呈现目标完成后的结果、情绪变化和产品证明", "形成可结束但仍有余韵的终局状态"),
        ],
        3: [
            ("建立目标", "建立人物、环境、目标和初始状态", "启动通向事件的动作"),
            ("事件转折", "让环境事件或人物选择改变动作、重心或注意力", "留下清晰反应并指向结果"),
            ("结果收束", "完成目标并让情绪与产品价值同时落地", "形成终局状态"),
        ],
        4: [
            ("建立目标", "建立空间、人物目标与初始状态", "准备启动动作"),
            ("行动启动", "以一个具体动作让故事开始移动", "把动作方向交给转折"),
            ("事件转折", "由环境或人物选择制造可见变化", "保留动作后果和情绪反应"),
            ("结果收束", "完成目标并以产品/人物关系收束", "形成终局状态"),
        ],
        5: [
            ("建立目标", "建立空间、人物目标与初始状态", "准备启动动作"),
            ("行动启动", "人物开始执行目标并产生第一处状态变化", "把运动方向交给事件"),
            ("事件转折", "环境事件或人物选择打断原有节奏", "留下明确失衡、发现或决定"),
            ("反应恢复", "人物回应转折并重新组织重心、目光和行动", "将恢复后的方向交给结尾"),
            ("结果收束", "目标、情绪和产品价值在同一结果中落地", "形成终局状态"),
        ],
    }
    if expected in small_roles:
        roles = small_roles[expected]
        return [
            {
                "index": index,
                "anchor": index in {1, expected} or role == "事件转折",
                "rhythm_role": role,
                "story_function": function,
                "transition_rule": transition,
                "energy": "凝聚" if expected == 1 else "建立" if index == 1 else "收束" if index == expected else "转折" if role == "事件转折" else "推进",
            }
            for index, (role, function, transition) in enumerate(roles, 1)
        ]

    turning_index = max(3, min(expected - 2, int(round(expected * 0.4))))
    contract: List[Dict[str, Any]] = []
    for index in range(1, expected + 1):
        if index == 1:
            role, function, transition, energy = "建立目标", "建立空间地理、人物目标、产品初始状态和行动方向", "以视线或准备动作明确下一张的运动方向", "建立"
        elif index == expected:
            role, function, transition, energy = "结果收束", "完成目标，让人物情绪、环境结果和产品价值同时落地", "形成可结束且有余韵的终局状态", "收束"
        elif index == turning_index:
            role, function, transition, energy = "事件转折", "由环境事件、阻力、发现或人物选择改变原动作", "把失衡、接触、发现或决定的直接后果交给下一张", "峰值"
        elif index == turning_index + 1:
            role, function, transition, energy = "即时反应", "表现转折后一拍内的目光、微表情、重心和接触反应", "反应必须驱动人物重新选择行动", "回落"
        elif index == expected - 1:
            role, function, transition, energy = "产品证明", "让产品材质、结构或穿着性能自然参与完成目标", "产品接触或动作结果直接导向终局", "再聚焦"
        elif index < turning_index:
            role, function, transition, energy = (
                ("行动启动", "以一个具体可见动作启动目标", "保持方向并增加下一张的动作幅度", "上升")
                if index == 2 else
                ("行动推进", "通过新的空间关系、接触或阻力推进同一目标", "保留动作余势并逼近事件转折", "上升")
            )
        else:
            role, function, transition, energy = (
                ("恢复掌控", "人物消化转折并重新组织目光、呼吸、重心和行动", "建立新的稳定方向", "恢复")
                if index == turning_index + 2 else
                ("行动兑现", "沿恢复后的选择继续推进，展示可见后果而非重复动作", "逐步压缩到产品证明和终局", "再上升")
            )
        contract.append({
            "index": index,
            "anchor": index in {1, turning_index, expected},
            "rhythm_role": role,
            "story_function": function,
            "transition_rule": transition,
            "energy": energy,
        })
    return contract


def enforce_lookbook_shot_scale_contract(cards: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    """把景别契约写回镜头卡；该锁优先于模型返回的泛化构图描述。"""
    plan = lookbook_shot_scale_contract(count)
    enforced: List[Dict[str, Any]] = []
    for position, source in enumerate(cards):
        card = dict(source)
        lock = dict(plan[position])
        camera = dict(card.get("camera") or {}) if isinstance(card.get("camera"), dict) else {}
        camera["shot_size"] = lock["shot_size"]
        camera["framing_lock"] = lock["framing"]
        card["camera"] = camera
        card["shot_scale_lock"] = lock
        enforced.append(card)
    return enforced


def enforce_lookbook_story_rhythm_contract(cards: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    """把确定性节奏角色写入镜头卡，防止 LLM 退化为同姿势换角度。"""
    rhythm = lookbook_story_rhythm_contract(count)
    enforced: List[Dict[str, Any]] = []
    for position, source in enumerate(cards):
        card = dict(source)
        lock = dict(rhythm[position])
        card["rhythm_lock"] = lock
        enforced.append(card)
    return enforced


def build_lookbook_series_quality_lock(count: int, layout_authorized: bool = False) -> str:
    """给独立多图系列注入与联合排版同等级的制作质量门。

    这段约束不授权模型绘制宫格，而是把“九宫格一次联合构图”带来的
    统一 art direction 转译为每个独立请求都必须执行的硬性检查。
    """
    expected = max(1, min(LOOKBOOK_MAX_COUNT, int(count or 1)))
    output_rule = (
        "This quality contract supports the authorized multi-panel layout: return one combined full-bleed layout image and do not fall back to separate files or an unrelated template. "
        if layout_authorized else
        "This is a quality contract only: output exactly one standalone full-bleed photograph and never draw a grid, collage, contact sheet, split screen or multiple panels. "
    )
    return (
        f"SERIES QUALITY ANCHOR ({expected} independent frames): treat this request as one frame from a single, top-tier fashion editorial campaign. "
        "The GLOBAL LOOKBOOK BIBLE is the shared production source of truth: keep the same person identity, denim/product geometry, wardrobe state, location geography, light direction, palette, lens language and photographic finish across every frame. "
        "Reach publication-grade quality in this single image—believable anatomy and hands, purposeful body mechanics, eyes locked to the external objective, event-triggered micro-expression, real weight/contact, tactile fabric construction, motivated depth and a decisive editorial composition. "
        "Use one clear action with a visible beginning or consequence; never substitute a generic model pose, stock smile, empty showroom, unrelated prop or decorative background. "
        "Before finalizing, self-check identity continuity, product fidelity, emotional cause, spatial continuity, shot-scale lock, lighting continuity and commercial finishing, then correct any weak item in this frame. "
        + output_rule
    )


def build_lookbook_shot_prompt(
    brief: str,
    bible: Any,
    card: Dict[str, Any],
    reference_labels: Optional[Iterable[str]] = None,
    wardrobe_mode: str = "",
    layout_intent: Optional[Dict[str, Any]] = None,
) -> str:
    """把全局视觉圣经和当前分镜卡编译成图片请求。"""
    index = int(card.get("index") or 1)
    layout_intent = layout_intent if isinstance(layout_intent, dict) else parse_lookbook_layout_intent(brief)
    references = " ".join(str(item).strip() for item in (reference_labels or []) if str(item).strip())
    bible_text = str(bible or "")
    if isinstance(bible, (dict, list)):
        import json

        bible_text = json.dumps(bible, ensure_ascii=False, separators=(",", ":"))
    raw_brief = str(brief or "").strip()
    if layout_intent["explicit"]:
        rows = int(layout_intent.get("rows") or 0)
        columns = int(layout_intent.get("columns") or 0)
        panel_count = int(layout_intent.get("panel_count") or 0)
        cell_ratio = str(layout_intent.get("cell_aspect_ratio") or "").strip()
        gap_prompt = str(layout_intent.get("gap_prompt") or "precise, coherent gutters").strip()
        structured_layout = (
            f"Divide the complete output into exactly {panel_count} panels arranged as {rows} rows x {columns} columns. "
            f"Each individual panel targets a {cell_ratio} aspect ratio; preserve that landscape/portrait orientation without stretching subjects. "
            "Read panels left to right, then top to bottom. "
            f"Use {gap_prompt}. Internal separators must be straight, aligned and visually consistent. "
            "The photographic panels must reach the outer edges of the final canvas: zero outer margin and zero surrounding background. "
            "ABSOLUTELY FORBIDDEN: presentation board, poster mockup, picture frame, mat board, mounting card, outer border, gray background outside the panels, drop shadow, floating sheet, rounded container or nested collage. "
            if rows and columns and panel_count and cell_ratio else ""
        )
        output_lock = (
            "EXPLICIT EDITORIAL-LAYOUT AUTHORIZATION: the user explicitly requested an arranged multi-image composition. "
            f"Execute only the requested layout specification ({layout_intent['specification']}) and make it feel art-directed for a top-tier fashion magazine: "
            + structured_layout
            + "precise visual hierarchy, intentional rhythm and scale contrast, coherent gutters/crops, disciplined negative space, seamless color continuity and publication-grade finishing. "
            "Every panel must advance the same narrative beat; never create a random collage, generic template, contact-sheet dump, repeated near-duplicates or ecommerce catalog tiles. "
            "Return exactly one combined image containing the complete panel layout, never separate image files for its panels. "
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
    series_quality_lock = build_lookbook_series_quality_lock(
        int(card.get("series_count") or 1),
        layout_authorized=bool(layout_intent.get("explicit")),
    )
    wardrobe_rule = (
        "IDENTITY-ONLY WARDROBE OVERRIDE: person reference images own face, hair, skin tone and body proportions only. "
        "Their photographed clothing is interview/source clothing and is forbidden in the final image. "
        "Use the scene-specific wardrobe defined by the GLOBAL LOOKBOOK BIBLE and CURRENT SHOT CARD, and keep that redesigned wardrobe continuous across the series. "
        if str(wardrobe_mode or "").strip().lower() == "scene_styled"
        else
        "WARDROBE REFERENCE LOCK: preserve the wardrobe and accessories visible in the supplied person references unless the user explicitly requests a change. "
    )
    return (
        output_lock
        + f"This is story frame {index}; execute only its assigned narrative beat and never add unrelated series frames. "
        f"USER STORY (narrative content only): {story_text}\n"
        f"GLOBAL LOOKBOOK BIBLE: {bible_text}\n"
        "CURRENT SHOT CARD: "
        + _compact_card(card)
        + "\nMANDATORY SHOT-SCALE LOCK: execute camera.shot_size and camera.framing_lock exactly. "
        "This lock overrides any wider framing implied by the scene reference or composition prose. "
        "The supplied full scene master owns the location identity, landmark geometry, spatial topology, facade/opening count and placement, materials, dominant colors, vegetation, terrain and motivated light. "
        "Select a real region visible in that master for CURRENT SHOT CARD.scene_region. The scene reference never owns the original camera position, crop or subject scale, but changing the camera never authorizes redesigning the place. "
        "When a new angle reveals off-frame space, outpaint it conservatively from visible structural evidence and CURRENT SHOT CARD.scene_extension. Do not invent a different side wall, door, window, fence, road, skyline, interior layout or landscaping; keep unseen areas simple and non-defining when the master provides no evidence. "
        "Any supplied derived scene crop is only a navigation detail from the same master, never a separate location and never permission to discard the complete master. "
        "Do not widen a medium or close shot merely to show the complete room or every spectator. "
        + "\nCONTINUITY RULE: preserve the incoming state, execute the current decisive action, and leave the outgoing state for the next frame. "
        + "RHYTHM LOCK: execute CURRENT SHOT CARD.rhythm_lock as the unique dramatic function of this frame. Do not repeat the previous frame's action, pose, gaze, composition or emotional state; make the outgoing state visibly prepare the next rhythm role. "
        + series_quality_lock
        + (f"REFERENCE LABELS: {references}\n" if references else "")
        + wardrobe_rule
        + "Preserve identity, product geometry, scene architecture and readable brand marks from the supplied references. "
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
            "scene_region",
            "scene_extension",
            "emotion_state",
            "objective",
            "action_chain",
            "micro_expression",
            "weight_and_contact",
            "subjects",
            "wardrobe_state",
            "prop_state",
            "camera",
            "composition",
            "lighting",
            "continuity_in",
            "continuity_out",
            "reference_ids",
            "shot_scale_lock",
            "rhythm_lock",
        )
        if card.get(key) not in (None, "", [], {})
    }
    return json.dumps(allowed, ensure_ascii=False, separators=(",", ":"))
