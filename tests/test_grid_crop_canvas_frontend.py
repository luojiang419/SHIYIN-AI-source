import unittest
import json
import subprocess
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

    def test_split_metadata_uses_cell_spans_and_preserves_crop_aspect_ratio(self):
        self.assertIn("itemMode:'cells'", self.javascript)
        self.assertIn("rowSpan:1, colSpan:1, ratioW:rects[i]?.w || 1, ratioH:rects[i]?.h || 1", self.javascript)
        self.assertIn("function gridOutputItemStyle(grid)", self.javascript)
        start = self.javascript.index("function gridOutputItemStyle(grid)")
        end = self.javascript.index("function selectionBoxLocalPoint", start)
        function_source = self.javascript[start:end]
        script = (
            function_source
            + "; console.log(JSON.stringify(gridOutputItemStyle({itemMode:'cells',row:1,col:2,w:300,h:200})));"
        )
        result = subprocess.run(["node", "-e", script], cwd=Path(__file__).resolve().parent.parent, check=True, capture_output=True, text=True)
        style = json.loads(result.stdout)
        self.assertIn("grid-row:2 / span 1", style)
        self.assertIn("grid-column:3 / span 1", style)
        self.assertIn("aspect-ratio:300/200", style)


if __name__ == "__main__":
    unittest.main()
