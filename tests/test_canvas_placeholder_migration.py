import tempfile
import unittest
from pathlib import Path

from canvas_core.canvas_placeholder_migration import (
    ORPHAN_OUTPUT_PENDING_MIGRATION_SETTING,
    migrate_orphan_output_pending_once,
)
from canvas_core.database import CanvasDatabase


ROOT = Path(__file__).resolve().parents[1]


def canvas(canvas_id: str, nodes, *, deleted_at: int = 0):
    return {
        "id": canvas_id,
        "title": canvas_id,
        "project": "default",
        "kind": "classic",
        "updated_at": 1,
        "deleted_at": deleted_at,
        "nodes": nodes,
        "connections": [],
    }


class CanvasPlaceholderMigrationTests(unittest.TestCase):
    def create_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        database = CanvasDatabase(Path(temp_dir.name) / "canvas.db")
        database.initialize()
        return database

    def test_migration_removes_only_nonrecoverable_output_placeholders(self):
        database = self.create_database()
        database.save_canvas(canvas("active", [
            {
                "id": "output-active",
                "type": "output",
                "_pending": [
                    {"id": "orphan"},
                    {"id": "recoverable-local", "canvasTaskId": "task-123"},
                    {"id": "recoverable-upstream", "recoverTaskId": "submit-456"},
                ],
            },
            {"id": "not-output", "type": "image", "_pending": [{"id": "leave-alone"}]},
        ]), touch=False)
        database.save_canvas(canvas("trashed", [
            {"id": "output-trash", "type": "output", "_pending": [{"id": "stale"}]},
        ], deleted_at=99), touch=False)

        report = migrate_orphan_output_pending_once(database, "1.0.272")

        self.assertEqual(report, {
            "removed": 2,
            "canvases": 2,
            "skipped": False,
            "completed_version": "1.0.272",
        })
        active = database.get_canvas("active")
        self.assertEqual(
            [item["id"] for item in active["nodes"][0]["_pending"]],
            ["recoverable-local", "recoverable-upstream"],
        )
        self.assertEqual(active["nodes"][1]["_pending"], [{"id": "leave-alone"}])
        self.assertEqual(database.get_canvas("trashed")["nodes"][0]["_pending"], [])
        marker = database.get_setting(ORPHAN_OUTPUT_PENDING_MIGRATION_SETTING)["value"]
        self.assertTrue(marker["done"])
        self.assertEqual(marker["completed_version"], "1.0.272")

    def test_migration_is_idempotent_after_the_completion_marker(self):
        database = self.create_database()
        database.save_canvas(canvas("first", [
            {"id": "output-first", "type": "output", "_pending": [{"id": "orphan"}]},
        ]), touch=False)

        first = migrate_orphan_output_pending_once(database, "1.0.272")
        database.save_canvas(canvas("later", [
            {"id": "output-later", "type": "output", "_pending": [{"id": "newer-orphan"}]},
        ]), touch=False)
        second = migrate_orphan_output_pending_once(database, "1.0.273")

        self.assertFalse(first["skipped"])
        self.assertEqual(second, {
            "removed": 0,
            "canvases": 0,
            "skipped": True,
            "completed_version": "1.0.272",
        })
        self.assertEqual(database.get_canvas("later")["nodes"][0]["_pending"], [{"id": "newer-orphan"}])

    def test_backend_startup_defers_the_persistent_placeholder_migration(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from canvas_core.canvas_placeholder_migration import migrate_orphan_output_pending_once", source)
        self.assertIn(
            '("orphan_output_cleanup", run_deferred_orphan_output_cleanup)',
            source,
        )


if __name__ == "__main__":
    unittest.main()
