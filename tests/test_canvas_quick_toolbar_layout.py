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
        self.assertIn("align-items:flex-start;", self.styles)
        self.assertIn("overflow:visible;", self.styles)
        self.assertIn(".toolbar-row {", self.styles)

    def test_canvas_modes_join_the_first_row_so_both_rows_are_left_aligned(self):
        toolbar = re.search(r'<div id="quickToolbar"(?P<body>.*?)</div>\s*</div>\s*</div>', self.html, re.DOTALL)
        self.assertIsNotNone(toolbar)
        body = toolbar.group("body")
        first_row = body.index('class="toolbar-row"')
        mode_switch = body.index('id="canvasToolSwitch"')
        first_node = body.index('onclick="addImageNode()"')
        second_row = body.index('class="toolbar-row"', first_row + 1)
        self.assertLess(first_row, mode_switch)
        self.assertLess(mode_switch, first_node)
        self.assertLess(first_node, second_row)

    def test_collapsed_toolbar_keeps_mode_switch_and_compacts_toggle(self):
        self.assertIn('.toolbar-node-panel.collapsed .toolbar-row > .tool-btn,', self.styles)
        self.assertNotIn('.toolbar-node-panel.collapsed .toolbar-items { display:none; }', self.styles)
        self.assertIn('.toolbar .toolbar-toggle[aria-expanded="false"] .toolbar-toggle-label { display:none; }', self.styles)
        self.assertIn('.toolbar .toolbar-toggle[aria-expanded="false"] i { transform:rotate(180deg); }', self.styles)

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

    def test_node_panel_keeps_canvas_modes_when_node_entries_are_collapsed(self):
        self.assertIn('id="toolbarNodePanel" class="toolbar-node-panel"', self.html)
        self.assertIn('id="toolbarNodeItems" class="toolbar-items"', self.html)
        self.assertIn('aria-controls="toolbarNodeItems"', self.html)
        self.assertIn('.toolbar-node-panel.collapsed .toolbar-row > .tool-btn,', self.styles)
        self.assertIn('.toolbar-node-panel.collapsed .toolbar-row + .toolbar-row { display:none; }', self.styles)
        self.assertIn("nodePanel.classList.toggle('collapsed', collapsed);", self.javascript)
        self.assertIn("const btn = toolbar.querySelector('.toolbar-toggle');", self.javascript)
        self.assertIn("btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');", self.javascript)

    def test_fixed_actions_end_with_toggle_after_log(self):
        fixed = re.search(r'<div class="toolbar-fixed">(?P<body>.*?)</div>', self.html, re.DOTALL)
        self.assertIsNotNone(fixed)
        body = fixed.group("body")
        self.assertLess(body.index('id="canvasAssetToggle"'), body.index('id="canvasLogToggle"'))
        self.assertLess(body.index('id="canvasLogToggle"'), body.index('class="tool-btn toolbar-toggle"'))

    def test_narrow_toolbar_compacts_nodes_and_wraps_before_overlap(self):
        self.assertIn('.toolbar-items .toolbar-row > .tool-btn { width:32px; min-width:32px; }', self.styles)
        self.assertIn('@media (max-width:480px)', self.styles)
        self.assertIn('.toolbar-node-panel:not(.collapsed) { flex:1 1 100%; width:100%; }', self.styles)


if __name__ == "__main__":
    unittest.main()
