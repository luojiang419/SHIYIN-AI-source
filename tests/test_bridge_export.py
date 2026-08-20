import tempfile
import unittest
from pathlib import Path

from PIL import Image

from canvas_core.bridge_export import build_shiyin_bridge_payload


class BridgeExportTests(unittest.TestCase):
    def test_builds_original_and_derived_variants_with_prompt(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            original = root / "original.png"
            line_art = root / "line.png"
            Image.new("RGB", (100, 200), "red").save(original)
            Image.new("RGB", (160, 90), "white").save(line_art)
            canvas = {"id": "canvas-1", "title": "桥接画布", "project": "project-1"}
            group = {
                "id": "group-1", "type": "group", "items": ["image-1"],
                "bridgeId": "film:p:b", "bridgeBoardId": "board-1", "bridgeBoardName": "故事板",
                "bridgeSelectedVariant": "original", "bridgePromptNodeIds": ["prompt-1"],
            }
            nodes = [
                group,
                {"id": "image-1", "type": "image", "url": "/original", "name": "原图", "bridgeFrameIndex": 0, "bridgeShotNumber": 1},
                {"id": "derived-group", "type": "group", "items": ["image-2"], "derivedFromGroupId": "group-1", "derivedOperation": "line-art"},
                {"id": "image-2", "type": "image", "url": "/line", "name": "线稿", "frameIndex": 0, "derivedOperation": "line-art"},
                {"id": "prompt-1", "type": "prompt", "text": "中景，人物转身", "bridgeShotNumber": 1, "bridgeSourceFrameNodeId": "image-1"},
            ]
            paths = {"/original": str(original), "/line": str(line_art)}
            manifest, files = build_shiyin_bridge_payload(
                canvas=canvas,
                group=group,
                nodes=nodes,
                local_path_for_url=lambda url: paths.get(url, ""),
            )
            self.assertEqual(manifest["direction"], "shiyin-to-film")
            self.assertEqual(manifest["storyboard"]["variants"], ["original", "line-art"])
            self.assertEqual(len(manifest["storyboard"]["frames"]), 2)
            self.assertEqual(manifest["storyboard"]["frames"][1]["width"], 160)
            self.assertEqual(manifest["shots"][0]["prompt"], "中景，人物转身")
            self.assertEqual(len(files), 2)


if __name__ == "__main__":
    unittest.main()
