import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CANVAS_JS = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
SMART_JS = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")


def body(source: str, signature: str, end_marker: str) -> str:
    start = source.index(signature)
    end = source.index(end_marker, start)
    return source[start:end]


class CanvasSaveMediaIsolationTests(unittest.TestCase):
    def test_classic_save_has_revision_sequence_guard(self):
        self.assertIn("const CLASSIC_SAVE_QUEUE_ENABLED = true;", CANVAS_JS)
        self.assertIn("let localCanvasSaveSequence = 0;", CANVAS_JS)
        save = body(CANVAS_JS, "async function saveCanvas()", "function applyCanvasRuntimeConfig")
        self.assertIn("const savingSequence = localCanvasSaveSequence;", save)
        self.assertIn("saveHadNewerEdits", save)
        self.assertIn("nodes:localNodes, connections:localConnections", save)
        self.assertIn("Math.max(Number(canvas.revision || 0), responseRevision)", save)

    def test_smart_save_tracks_newer_local_sequence_without_overwriting_nodes(self):
        self.assertIn("const SMART_SAVE_QUEUE_ENABLED = true;", SMART_JS)
        self.assertIn("let smartLocalSaveSequence = 0;", SMART_JS)
        schedule = body(SMART_JS, "function scheduleSave(delay=450)", "async function saveCanvas")
        save = body(SMART_JS, "async function saveCanvas()", "function imageMetaFromNode")
        self.assertIn("smartLocalSaveSequence += 1;", schedule)
        self.assertIn("const savingSequence = smartLocalSaveSequence;", save)
        self.assertIn("hasNewerLocalEdits", save)
        self.assertIn("canvas.updated_at = Math.max", save)
        self.assertNotIn("canvas = {...canvas, ...data.canvas", save)

    def test_image_measurement_and_full_scene_icons_are_idle_coalesced(self):
        for source, flag, icon_scheduler, measure_now, measure in (
            (CANVAS_JS, "CLASSIC_IDLE_MEDIA_ENABLED", "scheduleClassicIdleIconRefresh", "measureCanvasOriginalImageNodesNow", "measureCanvasOriginalImageNodes"),
            (SMART_JS, "SMART_IDLE_MEDIA_ENABLED", "scheduleSmartIdleIconRefresh", "measureSmartNodeImagesNow", "measureSmartNodeImages"),
        ):
            self.assertIn(f"const {flag} = true;", source)
            self.assertIn(f"function {icon_scheduler}", source)
            self.assertIn(f"function {measure_now}", source)
            self.assertIn("requestIdleCallback", source)
            self.assertIn(f"function {measure}", source)
        smart_render = body(SMART_JS, "function render(){", "function registerSmartCanvasPerfFixture")
        classic_render = body(CANVAS_JS, "function render(){", "function registerClassicCanvasPerfFixture")
        self.assertIn("scheduleSmartIdleIconRefresh(world)", smart_render)
        self.assertIn("scheduleClassicIdleIconRefresh(nodesEl)", classic_render)


if __name__ == "__main__":
    unittest.main()
