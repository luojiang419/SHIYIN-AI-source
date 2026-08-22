import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_CANVAS_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
FOCUS_GUARD_JS = (ROOT / "static" / "js" / "focus-guard.js").read_text(encoding="utf-8")
MAIN_PY = (ROOT / "main.py").read_text(encoding="utf-8")


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

    def test_floating_toolbar_actions_use_incremental_render_and_scoped_icons(self):
        multi_view = body(SMART_CANVAS_JS, "function createMultiViewNode", "const MULTI_VIEW_INPUT_SLOTS")
        batch = body(SMART_CANVAS_JS, "function createSmartBatchGeneratorNode", "const MULTI_VIEW_INPUT_SLOTS")
        self.assertIn("queueSmartRenderMutation({createdIds:[node.id]})", multi_view)
        self.assertIn("queueSmartRenderMutation({createdIds:[node.id]})", batch)
        editor = body(SMART_CANVAS_JS, "function openImageEditor", "function closeImageEditor")
        self.assertIn("refreshIcons(imageEditModal)", editor)
        render = body(SMART_CANVAS_JS, "function render(){", "function registerSmartCanvasPerfFixture")
        self.assertIn("refreshIcons(root)", render)
        self.assertIn("measureSmartNodeImages(nodeIndex, root)", render)

    def test_hidden_smart_toolbar_does_not_apply_backdrop_filter(self):
        css = (ROOT / "static" / "css" / "smart-canvas.css").read_text(encoding="utf-8")
        hidden = css[css.index(".smart-node-floating-menu {"):css.index(".smart-node-floating-menu.smart-node-image-menu")]
        self.assertIn("backdrop-filter:none", hidden)
        selected = css[css.index(".image-node.selected .smart-node-floating-menu"):css.index(".world.smart-multi-selected")]
        self.assertIn("backdrop-filter:blur(18px)", selected)

    def test_remote_canvas_sync_skips_timestamp_only_redraws(self):
        smart_apply = body(SMART_CANVAS_JS, "function applyMergedServerCanvas", "async function mergeReloadCanvasNow")
        classic_apply = body(CANVAS_JS, "function applyRemoteCanvasData", "function resetTransientRunState")
        self.assertIn("smartCanvasRenderFingerprint", smart_apply)
        self.assertIn("if(beforeFingerprint !== afterFingerprint) render();", smart_apply)
        self.assertIn("classicCanvasRenderFingerprint", classic_apply)
        self.assertIn("const contentChanged = beforeFingerprint !== afterFingerprint;", classic_apply)
        self.assertEqual(classic_apply.count("render();"), 2)
        self.assertNotIn("refreshMissingCanvasAssets().then(() => render())", classic_apply)

    def test_remote_sync_does_not_cancel_local_text_save(self):
        handler = body(CANVAS_JS, "function handleCanvasUpdatedMessage", "async function returnToCanvasManager")
        self.assertIn("if(localCanvasDirty || saveTimer || savingCanvasNow || saveCanvasAgain)", handler)
        self.assertNotIn("localCanvasDirty = false;", handler)
        smart_reload = body(SMART_CANVAS_JS, "async function mergeReloadCanvasNow", "function scheduleCanvasMergeReload")
        self.assertIn("smartCanvasTextInputActive()", smart_reload)

    def test_touch_only_updates_do_not_broadcast_canvas_event(self):
        touch = body(MAIN_PY, "@app.post(\"/api/canvases/{canvas_id}/touch\")", "@app.get(\"/api/canvas-assets\")")
        self.assertIn("save_canvas(canvas, broadcast=False)", touch)

    def test_replaced_text_editor_restores_unsaved_draft(self):
        restore = body(FOCUS_GUARD_JS, "function restore(snapshot)", "function shouldDeferDomUpdate")
        self.assertIn("if(replaced && snapshot.textEditable)", restore)
        self.assertIn("target.value = snapshot.value;", restore)
        self.assertIn("target.dispatchEvent(new Event('input', {bubbles:true}))", restore)


if __name__ == "__main__":
    unittest.main()
