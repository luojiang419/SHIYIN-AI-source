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

    def test_classic_hover_does_not_sample_every_connection_on_large_canvases(self):
        hover = body(CANVAS_JS, "function updateConnectionHoverFromMouse(e){", "function isConnectionSelected")
        self.assertIn("e.target?.closest?.('.link-hit')", hover)
        self.assertIn("connections.length > 120", hover)

    def test_copy_paths_use_structured_clone_when_available(self):
        classic_copy = body(CANVAS_JS, "function copySelectedNodes(){", "function clipboardNodeCount")
        smart_copy = body(SMART_CANVAS_JS, "function copySelectedNodes(){", "function pasteNodes")
        self.assertIn("structuredClone", classic_copy)
        self.assertIn("structuredClone", smart_copy)


if __name__ == "__main__":
    unittest.main()
