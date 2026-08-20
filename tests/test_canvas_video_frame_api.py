import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasVideoFrameApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "main.py").read_text(encoding="utf-8")

    def test_backend_exposes_probe_capabilities_and_async_lifecycle(self):
        for marker in (
            '@app.get("/api/canvas-tools/video-frames/capabilities")',
            '@app.post("/api/canvas-tools/video-frames/probe")',
            '@app.post("/api/canvas-video-frame-tasks")',
            '@app.get("/api/canvas-video-frame-tasks/{task_id}")',
            '@app.post("/api/canvas-video-frame-tasks/{task_id}/cancel")',
        ):
            self.assertIn(marker, self.source)
        self.assertIn("canvas_video_frame_directory", self.source)
        self.assertIn("register_internal_media_object(url, \"output\", \"image\", \"canvas-video-frame\")", self.source)

    def test_task_result_contains_provenance_fields(self):
        for field in ("source_video_url", "source_video_node_id", "extract_run_id", "derived_operation"):
            self.assertIn(f'"{field}"', self.source)

    def test_frontend_creates_right_side_derived_group_and_cleans_old_results(self):
        javascript = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        self.assertIn("function removeVideoFrameDerivedResults", javascript)
        self.assertIn("function createVideoFrameGroupFromResult", javascript)
        self.assertIn("derivedOperation:'video-frame-extraction'", javascript)
        self.assertIn("kind:'derived'", javascript)
        self.assertIn("sourceNode.x + sourceRect.w + 120", javascript)


if __name__ == "__main__":
    unittest.main()
