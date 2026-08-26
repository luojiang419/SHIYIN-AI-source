import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PERF_JS = (ROOT / "static" / "js" / "canvas-performance.js").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


class CanvasRealMediaPerformanceTests(unittest.TestCase):
    def test_fixture_presets_cover_requested_production_scales(self):
        for nodes, connections in ((500, 1000), (1000, 2000), (1500, 3000), (2000, 4000)):
            self.assertIn(
                f"{nodes}: Object.freeze({{nodes:{nodes}, connections:{connections}}})",
                PERF_JS,
            )

    def test_fixture_options_normalize_real_uploaded_media(self):
        self.assertIn("function fixtureMediaItems(items=[])", PERF_JS)
        self.assertIn("mediaItems:fixtureMediaItems(input.mediaItems)", PERF_JS)
        self.assertIn("url:String(item.url || '').trim()", PERF_JS)
        self.assertIn("kind:'image'", PERF_JS)

    def test_real_media_fixture_preserves_explicit_zero_connections(self):
        for source, label in (
            (CANVAS_JS, "classic"),
            (SMART_JS, "smart"),
        ):
            self.assertTrue("Number(options.connections ?? 1000)" in source, label)
            self.assertFalse("Number(options.connections || 1000)" in source, label)

    def test_classic_fixture_cycles_real_media_urls_across_image_nodes(self):
        start = CANVAS_JS.index("function registerClassicCanvasPerfFixture()")
        end = CANVAS_JS.index("registerClassicCanvasPerfFixture();", start)
        fixture = CANVAS_JS[start:end]
        self.assertIn("const mediaItems = options.mediaItems || [];", fixture)
        self.assertIn("const media = mediaItems[index % mediaItems.length]", fixture)
        self.assertIn("url:media.url", fixture)
        self.assertIn("mediaKind:'image'", fixture)

    def test_smart_fixture_cycles_real_media_into_image_arrays(self):
        start = SMART_JS.index("function registerSmartCanvasPerfFixture()")
        end = SMART_JS.index("registerSmartCanvasPerfFixture();", start)
        fixture = SMART_JS[start:end]
        self.assertIn("const mediaItems = options.mediaItems || [];", fixture)
        self.assertIn("const media = mediaItems[index % mediaItems.length]", fixture)
        self.assertIn("images:media ? [{...media, kind:'image'}] : []", fixture)


if __name__ == "__main__":
    unittest.main()
