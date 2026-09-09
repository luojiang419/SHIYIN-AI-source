import asyncio
import unittest
from unittest.mock import AsyncMock, patch


class MiniMaxH3VideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def test_builtin_provider_is_available_without_api_key(self):
        providers = {item["id"]: item for item in self.main.default_api_providers()}
        provider = providers["minimax-h3"]
        self.assertEqual(provider["base_url"], "http://127.0.0.1:7860")
        self.assertEqual(provider["video_models"], ["MiniMax H3"])

    def test_public_tunnel_address_is_preserved_for_remote_clients(self):
        providers = self.main.merge_default_api_providers([
            {
                "id": "minimax-h3",
                "name": "MiniMax H3",
                "base_url": "http://115.231.35.105:7866",
                "protocol": "minimax-h3",
                "enabled": True,
                "video_models": ["MiniMax H3"],
            }
        ])
        provider = next(item for item in providers if item["id"] == "minimax-h3")
        self.assertEqual(provider["base_url"], "http://115.231.35.105:7866")

    def test_public_tunnel_address_without_scheme_gets_http_prefix(self):
        self.assertEqual(
            self.main.normalize_minimax_h3_base_url("115.231.35.105:7866/"),
            "http://115.231.35.105:7866",
        )

        provider = self.main.normalize_provider({
            "id": "minimax-h3",
            "name": "MiniMax H3",
            "base_url": "115.231.35.105:7866",
            "protocol": "minimax-h3",
            "enabled": True,
            "video_models": ["MiniMax H3"],
        })
        self.assertEqual(provider["base_url"], "http://115.231.35.105:7866")

    def test_protocol_relative_h3_address_gets_http_scheme(self):
        self.assertEqual(
            self.main.normalize_minimax_h3_base_url("//115.231.35.105:7866/"),
            "http://115.231.35.105:7866",
        )

    def test_custom_remote_h3_address_is_preserved(self):
        self.assertEqual(
            self.main.normalize_minimax_h3_base_url("https://h3.example.test/api/"),
            "https://h3.example.test/api",
        )

    def test_resolution_uses_deployed_h3_presets(self):
        self.assertEqual(
            self.main.minimax_h3_resolution("16:9", ""),
            "0.2MP 16:9 - 608x352",
        )
        self.assertEqual(
            self.main.minimax_h3_resolution("9:16", "0.4MP 9:16 - 480x864"),
            "0.4MP 9:16 - 480x864",
        )

    def test_aspect_ratio_replaces_stale_resolution_but_keeps_mp_tier_when_available(self):
        cases = {
            "21:9": "0.2MP 21:9 - 672x288",
            "16:9": "0.2MP 16:9 - 608x352",
            "4:3": "0.2MP 4:3 - 512x384",
            "1:1": "Square 512x512",
            "3:4": "0.2MP 3:4 - 384x512",
            "9:16": "0.2MP 9:16 - 352x608",
        }
        for ratio, expected in cases.items():
            with self.subTest(ratio=ratio):
                self.assertEqual(
                    self.main.minimax_h3_resolution(ratio, "0.2MP 16:9 - 608x352"),
                    expected,
                )
        self.assertEqual(
            self.main.minimax_h3_resolution("9:16", "0.3MP 16:9 - 736x416"),
            "0.3MP 9:16 - 416x736",
        )

    def test_resolution_is_preserved_when_aspect_ratio_is_missing(self):
        self.assertEqual(
            self.main.minimax_h3_resolution("", "0.4MP 9:16 - 480x864"),
            "0.4MP 9:16 - 480x864",
        )

    def test_h3_request_repairs_stale_resolution_before_submission(self):
        payload = self.main.CanvasVideoRequest(
            prompt="A slow camera move.",
            provider_id="minimax-h3",
            model="MiniMax H3",
            aspect_ratio="3:4",
            resolution="0.2MP 16:9 - 608x352",
            duration=3,
            steps=8,
        )

        body = asyncio.run(self.main.minimax_h3_video_request(object(), payload))

        self.assertEqual(body["resolution"], "0.2MP 3:4 - 384x512")
        self.assertEqual(body["duration"], 3)
        self.assertEqual(body["steps"], 8)

    def test_keyframes_request_keeps_first_and_last_frame_roles(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self):
                self.post_body = None

            async def post(self, url, json):
                self.post_body = json
                return FakeResponse({"id": "job-1", "status": "queued"})

            async def get(self, url):
                return FakeResponse({"id": "job-1", "status": "done", "output": "/outputs/h3.mp4"})

        payload = self.main.CanvasVideoRequest(
            prompt="镜头缓慢推进",
            provider_id="minimax-h3",
            model="MiniMax H3",
            duration=5,
            aspect_ratio="16:9",
            resolution="0.2MP 16:9 - 608x352",
            steps=64,
            images=[
                {"url": "data:image/png;base64,AA==", "role": "first_frame"},
                {"url": "data:image/png;base64,AQ==", "role": "last_frame"},
            ],
            multimodal=False,
        )
        client = FakeClient()
        with (
            patch.object(self.main.asyncio, "sleep", new=AsyncMock()),
            patch.object(self.main, "save_remote_video_to_output", new=AsyncMock(return_value="/assets/output/h3.mp4")),
        ):
            result = asyncio.run(self.main.generate_minimax_h3_video(client, payload, {
                "id": "minimax-h3",
                "name": "MiniMax H3",
                "base_url": "http://h3.local",
            }))

        self.assertEqual(client.post_body["mode"], "keyframes")
        self.assertEqual(client.post_body["first_frame"], "data:image/png;base64,AA==")
        self.assertEqual(client.post_body["last_frame"], "data:image/png;base64,AQ==")
        self.assertEqual(client.post_body["steps"], 64)
        self.assertEqual(result["videos"], ["/assets/output/h3.mp4"])

    def test_h3_steps_accept_values_below_previous_lower_bound(self):
        payload = self.main.CanvasVideoRequest(
            prompt="镜头缓慢推进",
            provider_id="minimax-h3",
            model="MiniMax H3",
            steps=2,
        )
        self.assertEqual(payload.steps, 2)

    def test_multimodal_request_keeps_nine_images_and_three_videos(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self):
                self.post_body = None

            async def post(self, url, json):
                self.post_body = json
                return FakeResponse({"id": "job-2"})

            async def get(self, url):
                return FakeResponse({"status": "done", "output": "/outputs/mixed.mp4"})

        payload = self.main.CanvasVideoRequest(
            prompt="参考人物、动作、运镜和声音",
            provider_id="minimax-h3",
            model="MiniMax H3",
            duration=8,
            images=[{"url": f"data:image/png;base64,{index:02d}=="} for index in range(9)],
            videos=[f"data:video/mp4;base64,{index:02d}==" for index in range(3)],
            multimodal=True,
        )
        client = FakeClient()
        with (
            patch.object(self.main.asyncio, "sleep", new=AsyncMock()),
            patch.object(self.main, "save_remote_video_to_output", new=AsyncMock(return_value="/assets/output/mixed.mp4")),
        ):
            asyncio.run(self.main.generate_minimax_h3_video(client, payload, {
                "id": "minimax-h3",
                "name": "MiniMax H3",
                "base_url": "http://h3.local",
            }))

        self.assertEqual(client.post_body["mode"], "references")
        self.assertEqual(len(client.post_body["reference_images"]), 9)
        self.assertEqual(len(client.post_body["reference_videos"]), 3)

    def test_remote_reference_is_downloaded_and_converted_to_data_url(self):
        class FakeResponse:
            content = b"image-bytes"
            headers = {"content-type": "image/png"}

            def raise_for_status(self):
                return None

        class FakeClient:
            async def get(self, url):
                return FakeResponse()

        value = asyncio.run(self.main.minimax_h3_reference_value(FakeClient(), "https://assets.example/ref.png", "image"))
        self.assertTrue(value.startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
