import unittest

from canvas_core.bridge_manifest import (
    BRIDGE_SCHEMA,
    BridgeManifestError,
    frame_stable_id,
    safe_relative_path,
    shot_stable_id,
    validate_manifest,
)


def sample_manifest():
    return {
        "schema": BRIDGE_SCHEMA,
        "schema_version": 2,
        "bridge_id": "film:project-1:board-1",
        "direction": "film-to-shiyin",
        "exported_at": "2026-08-20T00:00:00Z",
        "source": {"app": "filmstoryboard"},
        "storyboard": {
            "board_name": "测试故事板",
            "selected_variant": "original",
            "variants": ["original", "line-art"],
            "frames": [{
                "stable_id": frame_stable_id("board-1", 0, "original"),
                "shot_stable_id": shot_stable_id("board-1", 1),
                "slot_index": 0,
                "shot_number": 1,
                "frame_index": 0,
                "timestamp_ms": 0,
                "source_name": "镜头 01",
                "relative_path": "images/original/001.png",
                "width": 1920,
                "height": 1080,
                "variant": "original",
                "caption": "",
                "sha256": "abc",
            }],
        },
        "shots": [{
            "stable_id": shot_stable_id("board-1", 1),
            "shot_number": 1,
            "frame_stable_id": frame_stable_id("board-1", 0, "original"),
            "duration_seconds": 2.5,
            "visual": "室内",
            "content": "",
            "prompt": "",
        }],
    }


class BridgeManifestTests(unittest.TestCase):
    def test_manifest_normalizes_optional_fields_and_preserves_frames(self):
        result = validate_manifest(sample_manifest())
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["storyboard"]["frames"][0]["width"], 1920)
        self.assertEqual(result["shots"][0]["duration_seconds"], 2.5)

    def test_stable_ids_are_deterministic(self):
        self.assertEqual(frame_stable_id("board-1", 3), "frame:board-1:0003:original")
        self.assertEqual(shot_stable_id("board-1", 3), "shot:board-1:3")

    def test_path_safety_rejects_absolute_and_traversal(self):
        self.assertEqual(safe_relative_path("images\\original\\001.png"), "images/original/001.png")
        for value in ("../secret.png", "/secret.png", "C:/secret.png", "images//bad.png"):
            with self.subTest(value=value), self.assertRaises(BridgeManifestError):
                safe_relative_path(value)

    def test_manifest_rejects_duplicate_frame_ids_and_unknown_variant(self):
        payload = sample_manifest()
        payload["storyboard"]["frames"].append(dict(payload["storyboard"]["frames"][0]))
        with self.assertRaises(BridgeManifestError):
            validate_manifest(payload)
        payload = sample_manifest()
        payload["storyboard"]["frames"][0]["variant"] = "unknown"
        with self.assertRaises(BridgeManifestError):
            validate_manifest(payload)

    def test_manifest_rejects_missing_dimensions(self):
        payload = sample_manifest()
        payload["storyboard"]["frames"][0]["width"] = 0
        with self.assertRaises(BridgeManifestError):
            validate_manifest(payload)


if __name__ == "__main__":
    unittest.main()
