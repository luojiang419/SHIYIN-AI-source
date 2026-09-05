import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasImageRatioOptionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classic = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.smart = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.special = (ROOT / "static" / "js" / "canvas-special-nodes.js").read_text(encoding="utf-8")
        cls.ecommerce = (ROOT / "static" / "js" / "canvas-ecommerce-nodes.js").read_text(encoding="utf-8")
        cls.lookbook = (ROOT / "static" / "js" / "canvas-lookbook-node.js").read_text(encoding="utf-8")
        cls.film = (ROOT / "static" / "js" / "canvas-film-nodes.js").read_text(encoding="utf-8")
        cls.classic_html = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.smart_html = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")

    def test_classic_and_smart_size_maps_resolve_real_four_by_five_dimensions(self):
        preset = "portrait45: { '1k':'1024x1280', '2k':'1632x2040', '4k':'2560x3200' }"
        compact_preset = "portrait45: {'1k':'1024x1280','2k':'1632x2040','4k':'2560x3200'}"
        self.assertIn(preset, self.classic)
        self.assertIn(compact_preset, self.smart)
        for source in (self.classic, self.smart):
            self.assertIn("'4:5':'portrait45'", source)

    def test_general_image_generators_offer_four_by_five(self):
        classic_generator = re.search(
            r"function renderGeneratorBody\(node\).*?(?=\nfunction videoParameterLabel)",
            self.classic,
            re.S,
        )
        self.assertIsNotNone(classic_generator)
        self.assertIn('<option value="portrait45">4:5</option>', classic_generator.group(0))

        modelscope = re.search(
            r"function renderMsGenBody\(node\).*?(?=\nfunction addOutputNode)",
            self.classic,
            re.S,
        )
        self.assertIsNotNone(modelscope)
        self.assertIn('<option value="portrait45">4:5</option>', modelscope.group(0))

        quick_drawer = re.search(
            r"function imageNodeQuickPromptHtml\(node\).*?(?=\nfunction bindImageNodeQuickPrompt)",
            self.classic,
            re.S,
        )
        self.assertIsNotNone(quick_drawer)
        self.assertIn("['portrait45','4:5']", quick_drawer.group(0))

        for marker in (
            "['portrait45','4:5']",
            "['portrait45','4:5','竖图']",
            "portrait45:'4:5'",
        ):
            self.assertIn(marker, self.smart)

    def test_special_image_nodes_offer_and_preserve_four_by_five(self):
        for marker in (
            "['16:9','9:16','1:1','4:3','3:4','4:5'].includes(node.panoramaAspect)",
            '<option value="4:5" ${node.panoramaAspect === \'4:5\' ? \'selected\' : \'\'}>4:5</option>',
            "'1080x1440','1024x1280'",
            '<option value="1024x1280"',
            "['source','1:1','16:9','9:16','4:3','3:4','4:5'].includes(node.poseReplicateRatio)",
            "const ratios = ['source','1:1','16:9','9:16','4:3','3:4','4:5']",
            "const EDIT_RATIOS = ['source','1:1','16:9','9:16','4:3','3:4','4:5']",
            '<option value="4:5" ${node.editRatio === \'4:5\' ? \'selected\' : \'\'}>4:5</option>',
        ):
            self.assertIn(marker, self.special)

    def test_domain_specific_image_nodes_offer_four_by_five(self):
        self.assertIn("['1:1','3:4','4:5','4:3','9:16','16:9']", self.ecommerce)
        self.assertIn("['1:1','2:3','3:4','4:3','4:5','9:16','16:9']", self.ecommerce)
        self.assertIn("const ratios=['1:1','2:3','3:2','3:4','4:3','4:5','5:4','9:16','16:9']", self.lookbook)
        self.assertGreaterEqual(self.film.count("node.aspectRatio==='4:5'"), 2)
        self.assertIn('<option value="4:5">4:5 竖屏</option>', self.classic_html)
        self.assertIn("'2:3','4:5'].includes(options.ratio)", self.classic)

    def test_changed_scripts_have_cache_busting_marker(self):
        for page in (self.classic_html, self.smart_html):
            self.assertIn("feature=image-ratio-4x5.1", page)


if __name__ == "__main__":
    unittest.main()
