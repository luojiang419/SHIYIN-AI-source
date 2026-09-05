from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from canvas_core.pose_replicate_templates_v3 import POSE_REPLICATE_V3_TEMPLATES

POSE_REPLICATE_TEMPLATE_ID = "pose-replicate.v3.0"
POSE_REPLICATE_LOCALE = "zh-CN"
POSE_REPLICATE_MODES = {"depth", "skeleton"}
POSE_REPLICATE_OUTPUT_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "4:5"}

SCENARIOS = {
    (False, False): "base-wardrobe",
    (True, False): "model-wardrobe",
    (False, True): "base-wardrobe-scene",
    (True, True): "model-full-look-scene",
}

ROLE_LABELS = {
    "pose_reference": "目标图片",
    "control_map": "深度图或骨架图",
    "target_image": "服装参考",
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
    custom_template: str | None = None,
) -> PoseReplicatePrompt:
    mode = str(control_mode or "").strip().lower()
    output_ratio = str(output_aspect_ratio or "").strip()
    if output_ratio not in POSE_REPLICATE_OUTPUT_RATIOS:
        raise PoseReplicatePromptError("一键复刻输出画幅不受支持")
    order = reference_order(mode, has_model_subject, has_scene)
    scenario = scenario_id(has_model_subject, has_scene)
    original = _clean_text(user_instruction, 5000)
    if custom_template is not None:
        if not custom_template.strip() or len(custom_template) > 30000:
            raise PoseReplicatePromptError("自定义模板不能为空且不能超过 30000 字符")
        # 字面替换而非 format/eval；用户文本中的花括号保持原样。
        prompt = custom_template.replace("{{output_aspect_ratio}}", output_ratio)
        if "{{user_instruction}}" in prompt:
            prompt = prompt.replace("{{user_instruction}}", str(user_instruction or ""))
        elif original:
            prompt += "\n\n【用户补充要求】\n" + str(user_instruction)
        return PoseReplicatePrompt(
            final_prompt=prompt, template_id=POSE_REPLICATE_TEMPLATE_ID,
            template_variant=f"{POSE_REPLICATE_TEMPLATE_ID}.{scenario}.{mode}.{POSE_REPLICATE_LOCALE}",
            scenario_id=scenario, control_mode=mode, output_aspect_ratio=output_ratio,
            prompt_source="custom-template", reference_order=order,
            user_instruction_original=original, normalized_instruction="",
        )
    normalized = None
    if original:
        if normalized_instruction is None:
            raise PoseReplicatePromptError("有用户补充要求时必须先完成 AI 助手规范化")
        normalized = normalize_instruction_payload(normalized_instruction, has_scene=has_scene)
    elif normalized_instruction:
        raise PoseReplicatePromptError("没有用户补充要求时不得注入 AI 助手增量")

    template_key = f"{mode}:{scenario}"
    try:
        template = POSE_REPLICATE_V3_TEMPLATES[template_key]
    except KeyError as error:
        raise PoseReplicatePromptError("一键复刻内置模板缺失") from error
    instruction = str((normalized or {}).get("normalized_instruction") or "")
    prompt = template.replace("{{output_aspect_ratio}}", output_ratio).replace(
        "{{user_instruction}}", instruction
    )
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
        normalized_instruction=instruction,
    )


def pose_replicate_template_catalog() -> list[dict[str, Any]]:
    """从同一编译器导出完整的八种组合，避免前后端维护两套默认提示词。"""
    entries = []
    for mode in ("depth", "skeleton"):
        for has_model, has_scene in SCENARIOS:
            compiled = compile_pose_replicate_prompt(mode, has_model_subject=has_model, has_scene=has_scene)
            labels = ["目标图片", "服装参考"]
            if has_model:
                labels.append("模特主体")
            if has_scene:
                labels.append("场景")
            template_key = f"{mode}:{compiled.scenario_id}"
            entries.append({
                "key": f"{mode}:{compiled.scenario_id}", "mode": mode,
                "title": " + ".join(labels), "scenario": compiled.scenario_id,
                "reference_order": list(compiled.reference_order),
                "prompt": POSE_REPLICATE_V3_TEMPLATES[template_key],
            })
    return entries


def _clean_text(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:limit]


def _clean_list(value: Any, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value[:limit] if (text := _clean_text(item, 600))]


