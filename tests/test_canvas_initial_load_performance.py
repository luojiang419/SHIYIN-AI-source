import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_CANVAS_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def function_body(source: str, signature: str, next_marker: str) -> str:
    start = source.index(signature)
    end = source.index(next_marker, start)
    return source[start:end]


class CanvasInitialLoadPerformanceTests(unittest.TestCase):
    def test_classic_canvas_schedules_touch_and_asset_check_after_first_render(self):
        body = function_body(CANVAS_JS, "async function openCanvas(id)", "function applyRemoteCanvasData")
        render_at = body.index("render();")
        self.assertLess(render_at, body.index("session.afterPaint(startCanvasSecondaryStartup)"))
        self.assertIn("async function startCanvasSecondaryStartup(session)", CANVAS_JS)
        self.assertNotIn("await touchCanvasOpened", body)
        self.assertNotIn("await refreshMissingCanvasAssets", body)

    def test_classic_canvas_applies_required_config_before_first_render(self):
        body = function_body(CANVAS_JS, "async function openCanvas(id)", "function showCanvasStartupNotice")
        self.assertLess(body.index("applyCanvasRuntimeConfig(result.config)"), body.index("render();"))
        self.assertNotIn("scheduleCanvasConfigSecondary", CANVAS_JS)
        self.assertNotIn("pruneMissingComfyWorkflows();", body)

    def test_classic_asset_check_cannot_apply_to_a_newer_canvas(self):
        body = function_body(
            CANVAS_JS,
            "async function refreshMissingCanvasAssets(expectedCanvasId=canvas?.id)",
            "async function syncRemoteCanvasNow",
        )
        self.assertIn("if(canvas?.id !== targetCanvasId) return;", body)
        self.assertLess(body.index("if(canvas?.id !== targetCanvasId) return;"), body.rindex("missingAssetUrls.clear();"))

    def test_smart_canvas_loads_project_before_secondary_libraries(self):
        onload = SMART_CANVAS_JS[SMART_CANVAS_JS.index("window.onload = async () => {"):]
        self.assertIn("const configTask = loadConfig({deferSecondary:true});", onload)
        self.assertIn("await loadCanvas();", onload)
        self.assertIn("scheduleSmartSecondaryStartup();", onload)
        self.assertNotRegex(onload, re.compile(r"await (loadSmartShortcutSettings|loadPromptTemplates|loadAssetLibrary)\("))
        self.assertLess(onload.index("await loadCanvas();"), onload.index("scheduleSmartSecondaryStartup();"))

    def test_smart_secondary_startup_keeps_noncritical_data_out_of_first_render(self):
        body = function_body(
            SMART_CANVAS_JS,
            "function scheduleSmartSecondaryStartup()",
            "window.onload = async () => {",
        )
        for loader in ("loadSmartShortcutSettings()", "loadPromptTemplates()", "loadAssetLibrary()"):
            self.assertIn(loader, body)
        self.assertIn("requestIdleCallback", body)
        self.assertIn("scheduleSmartConfigSecondary(loadSecondary)", SMART_CANVAS_JS)


if __name__ == "__main__":
    unittest.main()
