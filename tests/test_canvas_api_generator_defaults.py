import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasApiGeneratorDefaultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        match = re.search(
            r"function addGeneratorNode\(point\)\{(?P<body>.*?)\n\}\nfunction addMsGenNode",
            source,
            re.DOTALL,
        )
        if not match:
            raise AssertionError("未找到 addGeneratorNode 创建函数")
        cls.function_body = match.group("body")

    def test_prefers_existing_shiying_provider(self):
        self.assertIn("const providers = imageApiProviders()", self.function_body)
        self.assertIn("providers.find(provider => provider.id === 'shiying')", self.function_body)
        self.assertNotIn("apiProviders.push", self.function_body)

    def test_defaults_to_2k_widescreen(self):
        self.assertIn("ratio:'wide'", self.function_body)
        self.assertIn("resolution:'2k'", self.function_body)

    def test_uses_image_generation_display_name(self):
        i18n_source = (ROOT / "static" / "js" / "i18n" / "canvas.js").read_text(encoding="utf-8")
        html_source = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
        canvas_source = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")

        self.assertIn('"canvas.apiGenerate": { zh: "图片生成", en: "Image Generation" }', i18n_source)
        self.assertIn('"canvas.imageGenerateAction": { zh: "图片生成", en: "Generate Image" }', i18n_source)
        self.assertNotIn('"canvas.apiGenerate": { zh: "API生成"', i18n_source)
        self.assertEqual(html_source.count('data-i18n="canvas.apiGenerate">图片生成</span>'), 2)
        self.assertIn("请改用图片生成节点", canvas_source)
        self.assertIn("node.running ? tr('canvas.generating') : tr('canvas.imageGenerateAction')", canvas_source)


if __name__ == "__main__":
    unittest.main()
