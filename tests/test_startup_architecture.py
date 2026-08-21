import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / "static" / "index.html"
MAIN_PY = ROOT / "main.py"
STORAGE_BOOTSTRAP_PY = ROOT / "canvas_core" / "storage_bootstrap.py"


class VisibleShellStartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = INDEX_HTML.read_text(encoding="utf-8")

    def test_boot_screen_replaces_whole_body_visibility_blank(self):
        self.assertNotIn("html.studio-route-booting body {", self.source)
        self.assertIn('id="studio-boot-screen"', self.source)
        self.assertRegex(
            self.source,
            re.compile(
                r"html\.studio-route-booting\s+\.app-shell\s*\{[^}]*visibility\s*:\s*hidden",
                re.S,
            ),
        )
        self.assertIn("html:not(.studio-route-booting) #studio-boot-screen", self.source)

    def test_head_scripts_do_not_block_boot_screen_parsing(self):
        for script in ("theme.js", "focus-guard.js", "i18n.js"):
            self.assertRegex(
                self.source,
                rf'<script\s+defer\s+src="/static/js/{re.escape(script)}[^>]*></script>',
            )

    def test_account_boot_has_timeout_error_and_retry_contract(self):
        self.assertIn("STUDIO_BOOT_TIMEOUT_MS", self.source)
        self.assertIn("new AbortController()", self.source)
        self.assertIn("showStudioBootError(error)", self.source)
        self.assertIn("function retryStudioBoot()", self.source)
        self.assertIn("finishStudioBoot();", self.source)


class DeferredBackendMaintenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MAIN_PY.read_text(encoding="utf-8")
        startup = re.search(
            r"async def startup_event\(\):(?P<body>.*?)(?=\n@app\.)",
            cls.source,
            re.S,
        )
        if startup is None:
            raise AssertionError("startup_event body was not found")
        cls.startup_body = startup.group("body")

    def test_file_scans_and_indexes_are_outside_health_critical_path(self):
        for operation in (
            "migrate_asset_library_into_dirs",
            "migrate_double_extension_uploads",
            "migrate_mislabeled_image_extensions",
            "DATABASE.ensure_work_items_indexed",
            "ensure_local_upload_indexed",
            "reconcile_video_clip_assets",
        ):
            self.assertNotIn(operation, self.startup_body)
        self.assertIn(
            "asyncio.create_task(run_deferred_startup_maintenance())",
            self.startup_body,
        )

    def test_task_recovery_remains_ready_before_health(self):
        self.assertIn("load_online_image_tasks_from_disk", self.startup_body)
        self.assertIn("load_ecommerce_tasks_from_disk", self.startup_body)

    def test_deferred_maintenance_is_observable_and_failure_isolated(self):
        self.assertIn("async def run_deferred_startup_maintenance()", self.source)
        self.assertIn("STARTUP_MAINTENANCE_DELAY_SECONDS", self.source)
        self.assertIn("startup_maintenance_public_state()", self.source)
        self.assertIn('"startup_maintenance": startup_maintenance_public_state()', self.source)

    def test_disposable_storage_scan_is_not_run_during_module_import(self):
        bootstrap = STORAGE_BOOTSTRAP_PY.read_text(encoding="utf-8")
        self.assertNotIn("MAINTENANCE.run_once()", bootstrap)
        self.assertIn('(\"disposable_storage\", MAINTENANCE.run_once)', self.source)

    def test_runtime_info_returns_latest_maintenance_report(self):
        self.assertIn('"maintenance": MAINTENANCE.latest_report()', self.source)


if __name__ == "__main__":
    unittest.main()
