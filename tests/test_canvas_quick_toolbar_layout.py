import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasQuickToolbarLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.javascript = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
        cls.i18n = (ROOT / "static" / "js" / "i18n" / "canvas.js").read_text(encoding="utf-8")

    def test_toolbar_entries_are_split_into_two_explicit_rows(self):
        toolbar = re.search(r'<div id="quickToolbar"(?P<body>.*?)</div>\s*</div>\s*</div>', self.html, re.DOTALL)
        self.assertIsNotNone(toolbar)
        body = toolbar.group("body")
        self.assertEqual(body.count('class="toolbar-row"'), 2)
        self.assertIn('onclick="addImageNode()"', body)
        self.assertIn('onclick="addVideoNode()"', body)
        self.assertIn('onclick="addBlenderDirectorNode()"', body)
        self.assertIn('onclick="groupSelectedImages()"', body)

    def test_expanded_toolbar_uses_two_rows_without_horizontal_scrolling(self):
        self.assertIn(".toolbar-items { flex:1 1 auto; min-width:0; display:flex; flex-direction:column;", self.styles)
        self.assertIn("overflow:visible;", self.styles)
        self.assertIn(".toolbar-row {", self.styles)

    def test_collapsed_toolbar_keeps_all_items_in_one_compact_row(self):
        self.assertIn(".toolbar.collapsed .toolbar-items { flex-direction:row;", self.styles)
        self.assertIn(".toolbar.collapsed .toolbar-row { display:contents; }", self.styles)
        self.assertIn(".toolbar.collapsed .toolbar-items .tool-btn span { display:none; }", self.styles)
        self.assertNotIn(".toolbar.collapsed .toolbar-items { display:none; }", self.styles)

    def test_collapse_state_is_remembered_and_has_bilingual_labels(self):
        self.assertIn("QUICK_TOOLBAR_COLLAPSED_KEY", self.javascript)
        self.assertIn("tr('canvas.toolbarExpand')", self.javascript)
        self.assertIn("tr('canvas.toolbarCollapse')", self.javascript)
        self.assertIn('class="toolbar-toggle-label"', self.html)
        self.assertIn('"canvas.toolbarCollapse"', self.i18n)
        self.assertIn('"canvas.toolbarExpand"', self.i18n)

    def test_toggle_reverses_the_persisted_node_panel_state(self):
        toggle = re.search(
            r"function toggleQuickToolbar\(\)\{(?P<body>.*?)\n\}",
            self.javascript,
            re.DOTALL,
        )
        self.assertIsNotNone(toggle)
        body = toggle.group("body")
        self.assertIn(
            "localStorage.getItem(QUICK_TOOLBAR_COLLAPSED_KEY) === '1'",
            body,
        )
        self.assertIn("const next = !collapsed;", body)
        self.assertNotIn("toolbar?.classList.contains('collapsed')", body)

    def test_node_panel_has_right_side_toggle_and_collapses_to_one_icon(self):
        self.assertIn('id="toolbarNodePanel" class="toolbar-node-panel"', self.html)
        self.assertIn('id="toolbarNodeItems" class="toolbar-items"', self.html)
        self.assertIn('aria-controls="toolbarNodeItems"', self.html)
        self.assertIn('.toolbar-node-panel.collapsed .toolbar-items { display:none; }', self.styles)
        self.assertIn('.toolbar-node-panel.collapsed .toolbar-toggle-label { display:none; }', self.styles)
        self.assertIn("nodePanel.classList.toggle('collapsed', collapsed);", self.javascript)
        self.assertIn("btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');", self.javascript)


if __name__ == "__main__":
    unittest.main()