def _base_instruction(has_model_subject: bool, has_scene: bool) -> str:
    if has_model_subject and has_scene:
        return "请以图1模特主体为唯一人物编辑底图完成高保真跨图复刻：保留其身份与身体，换上服装参考中的完整服装，严格应用目标图片的姿势结构，并将最终人物自然置入场景图。"
    if has_model_subject:
        return "请以图1模特主体为唯一人物编辑底图完成高保真人物与服装迁移：保留其身份与身体，换上服装参考中的服装，并严格复刻目标图片的姿势、主体相对构图和原场景。"
    if has_scene:
        return "请以目标图片中的人物身份与姿势为基础，换上服装参考中的服装，并将人物自然置入场景图；不得让场景图改变人物身份。"
    return "请以图1目标图片为唯一编辑底图进行高保真服装替换：保留原人物、原姿势、原配饰、原背景和主体相对构图，只替换与图3服装参考对应的服装区域。"


def _reference_contract(mode: str, order: tuple[dict[str, Any], ...], has_model: bool, has_scene: bool) -> str:
    index = {item["role"]: item["index"] for item in order}
    lines = [
        "【参考图用途】",
        f"图{index['pose_reference']}（目标图片）：是需要换装并生成深度图或骨架图的目标人物图片；控制人物身份（未接入模特主体时）、每个可见身体部位的精确姿势、动作、左右关系、身体重心、头脸朝向、视线、手势、持物动作、主体相对构图与空间遮挡。原图裁切只作为内容取舍参考，不得覆盖最终输出画幅。",
        (
            f"图{index['control_map']}（人物深度图）：是目标图片对应的像素级三维几何证据。它严格控制人物体积、可见轮廓、各部位前后距离、遮挡边界，以及服装表面的隆起、凹陷、褶皱峰谷和堆叠层次；只是不提供身份、服装款式、颜色、图案、面料纹理或背景。"
            if mode == "depth"
            else f"图{index['control_map']}（人物骨架图）：控制关节位置、肢体方向、左右关系和身体重心；不提供人体表面、服装褶皱、身份、服装款式、纹理或背景。"
        ),
        f"图{index['target_image']}（服装参考）：当前任务服装设计的唯一来源，准确保留类别、版型、领口、肩袖、门襟、口袋、下摆、面料、颜色、图案、缝线、装饰、松量、厚度与垂坠。一次批量生成中的每项任务只使用自己对应的这一张服装参考，不得混入其他色号或款号。",
    ]
    if has_model:
        lines.append(f"图{index['model_subject']}（模特主体）：最终人物身份、面部、肤色、发型和身体比例的唯一来源，不提供姿势、服装或场景。")
    if has_scene:
        lines.append(f"图{index['scene']}（场景）：最终环境、背景结构、透视、环境光和空间接触的唯一来源，不提供人物身份、姿势或服装。")
    lines.append("任何参考图都不得越权提供其他角色的内容，也不得交换或重新解释上述编号。")
    return "\n".join(lines)


def _preservation_contract(has_model: bool, has_scene: bool, order: tuple[dict[str, Any], ...]) -> str:
    index = {item["role"]: item["index"] for item in order}
    identity = f"图{index['model_subject']}模特主体" if has_model else f"图{index['pose_reference']}目标图片人物"
    scene = f"图{index['scene']}场景" if has_scene else f"图{index['pose_reference']}目标图片原背景"
    lines = [
        "【必须保持不变】",
        f"最终人物必须是同一位{identity}：严格保留其五官、脸型、肤色、妆容、表情、发型、发色、发丝、耳朵、年龄感和可识别身份特征。",
        f"严格保留图{index['pose_reference']}中头部角度、视线方向、肩线、脊柱倾斜、肩髋关系、双臂弯曲方式、双手与每根可见手指的位置、持物动作、身体重心、人物在画面中的相对位置与尺度。",
        f"严格保留{scene}的镜头视角、透视、结构、光照方向、亮度、色温、阴影和景深；不得擅自增删或替换环境内容。",
        "严格保留所有不属于目标换装范围的裤装、鞋、眼镜、耳饰、项链、手袋、包带、手持物及其他配饰的款式、位置、角度、形状与遮挡关系。",
    ]
    if not has_model and not has_scene:
        lines.append(
            f"这是以图{index['pose_reference']}目标图片为底图的最小区域编辑：除服装参考对应的换装区域、由新服装外轮廓实际占用的相邻像素及其必要接触阴影外，其他区域不得重绘、重构或重新生成，并应保持与底图一致。"
        )
    else:
        lines.append("只允许为身份、服装参考或新场景的明确归属进行必要适配；不得借迁移之名改变未授权的动作、手势、配饰、镜头关系或局部几何。")
    return "\n".join(lines)


