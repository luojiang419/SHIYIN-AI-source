from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


POSE_REPLICATE_TEMPLATE_ID = "pose-replicate.v2.3"
POSE_REPLICATE_LOCALE = "zh-CN"
POSE_REPLICATE_MODES = {"depth", "skeleton"}
POSE_REPLICATE_OUTPUT_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4"}

SCENARIOS = {
    (False, False): "base-wardrobe",
    (True, False): "model-wardrobe",
    (False, True): "base-wardrobe-scene",
    (True, True): "model-full-look-scene",
}

ROLE_LABELS = {
    "pose_reference": "动作参考",
    "control_map": "深度图或骨架图",
    "target_image": "目标服装",
    "model_subject": "模特主体",
    "scene": "场景",
}

_ROLE_OVERRIDE_PATTERN = re.compile(
    r"(?:图\s*[1-5]|参考图\s*[1-5]).{0,32}(?:重新编号|交换|身份来源|角色定义|控制权|作为唯一|改为.*来源)",
    re.IGNORECASE,
)
_SYSTEM_OVERRIDE_PATTERN = re.compile(r"(?:忽略|覆盖|绕过|取消).{0,24}(?:硬约束|优先级|系统|模板|禁止事项)")
_IDENTITY_CHANGE_PATTERN = re.compile(r"(?:改变|替换|重绘|换掉).{0,16}(?:脸|五官|身份|肤色|年龄)")
_SCENE_CHANGE_PATTERN = re.compile(
    r"(?:(?:更换|替换|改成|改为|重建).{0,16}(?:背景|场景|环境)|(?:背景|场景|环境).{0,16}(?:更换|替换|改成|改为|重建))"
)


class PoseReplicatePromptError(ValueError):
    pass


@dataclass(frozen=True)
class PoseReplicatePrompt:
    final_prompt: str
    template_id: str
    template_variant: str
    scenario_id: str
    control_mode: str
    output_aspect_ratio: str
    prompt_source: str
    reference_order: tuple[dict[str, Any], ...]
    user_instruction_original: str
    normalized_instruction: str

    def audit_payload(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_variant": self.template_variant,
            "scenario_id": self.scenario_id,
            "control_mode": self.control_mode,
            "output_aspect_ratio": self.output_aspect_ratio,
            "prompt_source": self.prompt_source,
            "reference_order": [dict(item) for item in self.reference_order],
            "user_instruction_original": self.user_instruction_original,
            "normalized_instruction": self.normalized_instruction,
            "final_prompt": self.final_prompt,
        }


def scenario_id(has_model_subject: bool, has_scene: bool) -> str:
    return SCENARIOS[(bool(has_model_subject), bool(has_scene))]


def reference_order(control_mode: str, has_model_subject: bool, has_scene: bool) -> tuple[dict[str, Any], ...]:
    mode = str(control_mode or "").strip().lower()
    if mode not in POSE_REPLICATE_MODES:
        raise PoseReplicatePromptError("一键复刻模式只支持 depth 或 skeleton")
    roles = (
        ["model_subject", "pose_reference", "control_map", "target_image"]
        if has_model_subject
        else ["pose_reference", "control_map", "target_image"]
    )
    if has_scene:
        roles.append("scene")
    return tuple(
        {
            "index": index,
            "role": role,
            "label": "深度图" if role == "control_map" and mode == "depth" else (
                "骨架图" if role == "control_map" else ROLE_LABELS[role]
            ),
        }
        for index, role in enumerate(roles, 1)
    )


