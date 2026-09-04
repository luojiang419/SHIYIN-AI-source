from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class PoseReferenceRemovalContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = (STATIC / "js" / "canvas-special-nodes.js").read_text(encoding="utf-8")
        cls.classic = (STATIC / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.smart = (STATIC / "js" / "smart-canvas.js").read_text(encoding="utf-8")
        cls.shortcut = (STATIC / "js" / "shortcut-actions.js").read_text(encoding="utf-8")

    def test_dedicated_editor_assets_are_removed(self):
        self.assertFalse((STATIC / "js" / "pose-reference-editor.js").exists())
        self.assertFalse((STATIC / "css" / "pose-reference-editor.css").exists())
        for name in ("canvas.html", "smart-canvas.html"):
            page = (STATIC / name).read_text(encoding="utf-8")
            self.assertNotIn("pose-reference-editor", page)

    def test_dedicated_node_creation_and_binding_are_removed(self):
        for source in (self.classic, self.smart, self.shared, self.shortcut):
            self.assertNotIn("poseReferenceBodyHtml", source)
            self.assertNotIn("bindPoseReference", source)
            self.assertNotIn("createPoseReferenceNode", source)
        self.assertNotIn("type:'poseReference'", self.classic)
        self.assertNotIn("specialType:'pose-reference'", self.smart)
        self.assertNotIn("create.poseReference", self.shortcut)

    def test_action_reference_inputs_for_one_click_replicate_remain(self):
        for source in (self.classic, self.smart, self.shared):
            self.assertIn("pose-reference", source)
        self.assertIn("['pose-reference','动作参考']", self.classic)
        self.assertIn("['pose-reference','动作参考']", self.smart)


if __name__ == "__main__":
    unittest.main()
