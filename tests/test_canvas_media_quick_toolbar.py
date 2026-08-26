import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasMediaQuickToolbarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.javascript = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")

    def test_output_image_single_click_selects_and_double_click_previews(self):
        bind = re.search(r"function bindOutputWrap\(wrap, node\)\{(?P<body>.*?)\n\}", self.javascript, re.DOTALL)
        self.assertIsNotNone(bind)
        body = bind.group("body")
        self.assertIn("selectOutputMedia(node.id, img.dataset.url, wrap)", body)
        self.assertIn("e.detail >= 2", body)
        self.assertIn("img.ondblclick", body)

    def test_toolbar_supports_image_nodes_and_exact_output_images(self):
        self.assertIn("let selectedOutputMedia = null", self.javascript)
        self.assertIn("selectedOutputMedia?.nodeId === node.id", self.javascript)
        self.assertIn("mediaKindForOutputItem(item) === 'image'", self.javascript)
        self.assertIn("node.type === 'image'", self.javascript)
        self.assertIn('data-media-action=', self.javascript)

    def test_output_actions_materialize_the_selected_image_before_linking(self):
        self.assertIn("function materializeOutputMediaTarget(target)", self.javascript)
        self.assertIn("url:target.url", self.javascript)
        start = self.javascript.index("function addQuickActionNode(source, type)")
        end = self.javascript.index("function runMediaQuickAction", start)
        quick_action = self.javascript[start:end]
        self.assertIn("createdConnection = {id:uid('c'), from:source.id, to:created.id}", quick_action)
        self.assertIn("connections.push(createdConnection)", quick_action)
        self.assertIn("indexClassicConnectionModel(createdConnection)", quick_action)

    def test_image_toolbar_has_a_direct_crop_action_reusing_the_image_editor(self):
        start = self.javascript.index("function renderSelectionHub")
        end = self.javascript.index("function selectOutputMedia", start)
        body = self.javascript[start:end]
        self.assertEqual(body.count("{id:'crop', label:langIsEn() ? 'Crop' : '裁切', icon:'crop'}"), 1)
        self.assertLess(body.index("{id:'edit'"), body.index("{id:'crop'"))
        self.assertLess(body.index("{id:'crop'"), body.index("{id:'grid'"))

        run = re.search(r"function runMediaQuickAction\(action, target\)\{(?P<body>.*?)\n\}", self.javascript, re.DOTALL)
        self.assertIsNotNone(run)
        run_body = run.group("body")
        self.assertIn("['edit','crop','grid'].includes(action)", run_body)
        self.assertIn("action === 'edit' || action === 'crop' || action === 'grid'", run_body)
        self.assertIn("openImageEditor(image.id, action === 'grid' ? 'grid' : 'crop')", run_body)

    def test_toolbar_is_positioned_above_the_selected_media_and_has_visual_state(self):
        self.assertIn("function positionSelectionHub(anchor)", self.javascript)
        self.assertIn("anchorRect.top - boardRect.top - hubRect.height - 10", self.javascript)
        self.assertIn("max-width:calc(100vw - 32px)", self.styles)
        self.assertIn("flex-wrap:wrap", self.styles)
        self.assertIn(".media-quick-btn {", self.styles)
        self.assertIn(".output-img-wrap.quick-selected img", self.styles)


if __name__ == "__main__":
    unittest.main()