def normalize_instruction_payload(payload: Mapping[str, Any], *, has_scene: bool) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise PoseReplicatePromptError("AI 助手返回的一键复刻增量不是对象")
    normalized = _clean_text(payload.get("normalized_instruction"), 4000)
    if not normalized:
        raise PoseReplicatePromptError("AI 助手没有返回 normalized_instruction")
    combined = "\n".join(
        [normalized]
        + _clean_list(payload.get("allowed_changes"))
        + _clean_list(payload.get("must_preserve"))
        + _clean_list(payload.get("material_and_fit"))
        + _clean_list(payload.get("scene_adjustments"))
        + _clean_list(payload.get("negative_constraints"))
    )
    if _ROLE_OVERRIDE_PATTERN.search(combined) or _SYSTEM_OVERRIDE_PATTERN.search(combined):
        raise PoseReplicatePromptError("AI 助手增量试图改变固定参考角色或硬约束")
    if _IDENTITY_CHANGE_PATTERN.search(combined):
        raise PoseReplicatePromptError("AI 助手增量与人物身份保留约束冲突")
    scene_adjustments = _clean_list(payload.get("scene_adjustments"))
    if not has_scene and (scene_adjustments or _SCENE_CHANGE_PATTERN.search(normalized)):
        raise PoseReplicatePromptError("未连接场景输入时不能要求更换场景")
    return {
        "intent_summary": _clean_text(payload.get("intent_summary"), 1200),
        "allowed_changes": _clean_list(payload.get("allowed_changes")),
        "must_preserve": _clean_list(payload.get("must_preserve")),
        "material_and_fit": _clean_list(payload.get("material_and_fit")),
        "scene_adjustments": scene_adjustments,
        "negative_constraints": _clean_list(payload.get("negative_constraints")),
        "normalized_instruction": normalized,
    }


def compile_pose_replicate_prompt(
    control_mode: str,
    *,
    has_model_subject: bool = False,
    has_scene: bool = False,
    output_aspect_ratio: str = "16:9",
    user_instruction: str = "",
    normalized_instruction: Mapping[str, Any] | None = None,
) -> PoseReplicatePrompt:
    mode = str(control_mode or "").strip().lower()
    output_ratio = str(output_aspect_ratio or "").strip()
    if output_ratio not in POSE_REPLICATE_OUTPUT_RATIOS:
        raise PoseReplicatePromptError("一键复刻输出画幅不受支持")
    order = reference_order(mode, has_model_subject, has_scene)
    scenario = scenario_id(has_model_subject, has_scene)
    original = _clean_text(user_instruction, 5000)
    normalized = None
    if original:
        if normalized_instruction is None:
            raise PoseReplicatePromptError("有用户补充要求时必须先完成 AI 助手规范化")
        normalized = normalize_instruction_payload(normalized_instruction, has_scene=has_scene)
    elif normalized_instruction:
        raise PoseReplicatePromptError("没有用户补充要求时不得注入 AI 助手增量")

    parts = [
        _output_contract(output_ratio),
        _base_instruction(has_model_subject, has_scene),
        _reference_contract(mode, order, has_model_subject, has_scene),
        _control_contract(mode),
        _scenario_contract(has_model_subject, has_scene, order),
        _fold_contract(),
        _occlusion_contract(has_model_subject),
        _priority_contract(has_model_subject, has_scene, order, output_ratio),
    ]
    if normalized:
        parts.append(_user_increment_contract(normalized))
    parts.extend([_negative_contract(), _final_output_check(output_ratio)])
    prompt = "\n\n".join(part.strip() for part in parts if part.strip())
    return PoseReplicatePrompt(
        final_prompt=prompt,
        template_id=POSE_REPLICATE_TEMPLATE_ID,
        template_variant=f"{POSE_REPLICATE_TEMPLATE_ID}.{scenario}.{mode}.{POSE_REPLICATE_LOCALE}",
        scenario_id=scenario,
        control_mode=mode,
        output_aspect_ratio=output_ratio,
        prompt_source="assistant-merged" if normalized else "fixed-template",
        reference_order=order,
        user_instruction_original=original,
        normalized_instruction=str((normalized or {}).get("normalized_instruction") or ""),
    )


def _clean_text(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit]


def _clean_list(value: Any, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value[:limit] if (text := _clean_text(item, 600))]


