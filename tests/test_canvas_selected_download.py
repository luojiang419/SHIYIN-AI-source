import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasSelectedDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classic_html = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.classic_js = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.smart_html = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
        cls.smart_js = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")

    def test_both_context_menus_expose_selected_download_action(self):
        self.assertIn('id="canvasDownloadSelectedMenuBtn"', self.classic_html)
        self.assertIn('id="smartDownloadSelectedMenuBtn"', self.smart_html)
        self.assertIn("function selectedCanvasDownloadItems()", self.classic_js)
        self.assertIn("function downloadSelectedCanvasNodes()", self.classic_js)
        self.assertIn("function selectedSmartDownloadItems()", self.smart_js)
        self.assertIn("function downloadSelectedSmartNodes()", self.smart_js)
        self.assertIn("saveCanvasItemsToDirectory(`${canvas?.title || 'canvas'}-selected`, items)", self.classic_js)
        self.assertIn("saveDownloadImageItems('selected', items)", self.smart_js)

    def test_grid_split_closes_editor_after_uploaded_outputs(self):
        for source in (self.classic_js, self.smart_js):
            start = source.index("async function applyImageGridSplit()")
            end = source.index("\n}\n", start) + 2
            body = source[start:end]
            self.assertIn("(await uploadImageBlobs(blobs)) || []", body)
            self.assertIn("closeImageEditor()", body)


if __name__ == "__main__":
    unittest.main()
