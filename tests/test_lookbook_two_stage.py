import asyncio
import copy
import json
import unittest
from unittest.mock import AsyncMock, patch

import main
from canvas_core.lookbook_brief import normalize_story, STORY_VERSION


def fixture(count=3, reference_count=1, instruction="", **options):
    return {"operation": "universal", "mode": "standard", "count": count, "aspect_ratio": "3:4",
            "resolution": "2k", "quality": "high", "size": "1536x2048", "parameters": {}, "prompt": "base",
            "inputs": [{"url": f"/assets/input/ref-{i}.png", "reference_type": "subject", "lookbook_role": "人物", "label": f"R{i}"} for i in range(1, reference_count+1)],
            "options": {"lookbook_bold_editorial": False, "prompt_policy": "lookbook", "lookbook_mode": "story-campaign", "instruction": instruction,
                        "lookbook_style": {"id": "standard-advertising", "prompt": "selected-style"}, **options}}


def story_response(refs=1, count=3):
    return {"title": "并肩赴约", "story": "她在门口等同伴，随后沿台阶走下。对方在街角停步等她跟上，两人由前后错落转为并肩同行。",
            "intent": "从等待到同行的松弛情绪，让穿着和人物的生活自然连接。",
            "wardrobe": {"target": "原有完整造型", "visible_features": ["露腰系带上衣与独立半裙", "黑上衣与牛仔裤"], "coverage": ["步行中的垂坠", "转身的侧背剪裁"]},
            "reference_facts": [{"reference_index": i, "facts": "白色露腰系带衣物", "preserve": "身份与可见服装结构", "not_locked": "原图姿态、机位和背景"} for i in range(1, refs+1)],
            "creative_extensions": ["相邻街角为创作空间"],
            "beats": [{"event": "门口等待后同行", "motivation": "等同伴一起赴约", "garment_value": "走动展示廓形"}],
            "camera_intent": "侧面、侧后和低位交替，真实位置变化展示穿着，不以变焦替换机位。",
            "settings": {"count": count, "aspect_ratio": "3:4", "resolution": "2k", "quality": "high"},
            "auto_decision": {"selected_style_id": "levis-adaptive-campaign", "rationale": "自然穿着"}}


def shots_response(count=3):
    return {"logline": "原故事的自然穿着", "campaign_bible": {"wardrobe": "两件式，腰部开口", "palette": "cyan"},
            "shot_cards": [{"index": i, "beat": f"同行{i}", "story_purpose": "展示自然穿着", "continuity_in": "等待", "continuity_out": "同行",
                            "wardrobe_focus": "衣料垂坠与侧背廓形", "wardrobe_visibility": "前景不遮挡衣服", "camera": {"shot_size": "侧背中景", "angle": "低位",
                            "position": f"台阶第{i}处侧后观察", "visible_geometry": f"背景第{i}面墙；可见侧背"}} for i in range(1, count+1)]}


