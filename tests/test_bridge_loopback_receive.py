import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from canvas_core.bridge_package import write_bridge_package


class BridgeLoopbackReceiveTests(unittest.TestCase):
    def test_receives_package_and_persists_group(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            frame = root / "frame.png"
            Image.new("RGB", (16, 9), "white").save(frame)
            package_path = root / "film.filmbridge.zip"
            manifest = {
                "schema": "shiyin-film-bridge",
                "schema_version": 2,
                "bridge_id": "film:p:b",
                "direction": "film-to-shiyin",
                "source": {"app": "filmstoryboard", "board_id": "board-1"},
                "storyboard": {
                    "board_name": "自动桥接故事板",
                    "selected_variant": "original",
                    "variants": ["original"],
                    "frames": [{
                        "stable_id": "frame:board-1:0000:original",
                        "shot_stable_id": "shot:board-1:1",
                        "slot_index": 0,
                        "shot_number": 1,
                        "frame_index": 0,
                        "timestamp_ms": 0,
                        "source_name": "镜头 1",
                        "relative_path": "images/original/0001.png",
                        "width": 16,
                        "height": 9,
                        "variant": "original",
                    }],
                },
                "shots": [{
                    "stable_id": "shot:film:p:b:1",
                    "shot_number": 1,
                    "frame_stable_id": "frame:board-1:0000:original",
                    "prompt": "中景，人物转身",
                }],
            }
            write_bridge_package(manifest, {"images/original/0001.png": frame}, package_path)
            code = """
import sys
from fastapi.testclient import TestClient
import main
package_path = sys.argv[1]
with TestClient(main.app, client=("127.0.0.1", 50000)) as client:
    with open(package_path, "rb") as stream:
        response = client.post(
            "/api/canvas-bridges/film/receive",
            files={"file": ("film.filmbridge.zip", stream, "application/zip")},
            data={"canvas_title": "自动发送测试"},
        )
assert response.status_code == 200, response.text
payload = response.json()
assert payload["frame_count"] == 1
canvas = main.load_canvas(payload["canvas_id"])
assert any(node.get("id") == payload["group_id"] for node in canvas["nodes"])
"""
            environment = dict(os.environ)
            environment.update(
                {"CANVAS_DATA_DIR": str(root / "data"), "CANVAS_PORT": "3000"},
            )
            completed = subprocess.run(
                [sys.executable, "-c", code, str(package_path)],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
