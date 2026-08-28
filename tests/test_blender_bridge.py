import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from canvas_core.blender_bridge import (
    BlenderBridgeClient,
    BlenderBridgeError,
    build_blender_addon_zip,
    discover_blender_executables,
    launch_blender,
    load_or_create_bridge_secret,
    validated_render_path,
)


class StubBridge:
    def __init__(self, shared_secret="test-shared-secret-abcdefghijklmnopqrstuvwxyz-123456"):
        self.shared_secret = shared_secret
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(4)
        self.port = self.server.getsockname()[1]
        self.server.settimeout(0.2)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        for _ in range(4):
            try:
                connection, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                raw = b""
                while b"\n" not in raw:
                    raw += connection.recv(65536)
                request = json.loads(raw.split(b"\n", 1)[0])
                action = request["action"]
                if action == "ping":
                    data = {"addon_version": "1.0.0"}
                elif action == "authenticate":
                    if request.get("payload", {}).get("shared_secret") != self.shared_secret:
                        raise AssertionError("missing shared secret")
                    data = {"session_token": "x" * 32}
                else:
                    self.assert_session(request)
                    data = {"scene": "Scene"}
                response = {"id": request["id"], "ok": True, "data": data}
                connection.sendall(json.dumps(response).encode() + b"\n")

    def close(self):
        self.server.close()
        self.thread.join(timeout=1)

    @staticmethod
    def assert_session(request):
        if request.get("session_token") != "x" * 32:
            raise AssertionError("missing session")


class BlenderBridgeTests(unittest.TestCase):
    def test_auto_authenticates_then_runs_only_whitelisted_command(self):
        stub = StubBridge()
        try:
            client = BlenderBridgeClient()
            self.assertTrue(client.ping(stub.port)["connected"])
            with patch("canvas_core.blender_bridge.load_or_create_bridge_secret", return_value=stub.shared_secret):
                self.assertTrue(client.connect(stub.port)["authenticated"])
                self.assertEqual(client.command("scene_state", port=stub.port)["scene"], "Scene")
            with self.assertRaises(BlenderBridgeError):
                client.command("execute_python", port=stub.port)
        finally:
            stub.close()

    def test_shared_secret_is_created_once_and_never_exposed_to_frontend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            secret_path = Path(temp_dir) / "blender-bridge.key"
            with patch("canvas_core.blender_bridge.blender_bridge_secret_path", return_value=secret_path):
                first = load_or_create_bridge_secret()
                second = load_or_create_bridge_secret()
        self.assertEqual(first, second)
        self.assertGreaterEqual(len(first), 48)

    def test_connect_click_launches_blender_then_waits_for_plugin(self):
        client = BlenderBridgeClient()
        connected = {"connected": True, "authenticated": True, "port": 9876}
        with (
            patch.object(client, "connect", side_effect=[BlenderBridgeError("offline"), connected]) as connect,
            patch("canvas_core.blender_bridge.blender_process_running", return_value=False),
            patch(
                "canvas_core.blender_bridge.launch_blender",
                return_value={"launched": True, "blender_path": "D:\\Blender\\blender.exe", "pid": 42},
            ) as launch,
            patch("canvas_core.blender_bridge.time.sleep"),
        ):
            result = client.connect_or_launch(wait_seconds=3)
        self.assertTrue(result["launched"])
        self.assertEqual(result["pid"], 42)
        launch.assert_called_once_with()
        self.assertEqual(connect.call_count, 2)

    def test_discovers_and_prefers_latest_blender_installation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            older = root / "Blender 4.3" / "blender.exe"
            latest = root / "Blender 5.2" / "blender.exe"
            older.parent.mkdir()
            latest.parent.mkdir()
            older.write_bytes(b"old")
            latest.write_bytes(b"new")
            with (
                patch("canvas_core.blender_bridge._registry_blender_candidates", return_value=[]),
                patch("canvas_core.blender_bridge._candidate_blender_roots", return_value=[root]),
                patch("canvas_core.blender_bridge.shutil.which", return_value=None),
            ):
                installations = discover_blender_executables()
        self.assertEqual([item.name for item in installations], ["blender.exe", "blender.exe"])
        self.assertEqual(installations[0].parent.name, "Blender 5.2")

    def test_launch_uses_discovered_executable_without_shell(self):
        executable = Path("D:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
        process = type("Process", (), {"pid": 1234})()
        with (
            patch("canvas_core.blender_bridge.discover_blender_executables", return_value=[executable]),
            patch("canvas_core.blender_bridge.subprocess.Popen", return_value=process) as popen,
        ):
            result = launch_blender()
        self.assertTrue(result["launched"])
        self.assertEqual(result["pid"], 1234)
        self.assertEqual(popen.call_args.args[0], [str(executable)])
        self.assertNotIn("shell", popen.call_args.kwargs)

    def test_render_path_must_stay_inside_exchange_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            good = root / "render.png"
            good.write_bytes(b"png")
            outside = root.parent / "outside.png"
            outside.write_bytes(b"png")
            with patch("canvas_core.blender_bridge.blender_exchange_root", return_value=root.resolve()):
                self.assertEqual(validated_render_path(good, "image"), good.resolve())
                with self.assertRaises(BlenderBridgeError):
                    validated_render_path(outside, "image")
            outside.unlink(missing_ok=True)

    def test_addon_zip_has_installable_package_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            source.mkdir()
            (source / "__init__.py").write_text("bl_info = {}", encoding="utf-8")
            payload = build_blender_addon_zip(source)
        self.assertIn(b"shiyin_blender_bridge/__init__.py", payload)


if __name__ == "__main__":
    unittest.main()
