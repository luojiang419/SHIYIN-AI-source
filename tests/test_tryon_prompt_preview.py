import unittest
from unittest.mock import AsyncMock, patch

import main


class TryOnPromptPreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_skipped_visual_analysis_still_returns_rule_prompt(self):
        snapshot = {
            "operation": "try_on",
            "inputs": [
                {"role": "source", "url": "/assets/input/model.png"},
                {"role": "upper_garment", "url": "/assets/input/blazer.png"},
            ],
            "options": {"garment_category": "auto"},
            "prompt": "",
        }
        with patch.object(main, "analyze_ecommerce_garment", new=AsyncMock(return_value={"status": "skipped"})):
            enriched, analysis = await main.enrich_ecommerce_snapshot_with_garment_analysis(snapshot)
        self.assertEqual(analysis["status"], "skipped")
        self.assertIn("upper garment", enriched["prompt"])
        self.assertEqual(enriched["options"]["garment_category"], "auto")


if __name__ == "__main__":
    unittest.main()
