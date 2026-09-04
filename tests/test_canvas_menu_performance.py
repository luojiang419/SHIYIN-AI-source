import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_CANVAS_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
CANVAS_CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")
SMART_CANVAS_CSS = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")


def body(source: str, signature: str, end_marker: str) -> str:
    start = source.index(signature)
    end = source.index(end_marker, start)
    return source[start:end]


def css_rule(source: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]*)\}}", source)
    if not match:
        raise AssertionError(f"missing CSS rule: {selector}")
    return match.group("body")


class CanvasMenuPerformanceTests(unittest.TestCase):
    def test_classic_creation_flushes_one_render_after_menu_and_link_mutations(self):
        menu = body(CANVAS_JS, "function menuAdd", "function menuCreateFilmWorkflow")
        linked = body(CANVAS_JS, "function createLinkedNode", "function createNodeByType")
        batch = body(CANVAS_JS, "function beginCanvasMutationBatch", "function queueClassicRenderMutation")

        self.assertIn("beginCanvasMutationBatch();", menu)
        self.assertIn("endCanvasMutationBatch();", menu)
        self.assertIn("beginCanvasMutationBatch();", linked)
        self.assertIn("endCanvasMutationBatch({", linked)
        self.assertIn("removedConnectionIds", linked)
        self.assertIn("removedConnectionIds,", linked)
        self.assertIn("scheduleClassicRender();", batch)
        self.assertNotIn("render();", menu)
        self.assertNotIn("render();", linked)

    def test_classic_submenus_close_when_pointer_enters_other_menu_area(self):
        routing = body(CANVAS_JS, "function closeInactiveCanvasSubmenus", "document.addEventListener('pointerover', closeInactiveCanvasSubmenus, true);")
        closing = body(CANVAS_JS, "function scheduleCanvasSubmenuClose", "function closeInactiveCanvasSubmenus")

        self.assertIn("if(inFilm && !inLookbook)", routing)
        self.assertIn("else if(inLookbook && !inFilm)", routing)
        self.assertIn("else if(!inFilm && !inLookbook)", routing)
        self.assertIn("closeCanvasSubmenu(lookbookMenuHost, lookbookSubmenu, lookbookMenuTrigger)", routing)
        self.assertIn("closeCanvasSubmenu(filmMenuHost, filmSubmenu, filmMenuTrigger)", routing)
        self.assertIn("scheduleCanvasSubmenuClose();", routing)
        self.assertIn("if(canvasSubmenuCloseTimer)", routing)
        self.assertIn("setTimeout(() =>", closing)
        self.assertIn("filmMenuHost?.classList.remove('submenu-open','submenu-flip')", closing)
        self.assertNotIn("ecommerceMenuHost", closing)

    def test_classic_menu_icon_refreshes_are_scoped_to_open_overlays(self):
        create = body(CANVAS_JS, "function openCreateMenu(", "function closeCreateMenu")
        link = body(CANVAS_JS, "function openLinkCreateMenu(", "function openGeneratorNodeMenu")
        ports = body(CANVAS_JS, "function openGeneratorNodeMenu(", "function closeLinkCreateMenu")
        image = body(CANVAS_JS, "function openImageNodeMenu(", "function openImageNodePreview")
        output = body(CANVAS_JS, "function openOutputNodeMenu(", "function closeImageNodeMenu")

        self.assertIn("refreshIcons(createMenu)", create)
        self.assertIn("refreshIcons(linkCreateMenu)", link)
        self.assertIn("[nodeInputMenu, nodeOutputMenu].forEach(menu => refreshIcons(menu));", ports)
        self.assertIn("refreshIcons(imageNodeMenu)", image)
        self.assertIn("refreshIcons(imageNodeMenu)", output)
        for menu_body in (create, link, ports, image, output):
            self.assertNotIn("refreshIcons();", menu_body)

    def test_classic_create_menu_reads_final_layout_only_once(self):
        create = body(CANVAS_JS, "function openCreateMenu(", "function closeCreateMenu")
        estimate = body(
            CANVAS_JS,
            "function estimateClassicCreateMenuSingleColumnHeight(",
            "function openCreateMenu(",
        )

        self.assertEqual(create.count("getBoundingClientRect()"), 1)
        self.assertIn("estimateClassicCreateMenuSingleColumnHeight()", create)
        self.assertIn("clientY + singleColumnHeight + viewportMargin > window.innerHeight", create)
        self.assertIn("createMenu.classList.toggle('create-menu-two-column', lacksBottomSpace)", create)
        self.assertNotIn("getBoundingClientRect", estimate)
        self.assertNotIn("getComputedStyle", estimate)

    def test_classic_menu_positioning_and_submenu_flip_contract_is_preserved(self):
        create = body(CANVAS_JS, "function openCreateMenu(", "function closeCreateMenu")

        self.assertIn("window.innerWidth - menuRect.width - viewportMargin", create)
        self.assertIn("window.innerHeight - menuRect.height - viewportMargin", create)
        self.assertIn("left + menuRect.width + 232 > window.innerWidth - viewportMargin", create)

    def test_menu_overlays_use_opaque_backgrounds_without_backdrop_blur(self):
        for selector in (".create-menu", ".create-submenu", ".selection-hub"):
            rule = css_rule(CANVAS_CSS, selector)
            self.assertIn("background:var(--card-solid)", rule)
            self.assertNotIn("backdrop-filter", rule)

        classic_dark = css_rule(CANVAS_CSS, ".theme-dark .create-menu")
        self.assertIn("background:var(--card-solid)", classic_dark)

        smart_create = css_rule(SMART_CANVAS_CSS, ".create-menu")
        self.assertIn("background:var(--card)", smart_create)
        self.assertNotIn("backdrop-filter", smart_create)

    def test_smart_create_menu_keeps_scoped_icons_and_floating_menu_no_blur(self):
        create = body(SMART_CANVAS_JS, "function openCreateMenu(", "function addCreatedNodeToMenuGroup")
        floating = css_rule(SMART_CANVAS_CSS, ".smart-node-floating-menu")

        self.assertIn("refreshIcons(createMenu)", create)
        self.assertNotIn("refreshIcons();", create)
        self.assertIn("backdrop-filter:none", floating)
        self.assertIn("-webkit-backdrop-filter:none", floating)


if __name__ == "__main__":
    unittest.main()
