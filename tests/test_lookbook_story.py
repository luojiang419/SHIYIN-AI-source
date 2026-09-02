import asyncio
import json
import unittest
from unittest.mock import patch

import main
from canvas_core.lookbook_story import (
    LOOKBOOK_MAX_COUNT,
    build_lookbook_shot_prompt,
    enforce_lookbook_shot_scale_contract,
    lookbook_shot_scale_contract,
    normalize_lookbook_shot_cards,
    normalize_ai_lookbook_settings,
    parse_explicit_lookbook_settings,
    parse_lookbook_layout_intent,
    resolve_lookbook_settings,
)


class LookbookStoryContractTests(unittest.TestCase):
    def test_story_agent_plan_adds_story_stages_without_changing_legacy_mode(self):
        legacy = main.build_lookbook_agent_plan({
            "operation": "universal",
            "count": 4,
            "options": {"prompt_policy": "lookbook"},
        })
        self.assertEqual([item["id"] for item in legacy["stages"]], [
            "reference-analysis", "web-search", "art-direction", "generation"
        ])
        story = main.build_lookbook_agent_plan({
            "operation": "universal",
            "count": 20,
            "options": {"prompt_policy": "lookbook", "lookbook_mode": "story-campaign"},
        })
        self.assertEqual(story["mode"], "story-campaign")
        self.assertEqual(story["generation_settings"]["count"], 20)
        self.assertIn("storyboard", [item["id"] for item in story["stages"]])

    def test_explicit_chinese_settings_are_extracted(self):
        parsed = parse_explicit_lookbook_settings(
            "生成二十张16:9、4K、高质量的故事分镜图，模特在雨夜从地铁站走到书店。"
        )
        self.assertEqual(parsed["values"], {
            "count": 20,
            "aspect_ratio": "16:9",
            "resolution": "4k",
            "quality": "high",
        })

    def test_manual_settings_override_brief_and_brief_overrides_node_default(self):
        resolved = resolve_lookbook_settings(
            "生成20张16:9的故事分镜图",
            node_settings={"count": 4, "aspect_ratio": "1:1", "resolution": "2k", "quality": "high"},
        )
        self.assertEqual(resolved["values"]["count"], 20)
        self.assertEqual(resolved["values"]["aspect_ratio"], "16:9")
        self.assertEqual(resolved["sources"]["count"], "brief")
        manual = resolve_lookbook_settings(
            "生成20张16:9的故事分镜图",
            node_settings={"count": 4},
            manual_overrides={"count": 6},
        )
        self.assertEqual(manual["values"]["count"], 6)
        self.assertEqual(manual["sources"]["count"], "manual")

    def test_ai_settings_fill_implicit_requirements_but_never_override_explicit_text(self):
        ai = normalize_ai_lookbook_settings({
            "settings": {"count": 8, "aspect_ratio": "横版", "resolution": "高清", "quality": "premium"},
            "rationale": "完整故事需要足够镜头",
        })
        self.assertEqual(ai["count"], 8)
        self.assertEqual(ai["aspect_ratio"], "16:9")
        self.assertEqual(ai["resolution"], "2k")
        self.assertEqual(ai["quality"], "high")
        resolved = resolve_lookbook_settings("做一套完整的时装故事大片", ai_settings=ai)
        self.assertEqual(resolved["values"]["count"], 8)
        self.assertEqual(resolved["sources"]["count"], "ai")
        explicit = resolve_lookbook_settings("生成20张9:16的4K故事图", ai_settings=ai)
        self.assertEqual(explicit["values"]["count"], 20)
        self.assertEqual(explicit["values"]["aspect_ratio"], "9:16")
        self.assertEqual(explicit["values"]["resolution"], "4k")
        self.assertEqual(explicit["sources"]["count"], "brief")

    def test_story_count_is_bounded_to_twenty(self):
        self.assertEqual(LOOKBOOK_MAX_COUNT, 20)
        with self.assertRaisesRegex(ValueError, "1 到 20"):
            resolve_lookbook_settings("生成21张故事图")

    def test_story_task_snapshot_uses_brief_settings_before_generation(self):
        payload = main.EcommerceTaskRequest(
            operation="universal",
            mode="standard",
            inputs=[],
            options={
                "prompt_policy": "lookbook",
                "lookbook_mode": "story-campaign",
                "instruction": "生成20张16:9、4K的连续故事分镜图",
            },
            provider_id="shiying",
            model="gemini-3-pro-image-preview",
            # 模拟旧前端默认值；brief 应覆盖默认值。
            aspect_ratio="16:9",
            resolution="2k",
            quality="high",
            count=4,
        )
        provider = {"id": "shiying", "name": "shiying", "enabled": True, "image_models": ["gemini-3-pro-image-preview"]}
        with (
            patch.object(main, "configured_ecommerce_providers", return_value=[provider]),
            patch.object(main, "validate_ecommerce_local_inputs", return_value=([], (1024, 1024))),
        ):
            snapshot = main.prepare_ecommerce_request(payload)
        self.assertEqual(snapshot["count"], 20)
        self.assertEqual(snapshot["aspect_ratio"], "16:9")
        self.assertEqual(snapshot["resolution"], "4k")
        self.assertEqual(snapshot["options"]["lookbook_brief_parse"]["sources"]["count"], "brief")
        self.assertTrue(snapshot["options"]["lookbook_search"])
        self.assertEqual(snapshot["options"]["lookbook_layout_intent"]["mode"], "single-frame")

    def test_shot_cards_require_exact_order_and_continuity(self):
        cards = [
            {
                "index": 1,
                "beat": "开场",
                "story_purpose": "建立空间",
                "continuity_in": "故事开始",
                "continuity_out": "人物走向右侧",
            },
            {
                "index": 2,
                "beat": "发展",
                "story_purpose": "推进动作",
                "continuity_in": "接上人物走向右侧",
                "continuity_out": "人物停在门口",
            },
        ]
        normalized = normalize_lookbook_shot_cards(cards, 2)
        self.assertEqual([item["index"] for item in normalized], [1, 2])
        with self.assertRaisesRegex(ValueError, "数量不一致"):
            normalize_lookbook_shot_cards(cards[:1], 2)

    def test_shot_prompt_contains_single_frame_and_continuity_locks(self):
        prompt = build_lookbook_shot_prompt(
            "一个人在雨夜去书店",
            {"wardrobe": "黑色风衣"},
            {
                "index": 3,
                "beat": "转折",
                "story_purpose": "听见朋友呼喊后回头",
                "continuity_in": "右手仍持纸袋",
                "continuity_out": "视线转向街角",
            },
            ["人物·model.png", "场景·street.png"],
        )
        self.assertIn("exactly one standalone full-bleed", prompt)
        self.assertIn("story frame 3", prompt)
        self.assertIn("CONTINUITY RULE", prompt)
        self.assertIn("人物·model.png", prompt)

    def test_six_frame_story_uses_only_one_environmental_wide_and_forces_close_variation(self):
        plan = lookbook_shot_scale_contract(6)
        self.assertEqual(len(plan), 6)
        self.assertIn("wide establishing", plan[0]["shot_size"])
        self.assertNotIn("wide", plan[1]["shot_size"])
        self.assertIn("waist-up", plan[3]["shot_size"])
        self.assertIn("tight action close-up", plan[4]["shot_size"])
        self.assertIn("medium hero", plan[5]["shot_size"])

    def test_shot_scale_contract_overrides_ai_wide_repetition_and_reaches_final_prompt(self):
        cards = [
            {"index": index, "beat": "发展", "story_purpose": "推进", "continuity_in": "承接", "continuity_out": "继续", "camera": {"shot_size": "wide full body"}}
            for index in range(1, 7)
        ]
        enforced = enforce_lookbook_shot_scale_contract(cards, 6)
        self.assertIn("tight action close-up", enforced[4]["camera"]["shot_size"])
        prompt = build_lookbook_shot_prompt("两个女牛仔跳舞", {}, enforced[4])
        self.assertIn("MANDATORY SHOT-SCALE LOCK", prompt)
        self.assertIn("never owns the original camera position", prompt)

    def test_layout_requires_explicit_user_intent_and_negation_stays_single_frame(self):
        self.assertFalse(parse_lookbook_layout_intent("生成四张连续故事大片")['explicit'])
        self.assertFalse(parse_lookbook_layout_intent("生成四张图片，不要拼图或九宫格")['explicit'])
        intent = parse_lookbook_layout_intent("请生成一张4宫格杂志排版拼图，四格要有统一故事")
        self.assertTrue(intent['explicit'])
        self.assertEqual(intent['mode'], 'editorial-layout')

    def test_shot_prompt_authorizes_only_requested_editorial_layout(self):
        layout_prompt = build_lookbook_shot_prompt(
            "请生成一张4宫格杂志排版拼图，展示一段城市故事",
            {"palette": "黑白与红色"},
            {"index": 1, "beat": "开场", "story_purpose": "建立人物目标", "continuity_in": "故事开始", "continuity_out": "走向街角"},
        )
        self.assertIn("EDITORIAL-LAYOUT AUTHORIZATION", layout_prompt)
        self.assertIn("top-tier fashion magazine", layout_prompt)
        self.assertNotIn("SINGLE-FRAME HARD STOP", layout_prompt)

    def test_scene_styled_story_forbids_reference_interview_clothes(self):
        prompt = build_lookbook_shot_prompt(
            "为两个女牛仔重新设计经典蓝色牛仔套装",
            {"wardrobe": "classic blue tailored denim cowgirl suits"},
            {"index": 1, "beat": "开场", "story_purpose": "进入舞池", "continuity_in": "开始", "continuity_out": "准备solo"},
            ["人物1", "人物2", "场景"],
            wardrobe_mode="scene_styled",
        )
        self.assertIn("IDENTITY-ONLY WARDROBE OVERRIDE", prompt)
        self.assertIn("photographed clothing is interview/source clothing and is forbidden", prompt)
        self.assertNotIn("preserve the wardrobe and accessories visible", prompt)

    def test_storyboard_ai_response_must_return_exact_count(self):
        cards = [
            {
                "index": index,
                "beat": "开场" if index == 1 else "收束" if index == 2 else "发展",
                "story_purpose": f"推进第{index}个画面",
                "continuity_in": "承接上一画面",
                "continuity_out": "交给下一画面",
            }
            for index in range(1, 3)
        ]

        async def fake_canvas_llm(_request):
            return {"text": json.dumps({
                "logline": "雨夜走向书店",
                "campaign_bible": {"wardrobe": "黑色风衣", "continuity_locks": ["保持左手纸袋"]},
                "shot_cards": cards,
            }, ensure_ascii=False)}

        snapshot = {
            "operation": "universal",
            "count": 2,
            "aspect_ratio": "16:9",
            "resolution": "2k",
            "quality": "high",
            "inputs": [],
            "options": {
                "prompt_policy": "lookbook",
                "lookbook_mode": "story-campaign",
                "instruction": "生成两张连续故事图",
            },
            "prompt": "base",
        }
        with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vision-model"}), patch.object(main, "canvas_llm", new=fake_canvas_llm):
            enriched, meta = asyncio.run(main.enrich_lookbook_storyboard(snapshot))
        self.assertEqual(meta["status"], "succeeded")
        self.assertEqual(len(enriched["options"]["lookbook_shot_cards"]), 2)
        self.assertEqual(enriched["options"]["lookbook_bible"]["wardrobe"], "黑色风衣")

    def test_ai_brief_parser_chooses_settings_for_natural_language_without_fixed_keywords(self):
        async def fake_canvas_llm(_request):
            return {"text": json.dumps({
                "settings": {
                    "count": 8,
                    "aspect_ratio": "社媒竖版",
                    "resolution": "超清",
                    "quality": "高质量",
                    "delivery_type": "fashion-story",
                },
                "rationale": "需求是完整的社交媒体时装故事，需要多镜头竖版组图",
                "confidence": 0.92,
            }, ensure_ascii=False)}

        snapshot = {
            "operation": "universal",
            "count": 4,
            "aspect_ratio": "16:9",
            "resolution": "2k",
            "quality": "high",
            "mode": "standard",
            "source_dimensions": {"width": 1024, "height": 1024},
            "inputs": [],
            "options": {
                "prompt_policy": "lookbook",
                "lookbook_mode": "story-campaign",
                "instruction": "做一套适合社交媒体发布的完整时装故事大片",
            },
            "prompt": "base",
        }
        with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vision-model"}), patch.object(main, "canvas_llm", new=fake_canvas_llm):
            enriched, meta = asyncio.run(main.enrich_lookbook_brief_settings(snapshot))
        self.assertEqual(meta["status"], "succeeded")
        self.assertEqual(enriched["count"], 8)
        self.assertEqual(enriched["aspect_ratio"], "9:16")
        self.assertEqual(enriched["resolution"], "4k")
        self.assertEqual(enriched["options"]["lookbook_brief_parse"]["sources"]["count"], "ai")

    def test_ai_brief_parser_cannot_override_explicit_user_parameters(self):
        async def fake_canvas_llm(_request):
            return {"text": '{"settings":{"count":8,"aspect_ratio":"9:16","resolution":"2k","quality":"medium"}}'}

        snapshot = {
            "operation": "universal", "count": 4, "aspect_ratio": "16:9", "resolution": "2k", "quality": "high",
            "mode": "standard", "source_dimensions": {"width": 1024, "height": 1024}, "inputs": [], "prompt": "base",
            "options": {"prompt_policy": "lookbook", "lookbook_mode": "story-campaign", "instruction": "生成12张16:9、4K的故事图"},
        }
        with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vision-model"}), patch.object(main, "canvas_llm", new=fake_canvas_llm):
            enriched, _meta = asyncio.run(main.enrich_lookbook_brief_settings(snapshot))
        self.assertEqual(enriched["count"], 12)
        self.assertEqual(enriched["aspect_ratio"], "16:9")
        self.assertEqual(enriched["resolution"], "4k")
        self.assertEqual(enriched["options"]["lookbook_brief_parse"]["sources"]["count"], "brief")

    def test_story_generation_uses_one_request_per_shot_and_restores_order(self):
        calls = []

        async def fake_batch(**kwargs):
            calls.append(kwargs)
            frame = int(kwargs["prompt"].split("story frame ", 1)[1].split(";", 1)[0])
            await asyncio.sleep(0.01 * (4 - frame))
            return {
                "provider": {"id": "vision", "name": "Vision"},
                "model": "vision-model",
                "images": [f"/assets/frame-{frame}.png"],
                "image_items": [{"url": f"/assets/frame-{frame}.png"}],
                "raw": {},
            }

        cards = [
            {"index": index, "beat": "发展", "story_purpose": "推进", "continuity_in": "承接", "continuity_out": "继续"}
            for index in range(1, 4)
        ]
        snapshot = {
            "count": 3,
            "size": "1920x1080",
            "quality": "high",
            "inputs": [],
            "options": {
                "prompt_policy": "lookbook",
                "lookbook_mode": "story-campaign",
                "instruction": "连续故事",
                "lookbook_bible": {"wardrobe": "黑色风衣"},
                "lookbook_shot_cards": cards,
            },
        }
        with patch.object(main, "lookbook_generation_prompts", side_effect=lambda value: [f"story frame {index};" for index in range(1, 4)]), patch.object(main, "execute_ai_image_batch", new=fake_batch):
            batch = asyncio.run(main.execute_lookbook_story_batch(snapshot, {"provider_id": "vision", "model": "vision-model"}))
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call["count"] == 1 for call in calls))
        self.assertEqual(batch["images"], ["/assets/frame-1.png", "/assets/frame-2.png", "/assets/frame-3.png"])
        self.assertEqual([item["shot_index"] for item in batch["image_items"]], [1, 2, 3])
        self.assertEqual(batch["provider"]["id"], "vision")

    def test_scene_reference_zoom_tracks_mandatory_shot_scale(self):
        self.assertEqual(main.lookbook_scene_zoom_for_card({"camera": {"shot_size": "35mm environmental wide establishing shot"}}), 1.0)
        self.assertEqual(main.lookbook_scene_zoom_for_card({"camera": {"shot_size": "50mm medium-full action shot, knees-to-head"}}), 1.25)
        self.assertEqual(main.lookbook_scene_zoom_for_card({"camera": {"shot_size": "85mm tight action close-up, chest-up with hands entering frame"}}), 1.9)
        self.assertEqual(main.lookbook_scene_zoom_for_card({"camera": {"shot_size": "50mm low-angle medium hero two-shot, knees-up"}}), 1.5)


if __name__ == "__main__":
    unittest.main()
