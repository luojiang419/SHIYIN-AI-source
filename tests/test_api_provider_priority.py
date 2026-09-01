import unittest
from unittest.mock import patch


class ApiProviderPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main

    def provider(self, provider_id, *, enabled=True, models=None, base_url="http://127.0.0.1:9999/v1"):
        return {
            "id": provider_id,
            "name": provider_id,
            "protocol": "openai",
            "enabled": enabled,
            "base_url": base_url,
            "image_models": list(models or []),
        }

    def test_order_is_the_primary_priority(self):
        providers = [
            {**self.provider("first", models=["image-a"]), "primary": False},
            {**self.provider("second", models=["image-b"]), "primary": True},
        ]

        self.assertEqual(self.main.get_primary_provider_id(providers), "first")

    def test_invalid_requested_provider_falls_forward_to_next_ready_provider(self):
        providers = [
            self.provider("invalid", models=[]),
            self.provider("second", models=["image-b"]),
            self.provider("third", models=["image-c"]),
        ]

        selection = self.main.resolve_image_generation_selection("invalid", "old-model", providers)

        self.assertEqual(selection["provider_id"], "second")
        self.assertEqual(selection["model"], "image-b")
        self.assertTrue(selection["fallback_used"])
        self.assertEqual(selection["skipped"], [{"provider_id": "invalid", "reason": "未配置图片模型"}])

    def test_explicit_ready_provider_still_controls_generation(self):
        providers = [
            self.provider("first", models=["image-a"]),
            self.provider("chosen", models=["image-b", "image-c"]),
        ]

        selection = self.main.resolve_image_generation_selection("chosen", "image-c", providers)

        self.assertEqual(selection["provider_id"], "chosen")
        self.assertEqual(selection["model"], "image-c")
        self.assertFalse(selection["fallback_used"])

    def test_remote_provider_without_key_is_not_ready(self):
        provider = self.provider(
            "remote",
            models=["image-a"],
            base_url="https://example.invalid/v1",
        )
        with patch.object(self.main, "provider_env_key_value", return_value=""):
            readiness = self.main.image_generation_readiness(provider)

        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["reason"], "未配置 API Key")

    def test_raises_clear_error_when_no_image_provider_is_ready(self):
        providers = [
            self.provider("disabled", enabled=False, models=["image-a"]),
            self.provider("empty", models=[]),
        ]

        with self.assertRaises(self.main.HTTPException) as raised:
            self.main.resolve_image_generation_selection("", "", providers)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("没有有效的图片生成配置", raised.exception.detail)

    def test_ecommerce_vision_provider_is_preferred_for_ecommerce_analysis(self):
        providers = [
            {**self.provider("local-vision"), "chat_models": ["qwen-vl"]},
            {**self.provider("ecommerce-vision"), "name": "AI助手", "chat_models": ["custom-caption-model"]},
        ]
        with patch.object(self.main, "provider_env_key_value", return_value="configured-key"):
            route = self.main.configured_ecommerce_vision_route(providers)
        self.assertEqual(route["provider_id"], "ecommerce-vision")
        self.assertEqual(route["model"], "custom-caption-model")

    def test_default_provider_templates_include_ecommerce_vision(self):
        providers = self.main.default_api_providers()
        item = next((provider for provider in providers if provider["id"] == "ecommerce-vision"), None)
        self.assertIsNotNone(item)
        self.assertEqual(item["name"], "AI助手")
        self.assertTrue(item["chat_models"])

    def test_existing_ecommerce_provider_name_is_migrated_without_changing_configuration(self):
        saved = {
            "id": "ecommerce-vision",
            "name": "电商专用",
            "base_url": "https://api.example.com/v1",
            "protocol": "responses",
            "request_protocol": "responses",
            "image_request_mode": "openai-json",
            "enabled": False,
            "primary": True,
            "image_models": ["image-model"],
            "chat_models": ["vision-chat-model"],
            "video_models": ["video-model"],
            "model_protocols": {"vision-chat-model": "responses"},
        }

        item = next(
            provider
            for provider in self.main.merge_default_api_providers([saved])
            if provider["id"] == "ecommerce-vision"
        )

        self.assertEqual(item["name"], "AI助手")
        for field in (
            "base_url", "protocol", "request_protocol", "image_request_mode", "enabled", "primary",
            "image_models", "chat_models", "video_models", "model_protocols",
        ):
            self.assertEqual(item[field], saved[field])

    def test_ecommerce_provider_keeps_standard_model_fields(self):
        item = self.main.normalize_provider({
            "id": "ecommerce-vision",
            "name": "AI助手",
            "base_url": "https://api.example.com/v1",
            "protocol": "gemini",
            "image_models": ["image-model"],
            "chat_models": ["vision-chat-model"],
            "video_models": ["video-model"],
        })
        self.assertEqual(item["protocol"], "gemini")
        self.assertEqual(item["image_models"], ["image-model"])
        self.assertEqual(item["chat_models"], ["vision-chat-model"])
        self.assertEqual(item["video_models"], ["video-model"])

    def test_ecommerce_provider_is_not_fixed_protocol_backend(self):
        self.assertNotIn("ecommerce-vision", self.main.FIXED_PROTOCOL_PROVIDER_IDS)
        provider = self.main.normalize_provider({
            "id": "ecommerce-vision",
            "name": "AI助手",
            "base_url": "https://api.example.com/v1",
            "protocol": "responses",
            "request_protocol": "responses",
            "chat_models": ["vision-chat-model"],
        })
        self.assertEqual(self.main.effective_protocol(provider, "vision-chat-model"), "responses")


if __name__ == "__main__":
    unittest.main()
