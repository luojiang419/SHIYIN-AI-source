import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from canvas_core.kling_cli import KlingCliEnvironment


class KlingCanvasVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def test_builtin_provider_is_available_without_api_key(self):
        providers = {item["id"]: item for item in self.main.default_api_providers()}
        provider = providers["kling-cli"]

        self.assertEqual(provider["protocol"], "kling-cli")
        self.assertTrue(provider["video_models"])
        self.assertFalse(provider["image_models"])
        self.assertFalse(provider["chat_models"])

    def test_canvas_request_accepts_model_specific_parameters(self):
        payload = self.main.CanvasVideoRequest(
            prompt="生成一个短镜头",
            provider_id="kling-cli",
            model="kling-video-v3_0",
            model_parameters={"duration": "8", "prefer_multi_shots": "true"},
        )

        self.assertEqual(payload.model_parameters["duration"], "8")
        self.assertEqual(payload.model_parameters["prefer_multi_shots"], "true")

    def test_kling_generation_selects_text_schema_and_downloads_result(self):
        environment = KlingCliEnvironment(
            node_path="node.exe",
            npm_path="npm.cmd",
            kling_path="kling.cmd",
            entrypoint_path="cli.js",
            version="0.1.3",
        )
        captured = {}

        class FakeService:
            def __init__(self, environment):
                self.environment = environment

            def capabilities(self):
                return {
                    "text_to_video": [
                        {
                            "model": "kling-video-v3_0",
                            "arguments": [
                                {"name": "duration", "allowed_values": ["5", "8"]},
                                {"name": "aspect_ratio", "allowed_values": ["16:9"]},
                                {"name": "resolution", "allowed_values": ["1080p", "4k"]},
                            ],
                        }
                    ],
                    "image_to_video": [],
                }

            def generate(self, **kwargs):
                captured.update(kwargs)
                return {
                    "generation_id": "generation-1",
                    "credits_consumed": 20,
                    "url": "https://cdn.example/kling.mp4",
                    "raw": {"status": "COMPLETED"},
                }

        payload = self.main.CanvasVideoRequest(
            prompt="镜头缓慢推进",
            provider_id="kling-cli",
            model="kling-video-v3_0",
            duration=8,
            aspect_ratio="16:9",
            resolution="4k",
        )
        with (
            patch.object(self.main, "resolve_kling_cli", return_value=environment),
            patch.object(self.main, "KlingCliService", FakeService),
            patch.object(
                self.main,
                "save_remote_video_to_output",
                new=AsyncMock(return_value="/assets/output/kling.mp4"),
            ),
        ):
            result = asyncio.run(self.main.generate_kling_cli_video(payload))

        self.assertEqual(captured["command"], "text_to_video")
        self.assertEqual(captured["model"]["model"], "kling-video-v3_0")
        self.assertEqual(captured["parameters"]["duration"], "8")
        self.assertEqual(captured["parameters"]["resolution"], "4k")
        self.assertEqual(result["videos"], ["/assets/output/kling.mp4"])
        self.assertEqual(result["task_id"], "generation-1")
        self.assertEqual(result["credits_consumed"], 20)

    def test_kling_generation_switches_to_image_schema_and_materializes_data_url(self):
        environment = KlingCliEnvironment(
            node_path="node.exe",
            npm_path="npm.cmd",
            kling_path="kling.cmd",
            entrypoint_path="cli.js",
            version="0.1.3",
        )
        captured = {}

        class FakeService:
            def __init__(self, environment):
                self.environment = environment

            def capabilities(self):
                return {
                    "text_to_video": [],
                    "image_to_video": [
                        {
                            "model": "kling-image-video",
                            "arguments": [
                                {"name": "duration", "allowed_values": ["5", "10"]}
                            ],
                            "inputs": [{"name": "first_image", "required": True}],
                        }
                    ],
                }

            def generate(self, **kwargs):
                captured.update(kwargs)
                self.assert_materialized(kwargs["images"])
                return {
                    "generation_id": "generation-image-1",
                    "url": "https://cdn.example/image-video.mp4",
                    "raw": {"status": "COMPLETED"},
                }

            @staticmethod
            def assert_materialized(images):
                if len(images) != 1 or not __import__("pathlib").Path(images[0]).is_file():
                    raise AssertionError("data URL 应在调用 CLI 前转为临时本地文件")

        payload = self.main.CanvasVideoRequest(
            prompt="让参考图中的人物转身",
            provider_id="kling-cli",
            model="kling-image-video",
            duration=5,
            images=[{"url": "data:image/png;base64,iVBORw0KGgo="}],
        )
        with (
            patch.object(self.main, "resolve_kling_cli", return_value=environment),
            patch.object(self.main, "KlingCliService", FakeService),
            patch.object(
                self.main,
                "save_remote_video_to_output",
                new=AsyncMock(return_value="/assets/output/kling-image.mp4"),
            ),
        ):
            result = asyncio.run(self.main.generate_kling_cli_video(payload))

        self.assertEqual(captured["command"], "image_to_video")
        self.assertEqual(captured["model"]["model"], "kling-image-video")
        self.assertEqual(result["videos"], ["/assets/output/kling-image.mp4"])

    def test_kling_generation_submits_all_mapped_reference_images_in_one_request(self):
        environment = KlingCliEnvironment(
            node_path="node.exe", npm_path="npm.cmd", kling_path="kling.cmd",
            entrypoint_path="cli.js", version="0.1.3"
        )
        captured = {}

        class FakeService:
            def __init__(self, environment):
                self.environment = environment

            def capabilities(self):
                return {
                    "text_to_video": [],
                    "image_to_video": [{"model": "kling-multi", "arguments": []}],
                }

            def generate(self, **kwargs):
                captured.update(kwargs)
                return {"generation_id": "generation-multi-1", "url": "https://cdn.example/multi.mp4"}

        payload = self.main.CanvasVideoRequest(
            prompt="资产映射：@图1=分镜图，@图2=演员A，@图3=服装A。镜头1，演员A向镜头走近。",
            provider_id="kling-cli",
            model="kling-multi",
            images=[
                {"url": "https://cdn.example/storyboard.png", "asset_index": 1, "input_role": "storyboard", "role_label": "分镜图"},
                {"url": "https://cdn.example/actor.png", "asset_index": 2, "input_role": "actor-0", "role_label": "演员A"},
                {"url": "https://cdn.example/outfit.png", "asset_index": 3, "input_role": "outfit-0", "role_label": "服装A"},
            ],
        )
        with (
            patch.object(self.main, "resolve_kling_cli", return_value=environment),
            patch.object(self.main, "KlingCliService", FakeService),
            patch.object(self.main, "save_remote_video_to_output", new=AsyncMock(return_value="/assets/output/kling-multi.mp4")),
        ):
            result = asyncio.run(self.main.generate_kling_cli_video(payload))

        self.assertEqual(len(captured["images"]), 3)
        self.assertEqual(result["request"]["image_count"], 3)
        self.assertEqual(
            result["request"]["image_mapping"],
            [
                {"asset_index": 1, "input_role": "storyboard", "role_label": "分镜图"},
                {"asset_index": 2, "input_role": "actor-0", "role_label": "演员A"},
                {"asset_index": 3, "input_role": "outfit-0", "role_label": "服装A"},
            ],
        )

    def test_kling_omni_default_alias_submits_capability_model_name(self):
        environment = KlingCliEnvironment(
            node_path="node.exe",
            npm_path="npm.cmd",
            kling_path="kling.cmd",
            entrypoint_path="cli.js",
            version="0.1.3",
        )
        captured = {}

        class FakeService:
            def __init__(self, environment):
                self.environment = environment

            def capabilities(self):
                return {
                    "text_to_video": [
                        {"model": "kling-video-v3_0-omni", "alias": "VIDEO 3.0 Omni", "arguments": []}
                    ],
                    "image_to_video": [],
                }

            def generate(self, **kwargs):
                captured.update(kwargs)
                return {"generation_id": "generation-omni-1", "url": "https://cdn.example/omni.mp4"}

        payload = self.main.CanvasVideoRequest(
            prompt="镜头缓慢推进",
            provider_id="kling-cli",
            model="kling-v3-omni",
        )
        with (
            patch.object(self.main, "resolve_kling_cli", return_value=environment),
            patch.object(self.main, "KlingCliService", FakeService),
            patch.object(
                self.main,
                "save_remote_video_to_output",
                new=AsyncMock(return_value="/assets/output/kling-omni.mp4"),
            ),
        ):
            result = asyncio.run(self.main.generate_kling_cli_video(payload))

        self.assertEqual(captured["model"]["model"], "kling-video-v3_0-omni")
        self.assertEqual(result["request"]["model"], "kling-video-v3_0-omni")

    def test_kling_video_reference_is_rejected_before_cli_or_upload(self):
        payload = self.main.CanvasVideoRequest(
            prompt="参考视频的节奏生成新镜头",
            provider_id="kling-cli",
            model="kling-video-v3_0",
            videos=["/assets/output/canvases/canvas-1/video-clips/clip-1.mp4"],
        )
        with patch.object(self.main, "resolve_kling_cli") as resolve:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(self.main.generate_kling_cli_video(payload))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("已移除", str(raised.exception.detail))
        resolve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
