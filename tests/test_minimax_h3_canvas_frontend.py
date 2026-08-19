import unittest
from pathlib import Path


class MiniMaxH3CanvasFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.html = (root / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.javascript = (root / "static" / "js" / "canvas.js").read_text(encoding="utf-8")

    def test_h3_entry_is_merged_into_unified_video_node(self):
        self.assertNotIn('onclick="addH3VideoNode()"', self.html)
        self.assertNotIn("menuAdd('h3-video')", self.html)
        self.assertIn('onclick="addVideoNode()"', self.html)
        self.assertIn("menuAdd('video')", self.html)
        # 保留函数和旧类型路由，兼容历史画布或外部脚本。
        self.assertIn("function addH3VideoNode(point)", self.javascript)
        self.assertIn("if(type === 'h3-video') return addH3VideoNode(point);", self.javascript)
        self.assertIn("node.apiProvider = 'minimax-h3'", self.javascript)
        self.assertIn("node.model = 'MiniMax H3'", self.javascript)

    def test_h3_node_exposes_steps_and_deployed_resolutions(self):
        self.assertIn("data-h3-steps", self.javascript)
        self.assertIn("0.2MP 16:9 - 608x352", self.javascript)
        self.assertIn("0.4MP 9:16 - 480x864", self.javascript)

    def test_h3_request_preserves_local_multimodal_references(self):
        self.assertIn("const isH3 = isMiniMaxH3VideoNode(node);", self.javascript)
        self.assertIn("videos:isH3", self.javascript)
        self.assertIn("steps:Number(node.steps || 12)", self.javascript)

    def test_h3_status_is_checked_before_generation(self):
        self.assertIn("/api/minimax-h3/status", self.javascript)
        self.assertIn("await loadMiniMaxH3Status();", self.javascript)
        self.assertIn("if(!minimaxH3State.generationEnabled)", self.javascript)

    def test_api_settings_keeps_h3_as_a_fixed_protocol(self):
        root = Path(__file__).resolve().parent.parent
        settings_html = (root / "static" / "api-settings.html").read_text(encoding="utf-8")
        settings_js = (root / "static" / "js" / "api-settings.js").read_text(encoding="utf-8")
        self.assertIn('<option value="minimax-h3">', settings_html)
        self.assertIn("'minimax-h3'", settings_js)
        self.assertIn("item.id === 'minimax-h3'", settings_js)


if __name__ == "__main__":
    unittest.main()