def _base_instruction(has_model_subject: bool, has_scene: bool) -> str:
    if has_model_subject and has_scene:
        return "请以图1模特主体为唯一人物编辑底图完成高保真跨图复刻：保留其身份与身体，换上目标图完整服装，严格应用动作参考的姿势结构，并将最终人物自然置入场景图。"
    if has_model_subject:
        return "请以图1模特主体为唯一人物编辑底图完成高保真人物与服装迁移：保留其身份与身体，换上目标图服装，并严格复刻动作参考的姿势、主体相对构图和原场景。"
    if has_scene:
        return "请以动作参考中的人物身份与姿势为基础，换上目标图服装，并将人物自然置入场景图；不得让场景图改变人物身份。"
    return "请以图1为唯一编辑底图进行高保真服装替换：保留原人物、原姿势、原配饰、原背景和主体相对构图，只替换与图3目标服装对应的服装区域。"


def _reference_contract(mode: str, order: tuple[dict[str, Any], ...], has_model: bool, has_scene: bool) -> str:
    index = {item["role"]: item["index"] for item in order}
    lines = [
        "【参考图用途】",
        f"图{index['pose_reference']}（动作参考）：控制姿势、动作、身体重心、主体相对构图与空间遮挡；原图裁切只作为内容取舍参考，不得覆盖最终输出画幅。",
        f"图{index['control_map']}（{'人物深度图' if mode == 'depth' else '人物骨架图'}）：只控制人物空间结构与姿势，不提供身份、服装款式、纹理或背景。",
        f"图{index['target_image']}（目标图）：服装设计的唯一来源，准确保留类别、版型、领口、肩袖、门襟、口袋、下摆、面料、颜色、图案、缝线、装饰、松量、厚度与垂坠。",
    ]
    if has_model:
        lines.append(f"图{index['model_subject']}（模特主体）：最终人物身份、面部、肤色、发型和身体比例的唯一来源，不提供姿势、服装或场景。")
    if has_scene:
        lines.append(f"图{index['scene']}（场景）：最终环境、背景结构、透视、环境光和空间接触的唯一来源，不提供人物身份、姿势或服装。")
    lines.append("任何参考图都不得越权提供其他角色的内容，也不得交换或重新解释上述编号。")
    return "\n".join(lines)


def _control_contract(mode: str) -> str:
    if mode == "depth":
        return "【深度控制】深度图中白色表示靠近镜头、灰色表示中间距离、黑色背景不含场景信息。用它锁定头肩躯干、双臂、双手、人物体积、透视和前后遮挡；不得照搬原服装外轮廓或表面。"
    return "【骨架控制】骨架图只用于锁定关节位置、肢体方向、左右语义、身体重心与动作节奏。结合动作参考恢复真实人体体积与遮挡；不得把骨架线、节点颜色或空白背景画入结果。"


def _scenario_contract(has_model: bool, has_scene: bool, order: tuple[dict[str, Any], ...]) -> str:
    index = {item["role"]: item["index"] for item in order}
    if has_model and has_scene:
        return f"【组合任务】将图{index['target_image']}的完整服装造型真实穿到图{index['model_subject']}人物身上，身体动作严格遵循图{index['pose_reference']}，最终置入图{index['scene']}场景。保留模特主体身份，不复制目标图人物或动作参考人物的脸、身体与背景。"
    if has_model:
        return f"【组合任务】将图{index['target_image']}服装真实穿到图{index['model_subject']}人物身上，动作、机位、主体相对构图与背景严格遵循图{index['pose_reference']}。保留模特主体身份，不复制目标图或动作参考中的人物身份。"
    if has_scene:
        return f"【组合任务】保留图{index['pose_reference']}人物身份与动作，换上图{index['target_image']}服装，并自然进入图{index['scene']}场景。人物尺度、脚底接触、透视、环境光与投影必须适配新场景。"
    return f"【具体换装任务】完整移除图{index['pose_reference']}中与目标服装对应的原服装，将图{index['target_image']}服装真实、自然地穿在原人物身上。新版型可按目标服装合理改变外轮廓，但不得改变人物身体姿势、比例、身份、配饰、背景和主体相对构图。"


def _fold_contract() -> str:
    return "【自然褶皱与受力】高保真复刻动作参考中由肩线牵拉、腋下挤压、肘部弯曲、胸腹与腰部堆叠、袖口收束和下摆垂坠形成的受力链与褶皱拓扑，包括位置、走向、层次、拉伸、堆叠及前后深度关系。动作参考只提供受力依据；最终褶皱的数量、幅度、锐利度、厚度与垂坠必须根据目标服装的材质、版型、松量和结构重新计算，禁止把旧服装纹理、剪裁、轮廓或表面褶皱机械粘贴到新服装上。"


