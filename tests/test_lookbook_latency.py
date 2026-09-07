import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

import main


def snapshot(**options):
    return {
        "operation": "universal", "mode": "standard", "count": 2, "aspect_ratio": "16:9",
        "resolution": "2k", "quality": "high", "size": "2048x1152", "parameters": {},
        "inputs": [], "prompt": "base",
        "options": {"prompt_policy": "lookbook", "lookbook_mode": "story-campaign",
                    "instruction": "两张连续广告", "lookbook_style": {"id": "standard-advertising", "prompt": "style-lock-token"}, **options},
    }


class LookbookLatencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_analysis_merges_only_reference_facts_and_skips_separate_plan(self):
        entered = asyncio.Event()

        async def reference(value):
            entered.set()
            value["options"]["lookbook_reference_analysis"] = "visible-scene-facts"
            return value, {"status": "succeeded"}

        async def brief(value):
            await asyncio.wait_for(entered.wait(), 1)
            value.update(count=9, aspect_ratio="9:16")
            value["options"]["lookbook_count"] = 9
            value["options"]["lookbook_layout_intent"] = {"explicit": True}
            return value, {"status": "succeeded"}

        async def storyboard(value):
            self.assertEqual(value["count"], 9)
            self.assertEqual(value["aspect_ratio"], "9:16")
            self.assertEqual(value["options"]["lookbook_count"], 9)
            self.assertTrue(value["options"]["lookbook_layout_intent"]["explicit"])
            self.assertEqual(value["options"]["lookbook_reference_analysis"], "visible-scene-facts")
            return value, {"status": "succeeded"}

        original = snapshot()
        with patch.object(main, "enrich_lookbook_brief_settings", new=brief), patch.object(main, "enrich_lookbook_reference_analysis", new=reference), patch.object(main, "enrich_lookbook_plan", new_callable=AsyncMock) as plan, patch.object(main, "enrich_lookbook_storyboard", new=storyboard), patch.object(main, "canvas_llm", new_callable=AsyncMock) as llm:
            result, meta = await main.prepare_lookbook_creation(original)
        plan.assert_not_awaited()
        llm.assert_not_awaited()
        self.assertEqual(original, snapshot())
        self.assertEqual(meta["lookbook_research"]["status"], "disabled")
        self.assertEqual(set(result["lookbook_stage_timings"]), {"brief-parse", "reference-analysis", "web-search", "storyboard", "preparation"})

    async def test_brief_failure_cancels_pending_reference_analysis(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()

        async def reference(value):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def brief(value):
            await entered.wait()
            return value, {"status": "failed", "reason": "bad brief"}

        with patch.object(main, "enrich_lookbook_brief_settings", new=brief), patch.object(main, "enrich_lookbook_reference_analysis", new=reference):
            result, meta = await asyncio.wait_for(main.prepare_lookbook_creation(snapshot()), 1)
        self.assertTrue(cancelled.is_set())
        self.assertEqual(meta["failed_stage"], "brief-parse")
        self.assertEqual(result["lookbook_stage_timings"]["reference-analysis"]["status"], "cancelled")

    async def test_cancelling_preparation_cleans_both_children(self):
        entered, cancelled = [], []

        async def waiting(value):
            entered.append(True)
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)

        with patch.object(main, "enrich_lookbook_brief_settings", new=waiting), patch.object(main, "enrich_lookbook_reference_analysis", new=waiting):
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(main.prepare_lookbook_creation(snapshot()), .05)
        self.assertEqual(len(entered), 2)
        self.assertEqual(len(cancelled), 2)

    async def test_auto_style_still_selects_style_before_storyboard(self):
        order = []

        async def passthrough(value):
            return value, {"status": "succeeded"}

        async def plan(value):
            order.append("plan")
            value["options"]["lookbook_auto_decision"] = {"selected_style_id": "levis-adaptive-campaign"}
            return value, {"status": "succeeded"}

        async def story(value):
            order.append("story")
            self.assertEqual(value["options"]["lookbook_auto_decision"]["selected_style_id"], "levis-adaptive-campaign")
            return value, {"status": "succeeded"}

        with patch.object(main, "enrich_lookbook_brief_settings", new=passthrough), patch.object(main, "enrich_lookbook_reference_analysis", new=passthrough), patch.object(main, "enrich_lookbook_plan", new=plan), patch.object(main, "enrich_lookbook_storyboard", new=story):
            await main.prepare_lookbook_creation(snapshot(lookbook_style={"id": "auto"}))
        self.assertEqual(order, ["plan", "story"])

    async def test_search_shared_deadline_cancels_fallback_and_preserves_snapshot(self):
        calls, cancelled = [], asyncio.Event()

        async def llm(request):
            calls.append(request)
            if len(calls) == 1:
                self.assertEqual(request.web_search_content_types, ["text"])
                self.assertEqual(request.retry_524, 0)
                await asyncio.sleep(.01)
                raise main.HTTPException(400, "unsupported options")
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        value = snapshot(lookbook_search=True)
        with patch.object(main, "LOOKBOOK_SEARCH_TIMEOUT_SECONDS", .05), patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vision"}), patch.object(main, "canvas_llm", new=llm):
            result, meta = await main.enrich_lookbook_search(value)
        self.assertEqual(result, value)
        self.assertEqual(meta["status"], "skipped")
        self.assertTrue(cancelled.is_set())
        self.assertEqual(len(calls), 2)

    async def test_search_without_tool_evidence_does_not_inject_claimed_research(self):
        value = snapshot(lookbook_search=True)
        with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vision"}), patch.object(main, "canvas_llm", new=AsyncMock(return_value={"text": '{"summary":"unverified claims"}', "web_search": {"used": False}})):
            result, meta = await main.enrich_lookbook_search(value)
        self.assertEqual(meta["status"], "skipped")
        self.assertEqual(result, value)

    async def test_integrated_storyboard_keeps_style_and_art_direction(self):
        async def llm(request):
            self.assertFalse(request.web_search)
            for text in ["style-lock-token", "色板与比例", "面料和产品材质", "scene_region", "continuity_in", "story_purpose"]:
                self.assertIn(text, request.message)
            return {"text": json.dumps({"logline": "story", "campaign_bible": {"palette": "cyan", "wardrobe": "original"}, "shot_cards": [
                {"index": i, "beat": "action", "story_purpose": "advance", "continuity_in": "start", "continuity_out": "next"}
                for i in (1, 2)]})}

        with patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vision"}), patch.object(main, "canvas_llm", new=llm):
            result, meta = await main.enrich_lookbook_storyboard(snapshot())
        self.assertEqual(meta["status"], "succeeded")
        self.assertIn("cyan", result["options"]["lookbook_plan"])
        self.assertEqual(len(main.lookbook_generation_prompts(result)), 2)

    async def test_quality_is_off_by_default(self):
        batch = {"images": ["original"]}
        with patch.object(main, "analyze_lookbook_outputs", new_callable=AsyncMock) as check:
            result, meta = await main.improve_lookbook_batch(batch, snapshot(), {})
        self.assertIs(result, batch)
        self.assertIsNone(meta)
        check.assert_not_awaited()

    async def test_task_default_delivers_without_quality_or_second_generation(self):
        value = snapshot()
        value["route_candidates"] = [{"provider_id": "test", "model": "test"}]
        batch = {"provider": {"id": "test", "name": "Test"}, "model": "test", "images": ["one", "two"],
                 "image_items": [], "raw": {}, "generation_started_at": 1, "generation_completed_at": 2,
                 "generation_elapsed_seconds": 1}
        updates = {}

        async def passthrough(current):
            return current, None

        async def studio(current, _snapshot, _route):
            return current

        with patch.object(main, "update_ecommerce_task", side_effect=lambda _id, update: updates.update(update)), patch.object(main, "prepare_lookbook_creation", new=AsyncMock(return_value=(value, {}))), patch.object(main, "enrich_ecommerce_snapshot_with_garment_analysis", new=passthrough), patch.object(main, "enrich_ecommerce_snapshot_with_universal_analysis", new=passthrough), patch.object(main, "execute_lookbook_story_batch", new=AsyncMock(return_value=batch)) as generate, patch.object(main, "lookbook_generation_prompts", return_value=["one", "two"]), patch.object(main, "improve_lookbook_batch", new_callable=AsyncMock) as check, patch.object(main, "apply_lookbook_film_finish", side_effect=lambda current, _snapshot: current), patch.object(main, "apply_selected_studio_background", new=studio), patch.object(main, "save_to_history"), patch.object(main, "GLOBAL_LOOP", None):
            await main.execute_ecommerce_task("fixture", value)
        generate.assert_awaited_once()
        check.assert_not_awaited()
        self.assertEqual(updates["status"], "succeeded", updates.get("error"))
        self.assertIsNone(updates["result"]["lookbook_quality"])
        self.assertEqual(updates["result"]["images"], ["one", "two"])
        self.assertIn("未启用质检", updates["progress_status"])
        self.assertEqual(updates["lookbook_stage_timings"]["generation"]["elapsed_seconds"], 1)

    async def test_check_only_and_zero_retries_never_generate(self):
        failed = {"status": "succeeded", "passed": False, "weak_indices": [0]}
        for opts in ({}, {"lookbook_auto_repair": True, "lookbook_max_retries": 0}):
            with self.subTest(opts=opts), patch.object(main, "analyze_lookbook_outputs", new=AsyncMock(return_value=failed)), patch.object(main, "execute_ai_image_batch", new_callable=AsyncMock) as generate:
                batch, quality = await main.improve_lookbook_batch({"images": ["original"]}, snapshot(lookbook_quality_gate=True, **opts), {})
                generate.assert_not_awaited()
                self.assertEqual(batch["images"], ["original"])
                self.assertFalse(quality["passed"])

    async def test_quality_timeout_delivers_original_images(self):
        cancelled = asyncio.Event()

        async def llm(_request):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with patch.object(main, "LOOKBOOK_QUALITY_TIMEOUT_SECONDS", .02), patch.object(main, "configured_ecommerce_vision_route", return_value={"provider_id": "vision", "model": "vision"}), patch.object(main, "canvas_llm", new=llm), patch.object(main, "execute_ai_image_batch", new_callable=AsyncMock) as generate:
            batch, quality = await main.improve_lookbook_batch({"images": ["original"]}, snapshot(lookbook_quality_gate=True, lookbook_auto_repair=True), {})
        generate.assert_not_awaited()
        self.assertTrue(cancelled.is_set())
        self.assertEqual(batch["images"], ["original"])
        self.assertIn("质检未完成", main.lookbook_completion_message(quality))

    async def test_repair_failure_retains_original_and_does_not_escape(self):
        failed = {"status": "succeeded", "passed": False, "weak_indices": [0]}
        with patch.object(main, "analyze_lookbook_outputs", new=AsyncMock(return_value=failed)) as check, patch.object(main, "execute_ai_image_batch", new=AsyncMock(side_effect=main.HTTPException(502, "upstream failed"))):
            batch, quality = await main.improve_lookbook_batch({"images": ["original"]}, snapshot(lookbook_quality_gate=True, lookbook_auto_repair=True), {"provider_id": "test", "model": "test"})
        self.assertEqual(batch["images"], ["original"])
        self.assertFalse(quality["retries"][0]["replaced"])
        self.assertEqual(check.await_count, 1)
        self.assertIn("质检未达标", main.lookbook_completion_message(quality))

    async def test_explicit_repair_rechecks_and_keeps_new_image_when_recheck_fails(self):
        initial = {"status": "succeeded", "passed": False, "weak_indices": [0]}
        with patch.object(main, "analyze_lookbook_outputs", new=AsyncMock(side_effect=[initial, {"status": "failed"}])), patch.object(main, "execute_ai_image_batch", new=AsyncMock(return_value={"images": ["repaired"]})):
            batch, quality = await main.improve_lookbook_batch({"images": ["original"]}, snapshot(lookbook_quality_gate=True, lookbook_auto_repair=True), {"provider_id": "test", "model": "test"})
        self.assertEqual(batch["images"], ["repaired"])
        self.assertFalse(quality["passed"])
        self.assertIn("质检未完成", main.lookbook_completion_message(quality))

    def test_completion_message_does_not_claim_unperformed_or_failed_checks_passed(self):
        self.assertIn("未启用质检", main.lookbook_completion_message(None))
        self.assertIn("质检通过", main.lookbook_completion_message({"final": {"status": "succeeded", "passed": True}}))
