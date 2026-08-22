import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PERF_JS = (ROOT / "static" / "js" / "canvas-performance.js").read_text(encoding="utf-8")
CANVAS_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
SMART_HTML = (ROOT / "static" / "smart-canvas.html").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


class CanvasPerformanceObserverTests(unittest.TestCase):
    def test_observer_is_loaded_before_canvas_runtimes(self):
        self.assertLess(CANVAS_HTML.index("canvas-performance.js"), CANVAS_HTML.index("/static/js/canvas.js"))
        self.assertLess(SMART_HTML.index("canvas-performance.js"), SMART_HTML.index("/static/js/smart-canvas.js"))

    def test_observer_has_low_overhead_gate_and_bounded_samples(self):
        self.assertIn("query.get('canvasPerf') === '1'", PERF_JS)
        self.assertIn("const MAX_SAMPLES = 600", PERF_JS)
        self.assertIn("PerformanceObserver", PERF_JS)
        self.assertIn("requestAnimationFrame(frameLoop)", PERF_JS)

    def test_runtime_exposes_drop_and_fixture_measurement_hooks(self):
        self.assertIn("beginInteraction", PERF_JS)
        self.assertIn("markPaintFrom", PERF_JS)
        self.assertIn("registerFixtureFactory", PERF_JS)
        self.assertIn("installFixture", PERF_JS)
        self.assertIn("classic.output-drag", CANVAS_JS)
        self.assertIn("classic.drop-to-node-visible", CANVAS_JS)
        self.assertIn("registerClassicCanvasPerfFixture", CANVAS_JS)
        self.assertIn("registerSmartCanvasPerfFixture", SMART_JS)


if __name__ == "__main__":
    unittest.main()
