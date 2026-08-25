import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"


class CanvasNodeLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classic_html = (STATIC / "canvas.html").read_text(encoding="utf-8")
        cls.smart_html = (STATIC / "smart-canvas.html").read_text(encoding="utf-8")
        cls.classic = (STATIC / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.smart = (STATIC / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.shortcuts = (STATIC / "js" / "shortcut-actions.js").read_text(encoding="utf-8")
        cls.i18n = (STATIC / "js" / "i18n" / "canvas.js").read_text(encoding="utf-8")

    def test_llm_node_uses_ai_assistant_label(self):
        self.assertIn("<span>AI助手</span>", self.classic_html)
        self.assertIn('data-i18n="canvas.llmNode">AI助手</span>', self.classic_html)
        self.assertIn("node.type === 'llm' ? 'AI助手'", self.classic)
        self.assertIn("label:'AI助手'", self.classic)
        self.assertIn('"canvas.llmNode": { zh: "AI助手", en: "AI Assistant" }', self.i18n)
        self.assertIn("<span>AI助手</span>", self.smart)

    def test_loop_creation_entries_are_removed_but_legacy_runtime_remains(self):
        for source in (self.classic_html, self.smart_html, self.shortcuts):
            self.assertNotIn("create.loop", source)
            self.assertNotIn("menuAdd('loop')", source)
            self.assertNotIn('data-create-type="loop"', source)
        self.assertNotIn("{type:'loop', label:tr('canvas.loopNode')", self.classic)
        self.assertIn("function addLoopNode(point)", self.classic)
        self.assertIn("function createLoopNode(x, y, options={})", self.smart)


if __name__ == "__main__":
    unittest.main()
