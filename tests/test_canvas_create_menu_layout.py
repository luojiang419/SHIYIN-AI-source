import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasCreateMenuLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javascript = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")

    def test_menu_switches_to_two_columns_only_when_bottom_space_is_short(self):
        match = re.search(
            r"function openCreateMenu\(clientX, clientY\)\{(?P<body>.*?)\n\}",
            self.javascript,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("createMenu.classList.remove('create-menu-two-column')", body)
        self.assertIn("const singleColumnHeight = estimateClassicCreateMenuSingleColumnHeight()", body)
        self.assertEqual(body.count("getBoundingClientRect()"), 1)
        self.assertIn("clientY + singleColumnHeight + viewportMargin > window.innerHeight", body)
        self.assertIn("createMenu.classList.toggle('create-menu-two-column', lacksBottomSpace)", body)

    def test_two_column_menu_is_clamped_inside_the_viewport(self):
        self.assertIn(
            ".create-menu.open.create-menu-two-column { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr));",
            self.styles,
        )
        self.assertIn("max-height:calc(100vh - 20px); overflow-y:auto;", self.styles)
        self.assertIn("window.innerWidth - menuRect.width - viewportMargin", self.javascript)
        self.assertIn("window.innerHeight - menuRect.height - viewportMargin", self.javascript)


if __name__ == "__main__":
    unittest.main()
