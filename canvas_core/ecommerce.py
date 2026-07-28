"""Pure contracts, routing and prompts for the e-commerce image workspace."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable


OPERATIONS = (
    "try_on",
    "pose_transfer",
    "prop_replace",
    "angle_change",
    "background_change",
    "universal",
)
MODES = ("standard",)
LEGACY_MODES = {"preview", "publish"}
ASPECT_RATIOS = ("source", "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "9:16", "16:9")
RESOLUTIONS = ("auto", "1k", "2k", "4k")
QUALITIES = ("auto", "low", "medium", "high")

SIZE_PRESETS: dict[str, dict[str, str]] = {
    "1:1": {"1k": "1024x1024", "2k": "2048x2048", "4k": "2880x2880"},
    "2:3": {"1k": "1024x1536", "2k": "1360x2040", "4k": "2304x3456"},
    "3:2": {"1k": "1536x1024", "2k": "2040x1360", "4k": "3456x2304"},
    "3:4": {"1k": "1008x1344", "2k": "1536x2048", "4k": "2400x3200"},
    "4:3": {"1k": "1344x1008", "2k": "2048x1536", "4k": "3200x2400"},
    "4:5": {"1k": "1024x1280", "2k": "1632x2040", "4k": "2560x3200"},
    "9:16": {"1k": "720x1280", "2k": "1152x2048", "4k": "2160x3840"},
    "16:9": {"1k": "1280x720", "2k": "2048x1152", "4k": "3840x2160"},
}

OPERATION_INPUTS: dict[str, tuple[str, ...]] = {
    "try_on": ("source",),
    "pose_transfer": ("source",),
    "prop_replace": ("source", "prop"),
    "angle_change": ("source",),
    "background_change": ("source",),
    "universal": (),
}
UNIVERSAL_REFERENCE_LIMIT = 14
UNIVERSAL_REFERENCE_ROLES = [
    {"id": "subject", "label": {"zh": "主体/模特", "en": "Subject / model"}},
    {"id": "model_identity", "label": {"zh": "模特形象", "en": "Model identity"}},
    {"id": "upper_garment", "label": {"zh": "上装", "en": "Upper garment"}},
    {"id": "lower_garment", "label": {"zh": "下装", "en": "Lower garment"}},
    {"id": "full_garment", "label": {"zh": "连衣裙/套装", "en": "Dress / full outfit"}},
    {"id": "shoes", "label": {"zh": "鞋靴", "en": "Shoes"}},
    {"id": "accessory", "label": {"zh": "首饰/配饰", "en": "Accessory"}},
    {"id": "prop", "label": {"zh": "道具/商品", "en": "Prop / product"}},
    {"id": "detail", "label": {"zh": "细节图", "en": "Detail image"}},
    {"id": "pose", "label": {"zh": "动作参考", "en": "Pose reference"}},
    {"id": "scene", "label": {"zh": "场景/背景", "en": "Scene / background"}},
    {"id": "style", "label": {"zh": "风格/光影", "en": "Style / lighting"}},
]
UNIVERSAL_REFERENCE_ROLE_IDS = {item["id"] for item in UNIVERSAL_REFERENCE_ROLES}
ALLOWED_INPUT_ROLES = {"source", "garment", "pose", "prop", "background", "mask", *UNIVERSAL_REFERENCE_ROLE_IDS}
TRY_ON_OUTFIT_ROLES = {"garment", "upper_garment", "lower_garment", "full_garment", "shoes", "accessory"}
TRY_ON_REFERENCE_ROLES = {"source", "model_identity", *TRY_ON_OUTFIT_ROLES, "detail", "pose"}
UNIVERSAL_INTERACTIONS = {"wear", "put_on", "hold", "carry", "place", "use", "pose", "scene", "style", "identity"}
ACCESSORY_WEAR_KEYWORDS = (
    "necklace", "项链", "earring", "耳环", "bracelet", "手链", "bangle", "手镯", "ring", "戒指",
    "watch", "手表", "hat", "帽", "cap", "glasses", "眼镜", "sunglasses", "墨镜", "belt", "腰带",
    "scarf", "围巾", "brooch", "胸针", "tie", "领带",
)
HANDHELD_KEYWORDS = (
    "phone", "手机", "smartphone", "camera", "相机", "cup", "杯", "bottle", "瓶", "book", "书",
    "umbrella", "伞", "flower", "花", "wallet", "钱包", "card", "卡", "cosmetic", "口红", "lipstick",
)
BAG_KEYWORDS = ("bag", "包", "handbag", "tote", "clutch", "purse", "satchel", "backpack", "shoulder bag", "手提包", "托特包", "双肩包", "挎包")
PLACED_PROP_KEYWORDS = ("chair", "椅", "sofa", "沙发", "table", "桌", "vase", "花瓶", "lamp", "灯", "plant", "植物", "furniture", "家具", "decor", "摆件")

POSE_PRESETS = [
    {"id": "standing_front", "label": {"zh": "正面站立", "en": "Front standing"}, "prompt": "standing upright, front view, arms relaxed naturally"},
    {"id": "standing_three_quarter", "label": {"zh": "四分之三站姿", "en": "Three-quarter"}, "prompt": "three-quarter standing pose with a natural weight shift"},
    {"id": "side_profile", "label": {"zh": "侧身站立", "en": "Side profile"}, "prompt": "clean side-profile standing pose"},
    {"id": "walking", "label": {"zh": "自然行走", "en": "Walking"}, "prompt": "natural mid-step walking pose with realistic balance"},
    {"id": "sitting", "label": {"zh": "自然坐姿", "en": "Sitting"}, "prompt": "natural seated pose with anatomically correct limbs"},
    {"id": "arms_crossed", "label": {"zh": "双臂交叉", "en": "Arms crossed"}, "prompt": "standing with arms crossed naturally"},
    {"id": "hand_on_hip", "label": {"zh": "单手叉腰", "en": "Hand on hip"}, "prompt": "standing with one hand on the hip, confident catalog pose"},
    {"id": "product_hold", "label": {"zh": "手持商品", "en": "Holding product"}, "prompt": "balanced standing pose holding a product naturally at chest level"},
]

BACKGROUND_PRESETS = [
    {"id": "studio_white", "label": {"zh": "纯白棚拍", "en": "White studio"}, "prompt": "seamless calibrated pure white e-commerce studio cyclorama, two large softboxes, accurate white balance, soft grounded contact shadow, true SKU color"},
    {"id": "studio_gray", "label": {"zh": "中性灰棚拍", "en": "Gray studio"}, "prompt": "neutral light-gray commercial studio cyclorama, controlled three-point softbox lighting, clean product edges, gentle shadow gradient"},
    {"id": "warm_minimal", "label": {"zh": "暖色极简", "en": "Warm minimal"}, "prompt": "warm off-white minimal set with refined natural surfaces, soft directional daylight, uncluttered premium catalog composition"},
    {"id": "luxury_dark", "label": {"zh": "深色奢华", "en": "Luxury dark"}, "prompt": "premium dark charcoal studio set, controlled rim highlights, elegant reflections, deep but readable shadows, no color contamination on the product"},
    {"id": "home_lifestyle", "label": {"zh": "居家生活", "en": "Home lifestyle"}, "prompt": "tasteful modern home lifestyle scene, natural window light, realistic scale and contact shadows, product remains the visual hero"},
    {"id": "outdoor_daylight", "label": {"zh": "户外日光", "en": "Outdoor daylight"}, "prompt": "clean outdoor lifestyle scene in soft natural daylight, realistic environmental perspective, product color protected from green or sky color cast"},
    {"id": "festival_red", "label": {"zh": "节庆红金", "en": "Festive red"}, "prompt": "refined festive red and gold commercial set, tasteful negative space, premium shelf-ready styling, product color and branding remain exact"},
    {"id": "transparent_style", "label": {"zh": "透明底观感", "en": "Cutout style"}, "prompt": "isolated catalog cutout presentation with no visible environment, transparent-background feel, clean alpha-like edges and subtle contact shadow"},
]

STUDIO_REFERENCE_PRESETS = [
    {"id": "studio_white", "label": {"zh": "白棚", "en": "White studio"}, "prompt": "seamless pure white e-commerce photography studio, calibrated white balance, broad softbox lighting, clean floor-to-wall sweep, soft grounded contact shadow"},
    {"id": "studio_gray", "label": {"zh": "灰棚", "en": "Gray studio"}, "prompt": "neutral gray commercial photography studio, controlled three-point lighting, gentle gray shadow gradient, accurate SKU color separation"},
    {"id": "studio_black", "label": {"zh": "黑棚", "en": "Black studio"}, "prompt": "matte black studio set, precise rim light, controlled highlights, deep readable shadows, premium product texture emphasis"},
    {"id": "studio_warm", "label": {"zh": "暖米棚", "en": "Warm beige studio"}, "prompt": "warm beige studio cyclorama, soft creamy bounce light, refined premium catalog mood, no orange color cast on products"},
    {"id": "studio_cool", "label": {"zh": "冷蓝棚", "en": "Cool blue studio"}, "prompt": "cool pale-blue studio backdrop, crisp commercial lighting, clean high-tech freshness, protected neutral product whites and true colors"},
    {"id": "studio_pink", "label": {"zh": "粉色棚", "en": "Pink studio"}, "prompt": "soft pastel pink studio backdrop, flattering diffused light, clean beauty and accessory catalog presentation, restrained saturation"},
    {"id": "studio_red_gold", "label": {"zh": "红金棚", "en": "Red gold studio"}, "prompt": "refined red and gold festival e-commerce studio set, tasteful warm highlights, premium promotion mood, no random decorations or text"},
    {"id": "studio_cutout", "label": {"zh": "透明底棚", "en": "Cutout studio"}, "prompt": "clean isolated cutout-style studio, white-to-transparent background feel, crisp alpha-like edges, subtle natural contact shadow"},
]

QUALITY_CHECKS: dict[str, list[dict[str, Any]]] = {
    "try_on": [
        {"id": "identity", "label": {"zh": "人物脸部、发型、体型和肤色符合源图或模特形象参考", "en": "Face, hair, body shape, and skin tone match the source or model identity reference"}},
        {"id": "garment", "label": {"zh": "服装版型、颜色、面料、图案、Logo 和文字准确", "en": "Garment cut, color, fabric, pattern, logo, and text are accurate"}},
        {"id": "anatomy", "label": {"zh": "四肢、手指、衣褶和遮挡关系自然", "en": "Limbs, fingers, folds, and occlusions look natural"}},
        {"id": "background", "label": {"zh": "姿态、镜头、光线和背景未被意外修改", "en": "Pose, camera, lighting, and background were not changed unexpectedly"}},
        {"id": "artifacts", "label": {"zh": "放大检查后无破损、重影、水印或额外物体", "en": "No damage, ghosting, watermark, or extra objects at full size"}},
    ],
    "pose_transfer": [
        {"id": "identity", "label": {"zh": "人物身份、脸部和体型保持一致", "en": "Identity, face, and body shape are preserved"}},
        {"id": "outfit", "label": {"zh": "原服装、配饰、图案和文字保持一致", "en": "Original outfit, accessories, patterns, and text are preserved"}},
        {"id": "pose", "label": {"zh": "目标动作、关节、机位、景别、裁切和人物画面占比与姿势参考一致", "en": "Pose, joints, camera, shot scale, crop, and subject framing match the pose reference"}},
        {"id": "anatomy", "label": {"zh": "关节、手脚和遮挡关系符合人体结构", "en": "Joints, hands, feet, and occlusions are anatomically valid"}},
        {"id": "scene", "label": {"zh": "背景、镜头与光线没有非预期变化", "en": "Background, camera, and lighting have no unintended changes"}},
    ],
    "prop_replace": [
        {"id": "prop", "label": {"zh": "新道具的造型、材质、颜色、Logo 和文字准确", "en": "New prop shape, material, color, logo, and text are accurate"}},
        {"id": "placement", "label": {"zh": "尺寸、透视、握持或接触关系合理", "en": "Scale, perspective, grip, and contact are believable"}},
        {"id": "lighting", "label": {"zh": "道具光线、阴影和反射与场景匹配", "en": "Lighting, shadow, and reflections match the scene"}},
        {"id": "preservation", "label": {"zh": "替换区域以外的人物、商品和背景保持不变", "en": "People, products, and background outside the target are preserved"}},
        {"id": "artifacts", "label": {"zh": "边缘自然，无残留旧道具、重影或水印", "en": "Edges are clean with no old prop remnants, ghosting, or watermark"}},
    ],
    "angle_change": [
        {"id": "identity", "label": {"zh": "主体身份、商品结构和比例保持一致", "en": "Subject identity, product structure, and proportions are preserved"}},
        {"id": "details", "label": {"zh": "颜色、材质、Logo、文字与关键细节准确", "en": "Color, material, logo, text, and key details are accurate"}},
        {"id": "view", "label": {"zh": "水平角、俯仰角和景别符合选择", "en": "Azimuth, elevation, and distance match the controls"}},
        {"id": "geometry", "label": {"zh": "新露出的表面合理，无镜像、复制或结构畸变", "en": "Newly revealed surfaces are plausible with no mirroring or deformation"}},
        {"id": "scene", "label": {"zh": "非目标场景、光线和背景保持一致", "en": "Non-target scene, lighting, and background remain consistent"}},
    ],
    "background_change": [
        {"id": "foreground", "label": {"zh": "人物或商品主体、Logo、文字和颜色保持准确", "en": "Foreground subject, logo, text, and color remain accurate"}},
        {"id": "edges", "label": {"zh": "头发、透明材质和商品边缘无白边或缺损", "en": "Hair, transparent materials, and edges have no halos or damage"}},
        {"id": "scene", "label": {"zh": "背景内容符合所选模板、描述或参考图", "en": "Background matches the selected preset, prompt, or reference"}},
        {"id": "lighting", "label": {"zh": "接触阴影、反射、景深和光线方向自然", "en": "Contact shadow, reflections, depth, and light direction are natural"}},
        {"id": "artifacts", "label": {"zh": "无额外主体、文字、水印或明显生成瑕疵", "en": "No extra subjects, text, watermark, or visible generation defects"}},
    ],
    "universal": [
        {"id": "identity", "label": {"zh": "主体身体来自主体图；主体图自带鞋子和配饰默认保留；脸部、发型、肤色可由模特形象图独立指定", "en": "Body comes from subject references; subject-native shoes and accessories are preserved by default; face, hair, and skin tone may be specified by model identity references"}},
        {"id": "products", "label": {"zh": "服装、鞋、配饰和道具的版型、材质、颜色、Logo 与文字准确", "en": "Garments, shoes, accessories, and props preserve shape, material, color, logos, and text"}},
        {"id": "pose", "label": {"zh": "动作、关节、机位、景别、裁切、人物位置和画面占比严格匹配主姿势参考", "en": "Pose, joints, camera, shot scale, crop, position, and subject framing strictly match the primary pose reference"}},
        {"id": "scene", "label": {"zh": "场景构图、光线、透视和接触阴影协调", "en": "Scene composition, lighting, perspective, and contact shadows are coherent"}},
        {"id": "ownership", "label": {"zh": "各参考图没有串脸、串服装、串背景或复制无关物体", "en": "References do not leak identity, clothing, backgrounds, or unrelated objects"}},
        {"id": "artifacts", "label": {"zh": "放大检查后无重影、畸形肢体、镜像文字、水印或多余物体", "en": "No ghosting, malformed limbs, mirrored text, watermark, or extra objects at full size"}},
    ],
}

NANO_BANANA_PRO_ECOMMERCE_DIRECTIVE = (
    "NANO BANANA PRO EXECUTION: optimize this prompt for Gemini 3 Pro Image / Nano Banana Pro professional asset production. "
    "Resolve the task internally as an ordered edit plan before rendering: identify the final commercial image type, assign every reference a single owner role, protect unchanged regions, then output only one final photorealistic image. "
    "Use explicit subject, setting, action, composition, camera viewpoint, lens behavior, lighting design, color grade, texture, typography, and finish instructions instead of loose keyword piles. "
    "Favor the model's strengths in complex multi-reference reasoning, precision creative control, accurate brand consistency, multilingual text rendering, and 4K-ready detail."
)
NANO_BANANA_PRO_REFERENCE_DIRECTIVE = (
    "NANO BANANA PRO MULTI-REFERENCE MAP: use the ordered image map literally. Do not average references, blend identities, harmonize product colors, or borrow unrelated attributes across images. "
    "For high-fidelity preservation, prioritize up to five model/identity references, up to six product/object references, and up to three style references; additional references are supplemental evidence for their named role only. "
    "If references conflict, obey the explicit user supplement first, then the role ownership rules, then the earliest source for that role. "
    "When an image is labeled detail, pose, scene, or style, it controls only that attribute family and must not rewrite product identity, body identity, or unrelated regions."
)
NANO_BANANA_PRO_PHOTO_DIRECTIVE = (
    "COMMERCIAL PHOTO DIRECTION: render as high-end e-commerce photography, not illustration. Use believable focal length and perspective for the selected shot, controlled studio or natural light, clean negative space, realistic scale, contact shadows, reflections, occlusion, depth of field, and calibrated white balance. "
    "The final image should look ready for a marketplace PDP, hero image, ad creative, or social commerce placement without looking over-processed."
)
TEXT_AND_BRAND_FIDELITY_DIRECTIVE = (
    "TEXT, LOGO, AND BRANDING DIRECTIVE: preserve any existing product logo, label, tag, packaging copy, embroidery text, printed graphic, and UI-like text from its owning reference with the same wording, orientation, placement, font character, spacing, and legibility. "
    "If the user explicitly requests new text, render only the quoted text exactly and keep it readable; otherwise do not invent slogans, badges, watermarks, price tags, captions, QR codes, or random letters."
)
PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE = (
    "QUALITY AND LISTING DETAIL: render marketplace-ready premium commercial photography with SKU-level product fidelity. "
    "Preserve exact silhouette, proportions, construction, material micro-texture, high-fidelity fabric weave, stitching, seams, hems, buttons, zippers, trims, labels, tags, logos, readable text, "
    "leather, metal, glass, plastic, embroidery, print texture, packaging edges, and finish when present; keep clean edges, natural skin pores, realistic hair strands, balanced dynamic range, "
    "soft but defined studio lighting, physically correct contact shadows, reflections, ambient occlusion, and crisp but non-harsh detail. "
    "Avoid plastic or waxy skin, over-smoothed fabric, muddy textures, AI gloss, harsh HDR, fake sharpening, distorted logos, unreadable text, painterly style, cartoon finish, watermark, extra objects, and low-resolution artifacts."
)
REFERENCE_GROUNDED_MATERIAL_DIRECTIVE = (
    "REFERENCE-GROUNDED MATERIAL FIDELITY: treat uploaded garment, product, and detail images as the source of truth for material, not as loose style examples. "
    "Preserve the exact observed product color, hue, saturation, value, white balance, and local color temperature from the owning product reference; scene or style lighting may add natural shadows and highlights but must not recolor, tint, palette-match, or average the SKU color across references. "
    "Preserve observed weave or knit grain, thread direction, nap or pile, satin/silk/leather sheen, translucency, embroidery relief, print alignment, plaid/stripe registration, stitch density, seam puckering, wrinkles, lint, and natural surface imperfections at zoom inspection. "
    "When fitting a product to a new body, pose, angle, or scene, warp the original reference texture with the product geometry; do not redraw it from a generic fabric description, smooth it, plasticize it, or replace it with a similar-looking material."
)
ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE = (
    "ZOOM-READY QUALITY GATE: output must hold up at 100% marketplace zoom with crisp true-to-reference edges, readable logos and product text, stable color temperature, natural dynamic range, and no low-resolution mush. "
    "Use reference pixels as evidence for product identity and surface detail. Do not denoise away weave, pores, scratches, grain, stitching, labels, hardware, hair edges, transparent edges, or small manufacturing details. "
    "Avoid hallucinated seams, invented logos, mirrored or garbled text, duplicated fingers, melted hands, extra products, background leakage, posterized shadows, compression artifacts, and synthetic over-sharpening."
)
ECOMMERCE_COLOR_FIDELITY_DIRECTIVE = (
    "ECOMMERCE COLOR FIDELITY LOCK: each garment, product, prop, shoe, accessory, and named detail reference owns its exact SKU color. "
    "Match the reference hue/saturation/value and white balance before adapting it to the final light; keep local shadows and highlights natural, but never introduce color drift, mixed fabric tones, palette harmonization, global color casts, scene-color contamination, or inconsistent color patches across the same product. "
    "If a source garment is orange, cream, black, denim blue, or any specific color, the final product must remain that same reference color at every visible panel, seam, waistband, pocket, button area, side panel, and hem."
)
LOWER_GARMENT_STRUCTURE_DIRECTIVE = (
    "LOWER-GARMENT / PANTS SHAPE LOCK: when a lower garment, pants, trousers, skirt, or detail image is present, preserve the exact waist height, waistband width and contour, front rise, fly, button and hook placement, pocket shape and position, pleats, darts, belt loops, side seams, inseams, outseams, leg opening, hem width, silhouette, and panel geometry from the owning references. "
    "For high-waist pants, keep the waistband high and flat and keep navel coverage if shown by the reference; do not curve the waistline unless the reference does. "
    "For wide-leg, straight-leg, flared, tapered, or skinny pants, preserve that exact pants type; keep trouser crease lines and side seams straight when the reference shows straight lines, and do not convert the pants shape to another cut."
)
TEXTURE_CRITICAL_REFERENCE_ROLES = {"upper_garment", "lower_garment", "full_garment", "shoes", "accessory", "prop", "detail"}
PRIMARY_PRODUCT_REPLACEMENT_ROLES = {"upper_garment", "lower_garment", "full_garment", "garment", "prop"}
SUBJECT_NATIVE_STYLING_OVERRIDE_ROLES = {"shoes", "accessory", "prop"}
NO_HUMAN_SUBJECT_PRESENCE_VALUES = {
    "none",
    "no_person",
    "no_human",
    "product_only",
    "object_only",
    "garment_only",
    "flat_lay",
    "hanger",
    "mannequin_only",
}
HUMAN_SUBJECT_PRESENCE_VALUES = {"person", "human", "model", "partial_person", "body_only", "visible_person"}
NO_FACE_PRESENCE_VALUES = {"none", "no_face", "not_visible", "hidden", "covered"}

EDIT_MODEL_HINTS = (
    "qwen-image-edit",
    "flux.2-klein",
    "flux2-klein",
    "nano-banana",
    "gpt-image",
    "gemini-3-pro-image",
    "gemini-3.1-flash-image",
)
STANDARD_PRIORITIES = ("gemini-3-pro-image-preview", "gpt-image-2-vip", "nano-banana-pro-4k-vip", "qwen-image-edit-2511")

GARMENT_CATEGORY_ALIASES = {
    "upper": "upper",
    "upper_body": "upper",
    "upper-body": "upper",
    "top": "upper",
    "tops": "upper",
    "上装": "upper",
    "上衣": "upper",
    "lower": "lower",
    "lower_body": "lower",
    "lower-body": "lower",
    "bottom": "lower",
    "bottoms": "lower",
    "下装": "lower",
    "裤装": "lower",
    "裙装": "lower",
    "dress": "dress",
    "one-piece": "dress",
    "one_piece": "dress",
    "连衣裙": "dress",
    "连体衣": "dress",
}


def validate_operation(value: str) -> str:
    operation = str(value or "").strip().lower()
    if operation not in OPERATIONS:
        raise ValueError("不支持的电商功能")
    return operation


def validate_mode(value: str) -> str:
    mode = str(value or "").strip().lower()
    if mode in LEGACY_MODES:
        return "standard"
    if mode not in MODES:
        raise ValueError("生成模式只能是 standard")
    return "standard"


def normalize_garment_analysis(value: dict[str, Any] | None) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    raw_category = str(data.get("category") or data.get("garment_category") or "").strip().lower()
    category = GARMENT_CATEGORY_ALIASES.get(raw_category, "auto")
    garment_type = re.sub(r"\s+", " ", str(data.get("garment_type") or data.get("type") or "").strip())[:120]
    reason = re.sub(r"\s+", " ", str(data.get("reason") or "").strip())[:240]
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "category": category,
        "garment_type": garment_type,
        "confidence": round(confidence, 4),
        "reason": reason,
    }


def parse_garment_analysis(text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s*```$", "", value).strip()
    try:
        data = json.loads(value)
    except Exception:
        match = re.search(r"\{.*?\}", value, re.S)
        data = json.loads(match.group(0)) if match else {}
    return normalize_garment_analysis(data)


def normalize_universal_reference_analysis(value: dict[str, Any] | None) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    item_name = re.sub(r"\s+", " ", str(data.get("item_name") or data.get("name") or "").strip())[:120]
    category = re.sub(r"\s+", " ", str(data.get("category") or data.get("type") or "").strip())[:80]
    subject_presence = re.sub(
        r"\s+",
        "_",
        str(data.get("subject_presence") or data.get("human_presence") or data.get("person_presence") or "").strip().lower(),
    )[:40]
    face_presence = re.sub(r"\s+", "_", str(data.get("face_presence") or "").strip().lower())[:40]
    interaction = str(data.get("interaction") or "").strip().lower()
    if interaction not in UNIVERSAL_INTERACTIONS:
        interaction = ""
    placement = re.sub(r"\s+", " ", str(data.get("placement") or "").strip())[:160]
    visual_details = re.sub(r"\s+", " ", str(data.get("visual_details") or data.get("details") or "").strip())[:300]
    material_signature = re.sub(
        r"\s+",
        " ",
        str(
            data.get("material_signature")
            or data.get("texture_signature")
            or data.get("fabric_texture")
            or data.get("material_texture")
            or ""
        ).strip(),
    )[:360]
    pose_description = re.sub(r"\s+", " ", str(data.get("pose_description") or "").strip())[:240]
    shot_type = re.sub(r"\s+", " ", str(data.get("shot_type") or "").strip())[:80]
    camera_view = re.sub(r"\s+", " ", str(data.get("camera_view") or "").strip())[:160]
    face_direction = re.sub(r"\s+", " ", str(data.get("face_direction") or "").strip())[:120]
    body_direction = re.sub(r"\s+", " ", str(data.get("body_direction") or "").strip())[:120]
    left_right_semantics = re.sub(r"\s+", " ", str(data.get("left_right_semantics") or "").strip())[:220]
    mirror_risk = re.sub(r"\s+", " ", str(data.get("mirror_risk") or "").strip())[:160]
    subject_framing = re.sub(r"\s+", " ", str(data.get("subject_framing") or "").strip())[:200]
    composition = re.sub(r"\s+", " ", str(data.get("composition") or "").strip())[:240]
    reason = re.sub(r"\s+", " ", str(data.get("reason") or "").strip())[:240]
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence") or 0)))
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "item_name": item_name,
        "category": category,
        "subject_presence": subject_presence,
        "face_presence": face_presence,
        "interaction": interaction,
        "placement": placement,
        "visual_details": visual_details,
        "material_signature": material_signature,
        "pose_description": pose_description,
        "shot_type": shot_type,
        "camera_view": camera_view,
        "face_direction": face_direction,
        "body_direction": body_direction,
        "left_right_semantics": left_right_semantics,
        "mirror_risk": mirror_risk,
        "subject_framing": subject_framing,
        "composition": composition,
        "confidence": round(confidence, 4),
        "reason": reason,
    }


def parse_universal_reference_analysis(text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE).strip()
    value = re.sub(r"\s*```$", "", value).strip()
    try:
        data = json.loads(value)
    except Exception:
        match = re.search(r"\{.*?\}", value, re.S)
        data = json.loads(match.group(0)) if match else {}
    return normalize_universal_reference_analysis(data)


def is_compatible_edit_model(model: str) -> bool:
    value = str(model or "").strip().lower()
    return bool(value and any(hint in value for hint in EDIT_MODEL_HINTS))


def build_model_catalog(providers: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for provider_index, provider in enumerate(providers or []):
        if not isinstance(provider, dict) or not provider.get("enabled", True):
            continue
        provider_id = str(provider.get("id") or "").strip().lower()
        if not provider_id:
            continue
        for model_index, model in enumerate(provider.get("image_models") or []):
            model_name = str(model or "").strip()
            if not is_compatible_edit_model(model_name):
                continue
            low = model_name.lower()
            if "gemini-3" in low or "nano-banana-pro" in low or "nano-banana-2" in low:
                max_reference_images = 14
            elif "gemini-2.5" in low or low in {"nano-banana", "nano-banana-fast"}:
                max_reference_images = 3
            else:
                max_reference_images = 10
            catalog.append({
                "provider_id": provider_id,
                "provider_name": str(provider.get("name") or provider_id),
                "model": model_name,
                "primary": bool(provider.get("primary")),
                "provider_order": provider_index,
                "model_order": model_index,
                "supports_multi_reference": True,
                "supports_mask": "gpt-image" in low or "qwen-image-edit" in low or "flux.2" in low,
                "max_reference_images": max_reference_images,
            })
    return catalog


def _priority_index(model: str, mode: str) -> int:
    validate_mode(mode)
    low = str(model or "").lower()
    for index, hint in enumerate(STANDARD_PRIORITIES):
        if hint in low:
            return index
    return len(STANDARD_PRIORITIES) + 1


def route_candidates(
    catalog: Iterable[dict[str, Any]],
    mode: str,
    provider_id: str = "",
    model: str = "",
) -> list[dict[str, Any]]:
    mode = validate_mode(mode)
    provider_id = str(provider_id or "").strip().lower()
    model = str(model or "").strip()
    items = [dict(item) for item in catalog or [] if isinstance(item, dict)]
    if provider_id:
        items = [item for item in items if str(item.get("provider_id") or "").lower() == provider_id]
    if model:
        exact = [item for item in items if str(item.get("model") or "") == model]
        if not exact:
            raise ValueError("所选平台没有该兼容图片编辑模型")
        exact.sort(key=lambda item: (
            0 if item.get("primary") else 1,
            int(item.get("provider_order") or 0),
            int(item.get("model_order") or 0),
        ))
        return exact
    items.sort(key=lambda item: (
        _priority_index(item.get("model", ""), mode),
        0 if item.get("primary") else 1,
        int(item.get("provider_order") or 0),
        int(item.get("model_order") or 0),
    ))
    return items


def select_route(catalog: Iterable[dict[str, Any]], mode: str, provider_id: str = "", model: str = "") -> dict[str, Any]:
    candidates = route_candidates(catalog, mode, provider_id, model)
    if not candidates:
        raise ValueError("没有找到兼容的图片编辑模型，请检查 API 设置")
    return candidates[0]


def normalize_inputs(inputs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in inputs or []:
        if not isinstance(value, dict):
            continue
        role = str(value.get("role") or "").strip().lower()
        url = str(value.get("url") or "").strip()
        if role not in ALLOWED_INPUT_ROLES or not url or role in seen:
            continue
        seen.add(role)
        item = {
            "role": role,
            "url": url,
            "name": str(value.get("name") or role)[:240],
            "kind": "image",
            "mime": str(value.get("mime") or "")[:120],
        }
        for key in ("reference_id", "reference_type", "label", "instruction"):
            if value.get(key):
                item[key] = re.sub(r"\s+", " ", str(value.get(key) or "").strip())[:300 if key == "instruction" else 160]
        normalized.append(item)
    return normalized


def normalize_try_on_inputs(inputs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_source = False
    seen_ids: set[str] = set()
    for index, value in enumerate(inputs or []):
        if not isinstance(value, dict):
            continue
        role = str(value.get("role") or "").strip().lower()
        reference_type = str(value.get("reference_type") or role).strip().lower()
        if reference_type == "subject":
            reference_type = "source"
        if reference_type == "prop":
            reference_type = "accessory"
        url = str(value.get("url") or "").strip()
        if reference_type not in TRY_ON_REFERENCE_ROLES or not url:
            continue
        if reference_type == "source":
            if seen_source:
                continue
            seen_source = True
        raw_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(value.get("reference_id") or role or f"reference_{index + 1}"))[:80]
        reference_id = raw_id or f"reference_{index + 1}"
        if reference_id in seen_ids:
            reference_id = f"{reference_id}_{index + 1}"
        seen_ids.add(reference_id)
        item = {
            "role": reference_type,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "url": url,
            "name": str(value.get("name") or reference_type)[:240],
            "kind": "image",
            "mime": str(value.get("mime") or "")[:120],
        }
        for key in ("label", "instruction"):
            if value.get(key):
                item[key] = re.sub(r"\s+", " ", str(value.get(key) or "").strip())[:300 if key == "instruction" else 160]
        normalized.append(item)
    return normalized


def normalize_universal_inputs(inputs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, value in enumerate(inputs or []):
        if not isinstance(value, dict):
            continue
        reference_type = str(value.get("reference_type") or value.get("role") or "").strip().lower()
        url = str(value.get("url") or "").strip()
        if reference_type not in UNIVERSAL_REFERENCE_ROLE_IDS or not url:
            continue
        raw_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(value.get("reference_id") or f"reference_{index + 1}"))[:80]
        reference_id = raw_id or f"reference_{index + 1}"
        if reference_id in seen_ids:
            reference_id = f"{reference_id}_{index + 1}"
        seen_ids.add(reference_id)
        normalized.append({
            "role": reference_type,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "url": url,
            "name": str(value.get("name") or reference_type)[:240],
            "label": re.sub(r"\s+", " ", str(value.get("label") or "").strip())[:160],
            "instruction": re.sub(r"\s+", " ", str(value.get("instruction") or "").strip())[:300],
            "kind": "image",
            "mime": str(value.get("mime") or "")[:120],
        })
        if len(normalized) >= UNIVERSAL_REFERENCE_LIMIT:
            break
    return normalized


def primary_pose_reference(inputs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    for value in inputs or []:
        if not isinstance(value, dict) or not str(value.get("url") or "").strip():
            continue
        role = str(value.get("reference_type") or value.get("role") or "").strip().lower()
        if role == "pose":
            return dict(value)
    return {}


def comparison_reference(inputs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    values = [dict(value) for value in inputs or [] if isinstance(value, dict) and str(value.get("url") or "").strip()]
    if universal_composition_mode(values) == "base_transfer":
        return values[0] if values else {}
    pose = primary_pose_reference(values)
    if pose:
        return pose
    source = next((value for value in values if str(value.get("reference_type") or value.get("role") or "").strip().lower() in {"source", "subject"}), None)
    return source or (values[0] if values else {})


def universal_composition_mode(inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    subject_like: list[dict[str, Any]] = []
    for value in inputs or []:
        if not isinstance(value, dict) or not str(value.get("url") or "").strip():
            continue
        role = str(value.get("reference_type") or value.get("role") or "").strip().lower()
        if role in {"source", "subject"}:
            subject_like.append(value)
    if not subject_like:
        return "base_transfer"
    if all(_subject_reference_is_product_template(item, _reference_analysis(item, options)) for item in subject_like):
        return "base_transfer"
    return "subject_composite"


def validate_input_roles(operation: str, inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    operation = validate_operation(operation)
    options = options if isinstance(options, dict) else {}
    if operation == "universal":
        values = list(inputs or [])
        if len(values) > UNIVERSAL_REFERENCE_LIMIT:
            raise ValueError(f"全能模式最多上传 {UNIVERSAL_REFERENCE_LIMIT} 张参考图")
        normalized = normalize_universal_inputs(values)
        if not normalized:
            raise ValueError("全能模式至少需要一张已上传的参考图")
        return normalized
    normalized = normalize_try_on_inputs(inputs) if operation == "try_on" else normalize_inputs(inputs)
    roles = {item["role"] for item in normalized}
    required = set(OPERATION_INPUTS[operation])
    if operation == "pose_transfer" and str(options.get("pose_source") or "preset") == "reference":
        required.add("pose")
    if operation == "background_change" and str(options.get("background_mode") or "preset") == "reference":
        required.add("background")
    missing = sorted(required - roles)
    if missing:
        raise ValueError("缺少必需输入：" + "、".join(missing))
    if operation == "try_on" and not (roles & TRY_ON_OUTFIT_ROLES):
        raise ValueError("缺少必需输入：garment")
    return normalized


def target_size(width: int, height: int, mode: str, aspect_ratio: str = "source", resolution: str = "auto") -> str:
    mode = validate_mode(mode)
    width = max(1, int(width or 1))
    height = max(1, int(height or 1))
    aspect_ratio = str(aspect_ratio or "source").strip().lower()
    resolution = str(resolution or "auto").strip().lower()
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError("不支持的生成比例")
    if resolution not in RESOLUTIONS:
        raise ValueError("分辨率只能是 auto、1k、2k 或 4k")
    resolved_resolution = "2k" if resolution == "auto" else resolution
    if aspect_ratio != "source":
        return SIZE_PRESETS[aspect_ratio][resolved_resolution]
    long_edge = {"1k": 1024, "2k": 2048, "4k": 3840}[resolved_resolution]
    scale = long_edge / max(width, height)
    out_w = max(64, int(round(width * scale / 64)) * 64)
    out_h = max(64, int(round(height * scale / 64)) * 64)
    return f"{out_w}x{out_h}"


def resolve_generation_settings(
    width: int,
    height: int,
    mode: str,
    aspect_ratio: str = "source",
    resolution: str = "auto",
    quality: str = "auto",
    count: int = 0,
) -> dict[str, Any]:
    mode = validate_mode(mode)
    aspect_ratio = str(aspect_ratio or "source").strip().lower()
    resolution = str(resolution or "auto").strip().lower()
    quality = str(quality or "auto").strip().lower()
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError("不支持的生成比例")
    if resolution not in RESOLUTIONS:
        raise ValueError("分辨率只能是 auto、1k、2k 或 4k")
    if quality not in QUALITIES:
        raise ValueError("质量只能是 auto、low、medium 或 high")
    try:
        selected_count = int(count or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("生成数量必须是 1 到 4") from exc
    if selected_count < 0 or selected_count > 4:
        raise ValueError("生成数量必须是 1 到 4，或使用自动")
    resolved_resolution = "2k" if resolution == "auto" else resolution
    resolved_quality = "high" if quality == "auto" else quality
    resolved_count = 1 if selected_count == 0 else selected_count
    return {
        "parameters": {
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "quality": quality,
            "count": selected_count,
        },
        "aspect_ratio": aspect_ratio,
        "resolution": resolved_resolution,
        "size": target_size(width, height, mode, aspect_ratio, resolved_resolution),
        "quality": resolved_quality,
        "count": resolved_count,
    }


def _preset_prompt(items: list[dict[str, Any]], preset_id: str, default_id: str) -> str:
    selected = next((item for item in items if item.get("id") == preset_id), None)
    if not selected:
        selected = next((item for item in items if item.get("id") == default_id), items[0])
    return str(selected.get("prompt") or "")


def build_studio_reference_lock(options: dict[str, Any] | None = None) -> str:
    studio_id = str((options or {}).get("studio_reference") or "").strip()
    if not studio_id:
        return ""
    selected = next((item for item in STUDIO_REFERENCE_PRESETS if item.get("id") == studio_id), None)
    if not selected:
        return ""
    label = selected.get("label", {}).get("en") or selected.get("label", {}).get("zh") or selected.get("id")
    prompt = str(selected.get("prompt") or "").strip()
    return (
        f"STUDIO REFERENCE LOCK: use the selected {label} as the final commercial photography studio direction: {prompt}. "
        "STUDIO BACKGROUND AUTHORITY: this selected studio is the mandatory final background. It controls backdrop color family, studio lighting, floor or cyclorama treatment, contact shadows, and listing polish. "
        "It overrides every source, base, scene, style, and background-reference environment. Do not use, preserve, blend, or infer any reference-image background, scenery, set, environmental palette, or environmental lighting in the final image. "
        "This studio lock must not override reference-owned body identity, pose, product geometry, material, SKU color, logo, readable text, or local detail evidence."
    )


def _global_preservation() -> str:
    return (
        "Change only the requested dimension. Preserve identity, silhouette, proportions, colors, materials, "
        "patterns, logos, readable product text, approved accessories, lighting, camera, and every non-target region. "
        "Do not add people, products, text, watermarks, duplicated limbs, mirrored logos, or unrelated objects."
    )


def _clean_prompt_text(*values: Any) -> str:
    return re.sub(r"\s+", " ", " ".join(str(value or "") for value in values).strip()).lower()


def _analysis_lookup(options: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw = (options or {}).get("reference_analysis")
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = ((str(item.get("reference_id") or item.get("id") or index), item) for index, item in enumerate(raw) if isinstance(item, dict))
    else:
        items = []
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in items:
        if isinstance(value, dict):
            normalized[str(key)] = normalize_universal_reference_analysis(value)
    return normalized


def _reference_analysis(item: dict[str, Any], options: dict[str, Any] | None) -> dict[str, Any]:
    analysis = _analysis_lookup(options)
    return analysis.get(str(item.get("reference_id") or "")) or analysis.get(str(item.get("name") or "")) or {}


def _presence_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")


def _subject_reference_is_product_template(item: dict[str, Any], analysis: dict[str, Any] | None = None) -> bool:
    role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
    if role not in {"source", "subject"}:
        return False
    analysis = analysis or {}
    subject_presence = _presence_token(analysis.get("subject_presence"))
    if subject_presence in HUMAN_SUBJECT_PRESENCE_VALUES:
        return False
    if subject_presence in NO_HUMAN_SUBJECT_PRESENCE_VALUES:
        return True
    face_presence = _presence_token(analysis.get("face_presence"))
    text = _clean_prompt_text(
        item.get("label"),
        item.get("instruction"),
        item.get("name"),
        analysis.get("item_name"),
        analysis.get("category"),
        analysis.get("shot_type"),
        analysis.get("visual_details"),
        analysis.get("reason"),
    )
    product_only_keywords = (
        "product only", "object only", "garment only", "flat lay", "flat-lay", "hanger", "mannequin",
        "no model", "no person", "no human", "without face", "no face",
        "商品图", "产品图", "商品主图", "白底图", "平铺", "挂拍", "衣架", "人台", "假模特",
        "无模特", "无人", "没有人", "没有真人", "没有人脸", "无脸",
    )
    human_keywords = ("真人模特", "真人图", "模特图", "人物图", "人脸图", "脸部清晰", "model face", "visible face")
    if any(keyword in text for keyword in product_only_keywords) and not any(keyword in text for keyword in human_keywords):
        return True
    return face_presence in NO_FACE_PRESENCE_VALUES and any(
        keyword in text
        for keyword in ("商品", "产品", "服装", "平铺", "挂拍", "衣架", "mannequin", "flat lay", "hanger")
    )


def _reference_detail(item: dict[str, Any], analysis: dict[str, Any] | None = None) -> str:
    analysis = analysis or {}
    detail = (
        analysis.get("item_name")
        or item.get("label")
        or analysis.get("category")
        or item.get("name")
        or item.get("reference_type")
        or item.get("role")
        or "reference"
    )
    evidence = [analysis.get("visual_details"), analysis.get("material_signature")]
    suffix = "; ".join(str(value).strip() for value in evidence if str(value or "").strip())
    return re.sub(r"\s+", " ", f"{detail}; {suffix}" if suffix else str(detail)).strip()[:520]


def build_ordered_reference_map(inputs: Iterable[dict[str, Any]]) -> str:
    role_names = {
        "source": "SOURCE / EDIT BASE",
        "garment": "GARMENT PRODUCT SOURCE",
        "model_identity": "MODEL IDENTITY ONLY",
        "upper_garment": "UPPER GARMENT SOURCE",
        "lower_garment": "LOWER GARMENT SOURCE",
        "full_garment": "DRESS OR FULL OUTFIT SOURCE",
        "shoes": "SHOES SOURCE",
        "accessory": "ACCESSORY SOURCE",
        "detail": "LOCAL PRODUCT DETAIL SOURCE",
        "pose": "POSE / SPATIAL TEMPLATE ONLY",
        "prop": "PROP OR PRODUCT SOURCE",
        "background": "BACKGROUND SOURCE ONLY",
        "scene": "SCENE SOURCE ONLY",
        "style": "STYLE SOURCE ONLY",
    }
    lines = []
    for index, item in enumerate(inputs or [], 1):
        role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
        if role == "mask":
            continue
        detail = _reference_detail(item)
        note = f"; specific instruction: {item['instruction']}" if item.get("instruction") else ""
        lines.append(f"Image {index} = [{role_names.get(role, role.upper() or 'REFERENCE')}] {detail}{note}")
    if not lines:
        return ""
    return (
        "ORDERED REFERENCE MAP: "
        + "; ".join(lines)
        + ". Each image controls only its bracketed role unless an explicit user instruction says otherwise."
    )


def build_user_directed_ecommerce_prompt(inputs: Iterable[dict[str, Any]], instruction: str) -> str:
    reference_count = len([item for item in inputs or [] if isinstance(item, dict) and str(item.get("url") or "").strip()])
    image_indexes = ", ".join(f"Image {index}" for index in range(1, reference_count + 1))
    ordered_note = (
        "REFERENCE IMAGE ORDER: upload the reference images to the API in this exact current panel order: "
        + image_indexes
        + ". If the user names 图1, 图2, 图3, Image 1, Image 2, or similar, use that exact uploaded image index."
    )
    parts = [
        "USER GENERATION REQUIREMENT: " + str(instruction or "").strip(),
        ordered_note,
        "DIRECT USER PROMPT MODE: do not add, infer, or apply automatic action, pose, background, camera, composition, scene, style, or reference-role instructions. The user's generation requirement is the only creative instruction.",
        REFERENCE_GROUNDED_MATERIAL_DIRECTIVE,
        ECOMMERCE_COLOR_FIDELITY_DIRECTIVE,
    ]
    return " ".join(part for part in parts if part).strip()


def _pose_spatial_detail(analysis: dict[str, Any] | None = None) -> str:
    analysis = analysis or {}
    values = [
        analysis.get("pose_description"),
        analysis.get("shot_type"),
        analysis.get("camera_view"),
        analysis.get("face_direction"),
        analysis.get("body_direction"),
        analysis.get("left_right_semantics"),
        analysis.get("mirror_risk"),
        analysis.get("subject_framing"),
        analysis.get("composition"),
    ]
    detail = "; ".join(str(value).strip() for value in values if str(value or "").strip())
    return re.sub(r"\s+", " ", detail).strip()[:600]


def _pose_orientation_lock(index: int | None = None) -> str:
    image = f"Image {index}" if index else "the pose reference"
    return (
        f"Preserve {image}'s non-mirrored screen-side orientation: viewer-left remains viewer-left and viewer-right remains viewer-right. "
        "Match the face/gaze direction, nose/profile direction, torso yaw, visible body side, and the screen-side order of shoulders, arms, hands, hips, legs, and feet. "
        "If the reference face looks toward the viewer's right, the final person must also look toward the viewer's right; if it looks toward the viewer's left, keep it toward the viewer's left. "
        "Do not mirror, horizontally flip, reverse the profile, or swap left/right limbs."
    )


def build_subject_spatial_lock(inputs: Iterable[dict[str, Any]]) -> str:
    normalized = list(inputs or [])
    if any(str(item.get("reference_type") or item.get("role") or "").strip().lower() == "pose" for item in normalized):
        return ""
    for index, item in enumerate(normalized, 1):
        role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
        if role not in {"source", "subject"}:
            continue
        detail = _reference_detail(item)
        return (
            f"BASE SUBJECT SPATIAL LOCK: because no separate pose reference is provided, Image {index} ({detail}) owns the final pose, leg position, hand position, body posture, camera angle, shot scale, framing, crop, subject placement, and composition. "
            "Strictly preserve the base image's pose/action, legs, hands, gaze/body direction, perspective, and layout while changing only the mapped garment/product/detail regions. "
            + _pose_orientation_lock(index)
        )
    return ""


def build_no_model_product_subject_lock(inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    normalized = list(inputs or [])
    if not normalized:
        return ""
    first = normalized[0]
    role = str(first.get("reference_type") or first.get("role") or "").strip().lower()
    if role not in {"source", "subject"}:
        return ""
    analysis = _reference_analysis(first, options)
    if _subject_reference_is_product_template(first, analysis):
        prefix = "Image 1 has been identified as a no-model product base."
    else:
        prefix = "If Image 1 is a no-model product-only, mannequin, hanger, flat-lay, ghost-mannequin, or face-less product reference,"
    return (
        "NO-MODEL PRODUCT BASE LOCK: "
        + prefix
        + " Do not invent a real person, face, hands, feet, shoes, jewelry, bag, or styling accessory. Treat Image 1 as A款 base/template and fit only the explicitly mapped B款 product onto that A base silhouette, layout, camera, crop, and lighting. "
        "Later garment/product/detail references provide B款 product identity and local detail evidence only; incidental shoes, bags, jewelry, hats, props, people, backgrounds, or styling accessories inside those B references must be ignored unless uploaded and labeled as their own mapped reference."
    )


def _reference_named_scope(item: dict[str, Any]) -> str:
    values = [
        str(item.get("label") or "").strip(),
        str(item.get("instruction") or "").strip(),
        str(item.get("name") or "").strip(),
    ]
    return re.sub(r"\s+", " ", "; ".join(value for value in values if value)).strip()[:360]


def build_named_detail_region_lock(inputs: Iterable[dict[str, Any]]) -> str:
    lines = []
    for index, item in enumerate(inputs or [], 1):
        role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
        if role != "detail":
            continue
        scope = _reference_named_scope(item)
        if scope:
            lines.append(f"Image {index}: {scope}")
    if not lines:
        return ""
    return (
        "NAMED DETAIL REGION LOCK: custom detail names are binding local region labels, not generic style notes. "
        "Apply each named detail only to its matching garment/product region, such as waistband, pocket-button, side seam, hem, label, zipper, hardware, logo, or stitching. "
        "Do not merge different detail references into one generic detail, do not let a side-detail override a waistband-detail, and do not change pose, body identity, camera, background, or unrelated garment panels from detail images. "
        "Named detail evidence: " + "; ".join(lines) + "."
    )


def build_lower_garment_structure_lock(inputs: Iterable[dict[str, Any]]) -> str:
    lower_keywords = (
        "lower", "pants", "trousers", "jeans", "wide-leg", "straight-leg", "flared", "tapered", "skinny",
        "下装", "裤", "裤子", "长裤", "牛仔裤", "阔腿", "直筒", "喇叭", "小脚", "腰头", "口袋", "侧边", "侧缝", "裤线",
    )
    lines = []
    for index, item in enumerate(inputs or [], 1):
        role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
        text = _clean_prompt_text(role, item.get("label"), item.get("instruction"), item.get("name"))
        if role == "lower_garment" or any(keyword.lower() in text for keyword in lower_keywords):
            lines.append(f"Image {index}: {_reference_detail(item)}")
    if not lines:
        return ""
    return (
        LOWER_GARMENT_STRUCTURE_DIRECTIVE
        + " Mapped lower-body evidence: "
        + "; ".join(lines)
        + "."
    )


def build_user_waistband_geometry_lock(instruction: str) -> str:
    text = _clean_prompt_text(instruction).lower()
    if not text:
        return ""
    waist_terms = ("腰头", "腰线", "腰口", "腰围", "裤腰", "waistband", "waist line", "waistline")
    level_terms = (
        "红线", "水平", "同一水平", "齐平", "补高", "补齐", "下凹", "凹处", "前中", "中间",
        "flat", "level", "straight", "horizontal", "raise", "fill", "dip", "notch", "concave",
    )
    if not any(term in text for term in waist_terms) or not any(term in text for term in level_terms):
        return ""
    return (
        "USER-REQUESTED WAISTBAND GEOMETRY LOCK: treat the user's supplemental instruction as a hard local-edit constraint for the waistband top edge. "
        "If a red guide line or marked waist edge is visible in the reference, use it as the target level line. "
        "Raise and fill any lower center-front dip, notch, concave valley, or downward V in the waistband until the front-center top edge is flush with the left and right waistband top edge, forming one straight horizontal upper contour. "
        "Do not lower either side of the waistband, do not keep or recreate the center-front dip, and do not curve the final top edge. "
        "Preserve the original fabric color, texture, seams, button, belt loops, fly, pockets, body pose, crop, lighting, and background outside this local waistband geometry change."
    )


def infer_universal_interaction(item: dict[str, Any], analysis: dict[str, Any] | None = None) -> str:
    analysis = analysis or {}
    role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
    suggested = str(analysis.get("interaction") or "").strip().lower()
    text = _clean_prompt_text(
        role,
        item.get("label"),
        item.get("instruction"),
        item.get("name"),
        analysis.get("item_name"),
        analysis.get("category"),
        analysis.get("visual_details"),
    )
    if role == "subject":
        return "identity"
    if role in {"upper_garment", "lower_garment", "full_garment"}:
        return "wear"
    if role == "shoes":
        return "put_on"
    if role == "pose":
        return "pose"
    if role == "scene":
        return "scene"
    if role == "style":
        return "style"
    if any(keyword in text for keyword in BAG_KEYWORDS):
        return "carry"
    if any(keyword in text for keyword in PLACED_PROP_KEYWORDS):
        return "place"
    if any(keyword in text for keyword in HANDHELD_KEYWORDS):
        return "hold"
    if any(keyword in text for keyword in ACCESSORY_WEAR_KEYWORDS):
        return "wear"
    if suggested in {"wear", "put_on", "hold", "carry", "place", "use"}:
        return suggested
    return "wear" if role == "accessory" else "hold"


def _interaction_phrase(index: int, item: dict[str, Any], analysis: dict[str, Any] | None = None) -> str:
    role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
    detail = _reference_detail(item, analysis)
    interaction = infer_universal_interaction(item, analysis)
    if role == "subject":
        return (
            f"Use Image {index} as the exact same primary model, preserving identity, face, hair, body proportions, skin tone, "
            "and all visible native shoes, jewelry, bags, belts, watches, eyewear, hats, socks, and styling accessories unless an explicit mapped reference or user supplement replaces that exact item."
        )
    if role == "model_identity":
        return (
            f"Use Image {index} only as the MODEL IDENTITY reference, preserving the face, hairstyle, skin tone, makeup, age cues, and recognizable personal appearance. "
            "Do not copy its body pose, clothing, accessories, background, camera framing, or scene content."
        )
    if role == "upper_garment":
        return f"Dress the model in the exact upper garment from Image {index} ({detail})."
    if role == "lower_garment":
        return f"Dress the model in the exact lower garment from Image {index} ({detail})."
    if role == "full_garment":
        return f"Dress the model in the exact full outfit or dress from Image {index} ({detail})."
    if role == "shoes":
        return f"Put the exact shoes from Image {index} ({detail}) on the model's feet."
    if role == "detail":
        return f"Use the exact product detail from Image {index} ({detail}), preserving its construction, material, color, pattern, logo, text, and craftsmanship."
    if role in {"accessory", "prop"}:
        if interaction == "wear":
            verb = "Have the model wear"
        elif interaction == "put_on":
            verb = "Put"
        elif interaction == "carry":
            verb = "Have the model naturally carry"
        elif interaction == "place":
            verb = "Place"
        elif interaction == "use":
            verb = "Have the model naturally use"
        else:
            verb = "Have the model naturally hold"
        placement = f" {analysis.get('placement')}." if analysis and analysis.get("placement") else ""
        return f"{verb} the exact item from Image {index} ({detail}).{placement}"
    if role == "pose":
        detected = _pose_spatial_detail(analysis)
        detected_note = f" Detected spatial cues: {detected}." if detected else ""
        return (
            f"Use Image {index} as the PRIMARY SPATIAL / POSE TEMPLATE. Match its exact body pose/action, joint positions, gesture, balance, "
            "camera viewpoint, shot scale, framing and crop, subject size and position, and foreground composition. "
            + _pose_orientation_lock(index) + " "
            "If it is full-body, keep full-body; if it is three-quarter, half-body, or close-up, keep that same shot. "
            "Do not zoom, reframe, extend the body beyond the reference crop, or reposition the model by default. "
            "Treat it only as spatial control: never copy their identity, clothing, accessories, or background content."
            + detected_note
        )
    if role == "scene":
        return f"Place the model and products inside the scene from Image {index}, matching environment layout, perspective, and natural lighting."
    if role == "style":
        return f"Apply only the color, lighting, contrast, and finish style from Image {index}; do not copy its subjects or layout."
    return f"Use Image {index} as a reference for {detail}."


def _base_transfer_source_phrase(
    index: int,
    item: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    supplemental: bool = False,
    detail_auxiliary: bool = False,
) -> str:
    analysis = analysis or {}
    role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
    detail = _reference_detail(item, analysis)
    if supplemental:
        return (
            f"Use Image {index} only as supplemental evidence for the same {role or 'reference'} replacement ({detail}); "
            "it must not override the primary replacement source unless its per-image instruction explicitly says so."
        )
    if role == "detail":
        if detail_auxiliary:
            return (
                f"Use Image {index} only as auxiliary local detail evidence for the primary B replacement product ({detail}). "
                "Apply it only to the matching local region such as collar, cuff, waist, pocket, hem, label, zipper, hardware, logo, stitching, print, or fabric texture. "
                "Do not treat this detail image as a standalone replacement item and do not copy its background, styling props, shoes, bags, jewelry, hangers, or unrelated accessories."
            )
        return (
            f"Replace the product/detail content in Image 1 with the exact product detail from Image {index} ({detail}). "
            "This source owns the replacement product's geometry, construction, material, color, pattern, logo, readable text, stitching, and craftsmanship. "
            "Ignore incidental shoes, bags, jewelry, hats, props, people, hangers, backgrounds, or styling accessories inside this reference unless those items are explicitly uploaded as their own mapped reference."
        )
    if role == "model_identity":
        return (
            f"Transfer only the model identity from Image {index} ({detail}) onto the person in Image 1: face, hair, skin tone, makeup, age cues, and recognizable appearance. "
            "Keep Image 1's body proportions, pose, camera, crop, clothing or product layout, background, lighting, and shadows unless another mapped reference explicitly owns that attribute."
        )
    if role in {"upper_garment", "lower_garment", "full_garment", "shoes", "accessory", "prop"}:
        return (
            f"Replace or integrate the corresponding {role.replace('_', ' ')} in Image 1 using the exact item from Image {index} ({detail}). "
            "This source owns the replacement item's identity and product fidelity. "
            "Extract only the explicitly mapped target item for this role; ignore incidental shoes, bags, jewelry, hats, styling props, people, mannequins, backgrounds, or other accessories visible in the same product photo unless they are uploaded and labeled as their own shoes/accessory/prop reference."
        )
    if role == "scene":
        return f"Replace only the environment in Image 1 with the scene from Image {index}, while keeping Image 1's framing, camera, subject scale, and foreground layout."
    if role == "style":
        return f"Apply only the palette, lighting, contrast, and finish from Image {index}; do not copy its subjects, products, or layout."
    if role == "pose":
        return (
            f"Use Image {index} only for the requested pose or spatial cue while retaining Image 1 as the visual base; "
            "do not copy identity, clothing, products, or background content from the pose source."
        )
    return f"Apply the exact requested content from Image {index} ({detail}) to the corresponding region of Image 1."


def build_universal_base_transfer_instruction(inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    normalized = list(inputs or [])
    if not normalized:
        return ""
    base = normalized[0]
    base_analysis = _reference_analysis(base, options)
    base_detail = _reference_detail(base, base_analysis)
    spatial = _pose_spatial_detail(base_analysis)
    spatial_note = f" Detected base layout cues: {spatial}." if spatial else ""
    if _subject_reference_is_product_template(base, base_analysis):
        base_line = (
            f"Use Image 1 ({base_detail}) as the A-style product/body template and editable BASE IMAGE, not as a real human model. "
            "Preserve its product silhouette, support shape, hanger/mannequin/flat-lay form if present, shot type, camera angle, perspective, crop, composition, background, lighting, shadows, scale, placement, and negative space except where the mapped B replacement product requires a local change. "
            "Do not invent a face, head, hands, feet, full human body, shoes, jewelry, bag, or accessory just because later product references contain them."
            + spatial_note
        )
    else:
        base_line = (
            f"Use Image 1 ({base_detail}) as the editable BASE IMAGE and final visual template. Preserve its shot type, camera angle, "
            "perspective, crop, composition, background, lighting, shadows, scale, placement, and negative space except where a mapped replacement requires a local change."
            + spatial_note
        )
    lines = [base_line]
    seen_source_roles: set[str] = set()
    primary_product_seen = False
    for index, item in enumerate(normalized[1:], 2):
        role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
        detail_auxiliary = role == "detail" and primary_product_seen
        lines.append(_base_transfer_source_phrase(index, item, _reference_analysis(item, options), role in seen_source_roles, detail_auxiliary))
        seen_source_roles.add(role)
        if role in PRIMARY_PRODUCT_REPLACEMENT_ROLES:
            primary_product_seen = True
    lines.append(
        "Remove the superseded content from Image 1 completely. Do not blend old and new product identities, retain ghost remnants, invent a model, "
        "expand a close-up into a full-body scene, or copy unrelated people, products, backgrounds, text, or watermarks from replacement sources."
    )
    return "AUTO BASE TRANSFER: " + " ".join(lines)


def build_universal_auto_instruction(inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    normalized = list(inputs or [])
    if universal_composition_mode(normalized) == "base_transfer":
        return build_universal_base_transfer_instruction(normalized, options)
    lines = []
    for index, item in enumerate(normalized, 1):
        lines.append(_interaction_phrase(index, item, _reference_analysis(item, options)))
    if not lines:
        return ""
    return (
        "AUTO FINAL COMPOSITION: "
        + " ".join(lines)
        + " Produce one coherent, marketplace-ready high-end e-commerce product image with a polished catalog/lifestyle look, clean composition, believable fit, contact, scale, shadows, and SKU-level product fidelity."
    )


def build_universal_material_evidence_lock(inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    normalized = list(inputs or [])
    evidence_lines = []
    for index, item in enumerate(normalized, 1):
        role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
        if role not in TEXTURE_CRITICAL_REFERENCE_ROLES:
            continue
        detail = _reference_detail(item, _reference_analysis(item, options))
        evidence_lines.append(f"Image {index}: {role.replace('_', ' ')} material evidence ({detail})")
    if not evidence_lines:
        return REFERENCE_GROUNDED_MATERIAL_DIRECTIVE
    return (
        "MATERIAL EVIDENCE LOCK: use these references for pixel-grounded material fidelity: "
        + "; ".join(evidence_lines)
        + ". Detail images are texture and craftsmanship evidence for their matching garment or product only; they must not change body identity, pose, camera, background, or unrelated regions. "
        "Scene, style, pose, and model identity references must never override product material, weave, grain, color, print, logo, text, stitching, or finish. "
        + REFERENCE_GROUNDED_MATERIAL_DIRECTIVE
    )


def build_subject_native_styling_lock(inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    normalized = list(inputs or [])
    subject_sources = []
    explicit_overrides = []
    for index, item in enumerate(normalized, 1):
        role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
        analysis = _reference_analysis(item, options)
        if role in {"subject", "source"} and not _subject_reference_is_product_template(item, analysis):
            subject_sources.append(f"Image {index}")
        if role in SUBJECT_NATIVE_STYLING_OVERRIDE_ROLES:
            detail = _reference_detail(item, analysis)
            explicit_overrides.append(f"Image {index} ({role.replace('_', ' ')}: {detail})")
    if not subject_sources:
        return ""
    override_text = "; ".join(explicit_overrides) if explicit_overrides else "none"
    return (
        "SUBJECT-NATIVE STYLING LOCK: preserve visible shoes, socks, stockings, jewelry, eyewear, hats, belts, watches, hair accessories, bags, scarves, "
        "handheld or worn accessories, and styling props already present on the subject reference(s) "
        + ", ".join(subject_sources)
        + ". Treat these as subject-owned unchanged styling by default. Do not erase, simplify, replace, recolor, or borrow alternatives from garment, pose, scene, style, model identity, product, or detail references. "
        "Only replace a subject-native shoe, accessory, bag, jewelry item, or prop when the USER SUPPLEMENT or a per-image instruction explicitly names another image and the exact item to use, "
        "or when a later image is deliberately mapped as SHOES, JEWELRY OR ACCESSORY, or PROP OR PRODUCT for that exact item. "
        f"Explicit mapped styling overrides: {override_text}."
    )


def build_prompt(operation: str, inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    operation = validate_operation(operation)
    normalized = validate_input_roles(operation, inputs, options)
    options = options if isinstance(options, dict) else {}
    reference_map = build_ordered_reference_map(normalized)
    mask_note = " A final mask reference marks red pixels to replace and green pixels to preserve." if any(item["role"] == "mask" for item in normalized) else ""
    instruction = str(options.get("instruction") or "").strip()
    if instruction:
        return build_user_directed_ecommerce_prompt(normalized, instruction)
    lower_garment_lock = build_lower_garment_structure_lock(normalized)
    named_detail_lock = build_named_detail_region_lock(normalized)
    user_waistband_geometry_lock = build_user_waistband_geometry_lock(instruction)
    subject_spatial_lock = ""
    no_model_product_lock = build_no_model_product_subject_lock(normalized, options) if operation == "universal" else ""
    studio_reference_lock = build_studio_reference_lock(options)
    studio_background_selected = bool(studio_reference_lock)

    if operation == "universal":
        composition_mode = universal_composition_mode(normalized, options)
        if composition_mode == "subject_composite":
            subject_spatial_lock = build_subject_spatial_lock(normalized)
        subject_native_styling_lock = build_subject_native_styling_lock(normalized, options)
        role_names = {
            "subject": "PRIMARY SUBJECT / BODY MODEL / NATIVE STYLING",
            "model_identity": "MODEL IDENTITY",
            "upper_garment": "UPPER GARMENT",
            "lower_garment": "LOWER GARMENT",
            "full_garment": "DRESS OR FULL OUTFIT",
            "shoes": "SHOES",
            "accessory": "JEWELRY OR ACCESSORY",
            "prop": "PROP OR PRODUCT",
            "detail": "PRODUCT DETAIL",
            "pose": "PRIMARY SPATIAL / POSE TEMPLATE",
            "scene": "SCENE / BACKGROUND ONLY",
            "style": "STYLE / LIGHTING ONLY",
        }
        reference_map = []
        for index, item in enumerate(normalized):
            analysis = _reference_analysis(item, options)
            detail = _reference_detail(item, analysis)
            note = f"; specific instruction: {item['instruction']}" if item.get("instruction") else ""
            role_name = role_names[item["reference_type"]]
            if composition_mode == "base_transfer" and index == 0:
                role_name = "BASE IMAGE / PRODUCT TEMPLATE" if _subject_reference_is_product_template(item, analysis) else f"BASE IMAGE / {role_name}"
            elif composition_mode == "base_transfer" and item["reference_type"] == "detail":
                role_name = "DETAIL REPLACEMENT SOURCE"
            reference_map.append(f"Image {index + 1} = [{role_name}] {detail}{note}")
        auto_instruction = build_universal_auto_instruction(normalized, options)
        final_instruction = auto_instruction
        if composition_mode == "base_transfer":
            base_image_ownership = (
                "Image 1 owns the final layout, shot type, camera, perspective, crop, shadows, scale, placement, and negative space, but the selected studio exclusively owns the final background, backdrop, and environmental lighting. Do not preserve or reuse Image 1's background. "
                if studio_background_selected else
                "Image 1 owns the final layout, shot type, camera, perspective, crop, background, lighting, shadows, scale, placement, and negative space. "
            )
            conflict_priority = (
                "CONFLICT PRIORITY: The selected studio is highest priority for the final background. For all non-background attributes: an explicit USER SUPPLEMENT is highest. Otherwise: (1) Image 1 visual template, (2) the first replacement source of each reference type, "
                "(3) later same-type sources as supplemental evidence, (4) scene content, (5) style. "
                if studio_background_selected else
                "CONFLICT PRIORITY: An explicit USER SUPPLEMENT is highest. Otherwise: (1) Image 1 visual template, (2) the first replacement source of each reference type, "
                "(3) later same-type sources as supplemental evidence, (4) scene content, (5) style. "
            )
            task = (
                "Edit the first reference into one coherent, marketplace-ready photorealistic e-commerce image by following this exact ordered reference map:\n"
                + "\n".join(reference_map)
                + "\nFINAL COMPOSITION: " + final_instruction
                + "\n" + build_universal_material_evidence_lock(normalized, options)
                + ("\n" + subject_native_styling_lock if subject_native_styling_lock else "")
                + "\n" + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE
                + "\nREFERENCE OWNERSHIP RULES: " + base_image_ownership
                + "Image 1 also owns any visible native shoes, accessories, bags, jewelry, belts, watches, eyewear, socks, and styling props unless an exact mapped shoe/accessory/prop override or explicit USER SUPPLEMENT replaces that item. "
                + "Model identity references own only face, hair, skin tone, makeup, age cues, and recognizable personal appearance. "
                + "Each later product or detail source owns only the exact replacement item's geometry, construction, material, color, pattern, logo, readable text, stitching, and craftsmanship. "
                + "Scene references own only environment content; style references own only palette and finish. "
                + conflict_priority
                + "Keep all unaffected pixels and structures from Image 1 as stable as possible. Resolve boundaries, contact, scale, perspective, shadows, and reflections naturally. "
                + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
            )
        else:
            scene_ownership = (
                "Scene references do not contribute background, scenery, environmental palette, or environmental lighting when a studio is selected; the selected studio exclusively owns those attributes. "
                if studio_background_selected else
                "Scene references own environment appearance, environmental perspective, and lighting, but must fit the pose reference's camera and framing; never copy foreground people or products. "
            )
            conflict_priority = (
                "CONFLICT PRIORITY: The selected studio is highest priority for the final background. For all non-background attributes, an explicit USER SUPPLEMENT may override framing or shot scale. Otherwise: (1) model identity for face/hair/skin when present, (2) subject/body reference, (3) the primary pose reference as highest-priority spatial authority, (4) exact product fidelity, (5) scene content and lighting, (6) style. "
                if studio_background_selected else
                "CONFLICT PRIORITY: An explicit USER SUPPLEMENT may override framing or shot scale. Otherwise: (1) model identity for face/hair/skin when present, (2) subject/body reference, (3) the primary pose reference as highest-priority spatial authority, (4) exact product fidelity, (5) scene content and lighting, (6) style. "
            )
            task = (
                "Create one coherent, marketplace-ready photorealistic e-commerce image by following this exact ordered reference map:\n"
                + "\n".join(reference_map)
                + "\nFINAL COMPOSITION: " + final_instruction
                + "\n" + build_universal_material_evidence_lock(normalized, options)
                + ("\n" + subject_native_styling_lock if subject_native_styling_lock else "")
                + "\n" + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE
                + "\nREFERENCE OWNERSHIP RULES: Subject references own the primary body, body proportions, base silhouette, identity, and visible native shoes/accessories/styling unless a model identity reference is provided for face/hair/skin only or an exact mapped shoe/accessory/prop override is provided. "
                + "Model identity references own face, hair, skin tone, makeup, age cues, and recognizable personal appearance only; they do not own body proportions, pose, clothing, accessories, background, camera, or layout. "
                + "Garment, shoe, accessory, prop, and detail references own their exact product geometry, construction, material, color, pattern, logo, and readable text only. "
                + "The first pose reference is the highest-priority spatial authority and owns body posture, joint arrangement, balance, gesture, camera viewpoint, shot scale, framing and crop, subject size and position, foreground composition, non-mirrored screen-side orientation, face/gaze direction, torso yaw, and left/right limb order. Never copy its identity, clothing, accessories, or background content. "
                + scene_ownership
                + "Style references own only palette, finish, contrast, and lighting treatment; never copy subjects or layout. "
                + conflict_priority
                + "Resolve occlusion, fit, scale, perspective, grip, contact shadows, reflections, fabric folds, and anatomy physically. "
                + "Do not blend identities or leak clothing, people, props, or backgrounds between references. Do not silently zoom, reframe, change shot scale, change crop, alter subject placement, mirror the pose, reverse the profile direction, or swap left/right limbs from the primary pose reference. "
                + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
            )
    elif operation == "try_on":
        role_names = {
            "garment": "main garment",
            "model_identity": "model identity",
            "upper_garment": "upper garment",
            "lower_garment": "lower garment",
            "full_garment": "dress or full outfit",
            "shoes": "shoes",
            "accessory": "accessory",
            "detail": "detail image",
        }
        outfit_refs = [item for item in normalized if item["role"] in TRY_ON_OUTFIT_ROLES]
        pose_index = next((index + 1 for index, item in enumerate(normalized) if item["role"] == "pose"), 0)
        identity_index = next((index + 1 for index, item in enumerate(normalized) if item["role"] == "model_identity"), 0)
        legacy_category = {"upper": "upper-body garment", "lower": "lower-body garment", "dress": "dress or one-piece", "auto": "garment"}.get(str(options.get("garment_category") or "auto"), "garment")
        outfit_lines = []
        for item in outfit_refs:
            detail = item.get("label") or item.get("name") or role_names.get(item["role"], item["role"])
            note = f"; specific instruction: {item['instruction']}" if item.get("instruction") else ""
            role_label = legacy_category if item["role"] == "garment" else role_names.get(item["role"], item["role"])
            outfit_lines.append(f"{role_label}: exact reference product from its image ({detail}{note})")
        outfit_map = "; ".join(outfit_lines)
        detail_lines = []
        for index, item in enumerate(normalized, 1):
            if item["role"] != "detail":
                continue
            detail = item.get("label") or item.get("name") or role_names.get(item["role"], item["role"])
            note = f"; specific instruction: {item['instruction']}" if item.get("instruction") else ""
            detail_lines.append(f"Image {index}: exact local detail reference ({detail}{note})")
        detail_instruction = (
            " Use detail references only to refine corresponding garment or product fidelity: "
            + "; ".join(detail_lines)
            + ". Preserve their material, color, pattern, logo, readable text, stitching, edges, and craftsmanship without changing body identity, pose, framing, or unrelated garment regions."
            if detail_lines
            else ""
        )
        garment_type = re.sub(r"\s+", " ", str(options.get("garment_type") or "").strip())[:120]
        detected_note = f" If a generic garment reference is used, it was visually identified as {garment_type}." if garment_type else ""
        source_instruction = (
            f"Preserve the source person's body shape, limb proportions, source lighting, camera, and background. Use Image {identity_index} only as model identity: transfer face, hairstyle, skin tone, makeup, age cues, and recognizable appearance without copying its body pose, clothing, accessories, background, or framing."
            if identity_index
            else "Preserve the source person's face, hair, body shape, identity, skin tone, lighting, and background."
        )
        pose_instruction = (
            f" Use Image {pose_index} only as the spatial / pose template: match its body action, joint arrangement, gesture, balance, camera viewpoint, shot scale, framing, crop, subject size, and placement. "
            + _pose_orientation_lock(pose_index) + " "
            "Do not copy the pose reference person's identity, clothing, accessories, or background."
            if pose_index
            else " Preserve the source person's pose, hands, framing, lighting, and background."
        )
        task = (
            "Create a marketplace-ready virtual try-on outfit on the person in the source image with SKU-level garment fidelity. "
            f"Use these outfit references in their natural dress-up layer order: {outfit_map or legacy_category}. "
            f"{detected_note} "
            f"{source_instruction} "
            f"{pose_instruction} "
            "Preserve every referenced clothing item's neckline, sleeve and hem geometry, fit, fabric texture, material micro-texture, colors, pattern, logo, label, tag, and readable text. "
            f"{detail_instruction} "
            "Layer upper garments, lower garments, full outfits, shoes, and accessories with physically natural scale, folds, seams, clean edges, contact, coverage, occlusions, and e-commerce catalog polish. "
            "TRY-ON MATERIAL LOCK: garment, shoe, accessory, and detail references are pixel-grounded product evidence. Warp garment reference textures onto the body with correct tension, fold direction, seam alignment, fabric thickness, and occlusion; do not repaint the garment with a generic textile, simplify the weave, change hardware, or invent alternate trims. "
            "When product graphics or labels appear on garments, preserve their exact readable content and do not invent new markings. "
            + REFERENCE_GROUNDED_MATERIAL_DIRECTIVE + " "
            + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE + " "
            + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
        )
    elif operation == "pose_transfer":
        if str(options.get("pose_source") or "preset") == "reference":
            target = (
                "Use the pose reference image as the exact spatial template. Match its body posture, joint arrangement, balance, gesture, camera viewpoint, "
                "shot scale, framing and crop, subject size and position, and foreground composition. If it is full-body, keep full-body; if it is three-quarter, "
                "half-body, or close-up, keep the same shot. " + _pose_orientation_lock() + " "
                "Do not zoom, reframe, extend the body beyond its crop, or reposition the person unless the additional user instruction explicitly requests it. "
                "Do not copy the pose reference person's identity, clothes, accessories, or background content."
            )
            task = (
                target + " Preserve the source person's identity, facial features, body proportions, outfit, accessories, SKU-level product details, logos, labels, readable text, lighting, and background appearance. "
                "Let the pose reference override the source image only for pose and spatial composition. Keep anatomy, balance, hands, feet, fabric tension, folds, clean garment edges, and occlusions realistic. "
                "POSE TRANSFER SOURCE LOCK: reproject source clothing textures, product details, logos, labels, jewelry, hairstyle, skin texture, and background from the source image through the new pose; do not redesign, denoise, simplify, recolor, or replace the outfit while changing posture. "
                "Keep product graphics and garment text non-mirrored and readable after the pose change. "
                + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE + " "
                + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
            )
        else:
            target = "Apply this target pose: " + _preset_prompt(POSE_PRESETS, str(options.get("pose_preset") or "standing_front"), "standing_front") + "."
            task = (
                target + " Preserve the source person's identity, facial expression, body proportions, outfit, accessories, SKU-level product details, logos, labels, readable text, camera framing, lighting, and background. "
                "Keep anatomy, balance, hands, feet, fabric tension, folds, clean garment edges, and occlusions realistic. "
                "POSE TRANSFER SOURCE LOCK: reproject source clothing textures, product details, logos, labels, jewelry, hairstyle, skin texture, and background from the source image through the new pose; do not redesign, denoise, simplify, recolor, or replace the outfit while changing posture. "
                "Keep product graphics and garment text non-mirrored and readable after the pose change. "
                + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE + " "
                + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
            )
    elif operation == "prop_replace":
        target_description = str(options.get("target_description") or "the matching existing prop").strip()
        task = (
            f"Replace only {target_description} in the source image with the exact prop or product from the prop reference for a marketplace-ready listing image. "
            "The new prop owns SKU-level product fidelity: exact silhouette, dimensions, material micro-texture, colors, packaging seams, hardware, logo, label, and readable text. "
            "Match believable scale, perspective, grip or contact, lighting, shadow, reflection, occlusion, and clean edges. "
            "Remove every remnant of the old prop while leaving all pixels outside the target region semantically unchanged. "
            "PROP REPLACEMENT MATERIAL LOCK: the prop reference is the pixel-grounded material and branding source; preserve its surface finish, grain, stitching, packaging folds, metal/plastic/leather/glass response, printed text, and edge geometry. Do not leave old prop shadows, handles, straps, reflections, masks, halos, or ghost fragments. "
            + REFERENCE_GROUNDED_MATERIAL_DIRECTIVE + " "
            + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE + " "
            + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
        )
    elif operation == "angle_change":
        azimuth = max(-180, min(180, int(options.get("azimuth") or 0)))
        elevation = max(-30, min(30, int(options.get("elevation") or 0)))
        distance = {"close": "close shot", "medium": "medium shot", "wide": "wide full-subject shot"}.get(str(options.get("distance") or "medium"), "medium shot")
        task = (
            f"Move the camera to azimuth {azimuth} degrees and elevation {elevation} degrees, using a {distance}, as a clean e-commerce viewpoint regeneration. "
            "Rotate the viewpoint around the subject; do not rotate, redesign, mirror, recolor, or replace the subject. "
            "Infer newly visible surfaces consistently with the same SKU structure, dimensions, material micro-texture, colors, seams, hardware, logos, labels, and readable text. "
            "Keep geometry, perspective, product edges, contact shadows, reflections, and background continuity believable. "
            "ANGLE REGENERATION SKU LOCK: preserve the same product identity while changing only camera viewpoint; never mirror or garble logos/text, invent unseen decorations, change material scale, flatten curved surfaces, distort symmetry, or alter package/product proportions. Newly visible surfaces must follow the source material grain, construction logic, and lighting response. "
            + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE + " "
            + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
        )
    else:
        background_mode = str(options.get("background_mode") or "preset")
        if background_mode == "reference":
            target = "Use the background reference for environment, composition, palette, and lighting, without copying any foreground subject from it."
        elif background_mode == "prompt":
            target = str(options.get("background_prompt") or "clean professional e-commerce studio background").strip()
        else:
            target = _preset_prompt(BACKGROUND_PRESETS, str(options.get("background_preset") or "studio_white"), "studio_white")
        task = (
            f"Replace only the background with: {target} Create a marketplace-ready e-commerce scene while preserving the foreground person or product exactly, including silhouette, hair, transparent materials, colors, material micro-texture, logos, labels, and readable text. "
            "Keep cutout boundaries and product edges clean, with no halo, spill, clipping, smearing, or lost detail. "
            "Create natural contact shadows, reflections, depth of field, and coherent light direction without adding unrelated props, people, text, or watermark. "
            "BACKGROUND REPLACEMENT FOREGROUND LOCK: change only the environment and its contact lighting; do not retouch, denoise, redraw foreground, change outfit/product texture, alter face/body/product proportions, soften hair, erase transparent edges, or damage logos and readable text. Match new shadows and reflections to the preserved foreground without bleeding background color into product edges. "
            + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE + " "
            + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
        )

    if operation == "pose_transfer" and str(options.get("pose_source") or "preset") == "reference":
        preservation = (
            "Preserve source identity, clothing, products, lighting, and background content. The pose reference replaces the source pose and spatial composition, including camera viewpoint, shot scale, framing, crop, subject placement, non-mirrored screen-side orientation, face/gaze direction, torso yaw, and left/right limb order. "
            "Only an explicit additional user instruction may override the pose reference's spatial constraints. Do not add people, products, text, watermarks, duplicate objects, or extra limbs."
        )
    else:
        preservation = (
        "Preserve every reference-owned attribute unless the final composition explicitly changes it. "
        "Add only the mapped subjects and products. Do not add unrelated people, products, text, watermarks, duplicate objects, or extra limbs."
        if operation == "universal" else _global_preservation() + mask_note
        )
    operation_locks = [
        studio_reference_lock,
        ECOMMERCE_COLOR_FIDELITY_DIRECTIVE,
        lower_garment_lock,
        named_detail_lock,
        user_waistband_geometry_lock,
        subject_spatial_lock,
        no_model_product_lock,
        TEXT_AND_BRAND_FIDELITY_DIRECTIVE,
        NANO_BANANA_PRO_REFERENCE_DIRECTIVE,
        NANO_BANANA_PRO_PHOTO_DIRECTIVE,
        NANO_BANANA_PRO_ECOMMERCE_DIRECTIVE,
    ]
    parts = ([] if operation == "universal" else [reference_map]) + [task, *[lock for lock in operation_locks if lock], preservation]
    return " ".join(part for part in parts if part).strip()


def safe_fallback_error(status_code: int, detail: str) -> bool:
    status_code = int(status_code or 0)
    if status_code == 405:
        return True
    if status_code not in {400, 404, 422}:
        return False
    text = str(detail or "").lower()
    markers = (
        "not support", "unsupported", "does not support", "model not found", "model does not exist",
        "no such model", "images api is not supported", "不支持", "未找到模型", "模型不存在",
    )
    return any(marker in text for marker in markers)


def public_capabilities(providers: Iterable[dict[str, Any]]) -> dict[str, Any]:
    catalog = build_model_catalog(providers)
    routes: dict[str, Any] = {}
    candidates = route_candidates(catalog, "standard")
    routes["standard"] = candidates[0] if candidates else None
    provider_items: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in catalog:
        if item["provider_id"] in seen:
            continue
        seen.add(item["provider_id"])
        provider_items.append({"id": item["provider_id"], "name": item["provider_name"]})
    public_models = [{key: value for key, value in item.items() if key not in {"provider_order", "model_order", "primary"}} for item in catalog]
    public_routes = {
        mode: ({key: value for key, value in route.items() if key not in {"provider_order", "model_order", "primary"}} if route else None)
        for mode, route in routes.items()
    }
    return {
        "operations": list(OPERATIONS),
        "modes": list(MODES),
        "providers": provider_items,
        "models": public_models,
        "routes": public_routes,
        "pose_presets": POSE_PRESETS,
        "background_presets": BACKGROUND_PRESETS,
        "studio_reference_presets": STUDIO_REFERENCE_PRESETS,
        "quality_checks": QUALITY_CHECKS,
        "universal_reference_roles": UNIVERSAL_REFERENCE_ROLES,
        "universal_reference_limit": UNIVERSAL_REFERENCE_LIMIT,
        "defaults": {
            "standard": {"count": 1, "resolution": "2k", "quality": "high", "aspect_ratio": "source"},
        },
    }
