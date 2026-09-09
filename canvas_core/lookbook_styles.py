"""Lookbook 风格持久化与内置时尚广告导演规则。"""
from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path


FASHION_EDITORIAL_STYLE_ID = "fashion-advertising"
# 风格卡片/兼容旧客户端使用的简介；不再作为完整导演的运行时替代。
# fashion_director 完整加载随包分发的原始技能规划，再向生图模型发送编译后的摄影指令。
FASHION_EDITORIAL_PROMPT = " ".join([
    "FASHION EDITORIAL SEQUENCE DIRECTOR v1.2 / EDITORIAL_B: create photographed, alive, opinionated high-fashion campaign imagery. User intent and explicit appearance, wardrobe, weather, lighting, camera and delivery choices override preset defaults. EDITORIAL_B is a photographic method, not a sunny filter.",
    "REFERENCE ROUTER: assign SUBJECT_IDENTITY, WARDROBE, LOCATION, STYLE_ANCHOR, SKIN_REFERENCE, LIGHT_ONLY, COLOR_ONLY, COMPOSITION_ONLY, MAKEUP_HAIR, TEXTURE_ONLY, POSE, PROP or GENERAL_MOOD. Transfer only the assigned attributes. Never borrow identity from a style, lighting or clothing reference. Preserve facial geometry, recognizable relationships, body proportions and hair identity; preserve who the person is, not source exposure, white balance or beauty retouching.",
    "APPEARANCE AND SKIN: explicit complexion first, then explicit skin reference, then the subject adapted to the actual environment. Do not infer skin tone from ethnicity. Skin realism is independent of skin color: retain plausible pores, local color variation, facial planes, natural oils or moisture, lip texture and flyaway hair. Freckles are optional only when requested or evidenced, never mandatory. Reject plastic skin, universal cheek glow, over-whitening, polished teeth and beauty fill that erases physical shadows.",
    "ENVIRONMENT ENGINE: determine weather, time, season, geography, temperature, humidity, sky, ground and architecture. Derive ENVIRONMENT -> PHYSICAL LIGHT -> SKIN RESPONSE -> EXPOSURE -> PHOTOGRAPHIC SURFACE. Sun uses directional sunlight and actual bounce; rainy city uses overcast skylight and wet reflections without fake golden rims; snow uses snow bounce and plausible cold response; night uses real practical lights. Preserve supplied location geometry and scene-owned details. Never force sunlight, warmth, tan or high contrast onto every scene.",
    "CAMERA EXPRESSION: select intensity for the brief: quiet observation, deliberate editorial perspective, or bold expressive framing. Use intentional lens families: 20-28mm environment/perspective when justified, 35mm environmental portrait, 50mm natural editorial, 70-85mm compressed observation and close detail. Low hero angles, foreground occlusion, negative space, asymmetric crop and perspective risk are allowed when motivated. Avoid repeated safe eye-level catalog portraits; adjacent frames must change camera position, framing or body orientation. Do not force aggressive angles onto intimate scenes.",
    "EVENT AND CONTINUITY LEDGER: lock identity, wardrobe, shoes, accessories, hair, makeup, location, weather and light world; track props and screen sides; update event state. A micro-event may progress STATE -> TRIGGER -> ACTION -> REACTION -> DECISION -> RESOLUTION. Eyes lead real actions, hands make functional contact, weight and fabric respond physically. Establish action axis, gaze and movement direction for multi-person scenes; preserve left/right relationships unless a visible motivated crossing reorients the viewer. Do not produce nine repeated portraits or literal film coverage without standalone fashion heroes.",
    "HERO AND SURFACE: include independently usable campaign hero images proportionate to series length (about two in nine), varied scale and a deliberate visual hierarchy. Derive film or digital response from the brief: exposure, tonal shoulder, color response, skin, restrained organic grain and optical imperfection form one surface. Film is not a grain overlay or compulsory warm Portra filter. Reject HDR clarity, fake luxury softness, impossible glow, repetitive bokeh, ecommerce stance, perfect hair edges and cloned poses. BTS equipment appears only when requested.",
    "DELIVERY ADAPTER: obey the node's explicit frame count, final aspect ratio and layout. Plan the full series together as a continuity/contact-sheet map before execution. Render a master contact sheet only when the selected layout or user requests a grid; independent outputs remain single full-bleed photographs. Never add an extra grid image, approval step or fixed nine-frame recipe. Compose each shot for its final ratio; the grid serves the frame. If an approved visual anchor exists, reuse its camera, light, contrast and surface method without copying identity or weather from it.",
    "LAYER QA: verify identity, wardrobe, reference-role separation, plausible skin/light, environment, camera diversity, axis, event progression, hero strength, ratio and surface. Repair only failed layers. Explicit user intent remains above generic reference skin-tone, wardrobe, camera-height and sunny-film defaults.",
])

FASHION_EDITORIAL_STYLE = {
    "id": FASHION_EDITORIAL_STYLE_ID,
    "name": "时尚广告",
    "description": "完整导演技能、商品主角、独立镜头设计与真实摄影质感",
    "prompt": FASHION_EDITORIAL_PROMPT,
    "source": "builtin",
    "skill_version": "1.2",
    "runtime": "full-skill-director",
}

_STORE_LOCK = threading.RLock()


def load_styles(data_root: Path) -> list[dict]:
    path = Path(data_root) / "config" / "lookbook-styles.json"
    with _STORE_LOCK:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or any(not isinstance(item, dict) or not item.get("id") for item in data):
            raise ValueError("Lookbook 风格数据格式异常")
        return data


def save_styles(data_root: Path, styles: list[dict], *, only_missing: bool = False) -> list[dict]:
    """按 ID 合并并原子写入；迁移旧缓存不覆盖服务端已保存的数据。"""
    path = Path(data_root) / "config" / "lookbook-styles.json"
    with _STORE_LOCK:
        merged = {item["id"]: item for item in load_styles(data_root)}
        for item in styles:
            if not only_missing or item["id"] not in merged:
                merged[item["id"]] = {**merged.get(item["id"], {}), **item}
        result = list(merged.values())
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temp.open("w", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        return result


def shiying_cover_route(providers: list[dict]) -> dict:
    """封面只走已配置的拾影图片模型，不使用视觉分析聊天路由。"""
    provider = next((p for p in providers if p.get("id") == "shiying" and p.get("enabled", True)), None)
    models = (provider or {}).get("image_models") or []
    if not models:
        raise ValueError("请先在 API 设置中启用 shiying 平台并配置图片模型和 API Key")
    preferred = "gemini-3-pro-image-preview"
    return {"provider_id": "shiying", "model": preferred if preferred in models else models[0]}