def _control_contract(mode: str, has_model: bool) -> str:
    if mode == "depth":
        alignment = (
            "当接入独立模特主体时，在保持其身份与身体比例的前提下，把上述关节关系、朝向、透视、遮挡和褶皱峰谷按人物区域归一化一一映射；不得用身份迁移作为放松动作的理由。"
            if has_model
            else "目标图片与深度图是同一人物、同一画面的配准输入，人物区域内的二维位置、轮廓、遮挡与主要褶皱峰谷必须一一对齐。"
        )
        return "\n".join(
            [
                "【深度几何硬锁：不是构图建议】",
                "深度图中白色表示靠近镜头、灰色表示中间距离、黑色背景不含场景信息。先把非黑色人物区域理解成一张与目标图片逐像素配准的三维表面，再在这张表面上完成换装；不得把深度图仅当作大致姿势参考。",
                alignment,
                "严格锁定头部、颈部、双肩、胸廓、腰腹、骨盆、双臂、肘、腕、双手、手指和可见腿部的二维位置、关节角度、朝向、长度比例、透视缩短、前后距离与身体重心。不得美化、拉直、对称化、镜像、简化或改成更常见的姿势。",
                "严格锁定人物外轮廓及所有遮挡交界：头发与肩颈、上臂与躯干、前臂与胸腹、手与衣服、持物与手、包带与身体之间的边界必须落在深度图和目标图片对应的位置。",
                "深度图中的服装形态属于几何证据而非服装设计证据：保留可对应服装区域内每条主要褶皱的空间位置、起止点、走向、弯折节奏、峰谷极性、深浅层级、交汇关系、拉伸区、挤压区和堆叠区；不得抹平、挪位、减少、补造或重新设计这些几何起伏。",
                "禁止继承目标图片原服装的颜色、图案、面料纹理、领型、袖型、门襟、口袋、纽扣、缝线和装饰。需要继承的是深度记录的姿势与表面几何，不是原服装的视觉身份。",
            ]
        )
    return "【骨架控制】骨架图只用于锁定关节位置、肢体方向、左右语义、身体重心与动作节奏。结合目标图片恢复真实人体体积与遮挡；不得把骨架线、节点颜色或空白背景画入结果。"


def _scenario_contract(has_model: bool, has_scene: bool, order: tuple[dict[str, Any], ...]) -> str:
    index = {item["role"]: item["index"] for item in order}
    if has_model and has_scene:
        return f"【组合任务】将图{index['target_image']}服装参考中的完整服装造型真实穿到图{index['model_subject']}人物身上，身体动作严格遵循图{index['pose_reference']}目标图片，最终置入图{index['scene']}场景。保留模特主体身份，不复制服装参考人物或目标图片人物的脸、身体与背景。"
    if has_model:
        return f"【组合任务】将图{index['target_image']}服装参考中的服装真实穿到图{index['model_subject']}人物身上，动作、机位、主体相对构图与背景严格遵循图{index['pose_reference']}目标图片。保留模特主体身份，不复制服装参考或目标图片中的人物身份。"
    if has_scene:
        return f"【组合任务】保留图{index['pose_reference']}目标图片中的人物身份与动作，换上图{index['target_image']}服装参考中的服装，并自然进入图{index['scene']}场景。人物尺度、脚底接触、透视、环境光与投影必须适配新场景。"
    return f"【具体换装任务】完整移除图{index['pose_reference']}目标图片中与待替换服装对应的原服装，将图{index['target_image']}服装参考中的服装真实、自然地穿在原人物身上。新版型可按服装参考合理改变外轮廓，但不得改变人物身体姿势、比例、身份、配饰、背景和主体相对构图。"


