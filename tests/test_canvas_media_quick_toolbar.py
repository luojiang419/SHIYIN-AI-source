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
        self.assertIn("function addQuickActionNode(source, type)", self.javascript)
        self.assertIn("connections.push({id:uid('c'), from:source.id, to:created.id})", self.javascript)

    def test_toolbar_is_positioned_above_the_selected_media_and_has_visual_state(self):
        self.assertIn("function positionSelectionHub(anchor)", self.javascript)
        self.assertIn("anchorRect.top - boardRect.top - hubRect.height - 10", self.javascript)
        self.assertIn(".media-quick-btn {", self.styles)
        self.assertIn(".output-img-wrap.quick-selected img", self.styles)


if __name__ == "__main__":
    unittest.main()
