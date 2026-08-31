from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent


class CanvasOutputLightboxMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canvas = (ROOT / 'static' / 'js' / 'canvas.js').read_text(encoding='utf-8')
        cls.html = (ROOT / 'static' / 'canvas.html').read_text(encoding='utf-8')

    def test_lightbox_open_clears_all_canvas_media_menus(self):
        helper_start = self.canvas.index('function hideSelectionHubForLightbox()')
        helper_end = self.canvas.index('function openOutputLightbox', helper_start)
        helper = self.canvas[helper_start:helper_end]
        self.assertIn("selectionHub?.classList.remove('open','image-prompt-hub')", helper)
        self.assertIn("selectionHub.innerHTML = ''", helper)
        self.assertIn('selectionHubAnchor = null', helper)
        self.assertIn('selectedOutputMedia = null', helper)
        self.assertIn("nodesEl?.querySelectorAll('.output-img-wrap.quick-selected').forEach", helper)
        self.assertIn('closeImageNodeMenu()', helper)

        open_start = self.canvas.index('function openOutputLightbox')
        open_end = self.canvas.index('function closeOutputLightbox', open_start)
        opening = self.canvas[open_start:open_end]
        self.assertIn('hideSelectionHubForLightbox();', opening)
        self.assertLess(opening.index('hideSelectionHubForLightbox();'), opening.index('resetOutputPreviewZoom();'))

    def test_selection_hub_and_output_context_menu_stay_closed_during_lightbox(self):
        hub_start = self.canvas.index('function renderSelectionHub(options={})')
        hub_end = self.canvas.index('const CANVAS_IMAGE_CAMERA_DEFAULTS', hub_start)
        hub = self.canvas[hub_start:hub_end]
        self.assertIn("if(outputLightbox?.classList.contains('open'))", hub)
        self.assertIn('selectedOutputMedia = null;', hub)

        menu_start = self.canvas.index('function openOutputNodeMenu')
        menu_end = self.canvas.index('function closeImageNodeMenu', menu_start)
        menu = self.canvas[menu_start:menu_end]
        self.assertIn("if(outputLightbox?.classList.contains('open'))", menu)
        self.assertIn('closeImageNodeMenu();', menu)

    def test_canvas_static_cache_key_is_bumped_for_menu_fix(self):
        self.assertIn('feature=output-lightbox-menu.1', self.html)


if __name__ == '__main__':
    unittest.main()
