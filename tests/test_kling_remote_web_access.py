import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from canvas_core.accounts import AccountIdentity
from canvas_core.kling_cli import KlingCliEnvironment


ROOT = Path(__file__).resolve().parent.parent


def request_for(identity: AccountIdentity, host: str):
    return SimpleNamespace(
        state=SimpleNamespace(account_identity=identity),
        client=SimpleNamespace(host=host),
    )


class KlingRemoteWebAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main

        cls.main = main
        cls.canvas = (ROOT / "static" / "js" / "canvas.js").read_text(encoding="utf-8")
        cls.smart = (ROOT / "static" / "js" / "smart-canvas.js").read_text(encoding="utf-8")

    def test_remote_user_can_read_capabilities_and_generate_but_cannot_manage_cli(self):
        self.assertNotIn("/api/kling-cli/capabilities", self.main.ADMIN_ONLY_HTTP_PATHS)
        self.assertNotIn("/api/canvas-video", self.main.ADMIN_ONLY_HTTP_PATHS)
        self.assertNotIn("/api/canvas-video-tasks", self.main.ADMIN_ONLY_HTTP_PATHS)
        self.assertIn("/api/kling-cli/install", self.main.ADMIN_ONLY_HTTP_PATHS)
        self.assertIn("/api/kling-cli/login", self.main.ADMIN_ONLY_HTTP_PATHS)

        remote_user = AccountIdentity("user-1", "同事1", "user", "folder-1")
        request = request_for(remote_user, "192.168.0.88")
        environment = KlingCliEnvironment(
            node_path="node.exe",
            npm_path="npm.cmd",
            kling_path="kling.cmd",
            entrypoint_path="cli.js",
            version="kling-cli 0.1.3",
        )

        class FakeService:
            def __init__(self, _environment):
                pass

            def capabilities(self):
                return {
                    "text_to_video": [{"model": "kling-video-v3_0", "arguments": [], "inputs": []}],
                    "image_to_video": [{"model": "kling-video-v3_0", "arguments": [], "inputs": []}],
                }

        with (
            patch.object(self.main, "resolve_kling_cli", return_value=environment),
            patch.object(self.main, "KlingCliService", FakeService),
        ):
            result = asyncio.run(self.main.kling_cli_capabilities(request))

        self.assertTrue(result["authenticated"])
        self.assertTrue(result["generation_enabled"])
        self.assertFalse(result["can_manage"])
        self.assertEqual(result["capabilities"]["text_to_video"][0]["model"], "kling-video-v3_0")

    def test_only_loopback_admin_can_install_or_start_login(self):
        remote_user = AccountIdentity("user-1", "同事1", "user", "folder-1")
        remote_request = request_for(remote_user, "192.168.0.88")
        with patch.object(self.main, "install_kling_cli") as install:
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(
                    self.main.kling_cli_install(
                        self.main.KlingCliInstallRequest(region="china"),
                        remote_request,
                    )
                )
        self.assertEqual(caught.exception.status_code, 403)
        install.assert_not_called()

        local_admin = AccountIdentity("admin", "jiang", "admin", "")
        self.assertTrue(self.main.can_manage_kling_cli(request_for(local_admin, "127.0.0.1")))
        self.assertFalse(self.main.can_manage_kling_cli(request_for(local_admin, "192.168.0.88")))

    def test_infinite_canvas_hides_host_management_actions_from_remote_users(self):
        self.assertIn("generationEnabled:false", self.canvas)
        self.assertIn("canManage:false", self.canvas)
        self.assertIn("generationEnabled:Boolean(data.generation_enabled)", self.canvas)
        self.assertIn("canManage:Boolean(data.can_manage)", self.canvas)
        self.assertIn("state.canManage && !state.installed", self.canvas)
        self.assertIn("state.canManage && state.installed && !state.authenticated", self.canvas)

    def test_smart_canvas_loads_real_kling_models_and_rejects_placeholder_submission(self):
        self.assertIn("let smartKlingCliState =", self.smart)
        self.assertIn("async function loadSmartKlingCapabilities()", self.smart)
        self.assertIn("/api/kling-cli/capabilities", self.smart)
        self.assertIn("await loadSmartKlingCapabilities()", self.smart)
        self.assertIn("updateSmartKlingProviderModels", self.smart)
        self.assertIn("provider.video_models = [...new Set(models)]", self.smart)
        self.assertIn("if(!smartKlingCliState.authenticated || !smartKlingCliState.generationEnabled)", self.smart)
        self.assertIn("smartKlingModelsForMode(mode)", self.smart)
        self.assertIn("当前可灵账号的${label}能力中不存在模型", self.smart)
        self.assertIn("async function runPersistentSmartKlingVideo(payload)", self.smart)
        self.assertIn("fetch('/api/canvas-video-tasks'", self.smart)
        self.assertIn("/api/canvas-video-tasks/${encodeURIComponent(taskId)}", self.smart)
        self.assertIn("if(isKling) return await runPersistentSmartKlingVideo(payload);", self.smart)


if __name__ == "__main__":
    unittest.main()