class TwoStageLookbookTests(unittest.IsolatedAsyncioTestCase):
    def route(self):
        return patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vision"})

    async def test_two_independent_calls_keep_all_images_and_wardrobe_camera_decisions(self):
        source = fixture(reference_count=14)
        original = copy.deepcopy(source)
        requests = []

        async def llm(request):
            requests.append(request)
            self.assertEqual(len(request.images), 14)
            self.assertEqual(request.messages, [])
            self.assertFalse(request.web_search)
            if len(requests) == 1:
                self.assertIn("服装", request.system_prompt)
                return {"text": json.dumps(story_response(14), ensure_ascii=False)}
            self.assertIn("并肩赴约", request.system_prompt)
            self.assertIn("WARDROBE-FIRST", request.system_prompt)
            self.assertIn("visible_geometry", request.message)
            self.assertNotIn("后端强制契约", request.message)
            return {"text": json.dumps(shots_response())}

        with self.route(), patch.object(main, "canvas_llm", side_effect=llm):
            result, meta = await main.prepare_lookbook_creation(source)
        self.assertNotIn("failed_stage", meta)
        self.assertEqual(len(requests), 2)
        self.assertEqual(source, original)
        self.assertEqual(result["options"]["instruction"], "")
        self.assertEqual(result["options"]["lookbook_shot_cards"][0]["camera"]["shot_size"], "侧背中景")
        prompts = main.lookbook_generation_prompts(result)
        self.assertIn("并肩赴约", prompts[0])
        self.assertIn("衣料垂坠", prompts[0])
        self.assertIn("台阶第1处", prompts[0])
        self.assertNotIn("RHYTHM LOCK", prompts[0])
        self.assertEqual(set(result["lookbook_stage_timings"]), {"story-writing", "web-search", "storyboard", "preparation"})

    async def test_story_is_persisted_before_second_call_and_retained_on_failure(self):
        updates = []
        calls = 0

        async def llm(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"text": json.dumps(story_response())}
            stored = [item for item in updates if item.get("options", {}).get("lookbook_story")]
            self.assertTrue(stored, "故事必须在第二次请求之前写入任务")
            self.assertIn(stored[-1]["options"]["lookbook_story"]["ad_brief"], request.system_prompt)
            raise RuntimeError("second-stage failure")

        with self.route(), patch.object(main, "canvas_llm", side_effect=llm), patch.object(main, "update_ecommerce_task", side_effect=lambda _id, item: updates.append(copy.deepcopy(item))):
            result, meta = await main.prepare_lookbook_creation(fixture(), "test-task")
        self.assertEqual(meta["failed_stage"], "storyboard")
        self.assertIn("并肩赴约", result["options"]["lookbook_story"]["ad_brief"])
        self.assertEqual(calls, 2)

    async def test_bad_story_stops_before_storyboard(self):
        bad = story_response()
        bad["beats"][0].pop("garment_value")
        with self.route(), patch.object(main, "canvas_llm", new=AsyncMock(return_value={"text": json.dumps(bad)})) as llm, patch.object(main, "enrich_lookbook_storyboard", new_callable=AsyncMock) as storyboard:
            result, meta = await main.prepare_lookbook_creation(fixture())
        self.assertEqual(meta["failed_stage"], "story-writing")
        storyboard.assert_not_awaited()
        llm.assert_awaited_once()
        self.assertNotIn("lookbook_story", result["options"])

    async def test_missing_reference_fact_and_reference_overflow_stop_safely(self):
        for refs in (2, 21):
            with self.subTest(refs=refs), self.route(), patch.object(main, "canvas_llm", new=AsyncMock(return_value={"text": json.dumps(story_response())})) as llm:
                _, meta = await main.prepare_lookbook_creation(fixture(reference_count=refs))
                self.assertEqual(meta["failed_stage"], "story-writing")
                self.assertEqual(llm.await_count, 0 if refs == 21 else 1)

    async def test_user_quantity_wins_over_first_stage_suggestion(self):
        with self.route(), patch.object(main, "canvas_llm", new=AsyncMock(side_effect=[{"text": json.dumps(story_response(count=8))}, {"text": json.dumps(shots_response(12))}])) as llm:
            result, meta = await main.prepare_lookbook_creation(fixture(instruction="生成12张16:9、4K的自然穿着Lookbook"))
        self.assertNotIn("failed_stage", meta)
        self.assertEqual(result["count"], 12)
        self.assertEqual(result["aspect_ratio"], "16:9")
        self.assertEqual(result["resolution"], "4k")
        self.assertEqual(llm.await_count, 2)

    async def test_auto_style_is_selected_in_first_call_without_separate_plan(self):
        with self.route(), patch.object(main, "canvas_llm", new=AsyncMock(side_effect=[{"text": json.dumps(story_response())}, {"text": json.dumps(shots_response())}])) as llm, patch.object(main, "enrich_lookbook_plan", new_callable=AsyncMock) as separate:
            result, meta = await main.prepare_lookbook_creation(fixture(lookbook_style={"id": "auto"}))
        self.assertNotIn("failed_stage", meta)
        separate.assert_not_awaited()
        self.assertEqual(llm.await_count, 2)
        self.assertEqual(result["options"]["lookbook_auto_decision"]["selected_style_id"], "levis-adaptive-campaign")

    async def test_cached_story_and_shots_reuse_without_new_llm_then_changed_input_invalidates(self):
        with self.route(), patch.object(main, "canvas_llm", new=AsyncMock(side_effect=[{"text": json.dumps(story_response())}, {"text": json.dumps(shots_response())}])):
            result, _ = await main.prepare_lookbook_creation(fixture())
        checked, invalid = main.invalidate_stale_lookbook_context(result)
        self.assertFalse(invalid)
        with self.route(), patch.object(main, "canvas_llm", new_callable=AsyncMock) as llm:
            reused, meta = await main.prepare_lookbook_creation(checked)
        llm.assert_not_awaited()
        self.assertEqual(meta["lookbook_story"]["status"], "provided")
        reused["inputs"][0]["url"] = "/assets/input/new.png"
        reset, invalid = main.invalidate_stale_lookbook_context(reused)
        self.assertTrue(invalid)
        self.assertNotIn("lookbook_story", reset["options"])
        self.assertNotIn("lookbook_shot_cards", reset["options"])

    async def test_cancelling_story_does_not_start_second_stage(self):
        cancelled = asyncio.Event()

        async def llm(_):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with self.route(), patch.object(main, "canvas_llm", side_effect=llm), patch.object(main, "enrich_lookbook_storyboard", new_callable=AsyncMock) as second:
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(main.prepare_lookbook_creation(fixture()), .03)
        self.assertTrue(cancelled.is_set())
        second.assert_not_awaited()

    async def test_same_physical_position_is_not_accepted_as_multiple_viewpoints(self):
        shots = shots_response()
        for shot in shots["shot_cards"]:
            shot["camera"]["position"] = "同一扇门正面"
        with self.route(), patch.object(main, "canvas_llm", new=AsyncMock(side_effect=[{"text": json.dumps(story_response())}, {"text": json.dumps(shots)}, {"text": json.dumps(shots)}])):
            result, meta = await main.prepare_lookbook_creation(fixture())
        self.assertEqual(meta["failed_stage"], "storyboard")
        self.assertIn("重复同一机位", meta["lookbook_storyboard"]["reason"])
        self.assertNotIn("lookbook_shot_cards", result["options"])

    async def test_full_director_grid_also_inherits_story_and_wardrobe_fields(self):
        from tests.test_fashion_director import plan as director_plan
        data = director_plan(outputs=1, panels=4)
        for index, shot in enumerate(data["shot_cards"][0]["panel_cards"], 1):
            shot.update(wardrobe_focus="裤腿量感", wardrobe_visibility="从腰线到裤脚完整可见")
            shot["action_chain"] = ["低头触碰衣料", "侧身倚墙抬眼", "坐下舒展手臂", "近景回眸微笑"][index-1]
            shot["camera"].update(position=f"实际摄影师位置{index}", visible_geometry="可见侧背和不同背景面")
        source = fixture(count=1, lookbook_style={"id": "fashion-advertising"}, lookbook_layout_selection={"preset_id": "grid-2x2"})
        with self.route(), patch.object(main, "canvas_llm", new=AsyncMock(side_effect=[{"text": json.dumps(story_response(count=1))}, {"text": json.dumps(data)}])) as llm:
            result, meta = await main.prepare_lookbook_creation(source)
        self.assertNotIn("failed_stage", meta)
        self.assertEqual(llm.await_count, 2)
        prompts = main.lookbook_generation_prompts(result)
        self.assertEqual(len(prompts), 1)
        self.assertIn("PANEL 4", prompts[0])
        self.assertIn("WARDROBE-FIRST", prompts[0])

    async def test_task_does_not_submit_images_after_story_failure(self):
        source = fixture()
        source["route_candidates"] = [{"provider_id": "test", "model": "test"}]
        updates = {}
        with self.route(), patch.object(main, "canvas_llm", new=AsyncMock(return_value={"text": '{}'})), patch.object(main, "update_ecommerce_task", side_effect=lambda _id, data: updates.update(data)), patch.object(main, "execute_lookbook_story_batch", new_callable=AsyncMock) as generate:
            await main.execute_ecommerce_task("test", source)
        generate.assert_not_awaited()
        self.assertEqual(updates["status"], "failed")
        self.assertIn("title", updates["error"])


if __name__ == "__main__":
    unittest.main()
