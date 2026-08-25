import unittest


class ResponsesTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def test_legacy_provider_defaults_to_chat_completions(self):
        provider = self.main.normalize_provider({
            "id": "legacy-api",
            "name": "Legacy",
            "base_url": "https://example.test/v1",
            "protocol": "openai",
            "chat_models": ["text-model"],
        })

        self.assertEqual(provider["request_protocol"], "chat_completions")
        self.assertEqual(provider["responses_endpoint"], "/v1/responses")

    def test_responses_provider_defaults_to_native_transport(self):
        provider = self.main.normalize_provider({
            "id": "responses-api",
            "name": "Responses",
            "base_url": "https://api.example.test",
            "protocol": "responses",
            "chat_models": ["vision-model"],
        })

        self.assertEqual(provider["request_protocol"], "responses")
        self.assertEqual(
            self.main.provider_endpoint_url(provider, "responses_endpoint", self.main.DEFAULT_RESPONSES_ENDPOINT),
            "https://api.example.test/v1/responses",
        )

    def test_responses_endpoint_does_not_duplicate_v1(self):
        provider = self.main.normalize_provider({
            "id": "responses-v1",
            "name": "Responses",
            "base_url": "https://api.example.test/v1",
            "protocol": "responses",
            "responses_endpoint": "/v1/responses",
        })

        self.assertEqual(
            self.main.provider_endpoint_url(provider, "responses_endpoint", self.main.DEFAULT_RESPONSES_ENDPOINT),
            "https://api.example.test/v1/responses",
        )

    def test_responses_request_body_moves_system_to_instructions(self):
        transport = {
            "protocol": "responses",
            "model": "vision-model",
            "provider": {},
        }
        body = self.main.build_llm_request_body(transport, [
            {"role": "system", "content": "保持简洁"},
            {"role": "user", "content": "分析图片"},
        ])

        self.assertEqual(body["model"], "vision-model")
        self.assertEqual(body["instructions"], "保持简洁")
        self.assertEqual(body["input"], [{
            "role": "user",
            "content": [{"type": "input_text", "text": "分析图片"}],
        }])
        self.assertNotIn("messages", body)

    def test_responses_request_body_converts_image_url(self):
        transport = {"protocol": "responses", "model": "vision-model", "provider": {}}
        body = self.main.build_llm_request_body(transport, [{
            "role": "user",
            "content": [
                {"type": "text", "text": "描述"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
            ],
        }])

        self.assertEqual(body["input"][0]["content"][1], {
            "type": "input_image",
            "image_url": "data:image/png;base64,abc",
        })

    def test_responses_response_parser_reads_output_text(self):
        raw = {
            "id": "resp_123",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": "解析成功"}],
            }],
        }

        self.assertEqual(self.main.text_from_llm_response(raw, "responses"), "解析成功")

    def test_model_protocol_override_can_select_responses(self):
        provider = {
            "protocol": "openai",
            "request_protocol": "chat_completions",
            "model_protocols": {"vision-model": "responses"},
        }
        self.assertEqual(self.main.effective_request_protocol(provider, "vision-model"), "responses")


if __name__ == "__main__":
    unittest.main()
