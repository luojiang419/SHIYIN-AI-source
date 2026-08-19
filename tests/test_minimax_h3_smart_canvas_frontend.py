import unittest
from pathlib import Path


class MiniMaxH3SmartCanvasFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.html = (root / "static" / "smart-canvas.html").read_text(encoding="utf-8")
        cls.javascript = (root / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")

    def test_create_menu_contains_dedicated_h3_node(self):
        self.assertIn('data-create-type="h3-video"', self.html)
        self.assertIn("function createH3VideoNode(point)", self.javascript)
        self.assertIn("videoProvider:'minimax-h3'", self.javascript)
        self.assertIn("videoModel:'MiniMax H3'", self.javascript)

    def test_h3_settings_include_steps_and_deployed_resolutions(self):
        self.assertIn("videoSteps:12", self.javascript)
        self.assertIn("function renderH3VideoResolutionControl()", self.javascript)
        self.assertIn("0.4MP 9:16 - 480x864", self.javascript)

    def test_smart_h3_request_sends_local_reference_videos_and_steps(self):
        self.assertIn("const isH3 = isMiniMaxH3SmartSettings(runSettings);", self.javascript)
        self.assertIn("videos: refVideos", self.javascript)
        self.assertIn("steps: Math.max(4, Math.min(30, Number(runSettings.videoSteps) || 12))", self.javascript)

    def test_smart_h3_status_is_checked_before_generation(self):
        self.assertIn("/api/minimax-h3/status", self.javascript)
        self.assertIn("await loadSmartMiniMaxH3Status();", self.javascript)
        self.assertIn("if(!smartMiniMaxH3State.generationEnabled)", self.javascript)


if __name__ == "__main__":
    unittest.main()
