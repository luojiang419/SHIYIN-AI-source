import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_CANVAS_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def body(source: str, signature: str, end_marker: str) -> str:
    start = source.index(signature)
    end = source.index(end_marker, start)
    return source[start:end]


class CanvasInteractionPerformanceTests(unittest.TestCase):
    def test_classic_marquee_uses_world_coordinates_and_incremental_selection(self):
        selection = body(CANVAS_JS, "function finishSelection(){", "function formatVideoClipTime")
        self.assertIn("const endWorld = screenToWorld", selection)
        self.assertIn("refreshSelectionVisuals();", selection)
        self.assertNotIn("getBoundingClientRect()", selection)
        self.assertNotIn("render();", selection)

    def test_smart_marquee_does_not_rebuild_all_nodes(self):
        selection = body(SMART_CANVAS_JS, "function finishSelection(event){", "function groupSelectedNodes")
        self.assertIn("syncSelectionUi();", selection)
        self.assertIn("updateComposer();", selection)
        self.assertNotIn("render();", selection)

    def test_smart_batch_delete_is_single_pass(self):
        deletion = body(SMART_CANVAS_JS, "function deleteSelectedSmartNodes(){", "function selectAllSmartNodes")
        self.assertIn("const deleteIds = new Set(ids);", deletion)
        self.assertIn("nodes = nodes.filter(node => !deleteIds.has(node.id));", deletion)
        self.assertNotIn("deleteNode(id", deletion)
        self.assertEqual(deletion.count("render();"), 1)
        self.assertEqual(deletion.count("scheduleSave();"), 1)

    def test_connection_refresh_reuses_node_and_dom_indexes(self):
        links = body(CANVAS_JS, "function renderLinks(){", "function renderKnifeTrail")
        self.assertIn("const nodeIndex = new Map(nodes.map(node => [node.id, node]));", links)
        self.assertIn("const nodeElements = new Map();", links)
        self.assertIn("canResolvePort(c.from, nodeIndex)", links)
        self.assertNotRegex(links, re.compile(r"nodes\.find\(node => node\.id === c\.to\)"))

    def test_classic_links_keep_dom_elements_between_frames(self):
        links = body(CANVAS_JS, "function renderLinks(){", "function renderKnifeTrail")
        self.assertIn("classicLinkDom", links)
        self.assertIn("classicLinkControlDom", links)
        self.assertNotIn("linksEl.innerHTML = ''", links)
        self.assertNotIn("linkControlsEl.innerHTML = ''", links)

    def test_classic_hover_does_not_sample_every_connection_on_large_canvases(self):
        hover = body(CANVAS_JS, "function updateConnectionHoverFromMouse(e){", "function isConnectionSelected")
        self.assertIn("e.target?.closest?.('.link-hit')", hover)
        self.assertIn("connections.length > 120", hover)

    def test_classic_port_link_drag_is_frame_coalesced(self):
        link = body(CANVAS_JS, "function startLink(e, originId", "function nearestPort")
        self.assertIn("scheduleLinksRender();", link)
        self.assertNotIn("tempLink.x2 = p.x;\n        tempLink.y2 = p.y;\n        renderLinks();", link)

    def test_smart_port_drag_uses_raf_and_incremental_active_elements(self):
        drag = body(SMART_CANVAS_JS, "function processSmartPortDragMove(e)", "function scheduleSmartPortDragMove")
        visual = body(SMART_CANVAS_JS, "function updatePortDragVisual()", "function handlePortDrop")
        self.assertIn("requestAnimationFrame", SMART_CANVAS_JS[SMART_CANVAS_JS.index("function scheduleSmartPortDragMove"):SMART_CANVAS_JS.index("window.onmousemove")])
        self.assertIn("activePortEl", visual)
        self.assertNotIn("querySelectorAll('.node-port.is-active')", visual)
        self.assertIn("elementFromPoint", drag)

    def test_output_drag_checks_stable_mime_before_generic_file_probe(self):
        dragover = body(CANVAS_JS, "board.addEventListener('dragover'", "board.addEventListener('dragleave'")
        self.assertLess(dragover.index("if(hasOutputMediaDrag"), dragover.index("if(hasImageDropData"))
        self.assertIn("output-fast", dragover)

    def test_output_drag_preview_is_static_and_not_media_clone(self):
        preview = body(CANVAS_JS, "function setOutputDragPreview", "function setCanvasOutputDragData")
        self.assertIn("固定尺寸的静态 ghost", preview)
        self.assertIn("setDragImage(wrap, 48, 36)", preview)
        self.assertNotIn("cloneNode()", preview)

    def test_output_and_link_creation_use_node_patch_path(self):
        output_create = body(CANVAS_JS, "function createMediaCardFromOutput", "function createImageCardFromOutput")
        link = body(CANVAS_JS, "function startLink(e, originId", "function nearestPort")
        self.assertIn("patchCanvasNodeCreates([node])", output_create)
        self.assertIn("patchCanvasNodeCreates([], [toId])", link)
        self.assertIn("patchCanvasNodeCreates([out])", link)
        self.assertNotIn("render();", output_create)

    def test_smart_output_drop_does_not_render_empty_node_before_appending_media(self):
        create_node = body(SMART_CANVAS_JS, "function createNode(x, y", "function createPromptNode")
        append = body(SMART_CANVAS_JS, "function appendImagesToSmartNode", "async function handleFiles")
        self.assertIn("options.deferRender !== true", create_node)
        self.assertIn("deferRender:true", append)
        self.assertEqual(append.count("render();"), 1)

    def test_large_scene_uses_node_indexes_and_content_visibility_lod(self):
        self.assertIn("canvasNodeIndex = new Map", CANVAS_JS)
        self.assertIn("canvas-large-scene", CANVAS_JS)
        self.assertIn("smartNodeIndex = new Map", SMART_CANVAS_JS)
        self.assertIn("smart-large-scene", SMART_CANVAS_JS)

    def test_saves_are_idle_coalesced_and_serialization_is_measured(self):
        classic_save = body(CANVAS_JS, "function scheduleSave()", "function scheduleViewportSave")
        smart_save = body(SMART_CANVAS_JS, "function scheduleSave(delay=450)", "async function saveCanvas")
        self.assertIn("requestIdleCallback", classic_save)
        self.assertIn("requestIdleCallback", smart_save)
        self.assertIn("classic.save.serialize", CANVAS_JS)
        self.assertIn("smart.save.serialize", SMART_CANVAS_JS)

    def test_copy_paths_use_structured_clone_when_available(self):
        classic_copy = body(CANVAS_JS, "function copySelectedNodes(){", "function clipboardNodeCount")
        smart_copy = body(SMART_CANVAS_JS, "function copySelectedNodes(){", "function pasteNodes")
        self.assertIn("structuredClone", classic_copy)
        self.assertIn("structuredClone", smart_copy)


if __name__ == "__main__":
    unittest.main()
