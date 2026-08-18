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
        for source in (self.canvas_js, self.smart_js):
            self.assertIn("event?.ctrlKey || isControlKeyDown || isSpaceKeyDown", source)
            self.assertIn("e.key === ' '", source)
            self.assertIn("!isEditableTarget(e.target)", source)

    def test_middle_mouse_pan_is_preserved(self):
        self.assertIn("if(e.button === 1)", self.canvas_js)
        self.assertIn("if(e.button !== 0 && e.button !== 1) return", self.smart_js)


if __name__ == "__main__":
    unittest.main()
