import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch


class MemoryTaskDatabase:
    def __init__(self, tasks=None):
        self.tasks = {str(item["id"]): dict(item) for item in (tasks or [])}

    def load_tasks(self, kind):
        return list(self.tasks.values()) if kind == "canvas_video" else []

    def upsert_task(self, kind, task):
        if kind == "canvas_video":
            self.tasks[str(task["id"])] = dict(task)

    def delete_task(self, kind, task_id):
        return self.tasks.pop(str(task_id), None) is not None

    def save_tasks(self, kind, tasks):
        if kind == "canvas_video":
            self.tasks = {str(item["id"]): dict(item) for item in tasks}

    def next_revision(self, topic, entity_id):
        return 1


class CanvasVideoTaskRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def setUp(self):
        self.main.CANVAS_VIDEO_TASKS.clear()
        self.main.CANVAS_VIDEO_TASKS_LOADED_ACCOUNTS.clear()
        self.main.CANVAS_VIDEO_TASK_RUNNERS.clear()

    def tearDown(self):
        for runner in list(self.main.CANVAS_VIDEO_TASK_RUNNERS.values()):
            runner.cancel()
        self.main.CANVAS_VIDEO_TASK_RUNNERS.clear()
        self.main.CANVAS_VIDEO_TASKS.clear()
        self.main.CANVAS_VIDEO_TASKS_LOADED_ACCOUNTS.clear()

    def test_restart_keeps_upstream_id_recoverable_and_does_not_resubmit(self):
        now = time.time()
        database = MemoryTaskDatabase([
            {
                "id": "canvas_video_saved",
                "task_id": "canvas_video_saved",
                "status": "running",
                "provider_id": "kling-cli",
                "upstream_task_id": "generation-saved",
                "created_at": now - 30,
                "updated_at": now - 10,
                "_account_id": "admin",
            },
            {
                "id": "canvas_video_unknown",
                "task_id": "canvas_video_unknown",
                "status": "submitting",
                "provider_id": "kling-cli",
                "upstream_task_id": "",
                "created_at": now - 20,
                "updated_at": now - 5,
                "_account_id": "admin",
            },
        ])

        with patch.object(self.main, "DATABASE", database):
            self.main.load_canvas_video_tasks_from_disk()

        recovered = self.main.CANVAS_VIDEO_TASKS["canvas_video_saved"]
        interrupted = self.main.CANVAS_VIDEO_TASKS["canvas_video_unknown"]
        self.assertEqual(recovered["status"], "recovery_pending")
        self.assertEqual(recovered["upstream_task_id"], "generation-saved")
        self.assertEqual(interrupted["status"], "interrupted")
        self.assertIn("不会自动重新提交", interrupted["error"])

    def test_recovered_task_downloads_once_and_becomes_succeeded(self):
        now = time.time()
        task = {
            "id": "canvas_video_finish",
            "task_id": "canvas_video_finish",
            "type": "online-video",
            "status": "recovery_pending",
            "provider_id": "kling-cli",
            "upstream_task_id": "generation-finish",
            "created_at": now - 30,
            "updated_at": now,
            "result": None,
            "error": "",
            "_account_id": "admin",
        }
        database = MemoryTaskDatabase([task])
        self.main.CANVAS_VIDEO_TASKS[task["id"]] = dict(task)

        with (
            patch.object(self.main, "DATABASE", database),
            patch.object(
                self.main,
                "query_canvas_video_upstream",
                new=AsyncMock(return_value={
                    "status": "succeeded",
                    "url": "https://cdn.example/recovered.mp4",
                    "raw": {"status": "COMPLETED"},
                }),
            ) as query,
            patch.object(
                self.main,
                "save_remote_video_to_output",
                new=AsyncMock(return_value="/assets/output/recovered.mp4"),
            ) as download,
        ):
            asyncio.run(self.main.run_canvas_video_task("canvas_video_finish"))

        finished = self.main.CANVAS_VIDEO_TASKS["canvas_video_finish"]
        self.assertEqual(finished["status"], "succeeded")
        self.assertEqual(finished["result"]["videos"], ["/assets/output/recovered.mp4"])
        query.assert_awaited_once()
        download.assert_awaited_once()

    def test_create_persists_upstream_id_before_polling_starts(self):
        database = MemoryTaskDatabase()
        payload = self.main.CanvasVideoTaskRequest(
            task_id="canvas_video_client_1",
            canvas_id="canvas-1",
            node_id="video-1",
            prompt="持久化后再轮询",
            provider_id="kling-cli",
            model="kling-video-v3_0",
        )
        provider = {"id": "kling-cli", "protocol": "kling-cli", "base_url": ""}

        with (
            patch.object(self.main, "DATABASE", database),
            patch.object(self.main, "get_api_provider", return_value=provider),
            patch.object(
                self.main,
                "submit_canvas_video_upstream",
                new=AsyncMock(return_value={
                    "upstream_task_id": "generation-persisted",
                    "status": "submitted",
                    "credits_consumed": 5,
                }),
            ),
            patch.object(self.main, "start_canvas_video_task_runner") as start_runner,
        ):
            created = asyncio.run(self.main.create_canvas_video_task(payload))

        self.assertEqual(created["status"], "running")
        self.assertEqual(created["upstream_task_id"], "generation-persisted")
        self.assertEqual(database.tasks["canvas_video_client_1"]["upstream_task_id"], "generation-persisted")
        start_runner.assert_called_once_with("canvas_video_client_1")


if __name__ == "__main__":
    unittest.main()
