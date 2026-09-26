import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import main


PROVIDER = {"id": "grsai", "base_url": "https://grsaiapi.com", "name": "Grsai API"}
IMAGE_URL = "https://files.example/generated.png"


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self.body


class FakeClient:
    def __init__(self, submitted, queried=None):
        self.submitted = submitted
        self.queried = queried
        self.posts = []
        self.gets = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return FakeResponse(self.submitted)

    async def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        return FakeResponse(self.queried)


class GrsaiImageResultTests(unittest.TestCase):
    def test_gpt_image_edit_uses_native_generate_with_references(self):
        client = FakeClient({"id": "14-image", "status": "succeeded", "results": [{"url": IMAGE_URL}]})
        with (
            patch.object(main.httpx, "AsyncClient", return_value=client),
            patch.object(main, "api_headers", return_value={}),
            patch.object(main, "reference_to_data_url", return_value="data:image/png;base64,AA=="),
            patch.object(main, "get_api_provider", return_value=PROVIDER),
        ):
            image, raw = asyncio.run(main.generate_ai_image(
                "edit", "1536x1024", "high", "gpt-image-2.5",
                [{"url": "/assets/input/reference.png"}], "grsai",
            ))
        self.assertEqual(image, {"type": "url", "value": IMAGE_URL})
        self.assertEqual(raw["id"], "14-image")
        self.assertEqual(len(client.posts), 1)
        self.assertEqual(client.posts[0][0], "https://grsaiapi.com/v1/api/generate")
        self.assertEqual(client.posts[0][1]["json"], {
            "model": "gpt-image-2.5",
            "prompt": "edit",
            "images": ["data:image/png;base64,AA=="],
            "aspectRatio": "1536x1024",
            "quality": "high",
            "replyType": "async",
        })

    def test_async_result_uses_documented_query_and_recovers_image(self):
        client = FakeClient(
            {"id": "14-task", "status": "processing"},
            {"id": "14-task", "status": "succeeded", "results": [{"url": IMAGE_URL}]},
        )
        with (
            patch.object(main.httpx, "AsyncClient", return_value=client),
            patch.object(main, "api_headers", return_value={}),
            patch.object(main.asyncio, "sleep", new_callable=AsyncMock),
        ):
            image, raw = asyncio.run(main.generate_grsai_provider_image(
                "create", "1024x1024", "", "gpt-image-2", provider=PROVIDER,
            ))
        self.assertEqual(image["value"], IMAGE_URL)
        self.assertEqual(raw["id"], "14-task")
        self.assertEqual(client.posts[0][1]["json"]["quality"], "auto")
        self.assertEqual(client.gets, [(
            "https://grsaiapi.com/v1/api/result", {"headers": {}, "params": {"id": "14-task"}},
        )])

    def test_failed_async_result_keeps_upstream_task_id(self):
        client = FakeClient(
            {"id": "14-task", "status": "processing"},
            {"id": "14-task", "status": "failed", "error": "upstream failed"},
        )
        with (
            patch.object(main.httpx, "AsyncClient", return_value=client),
            patch.object(main, "api_headers", return_value={}),
            patch.object(main.asyncio, "sleep", new_callable=AsyncMock),
        ):
            with self.assertRaises(main.HTTPException) as captured:
                asyncio.run(main.generate_grsai_provider_image(
                    "create", "1024x1024", "", "gpt-image-2", provider=PROVIDER,
                ))
        self.assertEqual(captured.exception.upstream_task_id, "14-task")


if __name__ == "__main__":
    unittest.main()
