import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TAURI_HOST = ROOT / "src-tauri" / "src" / "lib.rs"
THEME = ROOT / "static" / "js" / "theme.js"


class WindowDpiTests(unittest.TestCase):
    def test_saved_window_placement_uses_logical_pixels(self):
        source = TAURI_HOST.read_text(encoding="utf-8")
        self.assertIn("scale_factor: f64", source)
        self.assertIn("position.x as f64 / scale_factor", source)
        self.assertIn("size.width as f64 / scale_factor", source)
        self.assertIn("placement_uses_logical_pixels", source)
        self.assertIn("app.primary_monitor()", source)

    def test_auto_scale_does_not_enlarge_high_resolution_viewports(self):
        source = THEME.read_text(encoding="utf-8")
        start = source.index("function autoScale()")
        end = source.index("function scaleForMode", start)
        self.assertIn("return 1;", source[start:end])
        self.assertNotIn("longEdge", source[start:end])


if __name__ == "__main__":
    unittest.main()
