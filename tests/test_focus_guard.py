import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"


class FocusGuardTests(unittest.TestCase):
    def test_main_pages_load_focus_guard_after_theme_runtime(self):
        pages = (
            "index.html",
            "canvas.html",
            "canvas-list.html",
            "smart-canvas.html",
            "gpt-chat.html",
            "asset-manager.html",
            "api-settings.html",
            "app-settings.html",
            "ecommerce.html",
            "works.html",
        )
        for page in pages:
            source = (STATIC / page).read_text(encoding="utf-8")
            theme_pos = source.index("/static/js/theme.js")
            guard_pos = source.index("/static/js/focus-guard.js")
            self.assertGreater(guard_pos, theme_pos, page)

    def test_focus_guard_blocks_programmatic_blur_during_ime_composition(self):
        source = (STATIC / "js" / "focus-guard.js").read_text(encoding="utf-8")
        self.assertIn("document.addEventListener('compositionstart'", source)
        self.assertIn("document.addEventListener('compositionend'", source)
        self.assertIn("HTMLElement.prototype.blur = function guardedBlur", source)
        self.assertIn("if(state.composing && isTextEditable(this)) return;", source)

    def test_dom_rerender_paths_defer_and_restore_editing_focus(self):
        canvas = (STATIC / "js" / "canvas.js").read_text(encoding="utf-8")
        smart = (STATIC / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        ecommerce = (STATIC / "js" / "ecommerce.js").read_text(encoding="utf-8")
        self.assertIn("deferDomUpdate('canvas-render', render)", canvas)
        self.assertIn("deferDomUpdate(`canvas-refresh-${uniqueIds.join(',')}`", canvas)
        self.assertIn("deferDomUpdate('smart-canvas-render', render)", smart)
        self.assertIn("deferDomUpdate('ecommerce-render-inputs', renderInputs)", ecommerce)
        self.assertIn("deferDomUpdate('ecommerce-render-operation-controls', renderOperationControls)", ecommerce)
        for source in (canvas, smart, ecommerce):
            self.assertIn("StudioFocusGuard?.capture?.()", source)
            self.assertIn("StudioFocusGuard?.restore?.(focusSnapshot)", source)

    def test_lookbook_fields_have_node_scoped_focus_restore_selectors(self):
        guard = (STATIC / "js" / "focus-guard.js").read_text(encoding="utf-8")
        canvas_html = (STATIC / "canvas.html").read_text(encoding="utf-8")
        self.assertIn("'data-lookbook-field'", guard)
        self.assertIn("const parentId = el.closest?.('[data-id]')", guard)
        self.assertIn('return parentId ? `[data-id="${cssEscape(parentId)}"] ${controlSelector}`', guard)
        self.assertIn("focus-guard.js?v=2026.09.03.lookbook-focus.1", canvas_html)


if __name__ == "__main__":
    unittest.main()
