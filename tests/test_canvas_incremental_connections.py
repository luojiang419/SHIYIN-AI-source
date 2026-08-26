import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CLASSIC = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def body(source: str, signature: str, marker: str) -> str:
    start = source.index(signature)
    end = source.index(marker, start)
    return source[start:end]


class IncrementalConnectionTests(unittest.TestCase):
    def test_classic_dirty_connections_and_full_fallback(self):
        self.assertIn("const CLASSIC_INCREMENTAL_LINKS = true", CLASSIC)
        self.assertIn("const classicConnectionDirtyIds = new Set()", CLASSIC)
        patch = body(CLASSIC, "function renderClassicConnectionPatch", "function scheduleLinksRender")
        self.assertIn("classicConnectionStructureDirty", patch)
        self.assertIn("renderLinks();", patch)
        self.assertIn("classicLinkDom.get(connectionId)", patch)
        drag = body(CLASSIC, "function onNodeDrag", "function startNodeResize")
        self.assertIn("markClassicConnectionsDirtyForNodes", drag)
        resize = body(CLASSIC, "function onNodeResize", "function startLink")
        self.assertIn("markClassicConnectionsDirtyForNodes", resize)

    def test_classic_temp_link_isolated_from_connection_patch(self):
        temp = body(CLASSIC, "function renderClassicTempLink", "function renderClassicConnectionPatch")
        self.assertIn("classicTempLinkDom", temp)
        self.assertNotIn("connections.forEach", temp)
        schedule = body(CLASSIC, "function scheduleLinksRender", "function renderMinimap")
        self.assertIn("renderClassicConnectionPatch(dirty)", schedule)
        self.assertIn("renderLinks();", schedule)

    def test_smart_connection_dom_index_and_incremental_fallback(self):
        self.assertIn("const SMART_INCREMENTAL_CONNECTIONS = true", SMART)
        self.assertIn("const smartConnectionDom = new Map()", SMART)
        patch = body(SMART, "function renderSmartConnectionIncremental", "function refreshConnectionLayer")
        geometry = body(SMART, "function setSmartConnectionPatchGeometry", "function createSmartConnectionDom")
        self.assertIn("smartConnectionNeedsFullSvg(connection)", patch)
        self.assertIn("setSmartConnectionPatchGeometry(entry, connection)", patch)
        self.assertIn("return false", patch)
        self.assertIn("cachedSmartPortPoint", geometry)
        refresh = body(SMART, "function refreshConnectionLayer", "function scheduleConnectionLayerRefresh")
        self.assertIn("rebuildSmartConnectionDomIndex();", refresh)
        interaction = body(SMART, "function scheduleInteractionLayerRefresh", "function moveNodeElementsDuringDrag")
        self.assertIn("renderSmartConnectionIncremental(dirty)", interaction)
        self.assertIn("refreshConnectionLayer();", interaction)

    def test_smart_temp_port_path_remains_separate(self):
        temp = body(SMART, "function ensurePortDragPathElement", "function clearPortDragVisual")
        self.assertIn("port-drag-temp", temp)
        self.assertIn("svg.appendChild(path)", temp)
        self.assertIn("clearPortDragVisual", SMART)

    def test_disconnect_uses_lightweight_history_and_incremental_render(self):
        classic = body(CLASSIC, "function deleteConnection", "function outputDownloadName")
        self.assertIn("beginClassicHistoryTransaction('disconnect')", classic)
        self.assertIn("commitClassicHistoryTransaction(historyTx)", classic)
        self.assertIn("queueClassicRenderMutation({removedConnectionIds:[id]})", classic)
        self.assertNotIn("pushUndo();", classic)

        smart = body(SMART, "function disconnectConnections(spec)", "function connectionMidpoint")
        self.assertIn("beginSmartHistoryTransaction('disconnect')", smart)
        self.assertIn("commitSmartHistoryTransaction(historyTx)", smart)
        self.assertIn("removedConnectionIds:removed.map(connection => connection.id)", smart)
        self.assertIn("requiresFullConnectionRender:removed.length > 1", smart)


if __name__ == "__main__":
    unittest.main()
