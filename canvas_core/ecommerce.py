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
FREE_CREATION_PROMPT_POLICY = "free"
LOOKBOOK_PROMPT_POLICY = "lookbook"

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
    {"id": "prop", "label": {"zh": "手持/携带物", "en": "Held / carried item"}},
    {"id": "scene_prop", "label": {"zh": "场景道具", "en": "Scene prop"}},
    {"id": "detail", "label": {"zh": "细节图", "en": "Detail image"}},
    {"id": "pose", "label": {"zh": "动作参考", "en": "Pose reference"}},
    {"id": "scene", "label": {"zh": "场景/背景", "en": "Scene / background"}},
    {"id": "style", "label": {"zh": "风格/光影", "en": "Style / lighting"}},
]
UNIVERSAL_REFERENCE_ROLE_IDS = {item["id"] for item in UNIVERSAL_REFERENCE_ROLES}
UNIVERSAL_POSE_EVIDENCE_ROLES = {"source", "subject", "pose"}
UNIVERSAL_HUMAN_POSE_ANALYSIS_FIELDS = (
    "pose_description",
    "face_direction",
    "body_direction",
    "left_right_semantics",
    "mirror_risk",
)
UNIVERSAL_SPATIAL_POSE_ANALYSIS_FIELDS = (
    "shot_type",
    "camera_view",
    "subject_framing",
    "composition",
)
UNIVERSAL_CANONICAL_ROLE_ORDER = (
    "subject",
    "model_identity",
    "upper_garment",
    "lower_garment",
    "full_garment",
    "shoes",
    "accessory",
    "prop",
    "scene_prop",
    "detail",
    "pose",
    "scene",
    "style",
)
UNIVERSAL_EXCLUSIVE_ROLES = {
    "subject",
    "model_identity",
    "upper_garment",
    "lower_garment",
    "full_garment",
    "shoes",
    "pose",
    "scene",
    "style",
}
UNIVERSAL_PRODUCT_ROLES = {
    "upper_garment",
    "lower_garment",
    "full_garment",
    "shoes",
    "accessory",
    "prop",
    "scene_prop",
}
UNIVERSAL_GARMENT_ROLES = {"upper_garment", "lower_garment", "full_garment"}
ALLOWED_INPUT_ROLES = {"source", "garment", "pose", "prop", "background", *UNIVERSAL_REFERENCE_ROLE_IDS}
TRY_ON_OUTFIT_ROLES = {"garment", "upper_garment", "lower_garment", "full_garment", "shoes", "accessory"}
TRY_ON_REFERENCE_ROLES = {"source", "model_identity", *TRY_ON_OUTFIT_ROLES, "detail", "pose"}
UNIVERSAL_INTERACTIONS = {"wear", "put_on", "hold", "carry", "place", "use", "pose", "scene", "style", "identity"}

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
        {"id": "identity", "label": {"zh": "身体、发型和非脸部区域来自主体图；只有脸部来自模特形象参考", "en": "Body, hair, and non-face regions come from the subject; only the face comes from the model identity reference"}},
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
        {"id": "identity", "label": {"zh": "主体身体、发型、背景来自主体图；模特形象图只提供脸部；主体自带鞋子和配饰默认保留", "en": "The subject supplies body, hair, and background; the model identity reference supplies only the face; subject-native shoes and accessories are preserved by default"}},
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
TEXTURE_CRITICAL_REFERENCE_ROLES = {"upper_garment", "lower_garment", "full_garment", "shoes", "accessory", "prop", "scene_prop", "detail"}
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


