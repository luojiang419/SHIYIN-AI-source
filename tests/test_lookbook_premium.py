import asyncio
import json
import unittest
from unittest.mock import patch

import main
from canvas_core.ecommerce import build_prompt


class LookbookPremiumResearchTests(unittest.TestCase):
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

    def test_structured_research_is_normalized_for_generation(self):
        value = main.normalize_lookbook_visual_research(json.dumps({
            "sources": [{"publication_or_brand": "Vogue", "case_or_campaign": "Street editorial", "url": "https://example.com", "why_relevant": "色彩"}],
            "visual_system": {
                "palette": {"dominant": "墨黑", "secondary": "骨白", "accent": "钴蓝", "ratios": "65/25/10", "contrast": "高对比", "light_color": "冷日光"},
                "color_grade": "冷暖分离",
                "anti_generic_rules": ["拒绝白底棚拍"],
            },
            "transferable_methods": ["用城市反射制造层次"],
            "summary": "色彩明确",
        }, ensure_ascii=False))
        self.assertEqual(value["sources"][0]["publication_or_brand"], "Vogue")
        self.assertEqual(value["visual_system"]["palette"]["ratios"], "65/25/10")
        self.assertEqual(value["visual_system"]["anti_generic_rules"], ["拒绝白底棚拍"])

    def test_reference_facts_are_analyzed_before_web_case_search(self):
        calls = []

        async def fake_canvas_llm(request):
            calls.append(request)
            if request.web_search:
                return {"text": json.dumps({
                    "sources": [{"publication_or_brand": "Dazed", "case_or_campaign": "street fashion", "url": "https://example.com", "why_relevant": "动态构图"}],
                    "visual_system": {"palette": {"dominant": "炭黑", "accent": "电光绿", "ratios": "70/20/10"}, "environment_and_motion": "行走与前景遮挡"},
                    "summary": "具体的街拍方法",
                }, ensure_ascii=False)}
            return {"text": '{"face":"清晰面部轮廓","wardrobe":"现有黑色外套","preserve_facts":["保持衣着"]}'}

        snapshot = {
            "operation": "universal",
            "inputs": [{"url": "/assets/input/model.png", "role": "prop", "reference_type": "prop", "lookbook_role": "人物", "label": "人物"}],
            "options": {
                "prompt_policy": "lookbook",
                "instruction": "时尚街景",
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
        self.assertEqual(researched["options"]["lookbook_visual_system"]["palette"]["ratios"], "70/20/10")


if __name__ == "__main__":
    unittest.main()
