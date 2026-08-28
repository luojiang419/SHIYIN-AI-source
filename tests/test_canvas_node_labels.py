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
        cls.smart_i18n = (STATIC / "js" / "i18n" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.api_html = (STATIC / "api-settings.html").read_text(encoding="utf-8")
        cls.api_i18n = (STATIC / "js" / "i18n" / "api-settings.js").read_text(encoding="utf-8")

    def test_llm_node_uses_ai_assistant_label(self):
        self.assertIn("id:'llm', label:'AI助手'", self.classic)
        self.assertIn("node.type === 'llm' ? 'AI助手'", self.classic)
        self.assertIn("label:'AI助手'", self.classic)
        self.assertIn('"canvas.llmNode": { zh: "AI助手", en: "AI Assistant" }', self.i18n)
        self.assertIn("<span>AI助手</span>", self.smart)
        self.assertNotIn("LLM 节点", self.classic_html)
        self.assertNotIn("LLM 节点", self.classic)
        self.assertNotIn("LLM 节点", self.smart_html)
        self.assertNotIn("LLM 节点", self.smart)
        self.assertNotIn("LLM 节点", self.api_html)
        self.assertNotIn("LLM 节点", self.api_i18n)
        self.assertIn("AI助手运行失败", self.classic)
        self.assertIn("AI助手运行失败", self.smart_i18n)

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
