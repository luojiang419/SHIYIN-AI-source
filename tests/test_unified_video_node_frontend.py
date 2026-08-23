import unittest
from pathlib import Path


class UnifiedVideoNodeFrontendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.html = (root / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.javascript = (root / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.styles = (root / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
        cls.settings_html = (root / "static" / "api-settings.html").read_text(encoding="utf-8")
        cls.settings_javascript = (root / "static" / "js" / "api-settings.js").read_text(encoding="utf-8")

    def test_unified_entry_replaces_separate_h3_entry(self):
        self.assertEqual(self.html.count('onclick="addVideoNode()"'), 1)
        self.assertEqual(self.html.count("menuAdd('video')"), 1)
        self.assertNotIn('onclick="addH3VideoNode()"', self.html)
        self.assertNotIn("menuAdd('h3-video')", self.html)

    def test_kling_capability_state_and_management_actions_exist(self):
        self.assertIn("let klingCliState =", self.javascript)
        self.assertIn("/api/kling-cli/capabilities", self.javascript)
        self.assertIn("/api/kling-cli/install", self.javascript)
        self.assertIn("/api/kling-cli/login", self.javascript)
        self.assertIn("function klingCapabilityModeForNode", self.javascript)

    def test_model_specific_panels_do_not_share_parameters(self):
        self.assertIn("function h3VideoSettingsHtml", self.javascript)
        self.assertIn("function klingVideoSettingsHtml", self.javascript)
        self.assertIn("function legacyVideoSettingsHtml", self.javascript)
        self.assertIn("model_parameters:isKling", self.javascript)
        self.assertIn("node.modelParameters = {}", self.javascript)

    def test_dynamic_kling_arguments_are_rendered_from_schema(self):
        self.assertIn("allowed_values", self.javascript)
        self.assertIn("data-kling-parameter", self.javascript)
        self.assertIn("kling-connection-panel", self.styles)
        self.assertIn(".video-input-actions[hidden] { display:none; }", self.styles)

    def test_kling_defaults_to_video_3_omni_and_does_not_expand_legacy_models(self):
        self.assertIn("node.model = preferredKlingOmniModel(node);", self.javascript)
        self.assertIn(
            "if(normalizedAllowedValues.length && !normalizedAllowedValues.includes(value))",
            self.javascript,
        )
        self.assertNotIn(
            "Array.from({length:13},(_,index)=>String(index + 3))",
            self.javascript,
        )

    def test_api_settings_preserves_kling_as_a_fixed_protocol(self):
        self.assertIn('<option value="kling-cli">', self.settings_html)
        self.assertIn("'kling-cli'", self.settings_javascript)
        self.assertIn("item.id === 'kling-cli'", self.settings_javascript)

    def test_h3_and_kling_tasks_are_saved_and_resumed_after_canvas_reload(self):
        self.assertIn("/api/canvas-video-tasks", self.javascript)
        self.assertIn("canvasTaskType:'online-video'", self.javascript)
        self.assertIn("function resumeCanvasVideoTasks()", self.javascript)
        self.assertIn("resumeCanvasVideoTasks();", self.javascript)
        self.assertIn("await saveCanvas();\n            const task = await createCanvasVideoTask", self.javascript)
        self.assertIn("node._videoPending", self.javascript)


if __name__ == "__main__":
    unittest.main()
