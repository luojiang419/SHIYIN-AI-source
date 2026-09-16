import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
CANVAS_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
SMART_CANVAS_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def function_body(source: str, signature: str, next_marker: str) -> str:
    start = source.index(signature)
    end = source.index(next_marker, start)
    return source[start:end]


class CanvasInitialLoadPerformanceTests(unittest.TestCase):
    def test_editor_does_not_create_a_normal_entry_overlay(self):
        body_start = CANVAS_HTML.split("<body>", 1)[1].split('<div id="canvasStartupNotice"', 1)[0]
        self.assertNotIn("CanvasEntryProgress.create", body_start)
        self.assertIn("canvas-entry-mounted", body_start)

    def test_upstream_engine_skips_media_readiness_gate(self):
        body = function_body(CANVAS_JS, "async function prepareCanvasEntry(session)", "function showCanvasStartupNotice")
        fast_path = body.split("if(window.CanvasEngine?.active){", 1)[1].split("while(session.isCurrent())", 1)[0]
        self.assertIn("hideCanvasStartupNotice()", fast_path)
        self.assertNotIn("CanvasResourceReady.wait", fast_path)

    def test_runtime_preferences_do_not_block_opening(self):
        body = function_body(CANVAS_JS, "async function initializeCanvasPage()", "// 不等待图片/媒体等 load 资源")
        self.assertLess(body.index("await openCanvas(openId)"), body.index("RuntimeSync"))
        self.assertNotIn("preferenceTimer", body)

    def test_classic_canvas_schedules_secondary_work_after_both_render_paths(self):
        body = function_body(CANVAS_JS, "async function openCanvas(id)", "function canvasEntryResourceVisible")
        # 磁盘恢复和首次打开是两个分支，不能把后一个分支的 render 与前一个分支比较。
        self.assertLess(body.index("restoreCanvasPage(saved,session)"), body.index("session.afterPaint(startCanvasSecondaryStartup)"))
        render_at = body.index("render();")
        self.assertLess(render_at, body.index("session.afterPaint(startCanvasSecondaryStartup)", render_at))
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
            "async function refreshMissingCanvasAssets(expectedCanvasId=canvas?.id,signal)",
            "async function syncRemoteCanvasNow",
        )
        self.assertIn("if(canvas?.id !== targetCanvasId) return;", body)
        self.assertLess(body.index("if(canvas?.id !== targetCanvasId) return;"), body.index("for(const url of missingAssetUrls)"))

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
