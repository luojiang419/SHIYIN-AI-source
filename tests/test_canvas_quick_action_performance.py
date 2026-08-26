import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_CANVAS_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")
CANVAS_CSS = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")


def section(start_marker, end_marker, source=CANVAS_JS):
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


class CanvasQuickActionPerformanceTests(unittest.TestCase):
    def test_smart_menu_creation_defers_nested_renders_until_batch_flush(self):
        batch = section(
            "let smartNodeCreateBatchDepth",
            "function uid(",
            SMART_CANVAS_JS,
        )
        menu = section(
            "function createNodeFromMenu",
            "shell.addEventListener('mousedown'",
            SMART_CANVAS_JS,
        )
        commit = section(
            "function commitSmartNodeCreate",
            "function createFilmNode",
            SMART_CANVAS_JS,
        )

        self.assertIn("beginSmartNodeCreateBatch", batch)
        self.assertIn("smartNodeCreateBatchFlushing", batch)
        self.assertIn("beginSmartNodeCreateBatch();", menu)
        self.assertIn("endSmartNodeCreateBatch();", menu)
        self.assertIn("!smartNodeCreateBatchDepth", commit)

    def test_incremental_selection_lod_only_visits_affected_nodes(self):
        lod_source = section(
            "function scheduleClassicSafeLod",
            "function currentWorldViewRect",
        )
        selection_source = section(
            "function refreshSelectionVisuals",
            "function syncConnectionSelectionVisuals",
        )

        self.assertIn("function scheduleClassicSafeLod(ids=null)", lod_source)
        self.assertIn("updateClassicSafeLod(pendingIds)", lod_source)
        self.assertIn("function updateClassicSafeLod(affectedIds=null)", lod_source)
        self.assertIn("canvasNodeDomIndex.get(id)", lod_source)
        self.assertIn("nodesEl.querySelectorAll('.node.canvas-lod-safe')", lod_source)
        self.assertIn("scheduleClassicSafeLod([...affectedNodeIds])", selection_source)

    def test_large_scene_lod_contains_visual_shell_without_clipping_ports(self):
        render_source = section(
            "function renderNode(",
            "function bindOutputWrap",
        )

        shell_create = render_source.index("visualShell.className = 'node-visual-shell'")
        shell_append = render_source.index("el.appendChild(visualShell)")
        output_port = render_source.index("if(canOutput) el.insertAdjacentHTML")
        self.assertLess(shell_create, shell_append)
        self.assertLess(shell_append, output_port)
        self.assertIn("visualShell.appendChild(body)", render_source)
        self.assertIn(
            "#nodes.canvas-large-scene > .node.canvas-lod-safe > .node-visual-shell",
            CANVAS_CSS,
        )
        self.assertNotIn(
            "#nodes.canvas-large-scene > .node.canvas-lod-safe { content-visibility:auto",
            CANVAS_CSS,
        )

    def test_incremental_node_icons_are_hydrated_before_dom_insertion(self):
        mutation_source = section(
            "function renderClassicMutation",
            "function serializableCanvasNodes",
        )
        hydrate_source = section(
            "function hydrateClassicMutationNodeRoots",
            "function renderClassicMutation",
        )

        created_icons = mutation_source.index("refreshIcons(fresh)")
        created_insert = mutation_source.index("nodesEl.appendChild(fresh)")
        self.assertLess(created_icons, created_insert)
        self.assertNotIn("scheduleClassicIdleIconRefresh(root)", hydrate_source)

    def test_new_connection_patch_uses_estimated_ports_before_layout_settles(self):
        patch_source = section(
            "function patchClassicMutationConnections",
            "function rebuildClassicConnectionModelIndexes",
        )
        port_source = section(
            "function portPoint",
            "function canResolvePort",
        )

        self.assertIn(
            "renderClassicConnectionPatch([...createdConnectionIds], {preferEstimated:true})",
            patch_source,
        )
        self.assertIn("if(layout?.preferEstimated)", port_source)
        self.assertIn("canvasNodeRectIndex.get(id) || estimatedNodeRect(n)", port_source)

    def test_incremental_mutation_defers_selection_hub_layout_read(self):
        mutation_source = section(
            "function renderClassicMutation",
            "function serializableCanvasNodes",
        )
        selection_source = section(
            "function refreshSelectionVisuals",
            "function syncConnectionSelectionVisuals",
        )
        hub_source = section(
            "function renderSelectionHub",
            "function selectOutputMedia",
        )

        self.assertIn("deferHubPosition:true", mutation_source)
        self.assertIn(
            "renderSelectionHub({deferPosition:options?.deferHubPosition})",
            selection_source,
        )
        self.assertIn("function renderSelectionHub(options={})", hub_source)
        self.assertIn("if(options.deferPosition) scheduleSelectionHubPosition()", hub_source)

    def test_incremental_node_index_defers_forced_layout_measurement(self):
        index_source = section(
            "function indexClassicNodeDom",
            "function rebuildCanvasDomIndexes",
        )
        mutation_source = section(
            "function renderClassicMutation",
            "function serializableCanvasNodes",
        )

        self.assertIn("function indexClassicNodeDom(el, node=null, options={})", index_source)
        self.assertIn("const measure = options.measure !== false", index_source)
        self.assertIn("indexClassicNodeDom(fresh, node, {measure:false})", mutation_source)
        self.assertIn("scheduleClassicNodeRectMeasure([id])", mutation_source)

    def test_image_load_geometry_refresh_is_scoped_to_the_created_node(self):
        render_source = section(
            "function renderNode(",
            "function bindOutputWrap",
        )
        image_source = render_source[
            render_source.index("if(loadedImg && loadedImg.complete"):
            render_source.index("} else {", render_source.index("if(loadedImg && loadedImg.complete"))
        ]

        self.assertIn("scheduleClassicNodeRectMeasure([node.id])", image_source)
        self.assertNotIn("refreshGeometry", image_source)

    def test_free_node_point_precomputes_cached_rectangles_before_candidate_loop(self):
        source = section(
            "function canvasFreeNodePoint",
            "function positionCanvasNodeRelative",
        )
        candidate_loop = source[source.index("for(let column=0;"):]

        self.assertIn("const occupiedRects = nodes", source)
        self.assertIn(".map(estimatedNodeRect)", source)
        self.assertIn(
            "occupiedRects.some(rect => canvasRectsOverlap(candidate, rect))",
            candidate_loop,
        )
        self.assertNotIn("nodeRect(node)", candidate_loop)

    def test_quick_action_batches_node_and_connection_into_one_incremental_commit(self):
        source = section(
            "function addQuickActionNode",
            "function runMediaQuickAction",
        )

        self.assertIn("beginCanvasMutationBatch();", source)
        self.assertIn("endCanvasMutationBatch({", source)
        self.assertIn("createdConnectionIds", source)
        self.assertIn("indexClassicConnectionModel(createdConnection)", source)
        self.assertNotIn("syncGeneratorInputs();", source)
        self.assertIn("syncGeneratorInputs(new Set([created.id]))", source)
        self.assertNotIn("render();", source)


if __name__ == "__main__":
    unittest.main()
