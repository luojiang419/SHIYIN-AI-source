import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class ClassicPromptNodeFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javascript = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
        cls.unified_styles = (ROOT / "static" / "css" / "studio-unified.css").read_text(encoding="utf-8")

    def test_multiple_selection_has_a_canvas_level_visual_state(self):
        self.assertIn("board?.classList.toggle('selection-multiple'", self.javascript)
        self.assertIn("Boolean(canvas && selected.size > 1)", self.javascript)
        self.assertIn("Boolean(canvas && nextSelected.size > 1)", self.javascript)

    def test_multiple_selection_hides_both_node_level_floating_surfaces(self):
        self.assertIn(".board.selection-multiple .node > .node-media-toolbar", self.styles)
        self.assertIn(".board.selection-multiple .node > .image-node-prompt-panel", self.styles)
        self.assertIn("pointer-events:none !important", self.styles)

    def test_classic_prompt_uses_text_node_layout_and_keeps_actions(self):
        render_start = self.javascript.index("if(node.type === 'prompt')")
        render_end = self.javascript.index("if(node.type === 'loop')", render_start)
        prompt_render = self.javascript[render_start:render_end]
        for marker in (
            "prompt-node-text-layout",
            "prompt-node-footer",
            "prompt-node-actions",
            "data-prompt-template-open",
            "data-prompt-expand",
        ):
            self.assertIn(marker, prompt_render)
        self.assertNotIn("fitAutoTextNode(node, el, [textarea]", prompt_render)
        self.assertIn("node.type === 'prompt'", self.javascript[self.javascript.index("const nodeTypeClass"):])

    def test_classic_prompt_editor_fills_resized_node_and_keeps_footer_at_bottom(self):
        for marker in (
            ".prompt-node .node-body { display:flex",
            ".prompt-node .prompt-node-text { width:100%; height:auto",
            ".prompt-node:not(.sized) .prompt-node-text { min-height:140px",
            ".node.sized.prompt-node .prompt-editor { min-height:0",
            ".node.sized.prompt-node .prompt-node-text { flex:1 1 auto",
        ):
            self.assertIn(marker, self.styles)

    def test_prompt_text_surfaces_are_theme_neutral(self):
        for marker in (
            ".prompt-node.prompt-text-node .node-body",
            ".prompt-node.prompt-text-node .prompt-node-text-layout",
            ".prompt-node.prompt-text-node .prompt-node-text",
            "background:transparent !important",
        ):
            self.assertIn(marker, self.unified_styles)


if __name__ == "__main__":
    unittest.main()
