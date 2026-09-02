"""使用两位新模特生成李维斯风格多场景互动样本。

直接调用 ``execute_ai_image_batch``，不经过 FastAPI TestClient；每个场景 4 个
独立 count=1 shot，方便逐张人工检查身份、互动因果、构图和光色。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MODEL_DIR = ROOT / "测试" / "模特"
OUTPUT_DEFAULT = ROOT / "输出" / "李维斯广告风格分析" / "多场景互动回归-20260902"

SCENES = {
    "western_bar": {
        "name": "美式西部复古酒吧",
        "brief": "美国西部小镇的复古酒吧，深色木质吧台、旧皮革卡座、锡制吊灯、窗外尘土和午后斜光；两位女性按各自段落完成到店、点单和交谈，部分镜头只有一人，部分镜头产生菜单/杯子交接。暖钨丝实景灯与窗外冷尘光分层，保留木材、皮革、玻璃和场景化丹宁服装纹理；不要复制模特参考图的面试穿搭。",
        "shots": [
            {"role": "环境建立", "camera": "wide eye-level documentary frame from the bar entrance, both women small in the room with bar geometry and practical lights readable", "action": "one woman holds the heavy door open and turns back to make eye contact as the other steps through; they arrive together toward two empty stools", "gaze": "their eye-lines meet briefly before returning to the shared bar destination, never posing for the camera", "performance": "door-holding creates a clear reason for proximity, different strides and natural spacing"},
            {"role": "动作经过", "subjects": "solo woman 1", "camera": "oblique medium frame across the wooden counter", "action": "woman 1 studies the menu and places an order with a bartender just outside frame", "gaze": "eyes follow the menu and bartender, not the camera", "performance": "one hand anchors the menu, the other rests naturally on worn wood"},
            {"role": "情绪停顿", "subjects": "solo woman 2", "camera": "intimate three-quarter portrait framed through a foreground bottle or mirror edge", "action": "woman 2 listens from the booth after hearing a surprising detail, turning slightly toward her friend off-frame", "gaze": "eyes stay on the speaking friend; no beauty pose or direct camera stare", "performance": "half-breath, small mouth change, relaxed shoulders, believable solo pause"},
            {"role": "材质收束", "camera": "close tactile crop of two hands, denim seams, glass condensation and worn wood", "action": "their hands briefly meet while exchanging the glass, with visible pressure and contact shadow", "gaze": "faces may be outside the crop", "performance": "show denim weave, stitching, skin pores, glass reflections and wood wear"},
        ],
    },
    "california_desert": {
        "name": "加州沙漠",
        "brief": "加州沙漠公路旁的旧加油站与低矮荒漠山脊，赭石沙土、褪色招牌、旧皮卡、仙人掌和干燥热浪；两位女性是同行旅伴，先分别观察路线，再在车尾共同整理地图和水壶，部分镜头为单人望向公路。硬朗低角度太阳、长阴影、风吹发丝和衣料，天空清澈，空气干燥透明，拒绝棚拍；不要复制模特参考图的面试穿搭。",
        "shots": [
            {"role": "环境建立", "subjects": "solo woman 1", "camera": "wide low-angle environmental frame with desert horizon, road and vehicle framing one woman", "action": "woman 1 walks from the parked pickup toward the station carrying a travel bag, checking the road ahead", "gaze": "attention fixed on the route, not the camera", "performance": "wind moves hair and scene-specific utility clothing, feet grounded in sand and gravel"},
            {"role": "动作经过", "camera": "human-distance side medium frame beside the pickup bed", "action": "one woman unfolds a paper map on the tailgate while the other holds the edge against the wind and points to a route", "gaze": "both eyes follow the map and pointing finger", "performance": "functional grips, torso rotation and weight shift against the wind"},
            {"role": "情绪停顿", "subjects": "solo woman 2", "camera": "close three-quarter portrait with sunlit rim and cool sky bounce", "action": "woman 2 pauses beside the pickup after spotting the route, taking a breath before looking toward the road", "gaze": "eyes move from the sign to the road beyond frame", "performance": "wind-released shoulders and restrained relief, no beauty pose"},
            {"role": "材质收束", "camera": "tactile close-up of denim waistband, dusty hands, map paper, truck paint and cactus shadow", "action": "one hand anchors the map while the other passes a metal canteen, creating overlapping contact", "gaze": "faces outside crop", "performance": "show dust, denim weave, paper fibers, metal highlights and hard cast shadows"},
        ],
    },
    "florida_resort": {
        "name": "佛罗里达海滨度假村",
        "brief": "佛罗里达海滨度假村的开放式泳池露台与棕榈树，白色遮阳伞、浅色躺椅、湿润石材、海面反光和远处大西洋；两位女性是同行旅伴，分别从海边回到露台，再在部分镜头共享毛巾和冷饮，另一些镜头只表现一人的湿发、脚步或情绪停顿。明亮湿润的海边天光、柔和反射、少量暖色度假村实景灯；按场景重新搭配轻薄丹宁/泳装层次，不复制面试穿搭。",
        "shots": [
            {"role": "环境建立", "camera": "wide eye-level resort terrace frame, pool, palms and ocean horizon establish humid daylight", "action": "the two women return from the water; one reaches the lounger first, lifts a shared towel and drapes it over the other's shoulders while the other steadies her wet sandals", "gaze": "they look at each other and the towel during the handoff, not at the camera", "performance": "the towel creates a visible shared contact point, wet hair and fabric have believable weight"},
            {"role": "动作经过", "subjects": "solo woman 1", "camera": "oblique medium frame beside a white lounger", "action": "woman 1 wrings seawater from a towel and sets her sandals beside the lounger", "gaze": "eyes follow the towel and wet floor, not the camera", "performance": "wet hair, damp scene-specific clothing and grounded weight"},
            {"role": "情绪停顿", "subjects": "both women", "camera": "intimate shaded two-shot framed by palm leaves and umbrella fabric", "action": "they pause under shade after a small joke, one leans into the other while both watch pool activity", "gaze": "shared off-frame focus, relaxed eyelids and mouth corners", "performance": "quiet breath, damp flyaway hair, comfortable interpersonal distance"},
            {"role": "材质收束", "camera": "close tactile crop of wet denim/knit, towel loops, condensation and sunlit stone", "action": "one hand squeezes water from the towel while the other steadies the glass on the lounger", "gaze": "faces outside crop", "performance": "show water beads, textile loops, skin texture, glass refraction and soft contact shadows"},
        ],
    },
    "western_bar_blue_hour": {
        "name": "美式西部复古酒吧·蓝调入夜",
        "brief": "同一间美国西部复古酒吧进入蓝调入夜：窗外蓝灰天光、吧台暖琥珀灯、旧木和皮革反光清楚；两位女性旅伴一人先在靠窗座位写明信片，另一人进门带来外套，随后在吧台分享一杯无酒精饮料。保持两人身份连续但不要求每张同框，服装改为适合夜间的丹宁夹克、针织和靴子，不复制面试穿搭。",
        "shots": [
            {"role": "环境建立", "subjects": "solo woman 1", "camera": "wide frame from the dim bar interior toward the blue window, one woman alone at a booth with practical lamps readable", "action": "woman 1 writes a postcard by the window and glances toward the empty doorway as evening falls", "gaze": "eyes move between postcard and doorway, never the camera", "performance": "quiet solo beat, shoulders relaxed, blue ambient and warm lamp separated"},
            {"role": "动作经过", "subjects": "both women", "camera": "oblique medium two-shot at the entrance", "action": "woman 2 arrives carrying a folded denim jacket and places it over the back of woman 1's chair; they exchange a brief greeting", "gaze": "they look at each other and the jacket during the handoff", "performance": "clear handoff contact, natural distance and different body angles"},
            {"role": "情绪停顿", "subjects": "solo woman 2", "camera": "intimate portrait through a foreground bottle and window reflection", "action": "woman 2 listens to a voice message at the bar and smiles softly after recognizing woman 1's voice", "gaze": "eyes lowered to the phone, then lift toward the booth", "performance": "small involuntary smile, restrained emotion, no catalog pose"},
            {"role": "材质收束", "subjects": "both women", "camera": "close tactile crop of two hands, denim cuffs, glass condensation and scratched wood", "action": "their hands meet while passing one chilled glass across the bar", "gaze": "faces outside crop", "performance": "accurate grip, condensation, denim weave and warm/cool mixed reflections"},
        ],
    },
    "california_desert_golden_wind": {
        "name": "加州沙漠·日落起风",
        "brief": "同一条加州沙漠公路在日落前后起风：旧皮卡、仙人掌、赭石山脊、尘土被低角度金光照亮；两位女性旅伴先各自检查车辆和路线，随后在车尾固定被风吹动的地图，最后一起望向即将出发的公路。场景化服装为耐磨丹宁、轻薄围巾、靴子和旅行包，不复制面试穿搭。",
        "shots": [
            {"role": "环境建立", "subjects": "solo woman 2", "camera": "wide profile frame with low sun, pickup and long desert road", "action": "woman 2 checks the pickup mirror and watches dust moving across the road", "gaze": "eyes follow the road and wind direction", "performance": "wind lifts scarf and hair, feet planted on gravel"},
            {"role": "动作经过", "subjects": "solo woman 1", "camera": "medium side frame at the open tailgate", "action": "woman 1 anchors a folded map with a metal canteen while the wind tries to lift the corners", "gaze": "eyes stay on the map and road marker", "performance": "one knee braces against the bumper, believable counterforce"},
            {"role": "情绪停顿", "subjects": "both women", "camera": "three-quarter two-shot against the low orange sun and cool ridge", "action": "they stand shoulder to shoulder after securing the map, sharing a silent look before leaving", "gaze": "eye-lines move from each other to the open road", "performance": "subtle nod, relaxed breath, no synchronized fashion stance"},
            {"role": "材质收束", "subjects": "both women", "camera": "close crop of dusty denim, scarf fibers, map paper and scratched truck paint", "action": "one hand catches the other's scarf end while the other closes the tailgate latch", "gaze": "faces outside crop", "performance": "dust particles, fabric tension, metal impact and hard-edged sunset shadow"},
        ],
    },
    "florida_resort_after_rain": {
        "name": "佛罗里达海滨度假村·雨后阴天",
        "brief": "同一处佛罗里达海滨度假村雨后阴天：棕榈叶滴水、泳池和石材地面湿润反光、海面灰蓝、遮阳伞收起一半；两位女性旅伴一人收拾湿毛巾和凉鞋，另一人撑伞回来，之后在雨棚下共同擦干一把躺椅。服装改为轻薄防水丹宁、针织背心和雨后凉鞋，不复制面试穿搭。",
        "shots": [
            {"role": "环境建立", "subjects": "solo woman 1", "camera": "wide quiet frame under a resort awning, wet pool deck and gray ocean horizon", "action": "woman 1 walks alone carrying two damp towels and a pair of sandals toward the covered lounge", "gaze": "eyes follow the slippery path and empty chair", "performance": "careful wet-footed steps, rain-darkened fabric and soft overcast light"},
            {"role": "动作经过", "subjects": "both women", "camera": "medium two-shot under the awning", "action": "woman 2 returns with a transparent umbrella and helps drape one towel over the wet chair while woman 1 holds the chair steady", "gaze": "both focus on chair, towel and each other's hands", "performance": "shared load and contact pressure, no posed smiling"},
            {"role": "情绪停顿", "subjects": "solo woman 2", "camera": "close portrait framed by dripping palm leaves and umbrella ribs", "action": "woman 2 pauses to listen to the rain, then looks toward the brighter sea beyond the awning", "gaze": "eyes travel from rain drops to horizon", "performance": "quiet reset after weather, damp flyaway hair, natural skin texture"},
            {"role": "材质收束", "subjects": "both women", "camera": "close tactile crop of wet denim, towel loops, umbrella handle and reflective stone", "action": "one hand wrings the towel while the other passes the umbrella handle and steadies a glass", "gaze": "faces outside crop", "performance": "water beads, fabric compression, umbrella sheen and soft contact shadows"},
        ],
    },
}

TEST_SCENE_SPECS = {
    "page-014_img-006": ("柏林地铁站台", "红色列车、薄荷绿柱体、绿色信息亭和长椅的室内站台；两位旅伴按时刻表会合，穿城市丹宁与轻便外套。", "查看站台信息并在列车进站前会合"),
    "page-017_img-001": ("地铁车厢", "复古地铁车厢内部，木色座椅、吊环和荧光灯形成对称纵深；穿通勤丹宁层次，动作围绕上车、找座和交换耳机。", "一人先上车寻找座位，另一人跟随并交换耳机"),
    "page-017_img-002": ("红色列车车头", "站台上的红色列车车头、轨道和高顶玻璃结构；硬朗城市光与金属反射，穿耐磨城市丹宁。", "一人确认车次，另一人在车门处招手示意上车"),
    "page-017_img-003": ("地铁站大厅", "明亮的复古地铁大厅、列车侧面、站牌和大面积地面留白；穿层次化城市服装，讲述赶路中的短暂停留。", "一人走过列车门，另一人停下等待并回头确认方向"),
    "page-020_img-002": ("法式街角咖啡馆", "暖色街角咖啡馆外立面、木框拱窗、遮阳篷和藤椅；穿轻薄丹宁与复古针织，围绕点单和落座。", "一人先选桌，另一人拿着菜单从街角走来"),
    "page-022_img-002": ("复古剧院门廊", "赭红与奶油色的复古剧院门廊、拱门和大型招牌；穿带西部细节的丹宁和皮革配件，围绕进场看演出。", "一人抬头确认演出海报，另一人递出两张票"),
    "page-026_img-002": ("艺术感客厅", "明亮艺术感客厅，白墙挂画、绿色边柜、木地板和唱片机；穿室内休闲丹宁与针织，围绕播放音乐和整理唱片。", "一人挑选唱片，另一人在沙发旁连接唱片机"),
    "page-027_img-003": ("复古餐厅", "复古餐厅内部，红棕色卡座、服务台和暖白顶灯；穿餐馆友好的场景化丹宁，围绕点餐和分享餐盘。", "一人坐下看菜单，另一人把饮料放到桌面并询问选择"),
    "page-029_img-005": ("复古汽车影院", "大型复古汽车影院/影院外立面，霓虹字牌、立柱和宽阔停车区；穿夜间丹宁与轻外套，围绕买票和寻找观影位置。", "一人从车旁走向售票处，另一人留在车边挥手指引"),
    "page-032_img-003": ("霓虹餐吧街角", "带霓虹招牌和玻璃橱窗的夜间餐吧街角，暖木与彩色灯管交错；穿夜间丹宁、皮夹克和简洁配饰，围绕碰面和短暂交谈。", "一人推门进入，另一人从吧台起身迎接并递出饮料"),
}


def make_test_scene_spec(scene_key: str) -> dict:
    name, setting, task = TEST_SCENE_SPECS[scene_key]
    brief = f"{setting} 两位女性旅伴不必每张同框，四张形成连续故事：先由一人建立地点，再由另一人完成 solo 任务，第三张产生共同注意或物件交接，第四张收束材质与空间接触。共同任务是：{task}。服装按场景重新搭配，不复制模特面试穿搭。"
    shots = [
        {"role": "环境建立", "subjects": "solo woman 1", "camera": "wide documentary frame preserving the supplied scene geometry", "action": f"woman 1 enters or observes the location while beginning to {task}", "gaze": "eyes follow the scene task, not the camera", "performance": "grounded posture and natural movement appropriate to the location"},
        {"role": "动作经过", "subjects": "solo woman 2", "camera": "human-distance medium frame with a real foreground occluder", "action": "woman 2 performs the next practical step of the shared task alone", "gaze": "eyes track the object, route or service point", "performance": "functional hands, believable weight shift and scene-specific wardrobe"},
        {"role": "情绪停顿", "subjects": "both women", "camera": "intimate three-quarter two-shot with environmental context readable", "action": "the two women notice each other and exchange a look or a scene-owned object before continuing", "gaze": "eye-lines meet briefly then return to the shared task", "performance": "quiet breath, distinct identities, no synchronized catalog pose"},
        {"role": "材质收束", "subjects": "both women", "camera": "close tactile crop of hands, garment texture and one scene-owned surface", "action": "their hands complete the task with a clear handoff or shared contact", "gaze": "faces may be outside the crop", "performance": "show fabric weave, skin texture, object wear and physically correct contact shadows"},
    ]
    return {"name": name, "brief": brief, "shots": shots}


def load_key(path: Path) -> str:
    current_url = ""
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line.lower().startswith("url") and ":" in line:
            current_url = line.split(":", 1)[1].strip().lower()
        if line.lower().startswith("key") and ":" in line and "shiying" in current_url:
            return line.split(":", 1)[1].strip()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="生成两位模特的李维斯多场景互动回归")
    parser.add_argument("--output-dir", default=str(OUTPUT_DEFAULT))
    parser.add_argument("--api-key-file", default=str(ROOT / "api文档" / "api key.md"))
    parser.add_argument("--provider", default="shiying")
    parser.add_argument("--model", default="gemini-3-pro-image-preview")
    parser.add_argument("--only", default="", help="只生成 western_bar/california_desert/florida_resort 中的一个或多个")
    parser.add_argument("--include-test-scenes", action="store_true", help="将测试/场景目录内的 10 张场景全部纳入生成")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    models = sorted([path for path in MODEL_DIR.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"}])
    if len(models) < 2:
        raise RuntimeError(f"需要至少两张模特参考图，当前找到 {len(models)} 张")
    requested = {value.strip() for value in args.only.split(",") if value.strip()}
    selected_keys = [key for key in SCENES if not args.only or key in requested]
    if args.include_test_scenes:
        selected_keys.extend([key for key in TEST_SCENE_SPECS if not args.only or key in requested])
    if not selected_keys:
        raise RuntimeError("--only 没有匹配到场景")

    key = load_key(Path(args.api_key_file))
    if key:
        os.environ.setdefault("API_PROVIDER_SHIYING_KEY", key)
    os.environ.setdefault("CANVAS_DESKTOP_TOKEN", "levis-multiscene-interactions")
    os.environ.setdefault("CANVAS_RUNTIME_MODE", "desktop")
    os.environ["CANVAS_DWPOSE_AUTO_DOWNLOAD"] = "0"
    os.environ["CANVAS_DEPTH_AUTO_DOWNLOAD"] = "0"

    started = time.time()
    report = {"status": "running", "style_id": "levis-adaptive-campaign", "provider": args.provider, "model": args.model, "models": [str(path) for path in models[:2]], "scenes": []}
    with tempfile.TemporaryDirectory(prefix="levis-multiscene-data-") as data_dir:
        os.environ["CANVAS_DATA_DIR"] = data_dir
        import main as canvas_main
        from canvas_core.ecommerce import build_prompt

        input_root = Path(os.fspath(canvas_main.OUTPUT_INPUT_DIR))
        input_root.mkdir(parents=True, exist_ok=True)
        refs = []
        for index, model_path in enumerate(models[:2], 1):
            target = input_root / f"model_{index}{model_path.suffix.lower()}"
            shutil.copy2(model_path, target)
            refs.append({"url": f"/assets/input/{target.name}", "role": "subject", "reference_type": "subject", "reference_id": f"model_{index}", "label": f"人物{index}", "lookbook_role": "人物", "instruction": "只保持该人物独立身份、脸型、发型、肤色和体态；参考图中的面试服装不用于最终合成，由当前场景重新设计服装。不要与另一位人物融合或换脸。"})

        for scene_key in selected_keys:
            scene = SCENES.get(scene_key) or make_test_scene_spec(scene_key)
            scene_refs = list(refs)
            scene_path = ROOT / "测试" / "场景" / f"{scene_key}.jpeg"
            if scene_path.is_file():
                target_scene = input_root / f"scene_{scene_key}.jpeg"
                shutil.copy2(scene_path, target_scene)
                scene_refs.append({"url": f"/assets/input/{target_scene.name}", "role": "scene", "reference_type": "scene", "reference_id": scene_key, "label": "场景", "lookbook_role": "场景", "instruction": "保留该场景的空间几何、主要色彩、材质、标识和光线线索；不要把场景中的文字或人物图形变成新的主体。"})
            options = {
                "prompt_policy": "lookbook",
                "instruction": scene["brief"] + " 生成四张同一系列原创丹宁广告照片，四张形成有因果的故事组：允许 solo、双人互动和材质细节交替，不要求每张都出现两人；只有标注 both women/both subjects 的镜头才同时出现两人。服装按该场景重新搭配并在四张内保持连续。",
                "lookbook_count": 4,
                "lookbook_style": {"id": "levis-adaptive-campaign", "name": "李维斯广告·环境自适应纪实"},
                "lookbook_search": False,
                "lookbook_quality_gate": False,
                "lookbook_wardrobe_mode": "scene_styled",
                "lookbook_research_shots": scene["shots"],
            }
            prompt = build_prompt("universal", scene_refs, options)
            snapshot = {"count": 4, "prompt": prompt, "options": options}
            prompts = canvas_main.lookbook_generation_prompts(snapshot)
            item_report = {"id": scene_key, "name": scene["name"], "brief": scene["brief"], "status": "running", "images": [], "prompt": prompt, "generation_prompts": prompts}
            try:
                batch = asyncio.run(canvas_main.execute_ai_image_batch(prompt=prompt, provider_id=args.provider, model=args.model, size="4:5", quality="high", references=scene_refs, count=4, prefix=f"levis_{scene_key}_", allow_edit_endpoint_fallback=False, semantic_mask=True, prompts=prompts))
                for index, url in enumerate(batch.get("images") or [], 1):
                    source = canvas_main.output_file_from_url(url)
                    if not source or not Path(source).is_file():
                        continue
                    target = output_dir / f"{scene_key}_{index:02d}{Path(source).suffix.lower()}"
                    shutil.copy2(source, target)
                    with Image.open(target) as image:
                        item_report["images"].append({"path": str(target), "size": f"{image.width}x{image.height}", "shot_index": index})
                item_report["status"] = "ok" if len(item_report["images"]) == 4 else "partial"
            except Exception as exc:
                item_report.update({"status": "failed", "error": str(exc)[:1000]})
            report["scenes"].append(item_report)
            (output_dir / "多场景互动生成报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report["status"] = "ok" if report["scenes"] and all(item.get("status") == "ok" for item in report["scenes"]) else "partial"
    report["elapsed_seconds"] = round(time.time() - started, 3)
    (output_dir / "多场景互动生成报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "scenes": len(report["scenes"]), "images": sum(len(item.get("images") or []) for item in report["scenes"]), "elapsed_seconds": report["elapsed_seconds"]}, ensure_ascii=False))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
