import unittest
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SMART_CANVAS_JS = ROOT / "static" / "js" / "smart-canvas.js"
CANVAS_JS = ROOT / "static" / "js" / "canvas.js"
ECOMMERCE_JS = ROOT / "static" / "js" / "ecommerce.js"
API_SETTINGS_JS = ROOT / "static" / "js" / "api-settings.js"
ASSET_MANAGER_JS = ROOT / "static" / "js" / "asset-manager.js"
INDEX_HTML = ROOT / "static" / "index.html"
SMART_CANVAS_CSS = ROOT / "static" / "css" / "smart-canvas.css"
CANVAS_CSS = ROOT / "static" / "css" / "canvas.css"
ECOMMERCE_CSS = ROOT / "static" / "css" / "ecommerce.css"
TAILWIND_CSS = ROOT / "static" / "vendor" / "css" / "tailwind.generated.css"
TAILWIND_RUNTIME = ROOT / "static" / "vendor" / "js" / "tailwindcss-cdn.js"
TAILWIND_PAGES = (
    ROOT / "static" / "index.html",
    ROOT / "static" / "canvas-list.html",
    ROOT / "static" / "canvas.html",
    ROOT / "static" / "gpt-chat.html",
    ROOT / "static" / "api-settings.html",
)


class RuntimeGrowthContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smart_source = SMART_CANVAS_JS.read_text(encoding="utf-8")
        cls.canvas_source = CANVAS_JS.read_text(encoding="utf-8")
        cls.ecommerce_source = ECOMMERCE_JS.read_text(encoding="utf-8")
        cls.api_settings_source = API_SETTINGS_JS.read_text(encoding="utf-8")
        cls.asset_manager_source = ASSET_MANAGER_JS.read_text(encoding="utf-8")
        cls.index_source = INDEX_HTML.read_text(encoding="utf-8")
        cls.smart_css = SMART_CANVAS_CSS.read_text(encoding="utf-8")
        cls.canvas_css = CANVAS_CSS.read_text(encoding="utf-8")
        cls.ecommerce_css = ECOMMERCE_CSS.read_text(encoding="utf-8")

    def test_canvas_media_and_logs_have_explicit_limits(self):
        self.assertIn("SMART_NODE_MEDIA_LIMIT = 96", self.smart_source)
        self.assertIn("SMART_HISTORY_MEDIA_LIMIT = 48", self.smart_source)
        self.assertIn("SMART_GENERATION_LOG_LIMIT = 120", self.smart_source)
        self.assertIn("boundedSmartNodeImages", self.smart_source)
        self.assertIn("boundedSmartHistoryImages", self.smart_source)
        self.assertIn("CANVAS_OUTPUT_MEDIA_LIMIT = 96", self.canvas_source)
        self.assertIn("CANVAS_GENERATION_LOG_LIMIT = 120", self.canvas_source)
        self.assertIn("pruneCanvasRuntimeCollections", self.canvas_source)

    def test_ecommerce_frontend_caps_resident_task_history(self):
        self.assertIn("ECOMMERCE_TASK_MEMORY_LIMIT = 300", self.ecommerce_source)
        self.assertIn("function pruneTaskMemory()", self.ecommerce_source)
        self.assertIn("/api/ecommerce/tasks?limit=500", self.ecommerce_source)

    def test_smart_canvas_uses_indexed_render_and_bounded_undo_memory(self):
        self.assertIn("UNDO_BYTE_LIMIT = 16 * 1024 * 1024", self.smart_source)
        self.assertIn("function appendUndoSnapshot(snapshot)", self.smart_source)
        self.assertIn("const nodeIndex = new Map(nodes.map(node => [node.id, node]))", self.smart_source)
        self.assertIn("function renderConnections(nodeIndex=", self.smart_source)
        self.assertIn("function bindNodeEvents(nodeIndex=", self.smart_source)
        self.assertIn("function measureSmartNodeImages(nodeIndex=", self.smart_source)
        self.assertIn("tpl.content.querySelectorAll('.image-node[data-id]')", self.smart_source)

    def test_smart_canvas_save_is_single_flight_and_coalesces_followups(self):
        self.assertIn("let saveRequestedWhileInFlight = false", self.smart_source)
        self.assertIn("if(canvasSyncInFlight){", self.smart_source)
        self.assertIn("trailingSaveDelay", self.smart_source)
        self.assertIn("scheduleSave(delay)", self.smart_source)

    def test_shell_broadcasts_iframe_route_lifecycle(self):
        self.assertIn("function syncRouteStateToFrame(iframe)", self.index_source)
        self.assertIn("type:'studio-route-active'", self.index_source)
        self.assertIn("broadcastRouteState();", self.index_source)
        self.assertIn("syncRouteStateToFrame(f);", self.index_source)

    def test_shell_can_unload_idle_iframes(self):
        self.assertIn("IFRAME_IDLE_UNLOAD_MS = 15 * 60 * 1000", self.index_source)
        self.assertIn("function maybeUnloadIdleFrames()", self.index_source)
        self.assertIn("item.frame.removeAttribute('src')", self.index_source)
        self.assertIn("studio-dirty-state", self.index_source)

    def test_background_pages_pause_recoverable_work(self):
        self.assertIn("function setSmartRouteActive(active)", self.smart_source)
        self.assertIn("stopCanvasMetaPoll();", self.smart_source)
        self.assertIn("function setCanvasRouteActive(active)", self.canvas_source)
        self.assertIn("stopCanvasRemotePolling();", self.canvas_source)
        self.assertIn("function setEcommerceRouteActive(active)", self.ecommerce_source)
        self.assertIn("if(!state.routeActive || document.hidden || !state.activeTaskIds.size) return", self.ecommerce_source)
        self.assertIn("function resumeJimengLoginPolling()", self.api_settings_source)
        self.assertIn("apiSettingsRouteActive = Boolean(event.data.active)", self.api_settings_source)

    def test_tailwind_is_precompiled_instead_of_observing_runtime_dom(self):
        self.assertTrue(TAILWIND_CSS.is_file())
        self.assertGreater(TAILWIND_CSS.stat().st_size, 1_000)
        self.assertLess(TAILWIND_CSS.stat().st_size, 50_000)
        self.assertFalse(TAILWIND_RUNTIME.exists())
        for page in TAILWIND_PAGES:
            source = page.read_text(encoding="utf-8")
            self.assertIn("/static/vendor/css/tailwind.generated.css", source, page.name)
            self.assertNotIn("tailwindcss-cdn.js", source, page.name)
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["devDependencies"]["tailwindcss"], "3.4.17")
        self.assertIn("tailwindcss/lib/cli.js", package["scripts"]["css:build"])

    def test_asset_manager_defers_heavy_tabs_until_selected(self):
        load_all = re.search(r"async function loadAll\(\)\{(?P<body>.*?)\n\}", self.asset_manager_source, re.S)
        self.assertIsNotNone(load_all)
        self.assertNotIn("loadLocalAssets()", load_all.group("body"))
        self.assertNotIn("/api/canvas-assets", load_all.group("body"))
        self.assertIn("async function ensureTabData(tab=activeTab)", self.asset_manager_source)
        self.assertIn("await Promise.all([loadSharedFolders(), loadLocalAssets()])", self.asset_manager_source)

    def test_persistent_full_size_layers_avoid_blur_compositing(self):
        iframe_rule = re.search(r"iframe\s*\{(?P<body>.*?)\}", self.index_source, re.S)
        self.assertIsNotNone(iframe_rule)
        self.assertIn("visibility: hidden", iframe_rule.group("body"))
        self.assertIn("filter: none", iframe_rule.group("body"))
        self.assertNotIn("transition: all", iframe_rule.group("body"))
        panel_rule = re.search(r"\.panel\s*\{(?P<body>.*?)\}", self.canvas_css, re.S)
        self.assertIsNotNone(panel_rule)
        self.assertNotIn("backdrop-filter", panel_rule.group("body"))
        self.assertIn("background:var(--card-solid)", panel_rule.group("body"))
        self.assertIn("持续可见的大面积面板使用不透明底色", self.ecommerce_css)
        self.assertIn(".ec-compare-backdrop {\n    display:none;", self.ecommerce_css)
        self.assertIn("background:rgba(252,247,241,.96)", self.smart_css)


class BackendTaskPoolContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def test_pruning_removes_oldest_terminal_tasks_and_keeps_active_work(self):
        tasks = {
            f"task-{index}": {
                "id": f"task-{index}",
                "status": "running" if index < 3 else "succeeded",
                "updated_at": index,
            }
            for index in range(305)
        }
        removed = self.main.prune_task_map_locked(tasks, {"queued", "running"}, 300)
        self.assertEqual(removed, [f"task-{index}" for index in range(3, 8)])
        self.assertEqual(len(tasks), 300)
        self.assertTrue(all(f"task-{index}" in tasks for index in range(3)))

    def test_pruning_never_evicts_active_tasks_to_force_the_limit(self):
        tasks = {
            f"task-{index}": {
                "id": f"task-{index}",
                "status": "running",
                "updated_at": index,
            }
            for index in range(4)
        }
        self.assertEqual(self.main.prune_task_map_locked(tasks, {"running"}, 2), [])
        self.assertEqual(len(tasks), 4)


if __name__ == "__main__":
    unittest.main()