def _occlusion_contract(has_model: bool) -> str:
    identity_source = "模特主体" if has_model else "动作参考人物"
    return f"【遮挡与边缘】严格保持头发、面部、双手、手指、现有配饰与服装之间的正确前后关系。新袖口自然衔接手腕，不覆盖或吞没手指；服装边缘不得出现发光、灰边、重影、破洞或抠图痕迹。保留{identity_source}的真实皮肤和发丝细节。"


def _priority_contract(has_model: bool, has_scene: bool, order: tuple[dict[str, Any], ...], output_ratio: str) -> str:
    index = {item["role"]: item["index"] for item in order}
    identity = f"图{index['model_subject']}" if has_model else f"图{index['pose_reference']}"
    scene = f"图{index['scene']}" if has_scene else f"图{index['pose_reference']}"
    return "\n".join(
        [
            "【执行优先级】",
            f"1. {identity}控制最终人物身份、面部和身体归属。",
            f"2. 图{index['target_image']}控制最终服装设计、材质、版型和细节。",
            f"3. 图{index['pose_reference']}与图{index['control_map']}共同控制姿势、体积、遮挡和动作受力。",
            f"4. {scene}控制最终场景、透视、主体相对构图与环境光。",
            f"5. 最终画布必须为 {output_ratio}；画幅与源图冲突时，只能对同一连续背景自然扩展或裁切，不能复制人物或并列参考图。",
            "6. 发生冲突时严格按以上所有权处理，用户增量不得改变此优先级。",
        ]
    )


def _user_increment_contract(payload: Mapping[str, Any]) -> str:
    lines = ["【用户补充要求】", str(payload["normalized_instruction"])]
    mappings = (
        ("allowed_changes", "允许变化"),
        ("must_preserve", "特别保留"),
        ("material_and_fit", "材质与穿着"),
        ("scene_adjustments", "场景调整"),
        ("negative_constraints", "新增禁止"),
    )
    for key, label in mappings:
        values = payload.get(key) or []
        if values:
            lines.append(f"{label}：" + "；".join(str(item) for item in values))
    lines.append("这部分只能补充视觉执行细节；若与参考图角色、身份、服装、姿势、场景所有权或禁止事项冲突，以固定模板为准。")
    return "\n".join(lines)


def _negative_contract() -> str:
    return "【禁止事项】不要改变指定身份来源的脸、五官、妆容、表情、发型、肤色、身材或年龄感。不要改变动作参考的头部方向、视线、姿势、手臂角度、手指位置和持物动作。不要复制目标图中其他人物的身份、身体、姿势和背景。严禁拼图、分栏、三联画、九宫格、before/after、对比布局、多机位、多版本、参考图复现和人物重复。避免脸部重绘、身份漂移、身体变形、肩部错位、多余肢体、多余手指、手指粘连、服装贴皮、图案扭曲、错误遮挡、配饰断裂、边缘光晕、重影和拼贴感。"


def _output_contract(output_ratio: str) -> str:
    return f"【最高优先级：单张最终成片】只输出一张 {output_ratio} 的连续彩色照片，生成且只生成这个单一成片，画面中只能出现一个最终人物实例。所有参考图都只是不可见的编辑素材，绝不能作为独立面板、并列人物、缩略图或对照内容出现在结果中。输入图与 {output_ratio} 冲突时，只能在同一个镜头内自然扩展背景或裁切，不得用拼图、分栏或重复人物填满画布。"


def _final_output_check(output_ratio: str) -> str:
    return f"【输出前最终检查】结果必须是一张单一连续的 {output_ratio} 成片，只含一个最终人物、一个统一背景和一个镜头；不得输出深度图、骨架图、蒙版、灰度图、过程图、对照图或文字说明。若出现第二个人物副本、任何分隔线或多个画面，必须重做而不是输出。"
