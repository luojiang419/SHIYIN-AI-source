import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from canvas_core.bridge_direct import DirectBridgeError, materialize_direct_bridge_frames


class DirectBridgeTests(unittest.TestCase):
    def _manifest(self, content: bytes) -> dict:
        checksum = hashlib.sha256(content).hexdigest()
        return {
            "schema": "shiyin-film-bridge",
            "schema_version": 2,
            "bridge_id": "film:project:board",
            "direction": "film-to-shiyin",
            "source": {"app": "filmstoryboard", "board_id": "board"},
            "storyboard": {
                "board_name": "直接故事板",
                "selected_variant": "original",
                "variants": ["original"],
                "frames": [{
                    "stable_id": "frame:board:0000:original",
                    "shot_stable_id": "shot:board:1",
                    "slot_index": 0,
                    "shot_number": 1,
                    "frame_index": 0,
                    "timestamp_ms": 0,
                    "source_name": "镜头 1",
                    "relative_path": "images/original/0000.png",
                    "upload_name": "frame_0000.png",
                    "width": 16,
                    "height": 9,
                    "variant": "original",
                    "sha256": checksum,
                }],
            },
            "shots": [],
        }

    def test_materializes_direct_upload_without_archive(self):
        with tempfile.TemporaryDirectory() as root:
            image = Path(root) / "source.png"
            Image.new("RGB", (16, 9), "white").save(image)
            content = image.read_bytes()
            result = materialize_direct_bridge_frames(
                self._manifest(content),
                {"frame_0000.png": content},
                Path(root) / "media",
                "canvas-1",
            )
            self.assertEqual(len(result), 1)
            self.assertTrue(Path(result[0]["local_path"]).is_file())
            self.assertEqual(result[0]["width"], 16)
            self.assertEqual(result[0]["height"], 9)

    def test_rejects_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            image = Path(root) / "source.png"
            Image.new("RGB", (16, 9), "white").save(image)
            manifest = self._manifest(image.read_bytes())
            with self.assertRaises(DirectBridgeError):
                materialize_direct_bridge_frames(
                    manifest,
                    {"frame_0000.png": b"not-an-image"},
                    Path(root) / "media",
                    "canvas-1",
                )


if __name__ == "__main__":
    unittest.main()
