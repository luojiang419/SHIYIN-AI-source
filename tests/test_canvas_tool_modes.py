import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasToolModeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canvas_html = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.canvas_js = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.canvas_css = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
        cls.smart_html = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
        cls.smart_js = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.smart_css = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")

    def test_classic_canvas_exposes_select_and_pan_tools(self):
        self.assertIn('id="canvasSelectTool"', self.canvas_html)
        self.assertIn('id="canvasPanTool"', self.canvas_html)
        self.assertIn("function setCanvasToolMode(mode)", self.canvas_js)
        self.assertIn("function activeCanvasTool(event=null)", self.canvas_js)
        self.assertIn("canvas-tool-pan", self.canvas_css)

    def test_smart_canvas_exposes_select_and_pan_tools(self):
        self.assertIn('id="smartCanvasSelectTool"', self.smart_html)
        self.assertIn('id="smartCanvasPanTool"', self.smart_html)
        self.assertIn("function setSmartCanvasToolMode(mode)", self.smart_js)
        self.assertIn("function activeSmartCanvasTool(event=null)", self.smart_js)
        self.assertIn("smart-tool-pan", self.smart_css)

    def test_both_canvases_support_ctrl_or_space_temporary_inversion(self):
        self.assertIn("event?.ctrlKey || isControlKeyDown || isSpaceKeyDown", self.canvas_js)
        self.assertIn("e.key === ' '", self.canvas_js)
        self.assertIn("!isEditableTarget(e.target)", self.canvas_js)
        self.assertIn("ShortcutActions.findAction", self.smart_js)
        self.assertIn("const holdAction = window.ShortcutActions.findAction", self.smart_js)
        self.assertIn("smartTemporaryToolMode", self.smart_js)

    def test_middle_mouse_pan_is_preserved(self):
        self.assertIn("if(e.button === 1)", self.canvas_js)
        self.assertIn("if(e.button !== 0 && e.button !== 1) return", self.smart_js)

    def test_smart_node_toolbar_keeps_gap_and_dismisses_on_canvas_pan(self):
        self.assertIn("bottom:calc(100% + 10px)", self.smart_css)
        self.assertIn(".world.smart-node-toolbar-dismissed .smart-node-floating-menu", self.smart_css)
        self.assertIn("function dismissSmartNodeToolbar()", self.smart_js)
        self.assertIn("function restoreSmartNodeToolbar()", self.smart_js)
        pan_start = self.smart_js.index("panState = {button:e.button")
        pan_context_start = self.smart_js.rfind("if(e.button !== 0 && e.button !== 1) return;", 0, pan_start)
        self.assertIn("dismissSmartNodeToolbar()", self.smart_js[pan_context_start:pan_start])
        node_click = self.smart_js.index("el.onclick = e => {")
        node_click_end = self.smart_js.index("const node = nodeIndex.get(id);", node_click)
        self.assertIn("restoreSmartNodeToolbar()", self.smart_js[node_click:node_click_end])


if __name__ == "__main__":
    unittest.main()
