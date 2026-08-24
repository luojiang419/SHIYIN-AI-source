import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
CANVAS_CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
SMART_CSS = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")


def body(source: str, signature: str, end_marker: str) -> str:
    start = source.index(signature)
    end = source.index(end_marker, start)
    return source[start:end]


class CanvasMinimapCanvasTests(unittest.TestCase):
    def test_both_minimaps_have_safe_canvas_switch_and_dom_fallback(self):
        self.assertIn("const CLASSIC_MINIMAP_CANVAS_ENABLED = true;", CANVAS_JS)
        self.assertIn("const SMART_MINIMAP_CANVAS_ENABLED = true;", SMART_JS)
        self.assertIn("function renderClassicMinimapDomFallback", CANVAS_JS)
        self.assertIn("function renderSmartMinimapDomFallback", SMART_JS)
        self.assertIn("minimapContent.innerHTML", CANVAS_JS)
        self.assertIn("minimapContent.innerHTML", SMART_JS)

    def test_primary_render_path_uses_single_canvas_and_preserves_viewport_dom(self):
        classic = body(CANVAS_JS, "function renderMinimap()", "function updateMinimapViewport")
        smart = body(SMART_JS, "function renderMinimap()", "function scheduleSmartMinimapRender")
        for render_body in (classic, smart):
            self.assertIn("ensure", render_body)
            self.assertIn("draw", render_body)
            self.assertNotIn("minimapContent.innerHTML", render_body)
        self.assertIn("updateMinimapViewport();", classic)
        self.assertIn("minimapViewport.style", smart)

    def test_dirty_updates_use_rect_index_and_not_per_node_dom_queries(self):
        classic = body(CANVAS_JS, "function redrawClassicMinimapDirty", "function renderClassicMinimapDomFallback")
        smart = body(SMART_JS, "function redrawSmartMinimapDirty", "function renderSmartMinimapDomFallback")
        for dirty_body in (classic, smart):
            self.assertIn("NodeRectIndex", dirty_body)
            self.assertIn("clearRect", dirty_body)
            self.assertNotIn("querySelector('.minimap-node", dirty_body)

    def test_canvas_is_non_interactive_so_minimap_drag_layer_stays_dom_backed(self):
        for css in (CANVAS_CSS, SMART_CSS):
            self.assertIn(".minimap-canvas", css)
            rule = css[css.index(".minimap-canvas"):css.index("}", css.index(".minimap-canvas"))]
            self.assertIn("pointer-events:none", rule)


if __name__ == "__main__":
    unittest.main()
