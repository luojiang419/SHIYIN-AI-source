import re
import unittest
from pathlib import Path


class ApiRecommendationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.source = (root / "static" / "js" / "api-settings.js").read_text(encoding="utf-8")
        cls.styles = (root / "static" / "css" / "api-settings.css").read_text(encoding="utf-8")

    def test_recommendations_are_not_opened_during_initial_provider_load(self):
        load_body = re.search(
            r"async function loadProviders\(\)\{(.*?)\n\}\nfunction saveProviders",
            self.source,
            re.S,
        )
        self.assertIsNotNone(load_body)
        self.assertNotIn("openRecommendApi();", load_body.group(1))

    def test_recommendations_still_open_from_the_recommend_api_action(self):
        self.assertIn("function openRecommendApi(){", self.source)
        self.assertIn("recommendInlineOpen = true;", self.source)
        self.assertIn("syncRecommendView();", self.source)

    def test_settings_content_is_hidden_when_recommendations_are_open(self):
        self.assertRegex(self.styles, r"#settingsContent\[hidden\]\s*\{[^}]*display:\s*none\s*!important", re.S)


if __name__ == "__main__":
    unittest.main()