def _fold_contract(mode: str) -> str:
    if mode == "depth":
        return "\n".join(
            [
                "【服装参考到锁定几何的映射】",
                "把服装参考的类别、剪裁、领口、肩袖、门襟、口袋、下摆、颜色、图案、面料纹理、缝线和装饰映射到深度图锁定的穿着表面，而不是先生成一件平整的新衣再自由摆姿势。服装参考中的服装必须随锁定动作发生同位置、同方向、同层级的变形。",
                "肩线牵拉、腋下挤压、肘部弯曲、胸腹与腰部堆叠、袖口收束、手部接触和下摆垂坠必须逐区对齐深度图。目标材质只改变褶皱的表面观感，例如光泽、织纹和边缘软硬，不得改变主要褶皱的拓扑、峰谷位置与受力路径。",
                "只有当服装参考确实不存在对应部件时，才允许在该部件边界内做最小必要拓扑变化，例如无袖款移除原袖体、短款在参考下摆处终止原衣身。变化必须局部化；裸露肢体仍保持原姿势与深度，且不得借机重画其他区域。",
                "完成前按头颈、肩线、左右上臂、左右肘、左右前臂、左右手指、胸腹、腰胯、下摆逐区比对目标图片与深度图；任何位置、角度、轮廓、遮挡或主要褶皱峰谷不一致，都视为未完成并在输出前重做。",
            ]
        )
    return "【自然褶皱与受力】骨架图不包含服装表面深度。严格复刻目标图片中的关节、身体重心和动作受力关系，并根据服装参考的材质、版型、松量和结构生成自然褶皱。肩线牵拉、腋下挤压、肘部弯曲、胸腹与腰部堆叠、袖口收束和下摆垂坠必须与动作一致；不得继承目标图片原服装的颜色、图案、剪裁或面料纹理。"


def _occlusion_contract(has_model: bool) -> str:
    identity_source = "模特主体" if has_model else "目标图片人物"
    return f"【遮挡与边缘】严格保持头发、面部、双手、手指、现有配饰与服装之间的正确前后关系。新袖口自然衔接手腕，不覆盖或吞没手指；服装边缘不得出现发光、灰边、重影、破洞或抠图痕迹。保留{identity_source}的真实皮肤和发丝细节。"


def _priority_contract(has_model: bool, has_scene: bool, order: tuple[dict[str, Any], ...], output_ratio: str) -> str:
    index = {item["role"]: item["index"] for item in order}
    identity = f"图{index['model_subject']}" if has_model else f"图{index['pose_reference']}"
    scene = f"图{index['scene']}" if has_scene else f"图{index['pose_reference']}"
    return "\n".join(
        [
            "【执行优先级】",
            f"1. {identity}控制最终人物身份、面部和身体归属。",
            f"2. 图{index['pose_reference']}目标图片与图{index['control_map']}共同硬锁姿势、关节、体积、轮廓、遮挡和动作受力；深度模式还硬锁主要褶皱峰谷与表面几何。",
            f"3. 图{index['target_image']}服装参考控制最终服装设计、材质、版型和细节，但必须服从第 2 项锁定的穿着几何。",
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


def _negative_contract(mode: str) -> str:
    mode_rule = (
        "禁止忽略、平滑、弱化、平均化或重新想象深度图中的人物轮廓、遮挡边界、局部体积和主要褶皱峰谷。"
        if mode == "depth"
        else "不得把骨架线、节点颜色或空白背景画入结果，也不得宣称骨架图提供了不存在的服装表面深度。"
    )
    return f"【禁止事项】不要改变指定身份来源的脸、五官、妆容、表情、发型、肤色、身材或年龄感。不要改变目标图片的头部方向、视线、姿势、身体重心、肩髋倾斜、手臂角度、肘腕位置、手指位置、左右关系或持物动作。{mode_rule}不要复制服装参考中其他人物的身份、身体、姿势和背景。严禁拼图、分栏、三联画、九宫格、before/after、对比布局、多机位、多版本、参考图复现和人物重复。避免脸部重绘、身份漂移、身体变形、肩部错位、多余肢体、多余手指、手指粘连、服装贴皮、图案扭曲、错误遮挡、配饰断裂、边缘光晕、重影和拼贴感。"


def _output_contract(output_ratio: str) -> str:
    return f"【最高优先级：单张最终成片】只输出一张 {output_ratio} 的连续彩色照片，生成且只生成这个单一成片，画面中只能出现一个最终人物实例。所有参考图都只是不可见的编辑素材，绝不能作为独立面板、并列人物、缩略图或对照内容出现在结果中。输入图与 {output_ratio} 冲突时，只能在同一个镜头内自然扩展背景或裁切，不得用拼图、分栏或重复人物填满画布。"


def _final_output_check(output_ratio: str) -> str:
    return f"【输出前最终检查】结果必须是一张单一连续的 {output_ratio} 成片，只含一个最终人物、一个统一背景和一个镜头；不得输出深度图、骨架图、蒙版、灰度图、过程图、对照图或文字说明。若出现第二个人物副本、任何分隔线或多个画面，必须重做而不是输出。"
