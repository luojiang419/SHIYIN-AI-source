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


if __name__ == "__main__":
    unittest.main()
