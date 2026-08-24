import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PERF_JS = (ROOT / "static" / "js" / "canvas-performance.js").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


class CanvasPerformanceBaselineTests(unittest.TestCase):
    def test_fixture_presets_cover_required_scene_sizes_and_connection_counts(self):
        for nodes, connections in ((100, 200), (300, 600), (500, 1000), (1000, 2000)):
            self.assertIn(f"{nodes}: Object.freeze({{nodes:{nodes}, connections:{connections}}})", PERF_JS)
        self.assertIn("const FIXTURE_PRESETS = Object.freeze({", PERF_JS)
        self.assertIn("function fixtureOptions(options={})", PERF_JS)

    def test_fixture_snapshot_records_resolved_options_and_cleanup(self):
        self.assertIn("activeFixture", PERF_JS)
        self.assertIn("fixture:activeFixture", PERF_JS)
        self.assertIn("const cleanup = factory(resolved);", PERF_JS)
        self.assertIn("finally { activeFixture = null; }", PERF_JS)
        self.assertIn("fixturePresets:FIXTURE_PRESETS", PERF_JS)

    def test_classic_has_repeatable_observation_for_required_interactions(self):
        for metric in (
            "classic.node-drag",
            "classic.pan",
            "classic.zoom",
            "classic.port-link",
            "classic.marquee",
            "classic.minimap-drag",
        ):
            self.assertIn(metric, CANVAS_JS)
        self.assertIn("beginInteraction?.('classic.node-drag'", CANVAS_JS)
        self.assertIn("markPaintFrom?.('classic.node-drag'", CANVAS_JS)

    def test_smart_has_repeatable_observation_for_required_interactions(self):
        for metric in (
            "smart.node-drag",
            "smart.pan",
            "smart.zoom",
            "smart.port-link",
            "smart.marquee",
            "smart.minimap-drag",
        ):
            self.assertIn(metric, SMART_JS)
        self.assertIn("beginInteraction?.('smart.node-drag'", SMART_JS)
        self.assertIn("markPaintFrom?.('smart.node-drag'", SMART_JS)

    def test_fixture_factories_keep_restore_paths(self):
        classic = CANVAS_JS[CANVAS_JS.index("registerClassicCanvasPerfFixture"):]
        smart = SMART_JS[SMART_JS.index("registerSmartCanvasPerfFixture"):]
        for source in (classic, smart):
            self.assertIn("const previous =", source)
            self.assertIn("return () => {", source)
            self.assertIn("render();", source)


if __name__ == "__main__":
    unittest.main()
