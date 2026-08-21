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

    def test_grsai_uses_the_standard_provider_card_layout(self):
        render_body = re.search(
            r"function renderProviderList\(\)\{(.*?)\n\}\nfunction handleProviderDragStart",
            self.source,
            re.S,
        )
        self.assertIsNotNone(render_body)
        self.assertNotIn("if(item.id === 'grsai')", render_body.group(1))
        self.assertIn('provider-card provider-card-sortable', render_body.group(1))
        self.assertIn('${escapeHtml(item.name || item.id)}', render_body.group(1))
        self.assertIn('${escapeHtml(item.base_url || \'未配置地址\')}', render_body.group(1))
        self.assertNotIn('provider-logo-fallback-visible', self.source)

    def test_provider_list_preserves_saved_order(self):
        sort_body = re.search(
            r"function sortedProviders\(\)\{(.*?)\n\}",
            self.source,
            re.S,
        )
        self.assertIsNotNone(sort_body)
        self.assertIn("return visibleProviders();", sort_body.group(1))
        self.assertNotIn("const order =", sort_body.group(1))

    def test_all_provider_cards_can_be_dragged(self):
        attrs_body = re.search(
            r"function providerDragAttrs\(item\)\{(.*?)\n\}",
            self.source,
            re.S,
        )
        self.assertIsNotNone(attrs_body)
        self.assertIn('draggable="true"', attrs_body.group(1))
        self.assertNotIn("isFixedProvider", attrs_body.group(1))
        self.assertGreaterEqual(self.source.count("provider-card-banner provider-card-sortable"), 4)
        self.assertIn("provider-priority", self.source)

    def test_dragging_normalizes_primary_to_first_enabled_provider(self):
        drop_body = re.search(
            r"function handleProviderDrop\(event, targetId\)\{(.*?)\n\}",
            self.source,
            re.S,
        )
        self.assertIsNotNone(drop_body)
        self.assertIn("firstEnabledIndex", drop_body.group(1))
        self.assertIn("item.primary = index === Math.max(0, firstEnabledIndex)", drop_body.group(1))


if __name__ == "__main__":
    unittest.main()
