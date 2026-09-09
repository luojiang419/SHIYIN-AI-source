"""时尚广告完整导演：技能原文、输出/分格规划与生产提示词。

不复用通用人物故事的固定景别；每个 output 拥有独立 panel 列表。
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

STYLE_ID = "fashion-advertising"
DIRECTOR_VERSION = "fashion-director-1.2-full-1"
SKILL_RELATIVE_PATH = Path("skills/fashion-editorial-sequence-director/SKILL.md")


@lru_cache(maxsize=1)
def full_skill() -> str:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    # 缺失资源必须明确失败，不能悄悄降级为简版提示词。
    return (root / SKILL_RELATIVE_PATH).read_text(encoding="utf-8").strip()


def skill_signature() -> str:
    return DIRECTOR_VERSION + ":" + hashlib.sha256(full_skill().encode("utf-8")).hexdigest()


def is_fashion(options: dict) -> bool:
    style = options.get("lookbook_style") or {}
    style_id = style.get("id") if isinstance(style, dict) else ""
    if style_id == "auto":
        decision = options.get("lookbook_auto_decision")
        style_id = decision.get("selected_style_id") if isinstance(decision, dict) else ""
    return style_id == STYLE_ID


def panel_count(layout: dict) -> int:
    count = int(layout.get("panel_count") or 1) if layout.get("explicit") else 1
    if not 1 <= count <= 20:
        raise ValueError("时尚广告每张输出的镜头数量必须为 1–20")
    return count


DIRECTOR_EXECUTION = """NODE EXECUTION ADAPTER (delivery only): the complete skill below is the directing method.
User intent remains first. Separate subject identity, appearance, wardrobe, product, environment and photographic surface.
Select camera intensity, performance amplitude and facial emotion INDEPENDENTLY. An elegant relaxed expression does not require timid movement or a level camera.
Translate each requested style into concrete per-shot decisions: lens, height, tilt, crop, foreground, weight transfer, gaze, contact and fabric response. Do not merely repeat 'high quality' or 'editorial'.
If a product is named, make that exact product the campaign protagonist: state target, immutable construction, required visible regions, crop limits and each shot's product proof. Product fidelity alone is not product prominence.
For trousers show waist, hip fit, knee construction, hems and full leg silhouette across the series as appropriate; do not let face portraits displace the product. For other products derive appropriate coverage; never invent denim or a second person.
Film, if requested, must specify exposure, shadow density, highlight shoulder, color response, grain scale/density, halation and optical softness. No universal warm filter and no grain-overlay substitute for physical light.
Build and audit all panel shots jointly. Distinct panels advance the action or provide purposeful product/hero studies; do not demand a dramatic twist in every simple event. Hero poses may pause the action. Avoid generic catalog repetition without banning deliberate editorial poses.
For bold briefs plan genuinely daring viewpoints and gestures with credible anatomy. For restrained briefs honor restraint. Do not force one fixed nine-shot or two-person template.
Respect the requested output count and ratio. A grid is ONE output containing its own complete ordered panel sequence, not one shot repeated across cells. Independent images use an internal master contact sheet as a visual anchor, never an extra delivered output. Do not ask for additional approval or reconstruct unrequested files.
"""


def planning_message(snapshot: dict, layout: dict) -> str:
    options = snapshot.get("options") or {}
    outputs = int(snapshot.get("count") or 1)
    panels = panel_count(layout)
    schema = {
        "campaign_bible": {
            "reference_roles": [{"reference_index": 1, "roles": ["SUBJECT_IDENTITY", "WARDROBE"], "read": "", "ignore": ""}],
            "identity": "", "appearance": "", "wardrobe": "",
            "product_direction": {"target": "", "immutable_features": [], "coverage": [], "crop_limits": ""},
            "environment": "", "physical_light": "", "photographic_surface": "",
            "camera_intensity": 3, "performance_amplitude": "", "facial_emotion": "",
            "axis_map": "", "continuity_ledger": [], "hero_indices": [],
        },
        "shot_cards": [{"index": 1, "panel_cards": [{
            "index": 1, "beat": "", "story_purpose": "", "continuity_in": "", "continuity_out": "",
            "scene_region": "", "scene_extension": "", "objective": "", "action_chain": "",
            "micro_expression": "", "weight_and_contact": "", "wardrobe_state": "", "prop_state": "",
            "camera": {"shot_size": "", "angle": "", "height": "", "tilt": "", "framing": ""},
            "composition": "", "lighting": "", "product_focus": "", "product_visibility": "",
            "composition_risk": 3, "hero": False,
        }]}],
        "logline": "",
    }
    return (
        "完整应用以下导演技能。只返回严格 JSON，先做联合镜头设计和分层自检，再输出可执行方案。\n"
        + DIRECTOR_EXECUTION
        + f"\n交付数量：{outputs} 个输出，每个输出恰好 {panels} 个 panel_cards。"
        + "shot_cards 的 index 按输出编号；每个 panel_cards 内部 index 从 1 连续编号。"
        + "每格必须有自己的动作、机位、景别、构图、产品展示和前后状态；不套固定景别模板。"
        + "不要输出空字段或示例占位值；未指定产品时 product_direction.target 明确写整体造型。"
        + "构图风险与主视觉比例按原技能和用户需求审核；不得把优雅表情误解为小幅动作。"
        + "\n用户需求（完整保留）：" + str(options.get("instruction") or "根据提供的参考图创作时尚广告")
        + "\n版式与画幅：" + json.dumps({"layout": layout, "aspect_ratio": snapshot.get("aspect_ratio")}, ensure_ascii=False)
        + "\n参考事实：" + str(options.get("lookbook_reference_analysis") or "直接观察随请求提供的参考图")
        + "\n可选研究（仅辅助方法）：" + str(options.get("search_context") or "")[:8000]
        + "\nJSON 结构：" + json.dumps(schema, ensure_ascii=False)
    )


def normalize_plan(data: dict, output_count: int, layout: dict) -> tuple[dict, list[dict]]:
    """校验双层数量及拍摄决定，保留模型真实设计而非重写镜头。"""
    bible = data.get("campaign_bible")
    if not isinstance(bible, dict):
        raise ValueError("时尚广告缺少完整 campaign_bible")
    if not isinstance(bible.get("reference_roles"), list):
        raise ValueError("时尚广告 reference_roles 必须为列表；无参考图时使用空列表")
    for key in ("identity", "wardrobe", "product_direction", "environment",
                "physical_light", "photographic_surface", "camera_intensity", "performance_amplitude",
                "facial_emotion", "axis_map", "continuity_ledger"):
        if bible.get(key) in (None, "", [], {}):
            raise ValueError(f"时尚广告方案缺少 {key}")
    product = bible["product_direction"]
    if not isinstance(product, dict) or not product.get("target") or not product.get("coverage"):
        raise ValueError("时尚广告缺少商品主角与镜头覆盖计划")
    outputs = data.get("shot_cards")
    if not isinstance(outputs, list) or len(outputs) != output_count:
        raise ValueError(f"时尚广告必须规划 {output_count} 个输出")
    expected = panel_count(layout)
    cards = []
    for index, output in enumerate(outputs, 1):
        if not isinstance(output, dict) or output.get("index") != index:
            raise ValueError("时尚广告输出编号必须连续")
        panels = output.get("panel_cards")
        if not isinstance(panels, list) or len(panels) != expected:
            raise ValueError(f"第 {index} 个输出必须包含 {expected} 个独立镜头")
        for number, panel in enumerate(panels, 1):
            if not isinstance(panel, dict) or panel.get("index") != number:
                raise ValueError("时尚广告分格编号必须连续")
            for key in ("beat", "story_purpose", "continuity_in", "continuity_out", "action_chain",
                        "composition", "product_focus", "product_visibility", "lighting",
                        "micro_expression", "weight_and_contact"):
                if not str(panel.get(key) or "").strip():
                    raise ValueError(f"输出 {index} 镜头 {number} 缺少 {key}")
            camera = panel.get("camera")
            if not isinstance(camera, dict) or not camera.get("shot_size") or not camera.get("angle"):
                raise ValueError(f"输出 {index} 镜头 {number} 缺少具体景别/机位")
        # 外层摘要兼容已有任务列表/进度；内层才是生成镜头权威。
        first, last = panels[0], panels[-1]
        cards.append({**first, "index": index, "panel_cards": panels,
                      "continuity_out": last["continuity_out"],
                      "director_version": DIRECTOR_VERSION})
    return {**bible, "director_version": DIRECTOR_VERSION, "skill_signature": skill_signature()}, cards


def generation_prompt(brief: str, bible: Any, card: dict, labels: list[str], layout: dict) -> str:
    panels = card["panel_cards"]
    if layout.get("explicit"):
        delivery = (
            f"ONE completed contact sheet, exactly {len(panels)} distinct photographs, "
            f"{layout.get('rows')} rows x {layout.get('columns')} columns, read left to right then top to bottom. "
            f"Every cell has aspect ratio {layout.get('cell_aspect_ratio')}; {layout.get('gap_prompt')}. "
            "Straight regular grid; camera tilt belongs INSIDE photographs. Zero outer margin, no captions, numbers or nested grids. "
            "Execute ALL ordered panel shots, each with its own decisive moment and camera design. "
        )
    else:
        delivery = (
            "ONE standalone full-bleed photograph. Execute the assigned single panel only; no grid, captions or border. "
            f"Assigned campaign output {card['index']}: when an internal master contact sheet is supplied, "
            f"reconstruct its cell {card['index']} (row-major order) as this single full-resolution photograph. "
        )
    return (
        full_skill() + "\n" + DIRECTOR_EXECUTION
        + "\nUSER BRIEF (creative authority, including product, mood and style): " + brief
        + "\nREFERENCE ORDER AND ROLES: " + json.dumps(labels, ensure_ascii=False)
        + "\nJOINT CAMPAIGN BIBLE: " + json.dumps(bible, ensure_ascii=False, separators=(",", ":"))
        + "\nORDERED PANEL SHOTS: " + json.dumps(panels, ensure_ascii=False, separators=(",", ":"))
        + "\nFINAL DELIVERY AUTHORITY: " + delivery
        + "Preserve each planned lens, viewpoint, product coverage and intentional crop. No generic shot-scale or two-person template. "
        "Audit product prominence AND fidelity, identity, wardrobe, physical light, film response if requested, camera variety, "
        "expression versus body amplitude, contact mechanics, prop state and axis. Repair failed layers without neutralizing the art direction."
    )


FASHION_QA = """时尚广告专项验收：优先依据完整用户需求与联合导演方案，而非通用剧情模板。
逐格检查主推商品是否成为视觉主角、结构/颜色是否保真、关键部位和完整轮廓是否按计划可见。
检查机位、镜头、倾斜、偏心裁切、遮挡、动作幅度是否达到用户要求；不要把大胆构图纠正成居中平拍。
优雅轻松的神态与大胆动作可同时成立；有意设计的英雄姿态和产品细节可以成立，不要求每格有剧情转折。
如要求胶片，检查真实影调、高光过渡、颗粒与光学表现，不能仅有噪点或统一橙色滤镜。
按每个输出内部 panel_cards 的顺序审查事件、道具状态、动作轴线与镜头节奏；九格不能重复一个动作。
核对参考角色、人物身份、衣物、天气和物理光源。指出具体弱分格编号及需修复的层；weak_indices 仍使用输出图片编号。
"""
