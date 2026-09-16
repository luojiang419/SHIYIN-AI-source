import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
CANVAS_HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
SMART_CANVAS_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
CANVAS_LIST_JS = (ROOT / "static" / "js" / "canvas-list.js").read_text(encoding="utf-8")
CANVAS_SESSION_HOST_JS = (ROOT / "static" / "js" / "canvas-session-host.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
CANVAS_SPECIAL_NODES_JS = (ROOT / "static" / "js" / "canvas-special-nodes.js").read_text(encoding="utf-8")
CANVAS_FILM_NODES_JS = (ROOT / "static" / "js" / "canvas-film-nodes.js").read_text(encoding="utf-8")


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

    def test_canvas_manager_prewarms_a_reusable_editor_runtime(self):
        self.assertIn("CanvasSessionHost?.prewarm()", CANVAS_LIST_JS)
        self.assertIn("/static/canvas.html?warm=1", CANVAS_SESSION_HOST_JS)
        self.assertIn("warmEditor?.frame?.isConnected ? warmEditor", CANVAS_SESSION_HOST_JS)
        self.assertIn("openProject(url.searchParams.get('id'), url.href)", CANVAS_SESSION_HOST_JS)
        self.assertIn("async openProject(id, url)", CANVAS_JS)

    def test_first_view_media_uses_stable_cache_urls_and_element_visibility(self):
        preview = function_body(CANVAS_JS, "function canvasMediaPreviewUrl(url, size=512)", "// 过滤调用方传入")
        viewport = function_body(CANVAS_JS, "function classicMediaViewportEntry(element)", "function classicPreviewCandidate")
        window = function_body(CANVAS_JS, "function classicMediaElementsInWindow()", "function applyViewport")
        self.assertIn("rev=${canvasMediaCacheRevision(raw)}", preview)
        self.assertIn("element.getBoundingClientRect", viewport)
        self.assertIn("visible || (!canvasEntryPreparing && near) || pinned", viewport)
        self.assertNotIn("if(canvasEntryPreparing)", window)
        self.assertNotIn("data-preview-state=\"queued\"", window)
        self.assertIn("/^\\/(?:assets|output)\\//i.test(original) ? '' : original", CANVAS_JS)
        self.assertIn("window.canvasPreviewImgHtml(url, 256, attrs)", CANVAS_SPECIAL_NODES_JS)
        self.assertIn("window.canvasPreviewImgHtml(item.url, 256", CANVAS_FILM_NODES_JS)
        self.assertIn("window.canvasPreviewImgHtml(state.url, 256", CANVAS_FILM_NODES_JS)

    def test_upstream_node_mount_wakes_media_queue(self):
        bridge = function_body(CANVAS_JS, "window.CanvasEngineBridge = {", "function registerClassicCanvasPerfFixture")
        mount = bridge[bridge.index("onNodeMount(node, element)"):bridge.index("onNodeUnmount(node)", bridge.index("onNodeMount(node, element)"))]
        unmount = bridge[bridge.index("onNodeUnmount(node)"):bridge.index("onNodeReplace(node", bridge.index("onNodeUnmount(node)"))]
        self.assertIn("classicMediaSpatialGridEpoch = -1", mount)
        self.assertIn("scheduleClassicMediaQueue()", mount)
        self.assertIn("classicMediaSpatialGridEpoch = -1", unmount)
        self.assertIn("scheduleClassicMediaQueue()", unmount)

    def test_inactive_eager_canvas_manager_does_not_start_editor_prewarm(self):
        self.assertIn("sourceFrame.classList.contains('active')", CANVAS_SESSION_HOST_JS)
        self.assertIn("target.src.includes('/static/canvas-list.html')", INDEX_HTML)
        self.assertIn("requestIdleCallback(prewarmCanvasEditor", INDEX_HTML)

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
