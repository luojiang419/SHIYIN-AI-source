import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"


class ThemePickerTests(unittest.TestCase):
    def test_theme_runtime_supports_three_persistent_modes(self):
        source = (STATIC / "js" / "theme.js").read_text(encoding="utf-8")
        self.assertIn("['light', 'dark', 'pure-white', 'system']", source)
        self.assertIn("studio-theme-pure-white", source)
        self.assertIn("theme-pure-white", source)
        self.assertIn("modes: THEME_MODES.slice()", source)

    def test_theme_picker_exposes_the_requested_choices(self):
        source = (STATIC / "index.html").read_text(encoding="utf-8")
        for theme in ("light", "dark", "pure-white"):
            self.assertIn(f'data-theme-choice="{theme}"', source)
        self.assertIn('id="theme-picker-modal"', source)
        self.assertIn("function openThemePicker()", source)
        self.assertIn("function chooseTheme(theme)", source)
        self.assertRegex(source, re.compile(r"function toggleTheme\(\)\s*\{\s*openThemePicker\(\);", re.S))

    def test_page_boot_scripts_recognize_pure_white_before_paint(self):
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
            self.assertIn("theme === 'pure-white'", source, page)
            self.assertIn("theme-pure-white", source, page)

    def test_pure_white_tokens_cover_workspace_and_ecommerce(self):
        unified = (STATIC / "css" / "studio-unified.css").read_text(encoding="utf-8")
        ecommerce = (STATIC / "css" / "ecommerce.css").read_text(encoding="utf-8")
        for marker in (
            "--studio-bg:#ffffff",
            "--studio-accent:#171717",
            "--studio-control-hover:#f5f5f5",
            "html.studio-theme-pure-white",
        ):
            self.assertIn(marker, unified)
        for marker in (
            "--ec-bg:#ffffff",
            "--ec-accent:#171717",
            "--ec-control-hover:#f5f5f5",
            "html.studio-theme-pure-white",
        ):
            self.assertIn(marker, ecommerce)


if __name__ == "__main__":
    unittest.main()
