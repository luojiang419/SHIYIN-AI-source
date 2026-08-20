import unittest

from canvas_core.bridge_sync import find_bridge_target, sync_film_bridge_canvas


def manifest(frames, shots=None, checksums=None):
    return {
        "bridge_id": "film:project:board",
        "direction": "film-to-shiyin",
        "exported_at": "2026-08-20T10:00:00Z",
        "source": {"board_id": "board-1"},
        "storyboard": {
            "board_name": "测试故事板",
            "selected_variant": "original",
            "frames": frames,
        },
        "shots": shots or [],
        "checksums": checksums or {},
    }


def frame(stable_id, relative_path, url, *, index=0, caption=""):
    return {
        "stable_id": stable_id,
        "relative_path": relative_path,
        "url": url,
        "source_name": f"镜头 {index + 1}",
        "variant": "original",
        "frame_index": index,
        "slot_index": index,
        "shot_number": index + 1,
        "width": 1600,
        "height": 900,
        "caption": caption,
    }


class BridgeSyncTests(unittest.TestCase):
    def setUp(self):
        self.counter = 0

    def make_id(self, prefix):
        self.counter += 1
        return f"{prefix}-{self.counter}"

    def test_create_then_repeat_is_idempotent(self):
        frames = [frame("frame:a", "images/a.png", "/input/a-hash.png")]
        value = manifest(frames, checksums={"images/a.png": "a" * 64})
        canvas = {"id": "canvas-1", "nodes": [], "connections": []}
        first = sync_film_bridge_canvas(canvas, value, frames, id_factory=self.make_id)
        image = first["image_nodes"][0]
        group = first["group"]
        image_position = (image["x"], image["y"])

        second = sync_film_bridge_canvas(canvas, value, frames, id_factory=self.make_id)

        self.assertEqual(second["sync_mode"], "unchanged")
        self.assertEqual(second["stats"]["unchanged"], 1)
        self.assertEqual(second["image_nodes"][0]["id"], image["id"])
        self.assertEqual((second["image_nodes"][0]["x"], second["image_nodes"][0]["y"]), image_position)
        self.assertEqual(second["group"]["id"], group["id"])
        self.assertEqual(len([node for node in canvas["nodes"] if node.get("type") == "group"]), 1)

    def test_changed_frame_updates_in_place_and_invalidates_only_its_derived_node(self):
        frames = [
            frame("frame:a", "images/a.png", "/input/a-v1.png", index=0),
            frame("frame:b", "images/b.png", "/input/b-v1.png", index=1),
        ]
        value = manifest(frames, checksums={"images/a.png": "a" * 64, "images/b.png": "b" * 64})
        canvas = {"id": "canvas-1", "nodes": [], "connections": []}
        first = sync_film_bridge_canvas(canvas, value, frames, id_factory=self.make_id)
        group = first["group"]
        first_by_stable = {node["bridgeFrameStableId"]: node for node in first["image_nodes"]}
        first_by_stable["frame:a"]["x"] = 777
        derived_a = {
            "id": "derived-a", "type": "image", "derivedFromGroupId": group["id"],
            "bridgeSourceFrameStableId": "frame:a",
        }
        derived_b = {
            "id": "derived-b", "type": "image", "derivedFromGroupId": group["id"],
            "bridgeSourceFrameStableId": "frame:b",
        }
        derived_group = {
            "id": "derived-group", "type": "group", "derivedFromGroupId": group["id"],
            "items": ["derived-a", "derived-b"], "frameCount": 2,
        }
        canvas["nodes"].extend([derived_a, derived_b, derived_group])
        canvas["connections"].append({"id": "c1", "from": group["id"], "to": "derived-group"})

        changed_frames = [
            frame("frame:a", "images/a.png", "/input/a-v2.png", index=0),
            frame("frame:b", "images/b.png", "/input/b-v1.png", index=1),
        ]
        changed_manifest = manifest(changed_frames, checksums={"images/a.png": "c" * 64, "images/b.png": "b" * 64})
        result = sync_film_bridge_canvas(canvas, changed_manifest, changed_frames, id_factory=self.make_id)
        by_stable = {node["bridgeFrameStableId"]: node for node in result["image_nodes"]}

        self.assertEqual(result["stats"]["updated"], 1)
        self.assertEqual(result["stats"]["unchanged"], 1)
        self.assertEqual(result["stats"]["invalidated_derived"], 1)
        self.assertEqual(by_stable["frame:a"]["id"], first_by_stable["frame:a"]["id"])
        self.assertEqual(by_stable["frame:a"]["x"], 777)
        self.assertEqual(by_stable["frame:a"]["url"], "/input/a-v2.png")
        self.assertEqual(by_stable["frame:b"]["id"], first_by_stable["frame:b"]["id"])
        self.assertNotIn("derived-a", {node["id"] for node in canvas["nodes"]})
        self.assertIn("derived-b", {node["id"] for node in canvas["nodes"]})
        kept_group = next(node for node in canvas["nodes"] if node["id"] == "derived-group")
        self.assertEqual(kept_group["items"], ["derived-b"])
        self.assertEqual(kept_group["frameCount"], 1)

    def test_add_remove_and_prompt_update_preserve_existing_positions(self):
        frames = [frame("frame:a", "images/a.png", "/input/a.png")]
        shots = [{
            "stable_id": "shot:a", "shot_number": 1,
            "frame_stable_id": "frame:a", "prompt": "旧提示词",
        }]
        value = manifest(frames, shots, {"images/a.png": "a" * 64})
        canvas = {"id": "canvas-1", "nodes": [], "connections": []}
        first = sync_film_bridge_canvas(canvas, value, frames, id_factory=self.make_id)
        old_image_id = first["image_nodes"][0]["id"]
        old_prompt = first["prompt_nodes"][0]
        old_prompt["x"] = 999

        new_frames = [frame("frame:b", "images/b.png", "/input/b.png", index=1)]
        new_shots = [{
            "stable_id": "shot:a", "shot_number": 1,
            "frame_stable_id": "frame:b", "prompt": "新提示词",
        }]
        result = sync_film_bridge_canvas(
            canvas,
            manifest(new_frames, new_shots, {"images/b.png": "b" * 64}),
            new_frames,
            id_factory=self.make_id,
        )

        self.assertEqual(result["stats"]["created"], 1)
        self.assertEqual(result["stats"]["removed"], 1)
        self.assertEqual(result["stats"]["prompt_updated"], 1)
        self.assertNotIn(old_image_id, {node["id"] for node in canvas["nodes"]})
        self.assertEqual(result["prompt_nodes"][0]["id"], old_prompt["id"])
        self.assertEqual(result["prompt_nodes"][0]["x"], 999)
        self.assertEqual(result["prompt_nodes"][0]["text"], "新提示词")

    def test_find_bridge_target_skips_deleted_canvas(self):
        deleted = {"id": "deleted", "deleted_at": 1, "nodes": [{
            "id": "g1", "type": "group", "bridgeId": "film:project:board", "bridgeDirection": "film-to-shiyin",
        }]}
        active_group = {
            "id": "g2", "type": "group", "bridgeId": "film:project:board", "bridgeDirection": "film-to-shiyin",
        }
        active = {"id": "active", "nodes": [active_group]}

        canvas, group = find_bridge_target([deleted, active], "film:project:board")

        self.assertEqual(canvas["id"], "active")
        self.assertEqual(group["id"], "g2")


if __name__ == "__main__":
    unittest.main()
