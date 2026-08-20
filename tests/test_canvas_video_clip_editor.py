import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class CanvasVideoClipEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "static" / "canvas.html").read_text(encoding="utf-8")
        cls.javascript = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "static" / "css" / "canvas.css").read_text(encoding="utf-8")

    def test_video_selection_toolbar_offers_trim_action(self):
        render = re.search(r"function renderSelectionHub\(\)\{(?P<body>.*?)\n\}", self.javascript, re.DOTALL)
        self.assertIsNotNone(render)
        body = render.group("body")
        self.assertIn("['image','video'].includes(mediaKindForNode(node))", body)
        self.assertIn("id:'trim-video'", body)
        self.assertIn("视频截取", body)
        self.assertIn("icon:'scissors'", body)

    def test_editor_contains_preview_timeline_io_and_resolution_controls(self):
        for element_id in (
            "videoClipModal",
            "videoClipPreview",
            "videoClipTimeline",
            "videoClipInHandle",
            "videoClipOutHandle",
            "videoClipResolution",
            "videoClipSubmit",
        ):
            self.assertIn(f'id="{element_id}"', self.html)
        self.assertIn('<option value="1080p">1080P（推荐）</option>', self.html)
        self.assertIn('data-clip-handle="in"', self.html)
        self.assertIn('data-clip-handle="out"', self.html)

    def test_editor_probes_source_and_submits_exact_range(self):
        self.assertIn("function openVideoClipEditor(nodeId)", self.javascript)
        self.assertIn("setVideoClipStatus('');\n    setVideoClipBusy(false);", self.javascript)
        self.assertIn("/api/canvas-tools/video-clip/capabilities", self.javascript)
        self.assertIn("/api/canvas-tools/video-clip/probe", self.javascript)
        self.assertIn("function submitVideoClip()", self.javascript)
        self.assertIn("/api/canvas-tools/video-clip/create", self.javascript)
        self.assertIn("start:state.start, end:state.end", self.javascript)
        self.assertIn("resolution:videoClipResolution?.value || '1080p'", self.javascript)

    def test_timeline_drag_and_transport_are_layout_stable(self):
        self.assertIn("function updateVideoClipHandle(kind, value)", self.javascript)
        self.assertIn("videoClipHandleDrag = handle.dataset.clipHandle", self.javascript)
        self.assertIn("videoClipPreview.currentTime >= videoClipEditor.end", self.javascript)
        self.assertIn(".video-clip-timeline {", self.styles)
        self.assertIn("height:64px", self.styles)
        self.assertIn("touch-action:none", self.styles)
        self.assertIn(".video-clip-handle", self.styles)

    def test_created_clip_node_keeps_canvas_owned_metadata(self):
        self.assertIn("function addVideoClipNodeFromResult(result, sourceNode)", self.javascript)
        self.assertIn("assetOwner:'videoClip'", self.javascript)
        self.assertIn("clipId:result.clip_id", self.javascript)
        self.assertIn("clipCanvasId:canvas?.id || ''", self.javascript)

    def test_owned_clip_deletion_waits_for_canvas_save_and_scrubs_undo(self):
        self.assertIn("function queueReleasedVideoClipAssets(deletedNodes", self.javascript)
        self.assertIn("stripVideoClipAssetsFromUndoHistory(assets)", self.javascript)
        self.assertIn("savedVideoClipSequencesByCanvas.set(", self.javascript)
        self.assertIn("void flushPendingVideoClipDeletions()", self.javascript)
        self.assertIn("/api/canvas-tools/video-clip/delete", self.javascript)
        self.assertIn("body:JSON.stringify({canvas_id:asset.canvasId, clip_id:asset.clipId})", self.javascript)

    def test_owned_clip_is_irreversible_but_shared_asset_waits_for_last_node(self):
        self.assertIn("const liveKeys = new Set(nodes.map(ownedVideoClipAsset)", self.javascript)
        self.assertIn("if(!asset || liveKeys.has(videoClipAssetKey(asset))) return", self.javascript)
        self.assertIn("if(ownedVideoClipAsset(node)) return false", self.javascript)
        self.assertIn("queueReleasedVideoClipAssets(deletingNode ? [deletingNode] : [])", self.javascript)
        self.assertIn("queueReleasedVideoClipAssets(deletingNodes)", self.javascript)


if __name__ == "__main__":
    unittest.main()
