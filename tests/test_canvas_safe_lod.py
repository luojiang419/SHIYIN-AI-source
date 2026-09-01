import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CLASSIC = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
CLASSIC_CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
SMART_CSS = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")


def body(source: str, signature: str, marker: str) -> str:
    start = source.index(signature)
    end = source.index(marker, start)
    return source[start:end]


class CanvasSafeLodTests(unittest.TestCase):
    def test_classic_lod_keeps_outer_node_and_ports(self):
        self.assertIn("const CLASSIC_SAFE_LOD_ENABLED = true", CLASSIC)
        self.assertIn("const CLASSIC_SAFE_LOD_MARGIN", CLASSIC)
        lod = body(CLASSIC, "function updateClassicSafeLod", "function currentWorldViewRect")
        self.assertIn("canvas-lod-outside", lod)
        self.assertIn("selected", lod)
        self.assertIn("tempLink?.from", lod)
        self.assertIn("resizeNode?.node?.id", lod)
        self.assertIn("'group','promptGroup'", CLASSIC)
        self.assertNotRegex(CLASSIC_CSS, r"content-visibility\s*:")
        self.assertNotIn("contain-intrinsic-size", CLASSIC_CSS)

    def test_smart_lod_excludes_special_prompt_loop_and_groups(self):
        self.assertIn("const SMART_SAFE_LOD_ENABLED = true", SMART)
        self.assertIn("const SMART_SAFE_LOD_MARGIN", SMART)
        lod = body(SMART, "function updateSmartSafeLod", "function screenToWorld")
        self.assertIn("smart-lod-outside", lod)
        self.assertIn("portDragState?.fromId", lod)
        self.assertIn("resizeState?.id", lod)
        render = body(SMART, "const smartLodSafe =", "const body = nodeBodyHtml")
        self.assertIn("!isSmartGroup", render)
        self.assertIn("!isPrompt", render)
        self.assertIn("!isLoop", render)
        self.assertIn("!isSpecial", render)
        self.assertNotRegex(SMART_CSS, r"content-visibility\s*:")
        self.assertNotIn("contain-intrinsic-size", SMART_CSS)

    def test_viewport_and_selection_schedule_lod_without_deleting_dom(self):
        classic_apply = body(CLASSIC, "function applyViewport", "function scheduleClassicSafeLod")
        self.assertIn("scheduleClassicSafeLod();", classic_apply)
        classic_lod = body(CLASSIC, "function updateClassicSafeLod", "function currentWorldViewRect")
        self.assertNotIn(".remove()", classic_lod)
        smart_apply = body(SMART, "function applyViewport", "function scheduleSmartSafeLod")
        self.assertIn("scheduleSmartSafeLod();", smart_apply)
        smart_lod = body(SMART, "function updateSmartSafeLod", "function screenToWorld")
        self.assertNotIn(".remove()", smart_lod)
        selection_body = body(CLASSIC, "function refreshSelectionVisuals", "function syncConnectionSelectionVisuals")
        self.assertRegex(selection_body, r"scheduleClassicSafeLod\(\[\.\.\.affectedNodeIds\]\);")
        self.assertIn("scheduleSmartSafeLod();", body(SMART, "function syncSelectionUi", "function syncConnectionSelectionUi"))

    def test_transform_media_subtrees_never_use_paint_skipping(self):
        self.assertNotRegex(CLASSIC_CSS, r"content-visibility\s*:")
        self.assertNotRegex(SMART_CSS, r"content-visibility\s*:")
        self.assertIn("document.body.classList.add('canvas-board-pan')", CLASSIC)
        self.assertIn("shell.classList.add('panning')", SMART)


if __name__ == "__main__":
    unittest.main()
