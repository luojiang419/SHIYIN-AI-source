import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from canvas_core.data_layout import DataLayout
from canvas_core.maintenance import MaintenanceManager
from canvas_core.paths import AppPaths


class MaintenanceTests(unittest.TestCase):
    def test_cache_temp_and_logs_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "app"
            paths = AppPaths(root, app_root, root / "data", app_root / "web", app_root / "workflows")
            layout = DataLayout.from_app_paths(paths)
            layout.ensure()
            layout.app_config.write_text(json.dumps({"cache_max_bytes": 8}), encoding="utf-8")

            old_cache = layout.cache_previews / "old.bin"
            new_cache = layout.cache_downloads / "new.bin"
            old_cache.write_bytes(b"a" * 8)
            new_cache.write_bytes(b"b" * 8)
            now = time.time()
            os.utime(old_cache, (now - 10, now - 10))
            os.utime(new_cache, (now, now))

            stale_temp = layout.temp / "stale.tmp"
            stale_temp.write_text("stale", encoding="utf-8")
            os.utime(stale_temp, (now - 90000, now - 90000))

            log = layout.logs / "canvas.log"
            log.write_bytes(b"x" * 32)
            manager = MaintenanceManager(layout)
            manager._rotate_logs(max_bytes=16, backups=2)
            report = manager.run_once()

            self.assertFalse(old_cache.exists())
            self.assertTrue(new_cache.exists())
            self.assertFalse(stale_temp.exists())
            self.assertTrue((layout.logs / "canvas.log.1").exists())
            self.assertLessEqual(report["cache"]["remaining_bytes"], 8)
            self.assertEqual(report["status"], "complete")
            self.assertEqual(manager.latest_report(), report)

    def test_report_is_pending_until_first_background_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "app"
            paths = AppPaths(root, app_root, root / "data", app_root / "web", app_root / "workflows")
            layout = DataLayout.from_app_paths(paths)
            layout.ensure()
            manager = MaintenanceManager(layout)

            report = manager.latest_report()

            self.assertEqual(report["status"], "pending")
            self.assertEqual(report["completed_at"], 0)
            report["status"] = "mutated"
            self.assertEqual(manager.latest_report()["status"], "pending")

    def test_failed_run_is_visible_in_latest_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            app_root = root / "app"
            paths = AppPaths(root, app_root, root / "data", app_root / "web", app_root / "workflows")
            layout = DataLayout.from_app_paths(paths)
            layout.ensure()
            manager = MaintenanceManager(layout)
            manager._trim_cache = lambda: (_ for _ in ()).throw(OSError("disk unavailable"))

            with self.assertRaisesRegex(OSError, "disk unavailable"):
                manager.run_once()

            report = manager.latest_report()
            self.assertEqual(report["status"], "error")
            self.assertIn("disk unavailable", report["error"])
            self.assertGreater(report["completed_at"], 0)


if __name__ == "__main__":
    unittest.main()
