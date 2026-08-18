import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class PromptExpandEditorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canvas_html = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.canvas_js = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.smart_html = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
        cls.smart_js = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")

    def test_both_canvases_render_a_centered_expanded_editor(self):
        for source in (self.canvas_html, self.smart_html):
            self.assertIn('id="expandedPromptModal"', source)
            self.assertIn('id="expandedPromptTextarea"', source)
            self.assertIn('data-i18n="canvas.promptExpandTitle"', source)

    def test_classic_prompt_node_opens_and_live_syncs_editor(self):
        self.assertIn("data-prompt-expand", self.canvas_js)
        self.assertIn("function openExpandedPromptEditor(source", self.canvas_js)
        self.assertIn("expandedPromptSource.dispatchEvent(new Event('input'", self.canvas_js)

    def test_smart_composer_and_prompt_nodes_open_editor(self):
        self.assertIn('id="composerPromptExpandBtn"', self.smart_html)
        self.assertIn("prompt-expand-open", self.smart_js)
        self.assertIn("function openExpandedPromptEditor(source", self.smart_js)
        bind_start = self.smart_js.index("function bindPromptNodeControls(el, node)")
        bind_end = self.smart_js.index("function bindLoopNodeControls", bind_start)
        self.assertIn("const expandBtn = el.querySelector('.prompt-expand-open')", self.smart_js[bind_start:bind_end])

    def test_smart_rich_mentions_are_preserved_during_live_sync(self):
        self.assertIn("expandedPromptRich.innerHTML = source.innerHTML", self.smart_js)
        self.assertIn("expandedPromptSource.innerHTML = expandedPromptRich.innerHTML", self.smart_js)
        self.assertIn("expandedPromptSource.dispatchEvent(new Event('input'", self.smart_js)


if __name__ == "__main__":
    unittest.main()
