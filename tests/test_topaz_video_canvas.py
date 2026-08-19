import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
TOPAZ_JS = (ROOT / "static" / "js" / "canvas-topaz-node.js").read_text(encoding="utf-8")
TOPAZ_CSS = (ROOT / "static" / "css" / "canvas-topaz-node.css").read_text(encoding="utf-8")


class TopazVideoCanvasTests(unittest.TestCase):
    def test_page_loads_topaz_node_assets_and_creation_entries(self):
        self.assertIn("/static/css/canvas-topaz-node.css", HTML)
        self.assertIn("/static/js/canvas-topaz-node.js", HTML)
        self.assertIn("onclick=\"addTopazVideoNode()\"", HTML)
        self.assertIn("menuAdd('topazVideo')", HTML)

    def test_node_face_has_exactly_three_common_controls(self):
        common_keys = re.findall(r'data-topaz-common="([^"]+)"', TOPAZ_JS)
        self.assertEqual(common_keys.count("model"), 1)
        self.assertEqual(common_keys.count("target"), 2)  # markup plus selected-value binding
        self.assertEqual(common_keys.count("quality"), 2)
        markup_keys = re.findall(
            r'<select data-topaz-common="([^"]+)"',
            TOPAZ_JS,
        )
        self.assertEqual(markup_keys, ["model", "target", "quality"])

    def test_detailed_parameters_open_in_a_body_level_modal(self):
        self.assertIn('data-topaz-advanced-open', TOPAZ_JS)
        self.assertIn("function openTopazAdvancedSettings(nodeId)", TOPAZ_JS)
        self.assertIn("document.body.appendChild(modal)", TOPAZ_JS)
        self.assertIn('role="dialog" aria-modal="true"', TOPAZ_JS)
        for key in (
            "preblur", "noise", "details", "halo", "blur", "compression",
            "pre_noise", "blend", "grain", "grain_size",
        ):
            self.assertIn(f"topazRangeField('{key}'", TOPAZ_JS)
        for key in (
            "estimate", "device",
            "vram", "instances", "encoder", "audio_mode", "audio_bitrate_kbps",
            "color_correction", "download_models",
        ):
            self.assertIn(f'data-topaz-advanced="{key}"', TOPAZ_JS)
        self.assertIn(".topaz-advanced-modal{position:fixed;inset:0;z-index:520", TOPAZ_CSS)
        self.assertIn(".topaz-advanced-dialog{width:min(720px", TOPAZ_CSS)

    def test_encoder_defaults_to_auto_and_migrates_legacy_h264_default(self):
        self.assertIn("encoder:'auto'", TOPAZ_JS)
        self.assertIn("savedAdvanced.encoder === 'h264_nvenc'", TOPAZ_JS)
        self.assertIn('<option value="auto">', TOPAZ_JS)

    def test_canvas_lifecycle_and_pipeline_are_integrated(self):
        self.assertIn("'topazVideo'", CANVAS_JS)
        self.assertIn("renderTopazVideoBody(node)", CANVAS_JS)
        self.assertIn("runTopazVideoNode(node.id, runOpts)", CANVAS_JS)
        self.assertIn("resumeTopazVideoTasks();", CANVAS_JS)
        self.assertIn("cancelTopazVideoTask(id)", CANVAS_JS)
        self.assertRegex(CANVAS_JS, r"CANVAS_MEDIA_OUTPUT_TYPES\s*=.*?'topazVideo'")

    def test_frontend_uses_local_task_api(self):
        self.assertIn("/api/topaz-video/capabilities", TOPAZ_JS)
        self.assertIn("/api/topaz-video/tasks", TOPAZ_JS)
        self.assertIn("method:'POST'", TOPAZ_JS)
        self.assertIn("input_url:input.url", TOPAZ_JS)
        self.assertIn("advanced:{...node.topazAdvanced}", TOPAZ_JS)


if __name__ == "__main__":
    unittest.main()
