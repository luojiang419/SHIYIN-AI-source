import asyncio
import json
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent


class FakeResponse:
    def __init__(self, status_code, payload=None, text=None, headers=None, stream_lines=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else (json.dumps(payload, ensure_ascii=False) if payload is not None else "")
        self._stream_lines = list(stream_lines or [])
        self.headers = dict(headers or {})
        if self._stream_lines:
            self.headers.setdefault("content-type", "text/event-stream")
        self.content = self.text.encode("utf-8")
        self.request = None

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"unexpected HTTP {self.status_code}")

    async def aread(self):
        return self.content

    def aiter_lines(self):
        async def iterator():
            for line in self._stream_lines:
                yield line
        return iterator()


class FakeStreamContext:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeAsyncClient:
    def __init__(self, *, get_responses=None, post_responses=None):
        self.get_responses = list(get_responses or [])
        self.post_responses = list(post_responses or [])
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.get_responses.pop(0)

    async def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.post_responses.pop(0)

    def stream(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return FakeStreamContext(self.post_responses.pop(0))


class ResponsesProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main
        cls.api_html = (ROOT / "static" / "api-settings.html").read_text(encoding="utf-8")
        cls.api_js = (ROOT / "static" / "js" / "api-settings.js").read_text(encoding="utf-8")
        cls.api_i18n = (ROOT / "static" / "js" / "i18n" / "api-settings.js").read_text(encoding="utf-8")

    def test_responses_protocol_is_exposed_and_persisted(self):
        self.assertIn('value="responses"', self.api_html)
        self.assertIn("Responses（原生）", self.api_html)
        self.assertIn('"api.protocolResponses"', self.api_i18n)
        self.assertIn("'openai', 'responses', 'apimart'", self.api_js)
        self.assertIn("item.request_protocol = item.protocol === 'responses' ? 'responses' : 'chat_completions'", self.api_js)
        self.assertIn("request_protocol:item.request_protocol", self.api_js)
        self.assertIn("responses", self.main.SUPPORTED_PROVIDER_PROTOCOLS)

    def test_responses_url_normalization(self):
        self.assertEqual(self.main.responses_api_url("https://example.test"), "https://example.test/v1/responses")
        self.assertEqual(self.main.responses_api_url("https://example.test/v1/"), "https://example.test/v1/responses")

    def test_probe_accepts_validation_error_as_reachable_endpoint(self):
        client = FakeAsyncClient(post_responses=[FakeResponse(400, {"error": {"message": "model is required"}})])

        ok, result = asyncio.run(self.main.probe_responses_endpoint(client, "https://example.test", "test-key"))

        self.assertTrue(ok)
        self.assertEqual(result["status"], 400)
        method, url, kwargs = client.requests[0]
        self.assertEqual((method, url), ("POST", "https://example.test/v1/responses"))
        self.assertEqual(kwargs["json"], {})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_address_validation_supports_missing_models_endpoint(self):
        client = FakeAsyncClient(
            get_responses=[FakeResponse(404, {"error": "not found"})],
            post_responses=[FakeResponse(400, {"error": {"message": "api relay request failed"}})],
        )
        payload = self.main.TestConnectionPayload(
            base_url="https://example.test",
            api_key="test-key",
            protocol="responses",
        )

        with patch.object(self.main.httpx, "AsyncClient", return_value=client):
            result = asyncio.run(self.main.test_provider_connection(payload))

        self.assertTrue(result["ok"])
        self.assertEqual(result["protocol"], "responses")
        self.assertTrue(result["manual_model_required"])
        self.assertEqual(result["model_count"], 0)

    def test_model_fetch_returns_manual_mode_when_models_endpoint_is_missing(self):
        client = FakeAsyncClient(
            get_responses=[FakeResponse(404, {"error": "not found"})],
            post_responses=[FakeResponse(422, {"detail": "model is required"})],
        )

        with patch.object(self.main.httpx, "AsyncClient", return_value=client):
            result = asyncio.run(self.main.fetch_models_from_upstream(
                "https://example.test", "test-key", "responses"
            ))

        self.assertEqual(result["protocol"], "responses")
        self.assertEqual(result["total"], 0)
        self.assertTrue(result["manual_model_required"])

    def test_model_fetch_uses_standard_models_endpoint_when_available(self):
        client = FakeAsyncClient(get_responses=[FakeResponse(200, {"data": [{"id": "gpt-5.6-sol"}]})])

        with patch.object(self.main.httpx, "AsyncClient", return_value=client):
            result = asyncio.run(self.main.fetch_models_from_upstream(
                "https://example.test/v1", "test-key", "responses"
            ))

        self.assertEqual(result["protocol"], "responses")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["chat_models"], ["gpt-5.6-sol"])
        self.assertFalse(result["manual_model_required"])

    def test_unified_request_body_converts_responses_visual_input(self):
        body = self.main.build_llm_request_body(
            {"model": "gpt-5.6-sol", "protocol": "responses", "provider": {}},
            [
                {"role": "system", "content": "system rule"},
                {"role": "assistant", "content": "previous answer"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
                    ],
                },
            ],
        )

        self.assertEqual(body["model"], "gpt-5.6-sol")
        self.assertEqual(body["instructions"], "system rule")
        self.assertEqual(
            body["input"][0],
            {"role": "assistant", "content": [{"type": "output_text", "text": "previous answer"}]},
        )
        self.assertEqual(body["input"][1]["content"][0], {"type": "input_text", "text": "describe"})
        self.assertEqual(
            body["input"][1]["content"][1],
            {"type": "input_image", "image_url": "data:image/png;base64,AAAA"},
        )

    def test_manual_reference_history_keeps_assistant_output_type(self):
        body = self.main.build_llm_request_body(
            {"model": "gpt-5.6-sol", "protocol": "responses", "provider": {}},
            [
                {"role": "system", "content": "只返回编辑结果"},
                {"role": "assistant", "content": "上一轮图片已生成"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "把这张图改成夜景"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,EDIT"}},
                    ],
                },
            ],
        )

        self.assertEqual(body["input"][0]["content"], [{"type": "output_text", "text": "上一轮图片已生成"}])
        self.assertEqual(body["input"][1]["content"][0], {"type": "input_text", "text": "把这张图改成夜景"})
        self.assertEqual(body["input"][1]["content"][1], {"type": "input_image", "image_url": "data:image/png;base64,EDIT"})

    def test_responses_rejects_raw_video_input(self):
        with self.assertRaises(self.main.HTTPException) as raised:
            self.main.build_llm_request_body(
                {"model": "gpt-5.6-sol", "protocol": "responses", "provider": {}},
                [{"role": "user", "content": [{"type": "video_url", "video_url": {"url": "https://example.test/a.mp4"}}]}],
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("关键帧", raised.exception.detail)

    def test_responses_can_attach_builtin_web_search_tool(self):
        body = self.main.build_llm_request_body(
            {"model": "gpt-5.6-sol", "protocol": "responses", "provider": {}, "web_search": True},
            [{"role": "user", "content": "检索优秀视频分镜案例并总结方法"}],
        )
        self.assertEqual(body["tools"], [{"type": "web_search"}])

    def test_ecommerce_native_responses_allows_builtin_web_search_for_text_requests(self):
        self.assertTrue(self.main.provider_supports_builtin_web_search({
            "id": "ecommerce-vision",
            "protocol": "responses",
            "base_url": "https://xsy-proxy.shiyingai.com/v1",
        }))
        self.assertTrue(self.main.provider_supports_builtin_web_search({
            "id": "another-responses-provider",
            "base_url": "https://relay.test/v1",
        }))

    def test_resolve_chat_transport_uses_configured_responses_endpoint(self):
        provider = {
            "id": "responses-provider",
            "protocol": "openai",
            "request_protocol": "responses",
            "responses_endpoint": "/v1/responses",
            "base_url": "https://relay.test/v1",
            "chat_models": ["gpt-5.6-sol"],
        }
        with (
            patch.object(self.main, "get_api_provider", return_value=provider),
            patch.object(self.main, "resolve_chat_provider", return_value=(
                "https://relay.test/v1",
                {"Authorization": "Bearer test-key"},
                "gpt-5.6-sol",
            )),
        ):
            transport = self.main.resolve_chat_transport("responses-provider", "gpt-5.6-sol", "")

        self.assertEqual(transport["protocol"], "responses")
        self.assertEqual(transport["url"], "https://relay.test/v1/responses")

    def test_responses_text_parser_supports_standard_output(self):
        raw = {
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "视觉识别结果"}]}
            ]
        }

        self.assertEqual(self.main.text_from_responses_response(raw), "视觉识别结果")
        self.assertEqual(self.main.text_from_responses_response({"output_text": "直接结果"}), "直接结果")

    def test_canvas_ai_assistant_posts_responses_visual_payload(self):
        client = FakeAsyncClient(
            post_responses=[FakeResponse(200, {
                "id": "resp_test",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "一只猫"}]}],
            })]
        )
        payload = self.main.CanvasLLMRequest(
            message="图中是什么？",
            model="gpt-5.6-sol",
            provider="responses-provider",
            system_prompt="简短回答",
            messages=[{"role": "assistant", "content": "上一轮回答"}],
            images=["https://example.test/cat.png"],
        )
        provider = {
            "id": "responses-provider",
            "name": "Responses Provider",
            "protocol": "responses",
            "base_url": "https://relay.test",
            "chat_models": ["gpt-5.6-sol"],
        }

        with (
            patch.object(self.main.httpx, "AsyncClient", return_value=client),
            patch.object(self.main, "resolve_chat_provider", return_value=(
                "https://relay.test/v1",
                {"Authorization": "Bearer test-key", "Content-Type": "application/json"},
                "gpt-5.6-sol",
            )),
            patch.object(self.main, "get_api_provider", return_value=provider),
        ):
            result = asyncio.run(self.main.canvas_llm(payload))

        self.assertEqual(result["text"], "一只猫")
        method, url, kwargs = client.requests[0]
        self.assertEqual((method, url), ("POST", "https://relay.test/v1/responses"))
        self.assertEqual(kwargs["json"]["instructions"], "简短回答")
        user_message = kwargs["json"]["input"][-1]
        self.assertEqual(user_message["content"][0], {"type": "input_text", "text": "图中是什么？"})
        self.assertEqual(
            user_message["content"][1],
            {"type": "input_image", "image_url": "https://example.test/cat.png"},
        )

    def test_responses_sse_is_aggregated_into_standard_response(self):
        client = FakeAsyncClient(post_responses=[FakeResponse(
            200,
            stream_lines=[
                "event: response.created",
                'data: {"type":"response.created","response":{"id":"resp_stream","status":"in_progress"}}',
                'data: {"type":"response.output_text.delta","delta":"第一段"}',
                'data: {"type":"response.output_text.delta","delta":"第二段"}',
                'data: {"type":"response.completed","response":{"id":"resp_stream","status":"completed","usage":{"total_tokens":7}}}',
            ],
        )])
        transport = {
            "provider": {"id": "responses-provider"},
            "protocol": "responses",
            "url": "https://relay.test/v1/responses",
            "headers": {"Authorization": "Bearer test-key"},
            "model": "gpt-5.6-sol",
        }

        deltas = []
        with patch.object(self.main.httpx, "AsyncClient", return_value=client):
            result = asyncio.run(self.main.request_llm_json(
                transport,
                [{"role": "user", "content": "继续执行"}],
                retry_524=0,
                on_text_delta=deltas.append,
            ))

        self.assertEqual(result["id"], "resp_stream")
        self.assertEqual(result["output_text"], "第一段第二段")
        self.assertEqual(result["usage"]["total_tokens"], 7)
        self.assertEqual(deltas, ["第一段", "第二段"])
        self.assertEqual(client.requests[0][2]["json"]["stream"], True)


if __name__ == "__main__":
    unittest.main()
