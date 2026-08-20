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

    def test_repeat_receive_updates_only_changed_frame_in_existing_group(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            frame_a_v1 = root / "frame_a_v1.png"
            frame_a_v2 = root / "frame_a_v2.png"
            frame_b = root / "frame_b.png"
            Image.new("RGB", (16, 9), "white").save(frame_a_v1)
            Image.new("RGB", (16, 9), "red").save(frame_a_v2)
            Image.new("RGB", (16, 9), "blue").save(frame_b)

            def build_manifest():
                frames = []
                shots = []
                for index, name in enumerate(("a", "b")):
                    stable_id = f"frame:board-1:000{index}:original"
                    frames.append({
                        "stable_id": stable_id,
                        "shot_stable_id": f"shot:board-1:{index + 1}",
                        "slot_index": index,
                        "shot_number": index + 1,
                        "frame_index": index,
                        "timestamp_ms": index * 1000,
                        "source_name": f"镜头 {index + 1}",
                        "relative_path": f"images/original/{name}.png",
                        "width": 16,
                        "height": 9,
                        "variant": "original",
                    })
                    shots.append({
                        "stable_id": f"shot:film:p:b:{index + 1}",
                        "shot_number": index + 1,
                        "frame_stable_id": stable_id,
                        "prompt": f"镜头提示 {index + 1}",
                    })
                return {
                    "schema": "shiyin-film-bridge",
                    "schema_version": 2,
                    "bridge_id": "film:p:b",
                    "direction": "film-to-shiyin",
                    "source": {"app": "filmstoryboard", "board_id": "board-1"},
                    "storyboard": {
                        "board_name": "增量桥接故事板",
                        "selected_variant": "original",
                        "variants": ["original"],
                        "frames": frames,
                    },
                    "shots": shots,
                }

            first_package = root / "first.filmbridge.zip"
            second_package = root / "second.filmbridge.zip"
            write_bridge_package(
                build_manifest(),
                {"images/original/a.png": frame_a_v1, "images/original/b.png": frame_b},
                first_package,
            )
            write_bridge_package(
                build_manifest(),
                {"images/original/a.png": frame_a_v2, "images/original/b.png": frame_b},
                second_package,
            )
            code = r'''
import sys
from fastapi.testclient import TestClient
import main

first_path, second_path = sys.argv[1], sys.argv[2]
with TestClient(main.app, client=("127.0.0.1", 50000)) as client:
    with open(first_path, "rb") as stream:
        first_response = client.post(
            "/api/canvas-bridges/film/receive",
            files={"file": ("first.filmbridge.zip", stream, "application/zip")},
        )
    assert first_response.status_code == 200, first_response.text
    first = first_response.json()
    assert first["sync_mode"] == "created", first
    canvas = main.load_canvas(first["canvas_id"])
    group = next(node for node in canvas["nodes"] if node.get("id") == first["group_id"])
    images = {node["bridgeFrameStableId"]: node for node in canvas["nodes"] if node.get("id") in group["items"]}
    original = {
        stable_id: {"id": node["id"], "url": node["url"]}
        for stable_id, node in images.items()
    }
    images["frame:board-1:0000:original"]["x"] = 987
    derived = {
        "id": "derived-a", "type": "image", "url": "/output/derived-a.png",
        "derivedFromGroupId": group["id"],
        "bridgeSourceFrameStableId": "frame:board-1:0000:original",
    }
    derived_group = {
        "id": "derived-group", "type": "group", "items": ["derived-a"],
        "derivedFromGroupId": group["id"], "derivedOperation": "line-art", "frameCount": 1,
    }
    canvas["nodes"].extend([derived, derived_group])
    canvas["connections"].append({"id": "derived-connection", "from": group["id"], "to": "derived-group"})
    main.save_canvas(canvas)

    with open(second_path, "rb") as stream:
        second_response = client.post(
            "/api/canvas-bridges/film/receive",
            files={"file": ("second.filmbridge.zip", stream, "application/zip")},
        )
    assert second_response.status_code == 200, second_response.text
    second = second_response.json()
    assert second["canvas_id"] == first["canvas_id"], second
    assert second["group_id"] == first["group_id"], second
    assert second["sync_mode"] == "updated", second
    assert second["sync_stats"]["updated"] == 1, second
    assert second["sync_stats"]["unchanged"] == 1, second
    assert second["sync_stats"]["invalidated_derived"] == 1, second

    updated_canvas = main.load_canvas(second["canvas_id"])
    updated_group = next(node for node in updated_canvas["nodes"] if node.get("id") == second["group_id"])
    updated_images = {node["bridgeFrameStableId"]: node for node in updated_canvas["nodes"] if node.get("id") in updated_group["items"]}
    changed = updated_images["frame:board-1:0000:original"]
    unchanged = updated_images["frame:board-1:0001:original"]
    assert changed["id"] == original["frame:board-1:0000:original"]["id"]
    assert changed["x"] == 987
    assert changed["url"] != original["frame:board-1:0000:original"]["url"]
    assert unchanged["id"] == original["frame:board-1:0001:original"]["id"]
    assert unchanged["url"] == original["frame:board-1:0001:original"]["url"]
    assert not any(node.get("id") in {"derived-a", "derived-group"} for node in updated_canvas["nodes"])
    assert len(main.DATABASE.list_canvases(include_deleted=False)) == 1
'''
            environment = dict(os.environ)
            environment.update({"CANVAS_DATA_DIR": str(root / "data"), "CANVAS_PORT": "3000"})
            completed = subprocess.run(
                [sys.executable, "-c", code, str(first_package), str(second_package)],
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
