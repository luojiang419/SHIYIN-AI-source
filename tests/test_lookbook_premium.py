import asyncio
import json
import tempfile
import unittest
import inspect
from unittest.mock import patch

from PIL import Image

import main
from canvas_core.ecommerce import build_prompt


class LookbookPremiumResearchTests(unittest.TestCase):
    def test_auto_mode_plan_keeps_reference_grounding_and_art_direction(self):
        plan = main.build_lookbook_agent_plan({
            "operation": "universal",
            "inputs": [{"url": "/assets/input/person.png"}, {"url": "/assets/input/scene.png"}],
            "options": {"prompt_policy": "lookbook", "lookbook_search": True, "instruction": ""},
        })
        self.assertEqual(plan["mode"], "auto-reference")
        self.assertTrue(plan["stages"][0]["enabled"])
        self.assertTrue(plan["stages"][1]["enabled"])
        self.assertTrue(plan["stages"][2]["enabled"])
        self.assertTrue(plan["stages"][3]["enabled"])

    def test_auto_person_scene_prompt_is_candid_and_series_oriented(self):
        prompt = build_prompt("universal", [
            {"role": "prop", "reference_type": "prop", "lookbook_role": "人物", "url": "/assets/input/person.png"},
            {"role": "prop", "reference_type": "prop", "lookbook_role": "场景", "url": "/assets/input/scene.png"},
        ], {
            "prompt_policy": "lookbook",
            "lookbook_style": {"name": "时尚街景", "prompt": "urban fashion editorial"},
            "lookbook_count": 4,
        })
        self.assertIn("AUTO LOOKBOOK MODE", prompt)
        self.assertIn("PERSON-SCENE LIFESTYLE LOCK", prompt)
        self.assertIn("candid lifestyle fashion snapshots", prompt)
        self.assertIn("never make a contact sheet", prompt)
        self.assertIn("WARDROBE IMMUTABILITY LOCK", prompt)
        self.assertIn("SCENE TYPOGRAPHY AND PLANE-FIGURE LOCK", prompt)
        self.assertIn("EDITORIAL CAMERA GRAMMAR", prompt)
        self.assertIn("NATURAL SUNLIGHT AND SOFT-FILM LOCK", prompt)
        self.assertIn("NARRATIVE COLOR SCRIPT", prompt)
        self.assertIn("CAMERA BEHAVIOR", prompt)

    def test_reference_first_skill_preserves_distinct_people_and_scene_contact(self):
        prompt = build_prompt("universal", [
            {"role": "prop", "reference_type": "prop", "lookbook_role": "人物", "url": "/assets/input/person-a.png"},
            {"role": "prop", "reference_type": "prop", "lookbook_role": "人物", "url": "/assets/input/person-b.png"},
            {"role": "prop", "reference_type": "prop", "lookbook_role": "场景", "url": "/assets/input/scene.png"},
        ], {
            "prompt_policy": "lookbook",
            "lookbook_style": {"id": "multi-person-interaction", "name": "多人互动纪实", "prompt": "multi-person interaction"},
            "lookbook_count": 4,
        })
        self.assertIn("MULTI-PERSON INTERACTION LOCK", prompt)
        self.assertIn("MULTI-PERSON INTERACTION LOCK", prompt)
        self.assertIn("2 distinct supplied people", prompt)
        self.assertIn("REFERENCE-SCENE INTEGRATION", prompt)
        self.assertIn("AUTO LOOKBOOK MODE", prompt)

    def test_agent_plan_keeps_node_generation_settings_and_clamps_timeout(self):
        snapshot = {
            "operation": "universal",
            "provider_id": "shiying",
            "model": "gemini-3-pro-image-preview",
            "aspect_ratio": "3:4",
            "resolution": "2k",
            "quality": "high",
            "count": 4,
            "size": "1536x2048",
            "inputs": [{"url": "/assets/input/model.png"}],
            "options": {"prompt_policy": "lookbook", "lookbook_timeout_minutes": 100, "lookbook_search": True, "lookbook_research_depth": "deep"},
        }
        plan = main.build_lookbook_agent_plan(snapshot)
        self.assertEqual(plan["strategy"], "durable-state-machine")
        self.assertEqual(plan["timeout_seconds"], 60 * 60)
        self.assertEqual(plan["generation_settings"]["model"], "gemini-3-pro-image-preview")
        self.assertEqual(plan["generation_settings"]["count"], 4)
        self.assertEqual(main.lookbook_agent_timeout_seconds({"lookbook_timeout_minutes": 1}), 5 * 60)
        self.assertNotIn("quality-gate", {stage["id"] for stage in plan["stages"]})

    def test_agent_marks_timeout_as_terminal_504_without_restarting_generation(self):
        async def slow_execute(_task_id, _snapshot):
            await asyncio.sleep(0.05)

        snapshot = {"operation": "universal", "options": {"prompt_policy": "lookbook"}}
        with patch.object(main, "lookbook_agent_timeout_seconds", return_value=0.01), patch.object(main, "execute_ecommerce_task", new=slow_execute), patch.object(main, "update_ecommerce_task") as update:
            asyncio.run(main.run_ecommerce_task("lookbook-timeout", snapshot))
        changes = [call.args[1] for call in update.call_args_list if len(call.args) > 1]
        self.assertTrue(any(item.get("status") == "failed" and item.get("status_code") == 504 for item in changes))
        self.assertTrue(any(item.get("agent_stage") == "timeout" for item in changes))

    def test_person_only_street_editorial_prompt_rejects_generic_studio_defaults(self):
        prompt = build_prompt(
            "universal",
            [{
                "role": "prop",
                "reference_type": "prop",
                "lookbook_role": "人物",
                "url": "/assets/input/model.png",
            }],
            {
                "prompt_policy": "lookbook",
                "instruction": "时尚街景，充满生命力",
                "lookbook_style": {"name": "时尚街景", "prompt": "urban fashion editorial"},
                "lookbook_reference_analysis": '{"face":"短发与清晰轮廓","wardrobe":"黑色皮夹克与宽腿裤"}',
                "lookbook_visual_system": {
                    "palette": {"dominant": "深炭黑", "accent": "酸性黄", "ratios": "70/20/10"},
                    "lighting": "傍晚侧逆光与受控闪光",
                    "environment_and_motion": "湿润街道、行走中的衣摆",
                },
            },
        )
        self.assertIn("PERSON-ONLY EDITORIAL LOCK", prompt)
        self.assertIn("face, identity, skin tone, hair", prompt)
        self.assertIn("EDITORIAL QUALITY DIRECTIVE", prompt)
        self.assertIn("default white seamless backdrops", prompt)
        self.assertIn("深炭黑", prompt)
        self.assertIn("70/20/10", prompt)
        self.assertIn("ANTI-ORDINARY CHECK", prompt)

    def test_person_scene_prompt_keeps_outfit_and_background_poster_as_graphic(self):
        prompt = build_prompt("universal", [
            {"role": "prop", "reference_type": "prop", "lookbook_role": "人物", "url": "/assets/input/model.png"},
            {"role": "prop", "reference_type": "prop", "lookbook_role": "场景", "url": "/assets/input/scene.jpeg"},
        ], {"prompt_policy": "lookbook", "lookbook_count": 4})
        self.assertIn("exact outfit is the styling source of truth", prompt)
        self.assertIn("printed/photographed face or editorial poster", prompt)
        self.assertIn("never treat it as a second live person", prompt)

    def test_auto_style_prompt_delegates_selection_to_visual_model(self):
        prompt = build_prompt("universal", [{"role": "prop", "reference_type": "prop", "lookbook_role": "人物", "url": "/assets/input/model.png"}], {
            "prompt_policy": "lookbook",
            "lookbook_style": {"id": "auto", "name": "自动", "prompt": "autonomous visual direction"},
            "instruction": "为这组人物和场景选择最合适的风格",
        })
        self.assertIn("AUTO STYLE ROUTER", prompt)
        self.assertIn("AUTO STYLE ROUTER", prompt)

    def test_auto_style_decision_is_normalized_to_valid_taxonomy(self):
        decision = main.normalize_lookbook_auto_decision({
            "selected_style_id": "street-film",
            "selected_style_name": "街头电影叙事",
            "rationale": "城市层次和硬切动作",
            "confidence": 0.87,
            "art_direction": "沿街跟拍，冷暖混合光",
        })
        self.assertEqual(decision["selected_style_id"], "street-film")
        self.assertEqual(decision["confidence"], 0.87)
        fallback = main.normalize_lookbook_auto_decision({"selected_style_id": "made-up-style"})
        self.assertEqual(fallback["selected_style_id"], "candid-lifestyle")
        fw = main.normalize_lookbook_auto_decision({"selected_style_id": "fw-cream-cyan-film", "confidence": 0.94})
        self.assertEqual(fw["selected_style_id"], "fw-cream-cyan-film")

    def test_auto_style_plan_persists_visual_model_decision(self):
        async def fake_canvas_llm(request):
            self.assertIn("自动风格", request.message)
            self.assertIn("selected_style_id", request.message)
            return {"text": json.dumps({
                "selected_style_id": "travel-dream",
                "selected_style_name": "旅行环境梦境",
                "rationale": "参考图包含海岸与自然光线索",
                "confidence": 0.91,
                "art_direction": "沿海岸线侧向跟拍，保留风和衣摆",
            }, ensure_ascii=False)}

        snapshot = {
            "operation": "universal",
            "inputs": [{"url": "/assets/input/scene.png", "label": "场景", "lookbook_role": "场景", "role": "scene", "reference_type": "scene"}],
            "options": {
                "prompt_policy": "lookbook",
                "instruction": "生成轻盈的旅行时装系列",
                "lookbook_style": {"id": "auto", "name": "自动", "prompt": "autonomous visual direction"},
            },
        }
        with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "ecommerce-vision", "model": "gpt-5.6-sol"}), patch.object(main, "canvas_llm", new=fake_canvas_llm):
            enriched, meta = asyncio.run(main.enrich_lookbook_plan(snapshot))
        self.assertEqual(enriched["options"]["lookbook_auto_decision"]["selected_style_id"], "travel-dream")
        self.assertIn("沿海岸线", enriched["options"]["lookbook_plan"])
        self.assertEqual(meta["auto_decision"]["selected_style_id"], "travel-dream")

    def test_light_family_switches_with_editorial_style(self):
        inputs = [{"role": "prop", "reference_type": "prop", "lookbook_role": "人物", "url": "/assets/input/model.png"}]
        daylight = build_prompt("universal", inputs, {
            "prompt_policy": "lookbook",
            "lookbook_style": {"id": "candid-lifestyle", "name": "生活化真实抓拍"},
        })
        night = build_prompt("universal", inputs, {
            "prompt_policy": "lookbook",
            "lookbook_style": {"id": "street-film", "name": "街头电影叙事"},
        })
        material = build_prompt("universal", inputs, {
            "prompt_policy": "lookbook",
            "lookbook_style": {"id": "material-closeup", "name": "材质细节特写"},
        })
        self.assertIn("NATURAL SUNLIGHT AND SOFT-FILM LOCK", daylight)
        self.assertIn("LOW-KEY SPECTACLE LOCK", night)
        self.assertNotIn("NATURAL SUNLIGHT AND SOFT-FILM LOCK", night)
        self.assertIn("MATERIAL PORTRAIT LIGHT LOCK", material)

    def test_fw_reference_film_style_injects_color_camera_emotion_and_analog_locks(self):
        prompt = build_prompt("universal", [
            {"role": "prop", "reference_type": "prop", "lookbook_role": "人物", "url": "/assets/input/model.png"},
            {"role": "prop", "reference_type": "prop", "lookbook_role": "场景", "url": "/assets/input/scene.jpeg"},
        ], {
            "prompt_policy": "lookbook",
            "lookbook_style": {"id": "fw-cream-cyan-film", "name": "2026 FW 奶油青蓝胶片抓拍"},
            "lookbook_count": 4,
        })
        for marker in (
            "2026 FW REFERENCE FILM LOCK",
            "warm ivory, cream and pale lemon-yellow",
            "faded turquoise/cyan",
            "FW CAMERA GRAMMAR",
            "FW HUMAN VITALITY LOCK",
            "FW ANALOG FINISH",
            "fine-to-medium 16mm/35mm film grain",
            "FW SERIES COLOR SCRIPT",
        ):
            self.assertIn(marker, prompt)

    def test_auto_decision_can_route_to_fw_reference_film_lock(self):
        prompt = build_prompt("universal", [{"role":"prop", "reference_type":"prop", "lookbook_role":"人物", "url":"/assets/input/model.png"}], {
            "prompt_policy":"lookbook",
            "lookbook_style":{"id":"auto", "name":"自动"},
            "lookbook_auto_decision":{"selected_style_id":"fw-cream-cyan-film", "selected_style_name":"2026 FW 奶油青蓝胶片抓拍"},
        })
        self.assertIn("AUTO STYLE ROUTER", prompt)
        self.assertIn("2026 FW REFERENCE FILM LOCK", prompt)

    def test_fw_prompt_requires_transparent_sun_and_irregular_coarse_grain(self):
        prompt = build_prompt("universal", [{"role":"prop", "reference_type":"prop", "lookbook_role":"人物", "url":"/assets/input/model.png"}], {
            "prompt_policy":"lookbook",
            "lookbook_style":{"id":"fw-cream-cyan-film", "name":"2026 FW 奶油青蓝胶片抓拍"},
        })
        self.assertIn("FW NATURAL SUN TRANSPARENCY", prompt)
        self.assertIn("luminous high-key daylight photograph", prompt)
        self.assertIn("Do not underexpose the whole frame", prompt)
        self.assertIn("fine-to-medium 16mm/35mm film grain structure", prompt)
        self.assertIn("USER-SUPPLIED MODEL", prompt)
        self.assertIn("Do not add freckles", prompt)
        self.assertIn("no large connected blotches", prompt)

    def test_levis_prompt_adapts_environment_weather_and_human_performance(self):
        prompt = build_prompt("universal", [
            {"role": "prop", "reference_type": "prop", "lookbook_role": "人物", "url": "/assets/input/model.png"},
            {"role": "prop", "reference_type": "prop", "lookbook_role": "场景", "url": "/assets/input/scene.jpeg"},
        ], {
            "prompt_policy": "lookbook",
            "instruction": "把人物放进这个真实街景，做四张连续广告图",
            "lookbook_style": {"id": "levis-adaptive-campaign", "name": "李维斯广告·环境自适应纪实"},
            "lookbook_count": 4,
        })
        for marker in (
            "ADAPTIVE DENIM CAMPAIGN METHOD",
            "interior or exterior",
            "Clear sun uses directional hard-edged light",
            "overcast uses broad cool skylight",
            "rain or wet ground",
            "blue hour",
            "HUMAN PERFORMANCE AND GROOMING",
            "LEVI'S BRAND PERSONALITY AND HUMAN PERFORMANCE LOCK",
            "PUPPET-POSING HARD BAN",
            "SINGLE-FRAME AND ORIGINALITY LOCK",
        ):
            self.assertIn(marker, prompt)

    def test_levis_style_is_valid_for_auto_selection_and_uses_light_grain_finish(self):
        decision = main.normalize_lookbook_auto_decision({
            "selected_style_id": "levis-adaptive-campaign",
            "selected_style_name": "李维斯广告·环境自适应纪实",
            "confidence": 0.91,
        })
        self.assertEqual(decision["selected_style_id"], "levis-adaptive-campaign")
        batch = {"images": ["/assets/generated/levis.jpg"]}
        snapshot = {"options": {"lookbook_style": {"id": "levis-adaptive-campaign"}}}
        with patch.object(main, "apply_lookbook_organic_film_grain", return_value=True) as grain:
            self.assertIs(main.apply_lookbook_film_finish(batch, snapshot), batch)
            grain.assert_called_once_with("/assets/generated/levis.jpg", amount=0.025)

    def test_levis_default_shot_cards_use_external_objectives_instead_of_beauty_poses(self):
        prompts = main.lookbook_generation_prompts({
            "count": 4,
            "prompt": "BASE",
            "options": {"lookbook_style": {"id": "levis-adaptive-campaign"}},
        })
        self.assertNotIn("28mm", prompts[0])
        self.assertNotIn("50mm", prompts[1])
        self.assertNotIn("85mm", prompts[2])
        self.assertIn("one heel lifted", prompts[0])
        self.assertIn("performs one concrete scene-owned task", prompts[1])
        self.assertIn("off-frame sound", prompts[2])
        self.assertIn("never a static beauty pose", prompts[2])
        self.assertIn("finger pressure", prompts[3])

    def test_levis_variants_are_valid_and_keep_scene_story_in_four_frames(self):
        common = {
            "prompt_policy": "lookbook",
            "instruction": "报刊亭门口的小情景：人物买完报纸，听见街角朋友招呼，边走边回头，最后整理牛仔袖口",
            "lookbook_count": 4,
        }
        for style_id, markers in {
            "standard-advertising": ("STANDARD ADVERTISING COLOR LOCK", "STANDARD ADVERTISING PERFORMANCE"),
            "levis-high-key-color": ("HIGH-KEY BRIGHT-COLOR LOCK", "HIGH-KEY FREE CONFIDENCE PERFORMANCE", "PUPPET-POSING HARD BAN"),
            "levis-black-white": ("BLACK-AND-WHITE TONAL LOCK", "BLACK-AND-WHITE FREE CONFIDENCE PERFORMANCE", "PUPPET-POSING HARD BAN"),
        }.items():
            prompt = build_prompt("universal", [
                {"role": "prop", "reference_type": "prop", "lookbook_role": "人物", "url": "/assets/input/model.png"},
                {"role": "prop", "reference_type": "prop", "lookbook_role": "场景", "url": "/assets/input/scene.jpeg"},
            ], {**common, "lookbook_style": {"id": style_id, "name": style_id}})
            for marker in markers:
                self.assertIn(marker, prompt)
            prompts = main.lookbook_generation_prompts({"count": 4, "prompt": prompt, "options": {**common, "lookbook_style": {"id": style_id}}})
            self.assertEqual(len(prompts), 4)
            self.assertTrue(all("SINGLE-FRAME HARD STOP" in item for item in prompts))

    def test_black_white_finish_removes_chroma_and_preserves_image(self):
        import numpy as np

        with tempfile.TemporaryDirectory() as temp_dir:
            path = f"{temp_dir}/bw.jpg"
            Image.new("RGB", (48, 32), (200, 80, 40)).save(path, "JPEG", quality=95)
            with patch.object(main, "output_file_from_url", return_value=path), patch.object(main, "apply_lookbook_organic_film_grain", return_value=True):
                main.apply_lookbook_film_finish({"images": ["/assets/generated/bw.jpg"]}, {"options": {"lookbook_style": {"id": "levis-black-white"}}})
            with Image.open(path) as image:
                arr = np.asarray(image.convert("RGB"), dtype=np.int16)
            self.assertLess(int(np.abs(arr[..., 0] - arr[..., 1]).max()), 2)
            self.assertLess(int(np.abs(arr[..., 1] - arr[..., 2]).max()), 2)

    def test_scene_styled_wardrobe_uses_identity_only_and_allows_solo_shots(self):
        prompt = build_prompt("universal", [
            {"role": "subject", "reference_type": "subject", "lookbook_role": "人物", "url": "/assets/input/model_a.jpg"},
            {"role": "subject", "reference_type": "subject", "lookbook_role": "人物", "url": "/assets/input/model_b.jpg"},
        ], {
            "prompt_policy": "lookbook",
            "instruction": "两位人物在西部酒吧组成四张故事组，允许 solo 与互动镜头",
            "lookbook_style": {"id": "levis-adaptive-campaign", "name": "李维斯广告·环境自适应纪实"},
            "lookbook_wardrobe_mode": "scene_styled",
            "lookbook_count": 4,
        })
        self.assertIn("WARDROBE SCENE STYLING LOCK", prompt)
        self.assertIn("interview outfits are not to be copied", prompt)
        self.assertIn("PERSON IDENTITY-ONLY EDITORIAL LOCK", prompt)
        self.assertNotIn("The wardrobe reference is the styling foundation", prompt)

    def test_fw_organic_grain_is_non_uniform_and_changes_pixels(self):
        import numpy as np

        with tempfile.TemporaryDirectory() as temp_dir:
            path = f"{temp_dir}/grain.jpg"
            Image.new("RGB", (96, 64), (180, 170, 150)).save(path, "JPEG", quality=95)
            with patch.object(main, "output_file_from_url", return_value=path):
                self.assertTrue(main.apply_lookbook_organic_film_grain("/assets/output/grain.jpg"))
            with Image.open(path) as image:
                arr = np.asarray(image.convert("RGB"), dtype=np.int16)
            self.assertGreater(float(arr.std()), 0.25)
            self.assertGreater(int(arr.max()) - int(arr.min()), 2)
            source = inspect.getsource(main.apply_lookbook_organic_film_grain)
            self.assertNotIn("coarse_h", source)
            self.assertNotIn("clump", source)

    def test_structured_research_is_normalized_for_generation(self):
        value = main.normalize_lookbook_visual_research(json.dumps({
            "sources": [{"publication_or_brand": "Vogue", "case_or_campaign": "Street editorial", "url": "https://example.com", "why_relevant": "色彩"}],
            "visual_system": {
                "palette": {"dominant": "墨黑", "secondary": "骨白", "accent": "钴蓝", "ratios": "65/25/10", "contrast": "高对比", "light_color": "冷日光"},
                "color_grade": "冷暖分离",
                "anti_generic_rules": ["拒绝白底棚拍"],
            },
            "transferable_methods": ["用城市反射制造层次"],
            "primary_direction": {"name": "冷日光街头纪实", "reason": "匹配现有场景", "source_basis": ["Vogue case"], "avoid_mixing": ["棚拍闪光"]},
            "shot_recommendations": [{"role": "环境建立", "camera": "35mm 眼平", "action": "沿街行走", "lighting": "侧逆光", "composition": "主体偏左", "material_focus": "皮革反光"}],
            "summary": "色彩明确",
        }, ensure_ascii=False))
        self.assertEqual(value["sources"][0]["publication_or_brand"], "Vogue")
        self.assertEqual(value["visual_system"]["palette"]["ratios"], "65/25/10")
        self.assertEqual(value["visual_system"]["anti_generic_rules"], ["拒绝白底棚拍"])
        self.assertEqual(value["primary_direction"]["name"], "冷日光街头纪实")
        self.assertEqual(value["shot_recommendations"][0]["camera"], "35mm 眼平")

    def test_context_signature_invalidates_stale_research_when_brief_changes(self):
        snapshot = {
            "operation": "universal",
            "aspect_ratio": "3:4",
            "count": 4,
            "inputs": [{"url": "/assets/input/model.png", "lookbook_role": "人物"}],
            "options": {
                "prompt_policy": "lookbook",
                "instruction": "旧需求",
                "lookbook_style": {"id": "fw-cream-cyan-film", "prompt": "fixed preset"},
                "search_context": "旧案例摘要",
                "lookbook_plan": "旧方案",
                "lookbook_context_signature": "stale",
            },
        }

        refreshed, invalidated = main.invalidate_stale_lookbook_context(snapshot)

        self.assertTrue(invalidated)
        self.assertNotIn("search_context", refreshed["options"])
        self.assertNotIn("lookbook_plan", refreshed["options"])
        self.assertEqual(len(refreshed["options"]["lookbook_context_signature"]), 64)

    def test_researched_shot_cards_create_distinct_single_frame_prompts(self):
        snapshot = {
            "count": 2,
            "prompt": "BASE LOOKBOOK PROMPT",
            "options": {
                "prompt_policy": "lookbook",
                "lookbook_research_shots": [
                    {"role": "环境建立", "camera": "35mm wide"},
                    {"role": "动作经过", "camera": "50mm medium"},
                ],
            },
        }

        prompts = main.lookbook_generation_prompts(snapshot)

        self.assertEqual(len(prompts), 2)
        self.assertIn("series frame 1/2", prompts[0])
        self.assertIn("35mm wide", prompts[0])
        self.assertIn("series frame 2/2", prompts[1])
        self.assertIn("50mm medium", prompts[1])
        self.assertIn("one full-bleed photograph only", prompts[0])

    def test_default_shot_cards_are_used_when_research_is_disabled(self):
        prompts = main.lookbook_generation_prompts({
            "count": 4,
            "prompt": "BASE LOOKBOOK PROMPT",
            "options": {"prompt_policy": "lookbook", "lookbook_search": False},
        })

        self.assertEqual(len(prompts), 4)
        self.assertIn("SINGLE-FRAME HARD STOP", prompts[0])
        self.assertIn("环境建立", prompts[0])
        self.assertIn("动作经过", prompts[1])
        self.assertIn("情绪停顿", prompts[2])
        self.assertIn("材质收束", prompts[3])

    def test_story_prompts_keep_selected_style_as_primary_lock(self):
        cards = [{
            "index": 1,
            "beat": "开场",
            "story_purpose": "建立空间",
            "continuity_in": "故事开始",
            "continuity_out": "人物继续前行",
        }]
        prompts = main.lookbook_generation_prompts({
            "count": 1,
            "options": {
                "prompt_policy": "lookbook",
                "lookbook_mode": "story-campaign",
                "instruction": "一段城市行走故事",
                "lookbook_style": {"id": "standard-advertising", "name": "标准广告", "prompt": "selected style token"},
                "lookbook_bible": {"palette": "warm neutral"},
                "lookbook_shot_cards": cards,
            },
        })
        self.assertIn("PRIMARY SELECTED STYLE LOCK", prompts[0])
        self.assertIn("selected style token", prompts[0])

    def test_image_search_parameter_error_falls_back_to_plain_web_search(self):
        calls = []

        async def fake_canvas_llm(request):
            calls.append(request)
            if request.web_search_content_types:
                raise main.HTTPException(status_code=400, detail="unsupported image search option")
            return {
                "text": json.dumps({"summary": "纯文本搜索仍可用", "visual_system": {"lighting": "侧光"}}, ensure_ascii=False),
                "web_search": {"used": True, "queries": ["fashion campaign"], "sources": [], "images": []},
            }

        snapshot = {
            "operation": "universal",
            "inputs": [],
            "options": {"prompt_policy": "lookbook", "instruction": "极简商品广告", "lookbook_search": True},
        }
        with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "responses", "model": "gpt-5.6-sol"}), patch.object(main, "canvas_llm", new=fake_canvas_llm):
            enriched, meta = asyncio.run(main.enrich_lookbook_search(snapshot))

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].web_search_content_types, ["image", "text"])
        self.assertEqual(calls[1].web_search_content_types, [])
        self.assertEqual(meta["search_mode"], "text_fallback")
        self.assertEqual(enriched["options"]["lookbook_visual_system"]["lighting"], "侧光")

    def test_reference_facts_are_analyzed_before_web_case_search(self):
        calls = []

        async def fake_canvas_llm(request):
            calls.append(request)
            if request.web_search:
                return {"text": json.dumps({
                    "sources": [{"publication_or_brand": "Dazed", "case_or_campaign": "street fashion", "url": "https://example.com", "why_relevant": "动态构图"}],
                    "primary_direction": {"name": "动态街头纪实", "reason": "适合现有外套"},
                    "visual_system": {"palette": {"dominant": "炭黑", "accent": "电光绿", "ratios": "70/20/10"}, "environment_and_motion": "行走与前景遮挡"},
                    "shot_recommendations": [{"role": "动作经过", "camera": "低机位跟拍"}],
                    "summary": "具体的街拍方法",
                }, ensure_ascii=False), "web_search": {
                    "used": True,
                    "queries": ["Dazed street fashion movement"],
                    "sources": [{"url": "https://dazed.example/editorial", "title": "Dazed movement editorial"}],
                    "images": [{"image_url": "https://cdn.example/dazed.jpg", "thumbnail_url": "https://cdn.example/dazed-thumb.jpg", "source_website_url": "https://dazed.example/editorial", "caption": "Low-angle walking frame"}],
                }}
            return {"text": '{"face":"清晰面部轮廓","wardrobe":"现有黑色外套","preserve_facts":["保持衣着"]}'}

        snapshot = {
            "operation": "universal",
            "inputs": [{"url": "/assets/input/model.png", "role": "prop", "reference_type": "prop", "lookbook_role": "人物", "label": "人物"}],
            "options": {
                "prompt_policy": "lookbook",
                "instruction": "时尚街景",
                "lookbook_search": True,
                "lookbook_style": {"name": "时尚街景", "prompt": "urban fashion editorial"},
            },
        }
        with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "ecommerce-vision", "model": "gpt-5.6-sol"}), patch.object(main, "canvas_llm", new=fake_canvas_llm):
            analyzed, analysis_meta = asyncio.run(main.enrich_lookbook_reference_analysis(snapshot))
            researched, research_meta = asyncio.run(main.enrich_lookbook_search(analyzed))

        self.assertEqual(len(calls), 2)
        self.assertFalse(calls[0].web_search)
        self.assertTrue(calls[1].web_search)
        self.assertIn("Dazed", calls[1].message)
        self.assertIn("清晰面部轮廓", calls[1].message)
        self.assertEqual(analysis_meta["status"], "succeeded")
        self.assertEqual(research_meta["status"], "succeeded")
        self.assertEqual(research_meta["evidence_status"], "verified")
        self.assertEqual(researched["options"]["lookbook_visual_system"]["palette"]["ratios"], "70/20/10")
        self.assertEqual(researched["options"]["lookbook_research_queries"], ["Dazed street fashion movement"])
        self.assertEqual(researched["options"]["lookbook_research_images"][0]["caption"], "Low-angle walking frame")
        self.assertEqual(researched["options"]["lookbook_research_shots"][0]["camera"], "低机位跟拍")


if __name__ == "__main__":
    unittest.main()
