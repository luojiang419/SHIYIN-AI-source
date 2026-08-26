import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_CANVAS_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def body(source: str, signature: str, end_marker: str) -> str:
    start = source.index(signature)
    end = source.index(end_marker, start)
    return source[start:end]


class CanvasIncrementalRenderPerformanceTests(unittest.TestCase):
    def test_classic_center_creation_queues_a_node_mutation(self):
        section = body(CANVAS_JS, "function addNode(node)", "function defaultPoint")
        self.assertIn("canvasNodeIndex.set(node.id, node)", section)
        self.assertIn("queueClassicRenderMutation({createdIds:[node.id]})", section)

    def test_node_dom_and_port_indexes_have_targeted_patch_helpers(self):
        for source, index_helper, remove_helper in (
            (CANVAS_JS, "function indexClassicNodeDom", "function removeClassicNodeDomIndex"),
            (SMART_CANVAS_JS, "function indexSmartNodeDom", "function removeSmartNodeDomIndex"),
        ):
            self.assertIn(index_helper, source)
            self.assertIn(remove_helper, source)

    def test_smart_member_dom_reindex_preserves_group_owner_mapping(self):
        remove_section = body(SMART_CANVAS_JS, "function removeSmartNodeDomIndex", "function indexSmartNodeDom")
        index_section = body(SMART_CANVAS_JS, "function indexSmartNodeDom", "function rebuildSmartCanvasDomIndexes")
        self.assertIn("preserveGroupOwner=false", remove_section)
        self.assertIn("if(!preserveGroupOwner) smartGroupOwnerIndex.delete(id)", remove_section)
        self.assertIn("preserveGroupOwner:!isSmartGroupNode(model)", index_section)

    def test_classic_mutation_avoids_global_dom_geometry_and_minimap_rebuilds(self):
        section = body(CANVAS_JS, "function renderClassicMutation", "function serializableCanvasNodes")
        affected = "const affectedNodeIds"
        self.assertIn(affected, section)
        self.assertIn("indexClassicNodeDom", section)
        self.assertIn("removeClassicNodeDomIndex", section)
        self.assertIn("patchClassicMutationConnections", section)
        self.assertIn("syncCanvasSelectedImageResolution(nodesEl, affectedNodeIds)", section)
        self.assertIn("scheduleMinimapNodeUpdate([...affectedNodeIds])", section)
        for forbidden in (
            "rebuildCanvasDomIndexes()",
            "refreshGeometryAfterLayout()",
            "scheduleMinimapRender()",
            "scheduleClassicIdleIconRefresh(nodesEl)",
            "bindCanvasPreviewImageFallbacks(nodesEl)",
        ):
            self.assertNotIn(forbidden, section)

    def test_smart_render_dispatches_mutations_to_a_separate_patch_path(self):
        self.assertIn("function renderSmartMutation", SMART_CANVAS_JS)
        section = body(SMART_CANVAS_JS, "function render(){", "function registerSmartCanvasPerfFixture")
        self.assertIn("renderSmartMutation(mutation)", section)
        self.assertIn(".map(node => ({node, html:smartNodeHtml(node)}))", section)
        self.assertNotIn("const title = node.specialType", section)

    def test_smart_mutation_avoids_global_dom_connection_media_and_minimap_work(self):
        self.assertIn("function renderSmartMutation", SMART_CANVAS_JS)
        section = body(SMART_CANVAS_JS, "function renderSmartMutation", "function render(){")
        self.assertIn("indexSmartNodeDom", section)
        self.assertIn("removeSmartNodeDomIndex", section)
        self.assertIn("patchSmartMutationConnections", section)
        self.assertIn("scheduleSmartMinimapNodeUpdate([...affectedNodeIds])", section)
        for forbidden in (
            "world.querySelectorAll('.image-node')",
            "captureMediaPlaybackStates()",
            "renderConnections(",
            "rebuildSmartCanvasDomIndexes()",
            "rebuildSmartConnectionDomIndex()",
            "scheduleSmartMinimapRender()",
        ):
            self.assertNotIn(forbidden, section)

    def test_smart_mutation_hydrates_new_roots_before_inserting_into_world(self):
        section = body(SMART_CANVAS_JS, "function renderSmartMutation", "function render(){")
        insert_at = section.index("world.appendChild(fresh)")
        self.assertLess(section.index("refreshIcons(fresh)"), insert_at)
        self.assertLess(section.index("bindSmartPreviewImageFallbacks(fresh)"), insert_at)
        self.assertLess(section.index("measureSmartNodeImages(smartNodeIndex, fresh)"), insert_at)

    def test_smart_mutation_defers_composer_rebuild_to_idle_period(self):
        mutation = body(SMART_CANVAS_JS, "function renderSmartMutation", "function render(){")
        self.assertIn("scheduleSmartComposerUpdate()", mutation)
        self.assertNotIn("\n    updateComposer();", mutation)
        helper = body(SMART_CANVAS_JS, "function scheduleSmartComposerUpdate", "function render(){")
        self.assertIn("smartComposerIdleHandle", helper)
        self.assertIn("smartComposerIdleTimer", helper)
        self.assertIn("requestIdleCallback", helper)
        self.assertIn("timeout:1200", helper)
        self.assertIn("}, 600);", helper)

    def test_mutations_carry_connection_structure_differences(self):
        classic = body(CANVAS_JS, "function queueClassicRenderMutation", "function renderClassicMutation")
        smart = body(SMART_CANVAS_JS, "function queueSmartRenderMutation", "function renderSmartMutation")
        for section in (classic, smart):
            self.assertIn("createdConnectionIds", section)
            self.assertIn("removedConnectionIds", section)
            self.assertIn("affectedConnectionIds", section)

    def test_smart_connections_receive_stable_ids_for_dom_patching(self):
        self.assertIn("function ensureSmartConnectionIds", SMART_CANVAS_JS)
        add_connection = body(SMART_CANVAS_JS, "function addConnection", "function connectInputNode")
        self.assertIn("id:uid('c')", add_connection)

    def test_smart_connection_selection_prefers_stable_ids(self):
        section = body(SMART_CANVAS_JS, "function syncConnectionSelectionUi", "function isNodeSelected")
        self.assertIn("hit?.dataset?.connectionId", section)
        self.assertIn("smartConnectionModelIndex.get(connectionId)", section)
        self.assertIn(".filter(rawIndex => rawIndex !== '')", section)

    def test_smart_member_deletion_replaces_affected_group_dom(self):
        sections = (
            body(SMART_CANVAS_JS, "function deleteSelectedSmartNodes", "function selectAllSmartNodes"),
            body(SMART_CANVAS_JS, "function deleteNode(id)", "function clearNodeMediaBeforeDelete"),
        )
        for section in sections:
            self.assertIn("const affectedGroupIds", section)
            self.assertIn("replaceIds:affectedGroupIds", section)

    def test_classic_selected_resolution_accepts_affected_node_ids(self):
        section = body(CANVAS_JS, "function syncCanvasSelectedImageResolution", "function applyLanguage")
        self.assertIn("affectedNodeIds=null", section)
        self.assertIn("canvasNodeDomIndex.get(id)", section)
        self.assertIn("const imageElements = affectedNodeIds", section)

    def test_menu_node_constructors_use_the_smart_create_commit_helper(self):
        self.assertIn("function commitSmartNodeCreate", SMART_CANVAS_JS)
        sections = (
            body(SMART_CANVAS_JS, "function createNode(x, y", "function createPromptNode"),
            body(SMART_CANVAS_JS, "function createPromptNode", "function createLoopNode"),
            body(SMART_CANVAS_JS, "function createSmartGroupNode", "function cloneSmartNode"),
            body(SMART_CANVAS_JS, "function createFilmNode", "function smartFilmLineArtRunSettings"),
            body(SMART_CANVAS_JS, "function createPanoramaNode", "function createDWPoseNode"),
            body(SMART_CANVAS_JS, "function createDWPoseNode", "function createPoseReferenceNode"),
            body(SMART_CANVAS_JS, "function createPoseReferenceNode", "function createPoseReplicateNode"),
            body(SMART_CANVAS_JS, "function createPoseReplicateNode", "function createRelightNode"),
            body(SMART_CANVAS_JS, "function createRelightNode", "function createAngleNode"),
        )
        for section in sections:
            self.assertIn("commitSmartNodeCreate", section)

    def test_smart_toolbar_batch_creation_uses_structure_transaction(self):
        section = body(SMART_CANVAS_JS, "function createSmartBatchGeneratorNode", "const MULTI_VIEW_INPUT_SLOTS")
        self.assertIn("beginSmartHistoryTransaction('toolbar-batch')", section)
        self.assertIn("commitSmartHistoryTransaction(historyTx)", section)
        self.assertNotIn("pushUndo();", section)

    def test_incremental_failures_are_observable_and_fall_back_to_full_render(self):
        for source, helper in (
            (CANVAS_JS, "function fallbackClassicRenderMutation"),
            (SMART_CANVAS_JS, "function fallbackSmartRenderMutation"),
        ):
            self.assertIn(helper, source)
            section = source[source.index(helper):]
            self.assertIn("console.warn", section)
            self.assertIn("render();", section)


if __name__ == "__main__":
    unittest.main()
