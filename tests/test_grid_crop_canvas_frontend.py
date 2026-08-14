import unittest
from pathlib import Path


class GridCropCanvasFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.html = (root / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.javascript = (root / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.main = (root / "main.py").read_text(encoding="utf-8")

    def test_standard_canvas_exposes_auto_detection_and_both_rulers(self):
        self.assertIn('id="gridAutoDetectBtn"', self.html)
        self.assertIn('id="gridRulerTop"', self.html)
        self.assertIn('id="gridRulerLeft"', self.html)
        self.assertIn("function autoDetectGridLines(force=false)", self.javascript)
        self.assertIn("/api/canvas-tools/grid/detect", self.javascript)
        self.assertIn('@app.post("/api/canvas-tools/grid/detect")', self.main)

    def test_manual_lines_can_be_added_dragged_and_removed_with_right_click(self):
        self.assertIn("function addGridCustomLine(type, pos)", self.javascript)
        self.assertIn("setGridCustomLinePos(gridCustomDrag.index", self.javascript)
        self.assertIn("function handleGridLineContextMenu(event)", self.javascript)
        self.assertIn("gridCustomLines.splice(hitIndex, 1)", self.javascript)
        self.assertIn("addEventListener('contextmenu', handleGridLineContextMenu)", self.javascript)

    def test_existing_grid_export_path_is_reused(self):
        self.assertIn("async function applyImageGridSplit()", self.javascript)
        self.assertIn("const rects = gridSplitRects(img.naturalWidth, img.naturalHeight);", self.javascript)
        self.assertIn("const layout = gridLayoutFromRects(rects);", self.javascript)


if __name__ == "__main__":
    unittest.main()
