import tempfile
import unittest
from pathlib import Path

from canvas_core.bridge_media import materialize_bridge_frames
from canvas_core.bridge_package import read_bridge_package, write_bridge_package


class BridgeMediaTests(unittest.TestCase):
    def test_materialize_selected_variant_and_metadata(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            original = root / "original.png"
            expanded = root / "expanded.png"
            original.write_bytes(b"original")
            expanded.write_bytes(b"expanded")
            manifest = {
                "schema": "shiyin-film-bridge",
                "schema_version": 2,
                "bridge_id": "film:p:b",
                "direction": "film-to-shiyin",
                "source": {"app": "filmstoryboard"},
                "storyboard": {
                    "board_name": "板",
                    "selected_variant": "expanded-16x9",
                    "variants": ["original", "expanded-16x9"],
                    "frames": [
                        {"stable_id": "frame:g:0000:original", "relative_path": "images/original/0001.png", "width": 10, "height": 10, "variant": "original", "frame_index": 0, "slot_index": 0},
                        {"stable_id": "frame:g:0000:expanded-16x9", "relative_path": "images/expanded-16x9/0001.png", "width": 16, "height": 9, "variant": "expanded-16x9", "frame_index": 0, "slot_index": 0},
                    ],
                },
                "shots": [],
            }
            package_path = root / "bridge.zip"
            write_bridge_package(manifest, {"images/original/0001.png": original, "images/expanded-16x9/0001.png": expanded}, package_path)
            package = read_bridge_package(package_path, root / "extract")
            try:
                records = materialize_bridge_frames(package, root / "media", "canvas-1", selected_variant="expanded-16x9")
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["variant"], "expanded-16x9")
                self.assertEqual(Path(records[0]["local_path"]).read_bytes(), b"expanded")
            finally:
                package.cleanup()


if __name__ == "__main__":
    unittest.main()