def restrict_universal_reference_analysis(
    reference_type: str,
    value: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep pose evidence owned only by an explicit pose or model-subject reference."""
    role = str(reference_type or "").strip().lower()
    analysis = normalize_universal_reference_analysis(value)
    if role in UNIVERSAL_POSE_EVIDENCE_ROLES:
        return analysis
    for field in UNIVERSAL_HUMAN_POSE_ANALYSIS_FIELDS:
        analysis[field] = ""
    if role not in {"scene", "style"}:
        for field in UNIVERSAL_SPATIAL_POSE_ANALYSIS_FIELDS:
            analysis[field] = ""
    return analysis


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
            if not model_name:
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


def normalize_universal_inputs(inputs: Iterable[dict[str, Any]], canonical_order: bool = True) -> list[dict[str, Any]]:
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
        item = {
            "role": reference_type,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "url": url,
            "name": str(value.get("name") or reference_type)[:240],
            "label": re.sub(r"\s+", " ", str(value.get("label") or "").strip())[:160],
            "instruction": re.sub(r"\s+", " ", str(value.get("instruction") or "").strip())[:300],
            "kind": "image",
            "mime": str(value.get("mime") or "")[:120],
        }
        if value.get("lookbook_role"):
            item["lookbook_role"] = re.sub(r"[\x00-\x1f]", "", str(value.get("lookbook_role") or "").strip())[:40]
        if value.get("detail_target_id"):
            item["detail_target_id"] = re.sub(
                r"[^a-zA-Z0-9_-]", "", str(value.get("detail_target_id") or "")
            )[:80]
        normalized.append(item)
        if len(normalized) >= UNIVERSAL_REFERENCE_LIMIT:
            break
    if not canonical_order:
        return normalized
    role_priority = {role: index for index, role in enumerate(UNIVERSAL_CANONICAL_ROLE_ORDER)}
    return [
        item
        for _, item in sorted(
            enumerate(normalized),
            key=lambda pair: (role_priority.get(pair[1]["reference_type"], len(role_priority)), pair[0]),
        )
    ]


def resolve_universal_reference_plan(
    inputs: Iterable[dict[str, Any]],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one deterministic, type-owned e-commerce composition plan.

    User-selected reference types are the only routing authority. Visual analysis may
    enrich fidelity descriptions later, but it never changes owners, fallbacks, or
    ordering in this plan.
    """
    options = options if isinstance(options, dict) else {}
    prompt_policy = str(options.get("prompt_policy") or "").strip().lower()
    raw_prompt = prompt_policy == FREE_CREATION_PROMPT_POLICY
    user_supplement = bool(str(options.get("instruction") or "").strip()) and not raw_prompt
    normalized = normalize_universal_inputs(inputs, canonical_order=not (raw_prompt or user_supplement))
    by_role: dict[str, list[dict[str, Any]]] = {role: [] for role in UNIVERSAL_CANONICAL_ROLE_ORDER}
    for item in normalized:
        by_role.setdefault(item["reference_type"], []).append(item)

    if raw_prompt:
        return {
            "mode": "manual_prompt",
            "inputs": normalized,
            "by_role": by_role,
            "conflicts": [],
            "owners": {},
            "fallbacks": {},
        }

    conflicts: list[str] = []
    for role in UNIVERSAL_EXCLUSIVE_ROLES:
        if len(by_role.get(role, [])) > 1:
            label = next(
                (entry["label"]["zh"] for entry in UNIVERSAL_REFERENCE_ROLES if entry["id"] == role),
                role,
            )
            conflicts.append(f"{label}只能选择一张主参考图")
    if by_role["full_garment"] and (by_role["upper_garment"] or by_role["lower_garment"]):
        conflicts.append("连衣裙/套装不能与上装或下装同时作为主服装，请选择一种穿搭方案")
    studio_reference = str(options.get("studio_reference") or "").strip()
    if by_role["scene"] and studio_reference:
        conflicts.append("场景参考图与摄影棚只能选择一个最终场景")

    products = [item for item in normalized if item["reference_type"] in UNIVERSAL_PRODUCT_ROLES]
    product_ids = {item["reference_id"] for item in products}
    for detail in by_role["detail"]:
        target_id = str(detail.get("detail_target_id") or "").strip()
        if not products:
            conflicts.append(f"细节图 {detail['reference_id']} 缺少可绑定的服装、鞋靴、配饰或道具")
        elif target_id and target_id not in product_ids:
            conflicts.append(f"细节图 {detail['reference_id']} 绑定的商品不存在")
        elif not target_id and len(products) == 1:
            detail["detail_target_id"] = products[0]["reference_id"]
        elif not target_id:
            conflicts.append(f"细节图 {detail['reference_id']} 必须明确绑定到一个商品参考图")

    subject = by_role["subject"][0] if by_role["subject"] else None
    identity = by_role["model_identity"][0] if by_role["model_identity"] else None
    pose = by_role["pose"][0] if by_role["pose"] else None
    scene = by_role["scene"][0] if by_role["scene"] else None
    style = by_role["style"][0] if by_role["style"] else None
    garment_refs = by_role["full_garment"] or (by_role["upper_garment"] + by_role["lower_garment"])
    accessories = by_role["shoes"] + by_role["accessory"] + by_role["prop"] + by_role["scene_prop"]

    if subject:
        mode = "subject_edit"
    elif identity:
        mode = "visible_model"
    elif garment_refs and pose:
        mode = "invisible_outfit"
    elif products:
        mode = "product_showcase"
    else:
        mode = ""
        conflicts.append("无提示词模式至少需要模特主体、模特形象或一张主商品参考图")

    if mode == "subject_edit":
        body_owner = subject["reference_id"]
        identity_owner = identity["reference_id"] if identity else subject["reference_id"]
        pose_owner = pose["reference_id"] if pose else subject["reference_id"]
        scene_owner = scene["reference_id"] if scene else (f"studio:{studio_reference}" if studio_reference else subject["reference_id"])
        style_owner = style["reference_id"] if style else (scene["reference_id"] if scene else subject["reference_id"])
        fallbacks = {
            "body": "subject",
            "identity": "model_identity" if identity else "subject",
            "garment": "reference" if garment_refs else "subject_native",
            "accessory": "reference" if accessories else "subject_native",
            "pose": "pose" if pose else "subject",
            "scene": "scene" if scene else ("studio_reference" if studio_reference else "subject"),
            "style": "style" if style else ("scene" if scene else "subject"),
        }
    elif mode == "visible_model":
        body_owner = "system_model"
        identity_owner = identity["reference_id"]
        pose_owner = pose["reference_id"] if pose else "system_pose"
        scene_owner = scene["reference_id"] if scene else (f"studio:{studio_reference}" if studio_reference else "system_studio")
        style_owner = style["reference_id"] if style else (scene["reference_id"] if scene else "commercial_photo")
        fallbacks = {
            "body": "system_model",
            "identity": "model_identity",
            "garment": "reference" if garment_refs else "system_basic_outfit",
            "accessory": "reference" if accessories else "none",
            "pose": "pose" if pose else "system_pose",
            "scene": "scene" if scene else ("studio_reference" if studio_reference else "system_studio"),
            "style": "style" if style else ("scene" if scene else "commercial_photo"),
        }
    elif mode == "invisible_outfit":
        body_owner = "invisible_volume"
        identity_owner = "none"
        pose_owner = pose["reference_id"]
        scene_owner = scene["reference_id"] if scene else (f"studio:{studio_reference}" if studio_reference else "system_studio")
        style_owner = style["reference_id"] if style else (scene["reference_id"] if scene else "commercial_photo")
        fallbacks = {
            "body": "invisible_volume",
            "identity": "none",
            "garment": "reference",
            "accessory": "reference" if accessories else "none",
            "pose": "pose",
            "scene": "scene" if scene else ("studio_reference" if studio_reference else "system_studio"),
            "style": "style" if style else ("scene" if scene else "commercial_photo"),
        }
    else:
        body_owner = "none"
        identity_owner = "none"
        pose_owner = "none"
        scene_owner = scene["reference_id"] if scene else (f"studio:{studio_reference}" if studio_reference else "system_product_studio")
        style_owner = style["reference_id"] if style else (scene["reference_id"] if scene else "commercial_photo")
        fallbacks = {
            "body": "none",
            "identity": "none",
            "garment": "reference" if garment_refs else "none",
            "accessory": "reference" if accessories else "none",
            "pose": "none",
            "scene": "scene" if scene else ("studio_reference" if studio_reference else "system_product_studio"),
            "style": "style" if style else ("scene" if scene else "commercial_photo"),
        }

    return {
        "mode": mode,
        "inputs": normalized,
        "by_role": by_role,
        "conflicts": conflicts,
        "owners": {
            "body": body_owner,
            "identity": identity_owner,
            "garments": [item["reference_id"] for item in garment_refs],
            "accessories": [item["reference_id"] for item in accessories],
            "pose": pose_owner,
            "scene": scene_owner,
            "style": style_owner,
        },
        "fallbacks": fallbacks,
    }


def primary_pose_reference(inputs: Iterable[dict[str, Any]]) -> dict[str, Any]:
    for value in inputs or []:
        if not isinstance(value, dict) or not str(value.get("url") or "").strip():
            continue
        role = str(value.get("reference_type") or value.get("role") or "").strip().lower()
        if role == "pose":
            return dict(value)
    return {}


def _primary_pose_reference_index(inputs: Iterable[dict[str, Any]]) -> int:
    for index, value in enumerate(inputs or [], 1):
        if not isinstance(value, dict) or not str(value.get("url") or "").strip():
            continue
        role = str(value.get("reference_type") or value.get("role") or "").strip().lower()
        if role == "pose":
            return index
    return 0


def comparison_reference(
    inputs: Iterable[dict[str, Any]],
    composition_mode: str = "",
) -> dict[str, Any]:
    values = [dict(value) for value in inputs or [] if isinstance(value, dict) and str(value.get("url") or "").strip()]
    pose = primary_pose_reference(values)
    if pose:
        return pose
    source = next((value for value in values if str(value.get("reference_type") or value.get("role") or "").strip().lower() in {"source", "subject"}), None)
    return source or {}


def universal_composition_mode(inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    return str(resolve_universal_reference_plan(inputs, options).get("mode") or "")


def validate_input_roles(operation: str, inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    operation = validate_operation(operation)
    options = options if isinstance(options, dict) else {}
    values = list(inputs or [])
    if any(
        isinstance(item, dict)
        and str(item.get("role") or item.get("reference_type") or "").strip().lower() == "mask"
        for item in values
    ):
        raise ValueError("电商专用已移除蒙版编辑，请使用提示词描述需要替换的内容")
    if operation == "universal":
        if len(values) > UNIVERSAL_REFERENCE_LIMIT:
            raise ValueError(f"全能模式最多上传 {UNIVERSAL_REFERENCE_LIMIT} 张参考图")
        prompt_policy = str(options.get("prompt_policy") or "").strip().lower()
        raw_prompt = prompt_policy == FREE_CREATION_PROMPT_POLICY
        user_supplement = bool(str(options.get("instruction") or "").strip()) and not raw_prompt
        normalized = normalize_universal_inputs(
            values,
            canonical_order=not (raw_prompt or user_supplement),
        )
        if not normalized and prompt_policy not in {FREE_CREATION_PROMPT_POLICY, LOOKBOOK_PROMPT_POLICY}:
            raise ValueError("全能模式至少需要一张已上传的参考图")
        # Lookbook 自己负责人物/商品/场景的语义编排，允许只连接场景或只连接人物；
        # 不应被电商 universal 的“主体+商品”组合冲突拦截。
        if raw_prompt or prompt_policy == LOOKBOOK_PROMPT_POLICY:
            return normalized
        plan = resolve_universal_reference_plan(normalized, options)
        if plan["conflicts"]:
            raise ValueError("；".join(plan["conflicts"]))
        return plan["inputs"]
    normalized = normalize_try_on_inputs(values) if operation == "try_on" else normalize_inputs(values)
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
        "STUDIO BACKGROUND AUTHORITY: this selected studio is the mandatory final background unless the USER SUPPLEMENT explicitly requests a conflicting final background or environment. It controls backdrop color family, studio lighting, floor or cyclorama treatment, contact shadows, and listing polish. "
        "It overrides every source, base, scene, style, and background-reference environment unless the USER SUPPLEMENT explicitly says otherwise. Do not use, preserve, blend, or infer any reference-image background, scenery, set, environmental palette, or environmental lighting in the final image unless requested by the USER SUPPLEMENT. "
        "This studio lock must not override reference-owned body identity, pose, product geometry, material, SKU color, logo, readable text, or local detail evidence."
    )


def build_final_studio_background_override(options: dict[str, Any] | None = None) -> str:
    studio_id = str((options or {}).get("studio_reference") or "").strip()
    if not studio_id:
        return ""
    selected = next((item for item in STUDIO_REFERENCE_PRESETS if item.get("id") == studio_id), None)
    if not selected:
        return ""
    label = selected.get("label", {}).get("en") or selected.get("label", {}).get("zh") or selected.get("id")
    prompt = str(selected.get("prompt") or "").strip()
    return (
        f"FINAL STUDIO BACKGROUND OVERRIDE: render the final background exclusively as the selected {label}: {prompt}. "
        "This final instruction supersedes every earlier instruction to preserve, continue, reproject, match, infer, or reuse any source/reference background, scenery, environmental palette, environmental lighting, floor, wall, or set, unless the USER SUPPLEMENT explicitly requests a conflicting final background or environment. "
        "Keep the foreground subject or product intact, but replace its environment and adapt only contact shadows, reflections, and light integration needed for the selected studio."
    )


def build_immutable_foreground_composition_lock(operation: str, inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    """Lock a source-only background edit to its original visible foreground and composition."""
    normalized = list(inputs or [])
    options = options or {}
    source_only_background_edit = operation == "background_change"
    single_subject_studio_edit = (
        operation == "universal"
        and bool(str(options.get("studio_reference") or "").strip())
        and len(normalized) == 1
        and str(normalized[0].get("reference_type") or normalized[0].get("role") or "").strip().lower() in {"source", "subject"}
    )
    if not (source_only_background_edit or single_subject_studio_edit):
        return ""
    return (
        "IMMUTABLE FOREGROUND AND COMPOSITION LOCK: Image 1 is an immutable foreground plate. Preserve the exact output canvas and source aspect ratio, "
        "camera viewpoint, crop, visible body extent, subject count, subject size, subject placement, pose, action, joint arrangement, hand and leg positions, "
        "face/gaze direction, screen-side orientation, clothing, accessories, and every visible foreground detail. "
        "Do not zoom out, zoom in, reframe, recrop, outpaint, reveal hidden body parts, extend a half-body or close-up into a full-body image, move subjects, "
        "change their pose, redraw their identity, or replace any foreground pixel. Only the environment outside the foreground silhouette may change. "
        "Studio lighting may affect only the background, contact shadow, reflection, and a subtle non-structural light integration; it must never alter foreground geometry, skin, hair, clothing, or product pixels."
    )


def build_source_photographic_character_lock(operation: str, inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    """Preserve hair and source capture character for prompt-only background edits."""
    normalized = list(inputs or [])
    options = options or {}
    source_only_background_edit = operation == "background_change"
    single_subject_studio_edit = (
        operation == "universal"
        and bool(str(options.get("studio_reference") or "").strip())
        and len(normalized) == 1
        and str(normalized[0].get("reference_type") or normalized[0].get("role") or "").strip().lower() in {"source", "subject"}
    )
    if not (source_only_background_edit or single_subject_studio_edit):
        return ""
    return (
        "SOURCE PHOTOGRAPHIC CHARACTER LOCK: treat Image 1 as the sole authority for the visible foreground's photographic character, not merely identity. "
        "Preserve the exact hairstyle: hairline, parting, length, silhouette, volume, strand direction, curl or wave pattern, flyaways, frizz, loose strands, color, and hair-edge transparency. "
        "Never restyle, recolor, tidy, smooth, thicken, thin, or replace hair. Preserve all visible source capture characteristics whenever present: analog film grain or ISO noise, grain scale and chroma, scan texture, focus softness, local sharpness, halation or bloom, tonal curve, contrast, dynamic range, white balance, lens character, natural pores, fabric texture, and realistic imperfections. "
        "Do not denoise, beauty-retouch, face-smooth, plasticize, sharpen, HDR-tone-map, or turn an editorial or film photograph into a sterile e-commerce render. "
        "If the source has visible film grain or noise, reproduce the same grain scale, density, color behavior, and distribution on the new background so the whole frame remains one photograph; if it has no grain, do not invent it."
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
    value = analysis.get(str(item.get("reference_id") or "")) or analysis.get(str(item.get("name") or "")) or {}
    role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
    return restrict_universal_reference_analysis(role, value)


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
        "subject": "MODEL SUBJECT / BODY / FALLBACK POSE",
        "garment": "GARMENT PRODUCT SOURCE",
        "model_identity": "MODEL FACE IDENTITY ONLY",
        "upper_garment": "UPPER GARMENT SOURCE",
        "lower_garment": "LOWER GARMENT SOURCE",
        "full_garment": "DRESS OR FULL OUTFIT SOURCE",
        "shoes": "SHOES SOURCE",
        "accessory": "ACCESSORY SOURCE",
        "detail": "LOCAL PRODUCT DETAIL SOURCE",
        "pose": "POSE / SPATIAL TEMPLATE ONLY",
        "prop": "PROP OR PRODUCT SOURCE",
        "scene_prop": "SCENE PROP SOURCE",
        "background": "BACKGROUND SOURCE ONLY",
        "scene": "SCENE SOURCE ONLY",
        "style": "STYLE SOURCE ONLY",
    }
    lines = []
    for index, item in enumerate(inputs or [], 1):
        role = str(item.get("reference_type") or item.get("role") or "").strip().lower()
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


def build_user_directed_ecommerce_prompt(instruction: str) -> str:
    # 手动提示词具有完全优先级：不追加参考图顺序、保真锁或任何内置规则。
    return str(instruction or "").strip()


def build_user_supplement_override_rule(instruction: str) -> str:
    text = re.sub(r"\s+", " ", str(instruction or "").strip())
    if not text:
        return ""
    return (
        "USER SUPPLEMENT RULE: apply the USER SUPPLEMENT only as an additional output requirement for explicitly mentioned framing, crop, camera, placement, styling, local edits, or color/material changes. "
        "It may refine an attribute inside its assigned reference type, but it must never reassign an image to another type, turn a scene into a product source, turn a pose into an identity source, or bypass the typed ownership map. "
        "Reference types remain authoritative; for attributes the USER SUPPLEMENT does not explicitly mention, follow the typed recipe and its deterministic fallbacks."
    )


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


def build_universal_auto_instruction(inputs: Iterable[dict[str, Any]], options: dict[str, Any] | None = None) -> str:
    options = options if isinstance(options, dict) else {}
    plan = resolve_universal_reference_plan(inputs, options)
    if plan["conflicts"]:
        raise ValueError("；".join(plan["conflicts"]))
    normalized = plan["inputs"]
    if not normalized:
        return ""
    indexed = [(index, item) for index, item in enumerate(normalized, 1)]
    by_role: dict[str, list[tuple[int, dict[str, Any]]]] = {role: [] for role in UNIVERSAL_CANONICAL_ROLE_ORDER}
    for index, item in indexed:
        by_role.setdefault(item["reference_type"], []).append((index, item))

    subject = by_role["subject"][0] if by_role["subject"] else None
    identity = by_role["model_identity"][0] if by_role["model_identity"] else None
    pose = by_role["pose"][0] if by_role["pose"] else None
    scene = by_role["scene"][0] if by_role["scene"] else None
    style = by_role["style"][0] if by_role["style"] else None
    studio_id = str(options.get("studio_reference") or "").strip()
    studio = next((item for item in STUDIO_REFERENCE_PRESETS if item.get("id") == studio_id), None)

    product_index = {item["reference_id"]: index for index, item in indexed if item["reference_type"] in UNIVERSAL_PRODUCT_ROLES}
    product_lines = []
    for role in ("upper_garment", "lower_garment", "full_garment", "shoes", "accessory", "prop", "scene_prop"):
        for index, item in by_role[role]:
            detail = _reference_detail(item, _reference_analysis(item, options))
            product_lines.append(
                f"Image {index} owns the exact {role.replace('_', ' ')} product itself and nothing else ({detail}). "
                "Treat everything outside that typed product's physical silhouette as excluded context, never as output evidence."
            )
    detail_lines = []
    for index, item in by_role["detail"]:
        target_index = product_index.get(str(item.get("detail_target_id") or ""))
        detail_lines.append(
            f"DETAIL EVIDENCE: Image {index} belongs only to product Image {target_index}; use it for matching construction, alternate view, flat-lay structure, material, weave, print, logo, text, stitching, hardware, and finish, never as another SKU."
        )

    style_line = (
        f"STYLE OWNER: Image {style[0]} controls only palette, light quality, contrast, and photographic finish."
        if style else
        f"STYLE FALLBACK: use the commercial lighting treatment of scene Image {scene[0]}."
        if scene else
        "STYLE FALLBACK: use clean premium commercial photography with restrained retouching."
    )
    pose_detail = _pose_spatial_detail(_reference_analysis(pose[1], options)) if pose else ""
    pose_evidence = f" Parsed pose evidence: {pose_detail}." if pose_detail else ""
    subject_pose_detail = _pose_spatial_detail(_reference_analysis(subject[1], options)) if subject else ""
    subject_pose_evidence = f" Parsed subject-pose evidence: {subject_pose_detail}." if subject_pose_detail else ""

    if plan["mode"] == "subject_edit":
        if identity:
            base_line = (
                f"BODY AND BASE SCENE OWNER: Image {subject[0]} is the only final base image and editing canvas. "
                "Preserve its body, anatomy, proportions, hands, feet, background, environment, lighting, shadows, reflections, camera, viewpoint, framing, crop, subject scale, placement, composition, and every region not explicitly replaced by another typed reference. "
                f"Do not preserve Image {subject[0]}'s original face identity because the typed model-identity reference explicitly replaces only that local identity region. "
                "Preserve its native pose and spatial composition when no typed pose reference is present."
            )
        else:
            base_line = (
                f"IMMUTABLE BASE: Image {subject[0]} is the final base image. Preserve its model, body, identity, skin, background, environment, lighting, shadows, reflections, and every region not explicitly replaced by another typed reference. "
                "Preserve its native pose, camera, viewpoint, framing, crop, subject scale and placement only when no typed pose reference is present."
            )
        parts = [
            "SUBJECT-BASED LOCAL EDIT RECIPE: reference type is the only edit authority.",
            base_line,
            "POSE EVIDENCE ALLOWLIST: only the typed pose reference and the model subject may provide human pose, action, gesture, joint, facing, left/right, viewpoint, framing, or person-placement evidence. Ignore every person and every pose-like cue visible in model-identity, garment, shoes, accessory, prop, detail, scene, and style references.",
        ]
        if identity:
            parts.append(
                f"FACE-IDENTITY-ONLY EDIT: use Image {identity[0]} only for the final face identity, including facial structure and features, complexion, makeup, age cues, and recognizable facial appearance. "
                f"Apply it strictly inside the facial region as a localized face swap onto the person and body from Image {subject[0]}; preserve Image {subject[0]}'s original hair, hairstyle, hair color, hairline outside the facial mask, body, neck and non-face skin, pose, camera, background, clothing unless separately replaced, and composition. "
                f"Never use Image {identity[0]} as the final base image and never copy its hair, hairstyle, hair color, body, anatomy, proportions, clothing, products, pose, gesture, camera, lens, crop, framing, placement, composition, background, environment, lighting, shadows, reflections, or photographic style."
            )
        parts.extend(product_lines)
        if product_lines:
            parts.append(
                f"PRODUCT LOCAL EDIT: replace only the regions explicitly owned by product references on base Image {subject[0]}. Remove the superseded item completely, fit the new product naturally, and keep all unassigned garments, shoes, accessories, carried items, scene props, and surroundings from the base unchanged."
            )
            parts.append(
                "PRODUCT-REFERENCE EXCLUSION LOCK: product references are isolated SKU sources, not composition templates. "
                "Never copy or imitate any product-reference wearer, face, hair, skin, identity, body shape, anatomy, pose, action, gesture, joint position, body direction, camera, lens, viewpoint, crop, framing, subject scale, placement, scene, background, floor, prop, lighting, shadow, reflection, color grade, or photographic style. "
                f"All of those attributes remain owned by base Image {subject[0]}; a typed model-identity reference may replace only the facial region, while pose, scene, and style references may replace only their explicitly assigned attributes."
            )
        product_reference_count = sum(len(by_role[role]) for role in UNIVERSAL_PRODUCT_ROLES)
        if by_role["lower_garment"] and product_reference_count == 1 and not pose:
            lower_index = by_role["lower_garment"][0][0]
            parts.append(
                f"LOWER-GARMENT-ONLY LOCAL EDIT: make exactly one semantic change to Image {subject[0]}: replace its existing lower garment with the exact lower garment from Image {lower_index}. "
                f"Image {lower_index} is evidence only for the lower garment itself; never use Image {lower_index} as evidence for its wearer, identity, body shape, anatomy, skin, pose, action, gesture, joint positions, body direction, camera, lens, viewpoint, crop, framing, subject scale or placement, scene, background, floor, props, lighting, shadows, reflections, color grade, or photographic style. "
                f"Extract the lower garment from Image {lower_index} and adapt the lower garment to Image {subject[0]}'s existing hips, legs, and native pose; never conform Image {subject[0]} to Image {lower_index}'s wearer or pose. "
                f"Preserve Image {subject[0]}'s upper garment, shoes, accessories, hands, exposed skin, hair, face, body proportions, posture, expression, background, camera, crop, composition, lighting, shadows, and every non-lower-garment pixel as strictly unchanged."
            )
        if pose:
            if identity:
                assigned_product_indexes = ", ".join(f"Image {index}" for index in sorted(product_index.values()))
                product_clause = f"the assigned products including {assigned_product_indexes}" if assigned_product_indexes else "the subject's assigned clothing"
                pose_subject_line = (
                    f"Image {subject[0]} supplies the body, Image {identity[0]} supplies only the face identity, and Image {pose[0]} supplies only the pose; the original subject pose is not retained. "
                    f"The final person uses the body from Image {subject[0]}, the face identity from Image {identity[0]}, {product_clause}, and only the pose from Image {pose[0]}. "
                    f"Keep Image {subject[0]}'s background, environment, and lighting; change camera, framing, placement, or composition only when physically required by Image {pose[0]}'s pose, and never copy the pose reference's person, face, clothing, or background."
                )
                pose_preservation = f"Preserve the face identity from Image {identity[0]} and the background from Image {subject[0]}"
            else:
                pose_subject_line = (
                    f"Image {subject[0]} supplies the model identity and body but the original subject pose is not retained; all assigned garments, shoes and accessories must conform to Image {pose[0]}'s pose, never the reverse. "
                    f"The final person is the model from Image {subject[0]} wearing the assigned products while performing Image {pose[0]}'s pose."
                )
                pose_preservation = "Preserve base identity and background"
            parts.append(
                f"SOLE POSE OWNER: Image {pose[0]} is the exclusive and highest-priority source for the final pose, action, gesture, joint arrangement, balance, facing direction, screen-side orientation, viewpoint, framing and person placement. {pose_subject_line} "
                f"POSE LOCAL EDIT: Image {pose[0]} replaces only the model's action and required garment deformation. {pose_preservation}; change framing or placement only when physically required by the pose. {_pose_orientation_lock(pose[0])}{pose_evidence}"
            )
        else:
            parts.append(
                f"SUBJECT POSE FALLBACK: Image {subject[0]} is the only pose source because no typed pose reference exists. Preserve its native action, joint arrangement, facing, camera, framing and placement; never borrow a pose from any other reference.{subject_pose_evidence}"
            )
            if identity and product_index:
                assigned_product_indexes = ", ".join(f"Image {index}" for index in sorted(product_index.values()))
                product_clause = f"the exact assigned product from {assigned_product_indexes}" if len(product_index) == 1 else f"the exact assigned products from {assigned_product_indexes}"
                parts.append(
                    f"SUBJECT-IDENTITY-PRODUCT ASSEMBLY LOCK: The final result remains Image {subject[0]}'s person, body, pose, camera, composition, lighting, and background, with only the face identity locally replaced from Image {identity[0]} and while wearing {product_clause}. "
                    f"Edit Image {subject[0]} in place; never rebuild the image around Image {identity[0]} or any product reference."
                )
        if scene:
            parts.append(f"SCENE LOCAL EDIT: replace only the base environment with scene Image {scene[0]}; preserve the edited model and products.")
        elif studio:
            parts.append(f"SCENE LOCAL EDIT: replace only the base environment with this selected studio: {studio['prompt']}.")
        if style:
            parts.append(f"STYLE LOCAL EDIT: apply only palette, light quality, contrast, and finish from Image {style[0]}; do not change layout or product identity.")
        parts.extend(detail_lines)
        parts.append("FINAL RESULT: a seamless local edit of the original subject image. Anything not explicitly assigned to another type must remain visually unchanged.")
        return " ".join(parts)

    if plan["mode"] == "visible_model":
        parts = [
            "VISIBLE-MODEL COMPOSITION RECIPE: reference type is the only ownership authority.",
            "BODY AND HAIR FALLBACK: generate one natural adult e-commerce body with anatomically correct hands and feet plus a neutral coherent hairstyle independent of the face reference.",
            f"FACE-IDENTITY-ONLY OWNER: Image {identity[0]} controls only the face inside the facial region: facial structure and features, complexion, makeup, age cues, and recognizable facial appearance. Never copy its hair, hairstyle, hair color, body, clothing, pose, camera, crop, composition, lighting, or background.",
            *product_lines,
        ]
        if not any(by_role[role] for role in UNIVERSAL_GARMENT_ROLES):
            parts.append("GARMENT FALLBACK: use plain, logo-free neutral basic clothing.")
        if pose:
            parts.append(f"SOLE POSE OWNER: Image {pose[0]} controls action, balance, gesture, joint arrangement, viewpoint, framing and placement exclusively; ignore pose-like evidence from every other reference. {_pose_orientation_lock(pose[0])}{pose_evidence}")
        else:
            parts.append("POSE FALLBACK: use a natural premium catalog standing pose.")
        if scene:
            parts.append(f"SCENE OWNER: place the visible model and products in scene Image {scene[0]} without copying its people or foreground products.")
        elif studio:
            parts.append(f"SCENE FALLBACK: use the selected studio: {studio['prompt']}.")
        else:
            parts.append("SCENE FALLBACK: use a neutral high-end e-commerce studio with soft grounded shadows.")
        parts.extend([style_line, *detail_lines, "FINAL RESULT: one coherent photorealistic visible-model e-commerce image with natural fit, anatomy, contact and product fidelity."])
        return " ".join(parts)

    if plan["mode"] == "invisible_outfit":
        parts = [
            "MODEL-FREE THREE-DIMENSIONAL OUTFIT RECIPE: create the confirmed premium invisible-mannequin fashion result; reference type is the only ownership authority.",
            "HUMAN ABSENCE LOCK: show absolutely no visible model, face, head, hair, skin, hands, feet, transparent body silhouette, plastic mannequin, stand, hanger, or horror/supernatural effect.",
            *product_lines,
            f"SOLE POSE OWNER: Image {pose[0]} is the exclusive pose source; ignore pose-like evidence from all garment, accessory, detail, scene and style references. POSE-DRIVEN GARMENT VOLUME: Image {pose[0]} controls only the three-dimensional wearing pose. Translate its shoulder turn, sleeve bends, waist and hip rotation, balance, step, trouser-leg or skirt movement, viewpoint, framing and screen-side orientation into the clothing itself. Never copy the pose person's identity, skin, body pixels, clothing, accessories, or background. {_pose_orientation_lock(pose[0])}{pose_evidence}",
            "INVISIBLE WEARING STRUCTURE: preserve convincing human-worn volume through shoulders, chest, waist, hips, sleeves and legs; keep realistic hollow openings at collar, cuffs, hems and trouser legs, correct layering, gravity, occlusion, fabric tension, drape and motion. The outfit must not look flat, collapsed, pasted, cut off, weightless, or supported by a visible body.",
            "ACCESSORY PLACEMENT: wearable accessories may occupy anatomically correct invisible wearing positions; shoes align to invisible foot positions; carried items may hang at the implied grip without generating hands; scene props remain in the environment.",
        ]
        if scene:
            parts.append(f"SCENE OWNER: present the model-free three-dimensional outfit inside scene Image {scene[0]}, matching its perspective and environmental lighting without copying people or unrelated products.")
        elif studio:
            parts.append(f"SCENE FALLBACK: present the outfit in the selected studio: {studio['prompt']}.")
        else:
            parts.append("SCENE FALLBACK: use a refined neutral luxury e-commerce studio with clean negative space and a subtle grounded floor shadow.")
        parts.extend([style_line, *detail_lines, "FINAL RESULT: a sophisticated model-free three-dimensional outfit image with premium fashion-editorial polish and exact SKU fidelity."])
        return " ".join(parts)

    parts = [
        "PRODUCT-ONLY E-COMMERCE RECIPE: create a product showcase without inventing a person; reference type is the only ownership authority.",
        "NO-MODEL LOCK: show no generated human, face, skin, hands, feet, invisible-body pose, or unrelated mannequin. If a product source contains a person, mannequin, hanger, background, or styling item, extract only the typed product.",
        *product_lines,
        "PRESENTATION: create a premium product hero, clean flat-lay, hanging presentation, coordinated product arrangement, or detail-focused catalog image according to the supplied product and bound supplemental/detail evidence. Keep the product complete, readable, physically plausible, and marketplace ready.",
    ]
    if scene:
        parts.append(f"SCENE OWNER: display the product arrangement inside scene Image {scene[0]} without adding a model or copying unrelated foreground products.")
    elif studio:
        parts.append(f"SCENE FALLBACK: use the selected product studio: {studio['prompt']}.")
    else:
        parts.append("SCENE FALLBACK: use a clean premium product-photography studio appropriate to the source presentation.")
    parts.extend([style_line, *detail_lines, "FINAL RESULT: one coherent model-free product image with exact construction, material, color, branding and detail fidelity."])
    return " ".join(parts)


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
        if role in {"subject", "source"}:
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
    options = options if isinstance(options, dict) else {}
    normalized = validate_input_roles(operation, inputs, options)
    raw_instruction = str(options.get("instruction") or "")
    instruction = raw_instruction.strip()
    prompt_policy = str(options.get("prompt_policy") or "").strip().lower()
    if prompt_policy == FREE_CREATION_PROMPT_POLICY:
        if operation != "universal":
            raise ValueError("自由创作提示词策略仅支持全能模式工作区")
        if not instruction:
            raise ValueError("自由创作必须填写提示词")
        return raw_instruction
    if prompt_policy == LOOKBOOK_PROMPT_POLICY:
        style = options.get("lookbook_style") if isinstance(options.get("lookbook_style"), dict) else {}
        style_id = str(style.get("id") or "").strip().lower()
        auto_decision = options.get("lookbook_auto_decision") if isinstance(options.get("lookbook_auto_decision"), dict) else {}
        effective_style_id = str(auto_decision.get("selected_style_id") or "").strip().lower() if style_id == "auto" else style_id
        style_name = str(style.get("name") or "").strip()
        style_prompt = str(style.get("prompt") or style.get("description") or "").strip()
        research = str(options.get("search_context") or "").strip()
        plan = str(options.get("lookbook_plan") or "").strip()
        reference_analysis = str(options.get("lookbook_reference_analysis") or "").strip()
        visual_system = options.get("lookbook_visual_system")
        if isinstance(visual_system, dict):
            visual_system_text = json.dumps(visual_system, ensure_ascii=False, separators=(",", ":"))[:12000]
        else:
            visual_system_text = str(visual_system or "").strip()[:12000]
        count = max(1, min(4, int(options.get("lookbook_count") or 1)))
        auto_mode = not instruction
        reference_lines = []
        for index, item in enumerate(normalized, 1):
            assigned = str(item.get("lookbook_role") or item.get("label") or "参考素材").strip()
            name = str(item.get("name") or "").strip()
            reference_lines.append(f"Image {index} is assigned to {assigned}{(' (' + name + ')') if name else ''}; use it only for that attribute family.")
        person_count = sum(1 for item in normalized if str(item.get("lookbook_role") or "").strip() == "人物")
        scene_count = sum(1 for item in normalized if str(item.get("lookbook_role") or "").strip() == "场景")
        user_line = instruction or "依据连接的参考图自由发挥，不额外添加用户未要求的主题"
        parts = [
            "LOOKBOOK FASHION CAMPAIGN RECIPE: create a cohesive premium fashion lookbook / flat advertising spread, with editorial art direction, intentional styling, a clear visual hierarchy, refined composition, believable commercial photography, and a polished campaign finish.",
            f"USER CREATIVE BRIEF: {user_line}.",
            f"SELECTED VISUAL STYLE SKILL{(' ' + style_name) if style_name else ''}: {style_prompt or ('visual model autonomously selects the best style from the connected references and user brief' if style_id == 'auto' else 'high-end fashion editorial with clean art direction')}.",
            "EDITORIAL QUALITY DIRECTIVE: build a distinct fashion image with a point of view, lived-in atmosphere and deliberate art direction. Avoid generic catalog staging, default white seamless backdrops, empty gray studios, passport-like posing, centered product cutouts, stock-photo smiles, random luxury props and unmotivated gradient backgrounds.",
            "COLOR DIRECTION: use a finite, intentional palette with a dominant field, supporting color and one controlled accent. Preserve the reference subject's true skin tone and garment identity while grading the environment, shadows, highlights and wardrobe relationships as one coherent fashion image; no muddy gray wash, candy-color overload or random color shifts between frames.",
            "FASHION PHOTOGRAPHY FINISH: favor a real editorial situation with depth, foreground/background layering, directional or available light, subtle motion in fabric/hair and believable contact with the environment. Use restrained filmic grain, halation, print texture or flash character only when supported by the selected style and research; never use generic 8k/best-quality filler as a substitute for decisions.",
            "MOTIVATED LIGHT FAMILY: choose one coherent lighting family from the supplied scene and selected style, then keep its source direction, exposure logic and palette continuous across the series. Never apply a generic low-contrast filter to every concept: daylight reportage, low-key spectacle and high-key material portraiture require different tonal structures.",
            "CAMERA BEHAVIOR: favor a lightly handheld documentary fashion camera at human eye or waist height, small off-axis imperfections, natural perspective and a responsive shutter moment. Use wide environmental space for context, medium distance for action, close framing for emotion and a low detail view for material/contact. Avoid sterile tripod symmetry, extreme wide-angle distortion, hyper-shallow CGI blur and identical centered poses.",
            "WARDROBE IMMUTABILITY LOCK: when a supplied 人物 reference visibly wears an outfit, that exact outfit is the styling source of truth. Preserve garment category, silhouette, neckline, closures, knit/weave, color, denim wash, footwear, bag and accessories at every frame; do not upgrade, restyle, replace or simplify the clothing merely because the brief says fashion editorial. Any change of clothing requires an explicit user instruction.",
            "SCENE TYPOGRAPHY AND PLANE-FIGURE LOCK: treat signage, posters, magazine covers, printed faces and storefront graphics inside a supplied 场景 image as flat environmental evidence only. Preserve their placement, scale and legibility when visible, but never turn a printed person into a second subject, never copy that face onto the model, and never invent replacement brand names, slogans or storefront text.",
            "EDITORIAL CAMERA GRAMMAR: design each frame around a photographic decision—environmental wide establishing view, oblique medium walk-by, low or eye-level three-quarter portrait, and one tactile detail/foreground-obscured moment. Vary distance, crop, horizon and subject placement with motivated negative space; keep feet grounded and let the environment occlude or frame the person naturally. The series must read as four separately photographed moments, not four near-identical catalog renders.",
            "Use connected reference images as factual sources for product identity, material, color, logo, model identity and scene wherever visible; do not invent or distort branded details.",
            "Create a finished standalone image suitable for a fashion lookbook cover or hero advertisement. Do not add watermarks, random text, UI elements, borders or unrelated products.",
            f"SERIES CONSISTENCY: this request produces {count} coordinated campaign image(s). Keep identity, SKU details, palette, styling language and world consistent while varying framing, shot scale or editorial moment only when useful.",
            "PRE-DELIVERY QUALITY GATE: inspect the planned render before finalizing for correct anatomy, clean product edges, exact Logo and text, faithful material texture, coherent contact shadows, believable perspective, intentional negative space and commercial advertising polish. Reject obvious defects and regenerate the weak frame when possible.",
        ]
        if style_id == "auto":
            parts.append(
                "AUTO STYLE ROUTER: the visual model owns the style decision. Use the connected reference facts and the user brief as the source of truth, then execute the selected style decision below. Do not average multiple styles or let generic fashion defaults override the decision."
            )
            if auto_decision:
                parts.append(
                    "AUTO STYLE DECISION: selected_style_id=" + str(auto_decision.get("selected_style_id") or "candid-lifestyle")
                    + "; selected_style_name=" + str(auto_decision.get("selected_style_name") or "")
                    + "; rationale=" + str(auto_decision.get("rationale") or "")
                    + "; confidence=" + str(auto_decision.get("confidence") or 0)
                )
        if effective_style_id in {"", "candid-lifestyle", "single-person-emotion", "casual-friends", "travel-dream", "pet-fashion"}:
            parts.extend([
                "NATURAL SUNLIGHT AND SOFT-FILM LOCK: build the light as a motivated daylight photograph, not a studio effect—warm sun filtered through leaves or thin cloud, broad sky/ground bounce opening the shadow side, a restrained edge glow on hair and fabric, and soft contact shadows that still describe form. Expose for highlight detail and use a gentle filmic S-curve: lifted blacks, open midtones, creamy highlight roll-off, low micro-contrast and protected neutral skin. Shape the grade as a daylight color-negative language: warm honey highlights, quiet olive/deep-green shadows, slightly desaturated supporting colors, and one small accent sampled from the supplied scene. Add fine organic grain with visible but delicate grain clumps, subtle analog halation only around bright edges, and a transparent airy atmosphere. Avoid crushed shadows, clipped highlights, HDR clarity, glossy commercial flash, teal-orange blockbuster grading and aggressive sharpening.",
                "NARRATIVE COLOR SCRIPT: the series should move from sunlit place to human gesture to private pause to tactile proof. Keep the same daylight direction and palette across frames; vary only the light's incidence, foreground occlusion and exposure breathing. The viewer should feel that a photographer observed a real afternoon, not that four images were color-filtered independently.",
            ])
        elif effective_style_id == "fw-cream-cyan-film":
            parts.extend([
                "2026 FW REFERENCE FILM LOCK: derive a repeatable fashion-film look from the supplied reference images, not from generic 'cinematic' adjectives. Use high-key natural sun or thin-cloud daylight with warm ivory, cream and pale lemon-yellow as the dominant 60-70% field; faded turquoise/cyan architecture or props as a controlled 20-30% complement; keep truthful warm-neutral skin and reserve any other hue for a small 5-10% accent sampled from the actual scene. Lift the black floor slightly while retaining edge detail, open the midtones, protect white garments and faces from clipping, and roll highlights into a creamy soft shoulder. Do not apply a flat low-contrast wash, teal-orange blockbuster grade or random hue shift.",
                "FW NATURAL SUN TRANSPARENCY: light must feel like real unfiltered afternoon sun entering the lens—visible warm directionality, gently blooming sunlit edges, translucent hair and fabric, airy atmospheric separation, natural specular glints and soft-edged cast shadows with a cool sky-bounce fill on the shadow side. Expose as a luminous high-key daylight photograph: keep faces, white garments and sunlit pavement open and readable, lift dark green interiors enough to retain texture while preserving a small true black point. Do not underexpose the whole frame. Do not simulate this with a beige overlay, studio softbox, flat ambient fill, foggy milk wash or artificial rim-light effect.",
                "FW CAMERA GRAMMAR: make every frame feel observed on location—off-axis or rotated horizon, non-centered subject placement, eye-level or waist-level handheld perspective, natural lens breathing, foreground rails/doorframes/bed linen/garment edges partially occluding the body, and real environmental depth. Alternate one contextual wide frame, one oblique medium frame, one intimate expression frame and one tactile fabric/product detail. Vary distance and crop with purpose; never repeat a centered full-body catalog stance or sterile tripod symmetry.",
                "FW HUMAN VITALITY LOCK: direct an internal emotional beat and a small physical action in every frame. Use reclining, leaning, turning, looking down or away, briefly closing the eyes, a soft unforced smile, fingers resting on a rail, adjusting a knit, tracing a fabric edge, shifting weight or taking a half-step. Let breath, gaze, eyelids, mouth corners, shoulder release and hand tension carry the mood; preserve micro-asymmetry and spontaneous timing. Use the USER-SUPPLIED MODEL as the sole identity source: keep the supplied face shape, skin tone, visible pores, marks, hairline and natural asymmetries exactly as provided. Do not add freckles, moles, scars, wrinkles, makeup, age cues or other facial traits that are not visible in the user image. Natural is more luxurious than airbrushed perfection; never pose for a storefront catalog.",
                "FW ANALOG FINISH: retain skin pores, stray hair, knit loops, lace holes, seams and hardware. Add a fine-to-medium 16mm/35mm film grain structure with irregular individual grains, random spacing, tiny density variation and subtle non-uniform RGB response that is stronger in midtones/shadows and gentler in highlights. Grain must remain point-like and emulsional, with no large connected blotches, cloudy patches, dirty stains, mottled islands, regular grid, checkerboard, repeating dots or uniform digital noise. Keep motion softness natural, sharpening low and halation very restrained. Reject plastic skin, waxy fabric, AI gloss, crunchy HDR, crushed blacks, clipped whites, excessive clarity and fake vignette.",
                "FW SERIES COLOR SCRIPT: keep the same cream/ivory + pale lemon + faded cyan relationship and daylight direction across all outputs. Progress from a sunlit establishing place to an observed gesture, then a private pause, then tactile proof of the supplied material or product; only the camera distance, occlusion and decisive moment change.",
                "FW SINGLE-FRAME OUTPUT LOCK: each API output is exactly one full-bleed photograph in the requested aspect ratio. Never draw a contact sheet, four-panel grid, split screen, storyboard page, collage or multiple moments inside one canvas; the four beats above are separate outputs generated independently.",
                "FW SCENE IMMUTABILITY LOCK: when a scene reference is supplied, keep that exact location, architecture, dominant paint colors, storefront/kiosk geometry and printed graphics as the set. Change only camera position, crop and natural time-of-day exposure; never relocate the person to a beach, cafe, generic street, studio or invented architecture.",
            ])
        elif effective_style_id in {"street-film", "sports-dynamic"}:
            parts.append(
                "LOW-KEY SPECTACLE LOCK: use only scene-motivated contrast such as streetlamp, fire, vehicle light, stadium light or blue-hour ambience. Keep readable shadow texture and accurate skin/product color while allowing deep blacks, controlled specular highlights, smoke/haze and one saturated accent. The contrast must express action and pressure; avoid arbitrary HDR, neon color soup and crushed unmotivated darkness."
            )
        else:
            parts.append(
                "MATERIAL PORTRAIT LIGHT LOCK: shape the image around the owning material—broad high-key light for skin, jewelry and eyewear; raking side light for leather, knit and hardware; controlled negative fill for form. Preserve micro-texture, reflective edges and product color with clean highlight roll-off, restrained grain and no plastic CGI gloss."
            )
        if style_id in {
            "fw-cream-cyan-film", "candid-lifestyle", "multi-person-interaction", "single-person-emotion", "sports-dynamic",
            "casual-friends", "street-film", "travel-dream", "product-story", "pet-fashion", "material-closeup",
        }:
            parts.append(
                "REFERENCE-FIRST NATURALISM SKILL: reference images are the primary creative input, not decorative inspiration. "
                "When the user brief is empty, do not invent a long generic prompt or add stock adjectives; infer a concrete photographic situation from the supplied people, products and locations. "
                "Keep each supplied person as a separate identity and place them in one physically coherent world. Use eye-lines, listening, touch, shared attention, walking, leaning, adjusting clothing or handling a supplied object to create a believable relationship. "
                "Preserve natural skin, hair, fabric weave, small asymmetries and camera imperfections; reject plastic skin, mannequin limbs, frozen smiles, isolated cutouts, generic studio gradients and over-processed HDR."
            )
        if person_count >= 2:
            parts.append(
                f"MULTI-PERSON INTERACTION LOCK: {person_count} distinct supplied people must remain separate and recognizable. "
                "Do not merge faces, swap clothing, duplicate limbs or make everyone pose frontally. Stage at least one observable relationship per frame (shared gaze, conversation, touch, passing an object, walking together or reacting to the same environment), with believable distance, occlusion, scale and contact shadows."
            )
        if person_count >= 1 and scene_count >= 1:
            parts.append(
                "REFERENCE-SCENE INTEGRATION: photograph the people inside the supplied location rather than pasting cutouts over a background. "
                "Preserve recognizable architectural cues while adapting viewpoint; align horizon, perspective, ambient color, cast shadows and foot-to-ground contact so the result reads as one captured photograph."
            )
        if auto_mode:
            parts.append(
                "AUTO LOOKBOOK MODE (no user brief): use the connected reference images and selected style as the creative source of truth. "
                "Generate a coordinated series of candid lifestyle fashion snapshots, as if an observant photographer caught real unposed moments between locations: relaxed micro-expressions, natural weight shifts, walking, turning, leaning, adjusting clothing or interacting with the supplied scene. "
                "Prefer authentic environmental light, subtle motion blur, foreground occlusion, imperfect but flattering framing, tactile film grain and lived-in details over polished studio posing. "
                "Vary each image by distance, angle, crop and decisive moment while keeping identity, wardrobe, palette and location continuous; never make a contact sheet, split panel, duplicate collage or isolated catalog cutout."
            )
        if reference_lines:
            parts.append("SEMANTIC INPUT MAP: " + " ".join(reference_lines))
        semantic_roles = {str(item.get("lookbook_role") or "").strip() for item in normalized}
        if "Logo" in semantic_roles:
            parts.append("LOGO AND BRAND TEXT LOCK: preserve the connected Logo reference exactly, including geometry, proportions, negative space, color, letterforms, spelling, orientation and placement. Never redraw, stylize, mirror, translate or invent brand marks.")
        if "人物" in semantic_roles and "场景" in semantic_roles:
            parts.append(
                "PERSON-SCENE LIFESTYLE LOCK: use the connected 人物 image as the sole source of face, identity, skin tone, hair, body proportions, existing wardrobe and accessories. "
                "Use the connected 场景 image as the exact geographic and architectural set, preserving its recognizable geometry, dominant colors, storefront/kiosk details and printed graphics; only camera position, crop and natural exposure may change. Never substitute a beach, cafe, generic street, studio or invented architecture. "
                "Photograph the person inside that world rather than compositing two cutouts: establish believable scale, feet-to-ground contact, directional light, atmospheric depth and an incidental interaction with the environment. "
                "The result must feel like premium street-style or travel-editorial reportage—spontaneous, intimate and quietly luxurious—not a white-background studio, rigid catalog pose or synthetic backdrop. "
                "The scene may contain a printed/photographed face or editorial poster; keep it as a background graphic and never treat it as a second live person or identity source."
            )
        elif "人物" in semantic_roles and "商品" in semantic_roles:
            parts.append("PERSON-PRODUCT ASSEMBLY LOCK: use the connected 人物 image as the final person's identity, face, body, hair, anatomy and natural base composition. Use the connected 商品 image as the sole source of the exact SKU. Compose them as one intentional commercial relationship: wear the product when it is apparel or an accessory, hold or place it naturally when it is an object, and never show the person and product as unrelated cutouts. Preserve the product's silhouette, material, color, Logo and readable text; do not replace the person's identity with the product reference wearer.")
        elif "人物" in semantic_roles:
            parts.append("PERSON-ONLY EDITORIAL LOCK: first preserve and accurately reinterpret the connected 人物 image's face, identity, skin tone, hair, body proportions, expression and existing clothing layers, silhouette, colors, footwear and accessories. The wardrobe reference is the styling foundation; do not replace it with generic fashion or a newly invented model unless the user explicitly asks. Build a lived-in fashion editorial around this person: choose an intentional urban location, time of day, weather/light condition, walking or interacting gesture, foreground depth and a responsive camera moment. For street fashion, show movement, attitude and environmental context rather than a blank studio pose.")
        elif "商品" in semantic_roles:
            parts.append("PRODUCT HERO LOCK: use the connected 商品 image as the exact SKU source and make it the visual hero. Do not invent a person unless the user explicitly requests one.")
        if "姿态" in semantic_roles:
            parts.append("POSE AND CAMERA REFERENCE LOCK: use the connected pose image only for body action, gesture, camera viewpoint, crop and subject placement; do not copy its identity, clothing, products or background.")
        if "版式" in semantic_roles:
            parts.append("LAYOUT REFERENCE LOCK: use the connected layout image only for composition hierarchy, negative space, balance, crop and text-safe regions; do not copy its brand, subject or literal text.")
        if reference_analysis:
            parts.append("REFERENCE FACT ANALYSIS (facts first; preserve identity and existing wardrobe unless the user explicitly overrides): " + reference_analysis[:10000])
        if visual_system_text:
            parts.append("RESEARCHED EDITORIAL VISUAL SYSTEM (execute these decisions, do not mention the research or copy any named campaign): " + visual_system_text)
        if research:
            parts.append("CASE STUDY RESEARCH SUMMARY (absorb methods only, do not copy subjects, brands, logos, locations or wording): " + research[:14000])
        if plan:
            parts.append("CREATIVE DIRECTOR PLAN (follow as the execution authority; it overrides generic defaults): " + plan[:14000])
        parts.append("ANTI-ORDINARY CHECK: before finalizing, verify that the image has a specific place, time/light, palette relationship, styling intention, physical gesture and editorial camera choice. If any are missing, redesign the frame; do not fall back to white-background studio photography.")
        return " ".join(parts)
    reference_map = build_ordered_reference_map(normalized)
    if instruction and operation != "universal":
        return build_user_directed_ecommerce_prompt(instruction)
    user_supplement = f"USER SUPPLEMENT: {instruction}" if instruction else ""
    user_supplement_override_rule = build_user_supplement_override_rule(instruction) if operation == "universal" else ""
    lower_garment_lock = build_lower_garment_structure_lock(normalized)
    named_detail_lock = build_named_detail_region_lock(normalized)
    user_waistband_geometry_lock = build_user_waistband_geometry_lock(instruction)
    subject_spatial_lock = ""
    studio_reference_lock = build_studio_reference_lock(options)
    studio_background_selected = bool(studio_reference_lock)
    selected_studio = next(
        (item for item in STUDIO_REFERENCE_PRESETS if item.get("id") == str(options.get("studio_reference") or "").strip()),
        None,
    )
    selected_studio_prompt = str((selected_studio or {}).get("prompt") or "").strip()
    immutable_foreground_composition_lock = build_immutable_foreground_composition_lock(operation, normalized, options)
    source_photographic_character_lock = build_source_photographic_character_lock(operation, normalized, options)

    if operation == "universal":
        typed_plan = resolve_universal_reference_plan(normalized, options)
        auto_instruction = build_universal_auto_instruction(typed_plan["inputs"], options)
        typed_reference_map = build_ordered_reference_map(typed_plan["inputs"])
        typed_parts = [
            typed_reference_map,
            f"USER SUPPLEMENT: {instruction}" if instruction else "",
            build_universal_material_evidence_lock(typed_plan["inputs"], options),
            build_subject_native_styling_lock(typed_plan["inputs"], options),
            studio_reference_lock,
            ECOMMERCE_COLOR_FIDELITY_DIRECTIVE,
            lower_garment_lock,
            named_detail_lock,
            user_waistband_geometry_lock,
            immutable_foreground_composition_lock,
            source_photographic_character_lock,
            TEXT_AND_BRAND_FIDELITY_DIRECTIVE,
            NANO_BANANA_PRO_REFERENCE_DIRECTIVE,
            NANO_BANANA_PRO_PHOTO_DIRECTIVE,
            NANO_BANANA_PRO_ECOMMERCE_DIRECTIVE,
            ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE,
            PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE,
            "Preserve every typed owner exactly. Add only the mapped model, garments, shoes, accessories, carried items, scene props, and environment; do not add unrelated people, products, text, watermarks, duplicate objects, or extra limbs.",
            auto_instruction,
            build_final_studio_background_override(options),
            user_supplement_override_rule,
        ]
        return " ".join(part for part in typed_parts if part).strip()

    if operation == "try_on":
        role_names = {
            "garment": "main garment",
            "model_identity": "model face identity only",
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
            f"Preserve the source person's body shape, limb proportions, original hair, hairstyle, hair color, non-face skin, source lighting, and camera; the selected studio replaces the source background. Use Image {identity_index} only as face identity: transfer facial structure and features, facial complexion, makeup, age cues, and recognizable facial appearance strictly inside the facial region without copying its hair, body pose, clothing, accessories, background, or framing."
            if studio_background_selected and identity_index
            else f"Preserve the source person's body shape, limb proportions, original hair, hairstyle, hair color, non-face skin, source lighting, camera, and background. Use Image {identity_index} only as face identity: transfer facial structure and features, facial complexion, makeup, age cues, and recognizable facial appearance strictly inside the facial region without copying its hair, body pose, clothing, accessories, background, or framing."
            if identity_index
            else "Preserve the source person's face, hair, body shape, identity, skin tone, lighting, and use the selected studio instead of the source background."
            if studio_background_selected
            else "Preserve the source person's face, hair, body shape, identity, skin tone, lighting, and background."
        )
        pose_instruction = (
            f" Use Image {pose_index} only as the spatial / pose template: match its body action, joint arrangement, gesture, balance, camera viewpoint, shot scale, framing, crop, subject size, and placement. "
            + _pose_orientation_lock(pose_index) + " "
            "Do not copy the pose reference person's identity, clothing, accessories, or background."
            if pose_index
            else " Preserve the source person's pose, hands, framing, and lighting; the selected studio replaces the source background."
            if studio_background_selected
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
                target + " Preserve the source person's identity, facial features, body proportions, outfit, accessories, SKU-level product details, logos, labels, readable text, and lighting; the selected studio replaces the source background. "
                if studio_background_selected
                else target + " Preserve the source person's identity, facial features, body proportions, outfit, accessories, SKU-level product details, logos, labels, readable text, lighting, and background appearance. "
                "Let the pose reference override the source image only for pose and spatial composition. Keep anatomy, balance, hands, feet, fabric tension, folds, clean garment edges, and occlusions realistic. "
                "POSE TRANSFER SOURCE LOCK: reproject source clothing textures, product details, logos, labels, jewelry, and hairstyle through the new pose; do not preserve the source background when a studio is selected, and do not redesign, denoise, simplify, recolor, or replace the outfit while changing posture. "
                "Keep product graphics and garment text non-mirrored and readable after the pose change. "
                + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE + " "
                + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
            )
        else:
            target = "Apply this target pose: " + _preset_prompt(POSE_PRESETS, str(options.get("pose_preset") or "standing_front"), "standing_front") + "."
            task = (
                target + " Preserve the source person's identity, facial expression, body proportions, outfit, accessories, SKU-level product details, logos, labels, readable text, camera framing, and lighting; the selected studio replaces the source background. "
                if studio_background_selected
                else target + " Preserve the source person's identity, facial expression, body proportions, outfit, accessories, SKU-level product details, logos, labels, readable text, camera framing, lighting, and background. "
                "Keep anatomy, balance, hands, feet, fabric tension, folds, clean garment edges, and occlusions realistic. "
                "POSE TRANSFER SOURCE LOCK: reproject source clothing textures, product details, logos, labels, jewelry, and hairstyle through the new pose; do not preserve the source background when a studio is selected, and do not redesign, denoise, simplify, recolor, or replace the outfit while changing posture. "
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
            "Remove every remnant of the old prop while leaving all non-environment pixels outside the target region semantically unchanged; the selected studio replaces the source background. "
            if studio_background_selected
            else "Remove every remnant of the old prop while leaving all pixels outside the target region semantically unchanged. "
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
            "Keep geometry, perspective, product edges, contact shadows, and reflections believable; render the selected studio instead of the source background. "
            if studio_background_selected
            else "Keep geometry, perspective, product edges, contact shadows, reflections, and background continuity believable. "
            "ANGLE REGENERATION SKU LOCK: preserve the same product identity while changing only camera viewpoint; never mirror or garble logos/text, invent unseen decorations, change material scale, flatten curved surfaces, distort symmetry, or alter package/product proportions. Newly visible surfaces must follow the source material grain, construction logic, and lighting response. "
            + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE + " "
            + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
        )
    else:
        background_mode = str(options.get("background_mode") or "preset")
        if studio_background_selected:
            target = selected_studio_prompt
        elif background_mode == "reference":
            target = "Use the background reference for environment, composition, palette, and lighting, without copying any foreground subject from it."
        elif background_mode == "prompt":
            target = str(options.get("background_prompt") or "clean professional e-commerce studio background").strip()
        else:
            target = _preset_prompt(BACKGROUND_PRESETS, str(options.get("background_preset") or "studio_white"), "studio_white")
        task = (
            f"Replace only the background with: {target} Render only a replacement environment while preserving the foreground person or product exactly, including silhouette, hair, transparent materials, colors, material micro-texture, logos, labels, and readable text. "
            "Keep cutout boundaries and product edges clean, with no halo, spill, clipping, smearing, or lost detail. "
            "Create natural contact shadows, reflections, depth of field, and coherent light direction without adding unrelated props, people, text, or watermark. "
            "BACKGROUND REPLACEMENT FOREGROUND LOCK: change only the environment and its contact lighting; do not retouch, denoise, redraw foreground, change outfit/product texture, alter face/body/product proportions, restyle hairstyle, change hairline/parting/curl pattern/flyaways, soften hair, erase transparent edges, or damage logos and readable text. Preserve the source's native photographic character, including any visible film grain, scan texture, tonal curve, focus softness, and natural imperfections; render the new background with that same character instead of a sterile e-commerce finish. Match new shadows and reflections to the preserved foreground without bleeding background color into product edges. "
            + ZOOM_READY_ECOMMERCE_GENERATION_DIRECTIVE + " "
            + PREMIUM_ECOMMERCE_TEXTURE_DIRECTIVE
        )

    if operation == "pose_transfer" and str(options.get("pose_source") or "preset") == "reference":
        preservation = (
            "Preserve source identity, clothing, products, and lighting; the selected studio replaces background content. The pose reference replaces the source pose and spatial composition, including camera viewpoint, shot scale, framing, crop, subject placement, non-mirrored screen-side orientation, face/gaze direction, torso yaw, and left/right limb order. "
            if studio_background_selected
            else "Preserve source identity, clothing, products, lighting, and background content. The pose reference replaces the source pose and spatial composition, including camera viewpoint, shot scale, framing, crop, subject placement, non-mirrored screen-side orientation, face/gaze direction, torso yaw, and left/right limb order. "
            "Only an explicit additional user instruction may override the pose reference's spatial constraints. Do not add people, products, text, watermarks, duplicate objects, or extra limbs."
        )
    else:
        preservation = (
        "Preserve every non-environment reference-owned attribute; the selected studio replaces every reference background and environmental lighting. "
        if studio_background_selected and operation != "universal" else
        "Preserve every reference-owned attribute unless the final composition explicitly changes it. "
        "Add only the mapped subjects and products. Do not add unrelated people, products, text, watermarks, duplicate objects, or extra limbs."
        if operation == "universal" else _global_preservation()
        )
    operation_locks = [
        studio_reference_lock,
        ECOMMERCE_COLOR_FIDELITY_DIRECTIVE,
        lower_garment_lock,
        named_detail_lock,
        user_waistband_geometry_lock,
        subject_spatial_lock,
        immutable_foreground_composition_lock,
        TEXT_AND_BRAND_FIDELITY_DIRECTIVE,
        NANO_BANANA_PRO_REFERENCE_DIRECTIVE,
        NANO_BANANA_PRO_PHOTO_DIRECTIVE,
        NANO_BANANA_PRO_ECOMMERCE_DIRECTIVE,
        source_photographic_character_lock,
    ]
    parts = ([] if operation == "universal" else [reference_map]) + [
        task,
        *[lock for lock in operation_locks if lock],
        preservation,
        build_final_studio_background_override(options),
        user_supplement_override_rule,
    ]
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
