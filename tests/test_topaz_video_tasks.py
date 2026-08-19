import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from canvas_core.topaz_video import TopazInstallation, TopazSignature


class MemoryTopazTaskDatabase:
    def __init__(self, tasks=None):
        self.tasks = {str(item["id"]): dict(item) for item in (tasks or [])}

    def load_tasks(self, kind):
        return list(self.tasks.values()) if kind == "topaz_video" else []

    def upsert_task(self, kind, task):
        if kind == "topaz_video":
            self.tasks[str(task["id"])] = dict(task)

    def delete_task(self, kind, task_id):
        return self.tasks.pop(str(task_id), None) is not None if kind == "topaz_video" else False

    def save_tasks(self, kind, tasks):
        if kind == "topaz_video":
            self.tasks = {str(item["id"]): dict(item) for item in tasks}

    def next_revision(self, topic, entity_id):
        return 1


class TopazVideoTaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def setUp(self):
        self.main.TOPAZ_VIDEO_TASKS.clear()
        self.main.TOPAZ_VIDEO_TASKS_LOADED_ACCOUNTS.clear()
        self.main.TOPAZ_VIDEO_TASK_RUNNERS.clear()
        self.main.TOPAZ_VIDEO_PROCESSES.clear()

    def tearDown(self):
        for runner in list(self.main.TOPAZ_VIDEO_TASK_RUNNERS.values()):
            runner.cancel()
        self.main.TOPAZ_VIDEO_TASK_RUNNERS.clear()
        self.main.TOPAZ_VIDEO_TASKS.clear()
        self.main.TOPAZ_VIDEO_TASKS_LOADED_ACCOUNTS.clear()
        self.main.TOPAZ_VIDEO_PROCESSES.clear()

    @staticmethod
    def ready_installation(root: Path) -> TopazInstallation:
        model_dir = root / "definitions"
        model_data_dir = root / "model-data"
        model_dir.mkdir()
        model_data_dir.mkdir()
        (model_dir / "tvai.tz").write_bytes(b"definition")
        (model_dir / "prob-4.json").write_text("{}", encoding="utf-8")
        ffmpeg = root / "ffmpeg.exe"
        ffprobe = root / "ffprobe.exe"
        ffmpeg.write_bytes(b"exe")
        ffprobe.write_bytes(b"exe")
        return TopazInstallation(
            root,
            ffmpeg,
            ffprobe,
            model_dir,
            model_data_dir,
            TopazSignature("Valid", "CN=Topaz Labs LLC", "7.0.0"),
            True,
        )

    def test_restart_marks_local_process_interrupted_instead_of_resubmitting(self):
        task = {
            "id": "topaz_video_saved",
            "task_id": "topaz_video_saved",
            "status": "running",
            "created_at": time.time() - 20,
            "updated_at": time.time() - 10,
            "_account_id": "admin",
        }
        database = MemoryTopazTaskDatabase([task])
        with patch.object(self.main, "DATABASE", database):
            self.main.load_topaz_video_tasks_from_disk()
        restored = self.main.TOPAZ_VIDEO_TASKS["topaz_video_saved"]
        self.assertEqual(restored["status"], "interrupted")
        self.assertIn("重新运行", restored["error"])

    def test_public_task_never_exposes_local_paths(self):
        public = self.main.public_topaz_video_task(
            {
                "id": "topaz_video_1",
                "status": "running",
                "_input_path": "D:/private/input.mp4",
                "_output_path": "D:/private/output.mp4",
                "_account_id": "admin",
            }
        )
        self.assertEqual(public["task_id"], "topaz_video_1")
        self.assertNotIn("_input_path", public)
        self.assertNotIn("_output_path", public)
        self.assertNotIn("_account_id", public)

    def test_create_validates_internal_video_and_persists_before_runner(self):
        database = MemoryTopazTaskDatabase()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input.mp4"
            source.write_bytes(b"video")
            installation = self.ready_installation(root)
            payload = self.main.TopazUpscaleTaskRequest(
                input_url="/assets/input/input.mp4",
                model="prob-4",
                target="2x",
                quality="balanced",
                canvas_id="canvas-1",
                node_id="topaz-1",
            )
            with (
                patch.object(self.main, "DATABASE", database),
                patch.object(self.main, "normalize_internal_media_url", return_value="/assets/input/input.mp4"),
                patch.object(self.main, "output_file_from_url", return_value=str(source)),
                patch.object(self.main, "current_topaz_installation", return_value=installation),
                patch.object(self.main, "start_topaz_video_task_runner") as start_runner,
            ):
                created = asyncio.run(self.main.create_topaz_video_task(payload))
        self.assertEqual(created["status"], "queued")
        self.assertEqual(created["settings"]["model"], "prob-4")
        self.assertEqual(created["settings"]["target"], "2x")
        self.assertIn(created["id"], database.tasks)
        start_runner.assert_called_once_with(created["id"])

    def test_canceling_queued_task_does_not_start_arbitrary_process(self):
        task = {
            "id": "topaz_video_cancel",
            "task_id": "topaz_video_cancel",
            "status": "queued",
            "created_at": time.time(),
            "updated_at": time.time(),
            "_account_id": "admin",
        }
        database = MemoryTopazTaskDatabase([task])
        self.main.TOPAZ_VIDEO_TASKS[task["id"]] = dict(task)
        self.main.TOPAZ_VIDEO_TASKS_LOADED_ACCOUNTS.add("admin")
        with patch.object(self.main, "DATABASE", database):
            canceled = asyncio.run(self.main.cancel_topaz_video_task(task["id"]))
        self.assertEqual(canceled["status"], "canceled")
        self.assertTrue(canceled["cancel_requested"])

    def test_process_cleanup_terminates_then_waits(self):
        class FakeProcess:
            def __init__(self):
                self.returncode = None
                self.terminated = False
                self.waited = False

            def terminate(self):
                self.terminated = True

            async def wait(self):
                self.waited = True
                self.returncode = 0
                return self.returncode

        process = FakeProcess()
        asyncio.run(self.main.stop_topaz_video_process(process))
        self.assertTrue(process.terminated)
        self.assertTrue(process.waited)
        self.assertEqual(process.returncode, 0)

    def test_process_cleanup_kills_after_grace_timeout(self):
        class StubbornProcess:
            def __init__(self):
                self.returncode = None
                self.terminated = False
                self.killed = False

            def terminate(self):
                self.terminated = True

            def kill(self):
                self.killed = True
                self.returncode = 1

            async def wait(self):
                if self.killed:
                    return self.returncode
                await asyncio.Event().wait()

        process = StubbornProcess()
        asyncio.run(self.main.stop_topaz_video_process(process, grace_seconds=0.01))
        self.assertTrue(process.terminated)
        self.assertTrue(process.killed)
        self.assertEqual(process.returncode, 1)


if __name__ == "__main__":
    unittest.main()
