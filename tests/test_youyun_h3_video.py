import asyncio
import unittest
from unittest.mock import AsyncMock, patch


class YouyunH3VideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main


    def test_h3_request_repairs_stale_resolution_before_submission(self):
        payload = self.main.CanvasVideoRequest(
            prompt="A slow camera move.",
            provider_id="youyun-h3",
            model="MiniMax H3",
            aspect_ratio="3:4",
            resolution="0.2MP 16:9 - 608x352",
            duration=3,
            steps=8,
        )

        body = asyncio.run(self.main.youyun_h3_video_request(object(), payload))

        self.assertEqual(body["resolution"], "768P")
        self.assertEqual(body["duration"], 4)
        self.assertEqual(body["ratio"], "3:4")


    def test_compshare_request_uses_official_audio_and_delivery_options(self):
        payload = self.main.CanvasVideoRequest(
            prompt="A quiet studio shot.",
            provider_id="youyun-h3",
            model="MiniMax-H3",
            duration=99,
            aspect_ratio="adaptive",
            resolution="2K",
            watermark=True,
            mute_audio=True,
            multimodal=True,
            images=[{"url": "data:image/png;base64,AA=="}],
            audios=["data:audio/mpeg;base64,AA=="],
        )

        body = asyncio.run(self.main.youyun_h3_video_request(object(), payload))

        self.assertEqual(body["resolution"], "2K")
        self.assertEqual(body["duration"], 30)
        self.assertEqual(body["ratio"], "adaptive")
        self.assertTrue(body["aigc_watermark"])
        self.assertTrue(body["mute_audio"])
        self.assertEqual(body["content"][-1]["type"], "audio_url")


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

            async def post(self, url, headers, json):
                self.post_body = json
                return FakeResponse({"task_id": "job-1"})

            async def get(self, url, headers):
                return FakeResponse({"task": {"id": "job-1", "status": "succeeded", "content": {"url": "https://cdn.example/h3.mp4"}}})

        payload = self.main.CanvasVideoRequest(
            prompt="镜头缓慢推进",
            provider_id="youyun-h3",
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
            patch.object(self.main, "provider_env_key_value", return_value="test-only"),
        ):
            result = asyncio.run(self.main.generate_youyun_h3_video(client, payload, {
                "id": "youyun-h3",
                "name": "MiniMax H3",
                "base_url": "http://h3.local",
            }))

        self.assertEqual(client.post_body["model"], "MiniMax-H3")
        self.assertEqual(client.post_body["content"][1]["role"], "first_frame")
        self.assertEqual(client.post_body["content"][2]["role"], "last_frame")
        self.assertEqual(result["videos"], ["/assets/output/h3.mp4"])


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

            async def post(self, url, headers, json):
                self.post_body = json
                return FakeResponse({"task_id": "job-2"})

            async def get(self, url, headers):
                return FakeResponse({"task": {"status": "succeeded", "content": {"url": "https://cdn.example/mixed.mp4"}}})

        payload = self.main.CanvasVideoRequest(
            prompt="参考人物、动作、运镜和声音",
            provider_id="youyun-h3",
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
            patch.object(self.main, "provider_env_key_value", return_value="test-only"),
        ):
            asyncio.run(self.main.generate_youyun_h3_video(client, payload, {
                "id": "youyun-h3",
                "name": "MiniMax H3",
                "base_url": "http://h3.local",
            }))

        self.assertEqual(sum(item["type"] == "image_url" for item in client.post_body["content"]), 9)
        self.assertEqual(sum(item["type"] == "video_url" for item in client.post_body["content"]), 3)


    def test_remote_reference_is_downloaded_and_converted_to_data_url(self):
        class FakeResponse:
            content = b"image-bytes"
            headers = {"content-type": "image/png"}

            def raise_for_status(self):
                return None

        class FakeClient:
            async def get(self, url):
                return FakeResponse()

        value = asyncio.run(self.main.youyun_h3_reference_value(FakeClient(), "https://assets.example/ref.png", "image"))
        self.assertTrue(value.startswith("data:image/png;base64,"))
