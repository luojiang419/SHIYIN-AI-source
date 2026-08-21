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


if __name__ == "__main__":
    unittest.main()
