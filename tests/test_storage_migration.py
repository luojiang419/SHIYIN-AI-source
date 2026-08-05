import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canvas_core.data_layout import DataLayout
from canvas_core.database import CanvasDatabase
from canvas_core.migration import LegacyMigrator
from canvas_core.paths import AppPaths


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class StorageMigrationTests(unittest.TestCase):
    def test_legacy_data_is_migrated_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "static").mkdir()
            (root / "workflows" / "custom").mkdir(parents=True)
            write_json(root / "data" / "api_providers.json", [{"id": "demo", "name": "Demo", "enabled": True}])
            write_json(root / "data" / "projects.json", {"projects": [{"id": "default", "name": "默认项目"}]})
            write_json(root / "data" / "canvases" / "canvas-1.json", {
                "id": "canvas-1", "title": "测试", "kind": "smart", "project": "default", "updated_at": 10,
            })
            write_json(root / "history.json", [{"timestamp": 1.5, "type": "online", "images": ["/assets/output/a.png"]}])
            write_json(root / "data" / "asset_library.json", {"libraries": [], "updated_at": 1})
            write_json(root / "data" / "online_image_tasks.json", {"tasks": [{"id": "task-1", "status": "done"}]})
            (root / "assets" / "input").mkdir(parents=True)
            (root / "assets" / "input" / "sample.png").write_bytes(b"sample-media")
            (root / "API").mkdir()
            (root / "API" / ".env").write_text("DEMO_KEY=secret\n", encoding="utf-8")
            (root / "workflows" / "custom" / "demo.json").write_text("{}", encoding="utf-8")

            paths = AppPaths.discover(environ={}, module_file=root / "canvas_core" / "paths.py", executable=root / "python.exe", frozen=False)
            layout = DataLayout.from_app_paths(paths)
            layout.ensure()
            database = CanvasDatabase(layout.database_file)
            database.initialize()
            report = LegacyMigrator(paths, layout, database).run()

            self.assertEqual(report["status"], "complete")
            self.assertEqual(database.get_canvas("canvas-1")["title"], "测试")
            self.assertEqual(len(database.load_providers()), 1)
            self.assertEqual(len(database.list_history("online")), 1)
            self.assertEqual(len(database.load_tasks("online_image")), 1)
            self.assertTrue((layout.media_input / "sample.png").is_file())
            self.assertTrue((layout.workflow_custom / "demo.json").is_file())
            self.assertTrue(layout.secret_env.is_file())
            self.assertFalse((root / "history.json").exists())
            self.assertEqual(database.pragma_summary()["journal_mode"].lower(), "wal")

            second_report = LegacyMigrator(paths, layout, database).run()
            self.assertEqual(second_report["completed_at"], report["completed_at"])
            self.assertEqual(database.counts()["canvases"], 1)

    def test_canvas_and_history_crud(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = CanvasDatabase(Path(tmp) / "canvas.db")
            database.initialize()
            canvas = {"id": "c1", "title": "A", "project": "default", "kind": "classic", "updated_at": 1}
            database.save_canvas(canvas, touch=False)
            self.assertEqual(database.get_canvas("c1")["revision"], 1)
            canvas["title"] = "B"
            database.save_canvas(canvas, touch=False)
            self.assertEqual(database.get_canvas("c1")["revision"], 2)
            database.prepend_history({"timestamp": 2.5, "type": "online", "images": ["x"]})
            removed = database.delete_history_timestamp(2.5)
            self.assertEqual(removed["images"], ["x"])
            self.assertEqual(database.list_history(), [])

    def test_tasks_support_incremental_upsert_and_pruning(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = CanvasDatabase(Path(tmp) / "canvas.db")
            database.initialize()
            for index in range(6):
                database.upsert_task("ecommerce", {"id": f"task-{index}", "status": "queued", "updated_at": index})
            database.upsert_task("ecommerce", {"id": "task-5", "status": "succeeded", "updated_at": 10})
            tasks = database.load_tasks("ecommerce")
            self.assertEqual(len(tasks), 6)
            self.assertEqual(tasks[0]["id"], "task-5")
            self.assertEqual(tasks[0]["status"], "succeeded")
            database.prune_tasks("ecommerce", 3)
            self.assertEqual(len(database.load_tasks("ecommerce")), 3)
            self.assertTrue(database.delete_task("ecommerce", "task-5"))
            self.assertFalse(database.delete_task("ecommerce", "task-5"))
            self.assertNotIn("task-5", [item["id"] for item in database.load_tasks("ecommerce")])

    def test_local_asset_and_media_indexes_are_queryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / "media" / "generated" / "a.png"
            media.parent.mkdir(parents=True)
            media.write_bytes(b"image")
            database = CanvasDatabase(root / "canvas.db")
            database.initialize()
            database.replace_local_asset_index([
                {"id": "tops/a.png", "file": "tops/a.png", "folder": "tops", "name": "A", "url": "/assets/uploads/tops/a.png", "kind": "image", "size": 5, "created_at": 2},
                {"id": "tops/b.png", "file": "tops/b.png", "folder": "tops", "name": "B", "url": "/assets/uploads/tops/b.png", "kind": "image", "size": 5, "created_at": 1},
            ])
            page = database.list_local_asset_items(folder="tops", limit=1)
            self.assertEqual(page["total"], 2)
            self.assertEqual(page["items"][0]["id"], "tops/a.png")
            self.assertTrue(page["next_cursor"])
            database.upsert_media_object(url="/assets/output/a.png", path=str(media), category="output", kind="image", source="test")
            summary = database.media_storage_summary()
            self.assertEqual(summary["categories"]["output"]["count"], 1)
            self.assertEqual(summary["categories"]["output"]["bytes"], 5)

    def test_work_items_fts_search_is_queryable_and_synced(self):
        with tempfile.TemporaryDirectory() as tmp:
            database = CanvasDatabase(Path(tmp) / "canvas.db")
            database.initialize()
            database.prepend_history({
                "id": "history-red",
                "type": "ecommerce",
                "timestamp": 20,
                "prompt": "red coat campaign",
                "images": ["/output/red.png"],
            })
            database.prepend_history({
                "id": "history-blue",
                "type": "ecommerce",
                "timestamp": 10,
                "prompt": "blue shoes campaign",
                "images": ["/output/blue.png"],
            })
            with database.connect() as connection:
                self.assertIsNotNone(connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='work_items_fts'"
                ).fetchone())
            red = database.list_work_items(search="red campaign", limit=10)
            self.assertEqual(red["total"], 1)
            self.assertEqual(red["items"][0]["history_id"], "history-red")

            work_id = red["items"][0]["id"]
            database.update_work_item_metadata(work_id, {"name": "midnight archive", "updated_at": 30})
            renamed = database.list_work_items(search="midnight archive", limit=10)
            self.assertEqual(renamed["total"], 1)
            self.assertEqual(renamed["items"][0]["id"], work_id)

            database.delete_history_ids(["history-red"])
            removed = database.list_work_items(search="midnight archive", limit=10)
            self.assertEqual(removed["total"], 0)


if __name__ == "__main__":
    unittest.main()
