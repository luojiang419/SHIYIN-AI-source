"""自由换衣的底图与商品职责分离，复用批量换款的材质契约。"""
from __future__ import annotations

from .ecommerce import TRY_ON_OUTFIT_ROLES
from .pose_replicate_prompts import compile_pose_replicate_prompt


def role(ref):
    return ref.get("reference_type") or ref.get("role")


def compile_outfit_edit(base, depth, inputs, aspect_ratio, instruction=""):
    products = [dict(ref) for ref in inputs if role(ref) in TRY_ON_OUTFIT_ROLES]
    details = [dict(ref) for ref in inputs if role(ref) == "detail"]
    if len(products) != 1:
        raise ValueError("每次换装只处理一件商品，多个商品须依次生成")
    refs = [dict(base), dict(depth), *products, *details]
    single_detail = len(products) == 1 and len(details) == 1
    compiled = compile_pose_replicate_prompt(
        "depth", has_fabric_detail=single_detail, output_aspect_ratio=aspect_ratio,
    )
    prompt = compiled.final_prompt
    lines = ["【本次商品所有权：优先于模板中的默认单件换装范围】"]
    owners = {}
    labels = {"upper_garment": "上装", "lower_garment": "下装", "full_garment": "连体/全套服装",
              "garment": "指定服装", "shoes": "鞋靴", "accessory": "指定配饰"}
    for index, ref in enumerate(products, 3):
        owners[ref.get("reference_id")] = index
        lines.append(f"图{index}只负责{labels[role(ref)]}，完整替换该商品对应区域；"
                     "款式、开合、口袋、颜色和表面组织均来自这张原始商品图，不借用其他商品。"
                     + str(ref.get("instruction") or ""))
    for index, ref in enumerate(details, 3 + len(products)):
        owner = owners.get(ref.get("detail_target_id"))
        if owner is None and not ref.get("detail_target_id"):
            owner = 3
        if owner is None:
            raise ValueError("面料细节缺少对应商品，已停止生成")
        lines.append(f"图{index}只补充图{owner}的局部织物组织、缝线和细节，"
                     f"图{owner}仍是款式与颜色标准。按自然尺度还原，禁止放大纤维、跨衣片串纹理或平铺特写。"
                     + str(ref.get("instruction") or ""))
    lines.append("图1是已确定身份、动作、机位和光线的唯一照片底图。最终换装不再换人、换动作或重建背景。"
                 "当前商品完成后再处理下一件；未指定的衣物、鞋、持物和非衣区域保持图1。")
    if instruction:
        lines.append("用户补充要求（图号仍指原始输入，见映射）：" + instruction)
    prompt += "\n\n" + "\n".join(lines)
    return refs, prompt, compiled.template_variant


def original_reference_map(inputs, final_refs):
    indices = {ref.get("reference_id"): index for index, ref in enumerate(final_refs, 1)}
    return "原始输入图号映射：" + "；".join(
        f"原图{index}→" + (f"当前图{indices[ref.get('reference_id')]}" if ref.get('reference_id') in indices
                           else ("由其他单品阶段处理，本轮不作为商品来源" if role(ref) in TRY_ON_OUTFIT_ROLES or role(ref) == "detail"
                                 else "已融合入当前图1的人物/动作底图"))
        for index, ref in enumerate(inputs, 1)
    )
