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


class CanvasClipboardPerformanceTests(unittest.TestCase):
    def test_copy_paths_use_node_indexes_without_selected_nodes_find(self):
        classic = body(CANVAS_JS, "function copySelectedNodes(){", "function clipboardNodeCount")
        smart = body(SMART_CANVAS_JS, "function copySelectedNodes(){", "function pasteNodes")

        self.assertIn("canvasNodeIndex.get", classic)
        self.assertIn("smartNodeIndex.get", smart)
        self.assertNotRegex(classic, re.compile(r"\.map\(id\s*=>\s*nodes\.find"))
        self.assertNotRegex(smart, re.compile(r"\.map\(id\s*=>\s*nodes\.find"))

    def test_copy_paths_collect_only_adjacent_internal_connections(self):
        classic = body(CANVAS_JS, "function copySelectedNodes(){", "function clipboardNodeCount")
        smart = body(SMART_CANVAS_JS, "function copySelectedNodes(){", "function pasteNodes")

        self.assertIn("classicClipboardConnections", classic)
        self.assertNotIn("(connections || []).filter", classic)
        self.assertIn("smartClipboardConnections", smart)
        self.assertNotIn("(canvas.connections || []).filter", smart)
        self.assertIn("classicClipboardConnectionIndex", CANVAS_JS)
        self.assertIn("smartClipboardConnectionIndex", SMART_CANVAS_JS)

    def test_group_copy_and_paste_remap_member_ids(self):
        classic_copy = body(CANVAS_JS, "function copySelectedNodes(){", "function clipboardNodeCount")
        classic_paste = body(CANVAS_JS, "function pasteNodes(){", "function selectedWorkflowPayload")
        smart_copy = body(SMART_CANVAS_JS, "function copySelectedNodes(){", "function pasteNodes")
        smart_paste = body(SMART_CANVAS_JS, "function pasteNodes(){", "const SMART_CANVAS_ASSET_INBOX_KEY")

        self.assertIn("collectClassicClipboardNode", classic_copy)
        self.assertIn("collectSmartClipboardNode", smart_copy)
        self.assertIn("c.items = c.items.map(id => idMap.get(id)).filter(Boolean)", classic_paste)
        self.assertIn("copy.items = copy.items.map", smart_paste)

    def test_connection_indexes_detect_same_length_array_replacement(self):
        classic = body(CANVAS_JS, "function classicClipboardConnections", "function appendValidatedPastedConnections")
        smart = body(SMART_CANVAS_JS, "function smartClipboardConnections", "function rebuildSmartConnectionDomIndex")

        self.assertIn("classicClipboardConnectionSource !== connections", classic)
        self.assertIn("smartClipboardConnectionSource !== connectionList", smart)

    def test_classic_paste_validates_only_new_connections(self):
        paste = body(CANVAS_JS, "function pasteNodes(){", "function selectedWorkflowPayload")

        self.assertIn("appendValidatedPastedConnections(newConnections)", paste)
        self.assertNotIn("sanitizeConnections();", paste)

    def test_classic_generator_sync_accepts_target_ids(self):
        sync = body(CANVAS_JS, "function syncGeneratorInputs", "let generatorInputSyncTimer")
        paste = body(CANVAS_JS, "function pasteNodes(){", "function selectedWorkflowPayload")

        self.assertIn("targetIds=null", sync)
        self.assertIn("affectedGeneratorIds", paste)
        self.assertIn("syncGeneratorInputs(affectedGeneratorIds)", paste)

    def test_paste_shortcuts_have_event_cycle_fallback_without_90ms_delay(self):
        classic = body(CANVAS_JS, "function runClassicCanvasShortcutAction", "function handleClassicShortcutKeyDown")
        smart = body(SMART_CANVAS_JS, "function runSmartCanvasShortcutAction", "function handleSmartShortcutKeyDown")

        self.assertIn("scheduleClassicNodePasteFallback", classic)
        self.assertIn("scheduleSmartNodePasteFallback", smart)
        self.assertNotRegex(classic, re.compile(r"setTimeout\([^;]+,\s*90\s*\)", re.S))
        self.assertNotRegex(smart, re.compile(r"setTimeout\([^;]+,\s*90\s*\)", re.S))
        self.assertIn("}, 0);", CANVAS_JS)
        self.assertIn("}, 0);", SMART_CANVAS_JS)

    def test_paste_events_keep_system_media_ahead_of_node_clipboard(self):
        classic = body(CANVAS_JS, "function handleClassicClipboardPaste", "function classicShortcutSelectionTarget")
        smart = body(SMART_CANVAS_JS, "function handleSmartClipboardPaste", "function handleSmartShortcutKeyDown")
        classic_parent = body(CANVAS_JS, "function detachClassicParentShortcutListeners", "window.addEventListener('keydown'")
        smart_parent = body(SMART_CANVAS_JS, "function detachSmartParentShortcutListeners", "window.addEventListener('keydown'")

        self.assertLess(classic.index("if(files.length)"), classic.index("clipboardNodeCount()"))
        self.assertLess(smart.index("if(files.length)"), smart.index("nodeClipboard?.nodes?.length"))
        self.assertIn("pasteNodes();", classic)
        self.assertIn("pasteNodes();", smart)
        self.assertIn("removeEventListener('paste', handleClassicClipboardPaste)", classic_parent)
        self.assertIn("addEventListener('paste', handleClassicClipboardPaste)", classic_parent)
        self.assertIn("removeEventListener('paste', handleSmartClipboardPaste)", smart_parent)
        self.assertIn("addEventListener('paste', handleSmartClipboardPaste)", smart_parent)


if __name__ == "__main__":
    unittest.main()
