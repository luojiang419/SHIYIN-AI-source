import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def body(source: str, signature: str, end_marker: str) -> str:
    start = source.index(signature)
    end = source.index(end_marker, start)
    return source[start:end]


class CanvasHotpathIndexTests(unittest.TestCase):
    def test_classic_has_model_dom_port_and_geometry_indexes(self):
        for token in (
            "canvasNodeIndex",
            "canvasNodeDomIndex",
            "canvasPortDomIndex",
            "canvasNodeRectIndex",
            "canvasPortGeometryIndex",
            "rebuildCanvasDomIndexes",
            "invalidateCanvasGeometry",
        ):
            self.assertIn(token, CANVAS_JS)
        self.assertIn("canvasNodeRectIndex.get(n.id)", body(CANVAS_JS, "function estimatedNodeRect", "function currentWorldViewRect"))
        self.assertIn("canvasPortDomIndex.get(cacheKey)", body(CANVAS_JS, "function portPoint", "function canResolvePort"))
        links = body(CANVAS_JS, "function renderLinks", "function renderKnifeTrail")
        self.assertIn("canvasNodeIndex.size ? canvasNodeIndex", links)
        self.assertIn("canvasNodeDomIndex.size ? canvasNodeDomIndex", links)

    def test_classic_viewport_moves_do_not_rebuild_link_geometry(self):
        for signature, marker in (
            ("function centerViewportOnWorldPoint", "function safeViewportScale"),
            ("function fitAllNodesViewport", "function enterZoomPreview"),
            ("function exitZoomPreview", "function exitZoomPreviewToNode"),
            ("function exitZoomPreviewToNode", "function toggleZoomPreview"),
        ):
            segment = body(CANVAS_JS, signature, marker)
            self.assertIn("applyViewport();", segment)
            self.assertNotIn("renderLinks();", segment)

    def test_smart_has_model_dom_port_and_geometry_indexes(self):
        for token in (
            "smartNodeIndex",
            "smartNodeDomIndex",
            "smartPortDomIndex",
            "smartNodeRectIndex",
            "smartPortGeometryIndex",
            "rebuildSmartCanvasDomIndexes",
            "invalidateSmartGeometry",
            "cachedSmartNodeRect",
            "cachedSmartPortPoint",
        ):
            self.assertIn(token, SMART_JS)
        connections = body(SMART_JS, "function renderConnections", "function refreshConnectionLayer")
        self.assertIn("cachedSmartNodeRect(fromNode)", connections)
        self.assertIn("cachedSmartPortPoint(fromNode", connections)
        self.assertIn("cachedSmartPortPoint(toNode", connections)
        self.assertIn("smartNodeDomIndex.get(id)", body(SMART_JS, "function moveNodeElementsDuringDrag", "function updateNodeElementDuringResize"))

    def test_smart_pan_and_zoom_only_apply_viewport_transform(self):
        pan = body(SMART_JS, "if(panState){", "if(!dragState) return;")
        self.assertIn("applyViewport();", pan)
        self.assertNotIn("scheduleConnectionLayerRefresh();", pan)
        wheel = body(SMART_JS, "shell.addEventListener('wheel'", "shell.ondragover")
        self.assertIn("applyViewport();", wheel)
        self.assertNotIn("scheduleConnectionLayerRefresh();", wheel)

    def test_geometry_invalidation_is_scoped_to_moved_nodes(self):
        classic_drag = body(CANVAS_JS, "function onNodeDrag", "function startNodeResize")
        self.assertIn("invalidateCanvasGeometry([dragNode.node.id", classic_drag)
        smart_drag = body(SMART_JS, "function moveNodeElementsDuringDrag", "function updateNodeElementDuringResize")
        self.assertIn("invalidateSmartGeometry(groupItems.map(item => item.id))", smart_drag)


if __name__ == "__main__":
    unittest.main()
