import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canvas_core.auth import AuthManager
from canvas_core.database import CanvasDatabase
from canvas_core.secrets import DpapiProtector, SecretStore


class SecurityTests(unittest.TestCase):
    def make_database(self, root: str) -> CanvasDatabase:
        database = CanvasDatabase(Path(root) / "canvas.db")
        database.initialize()
        return database

    def test_secret_import_verifies_then_removes_plaintext(self):
        with tempfile.TemporaryDirectory() as root:
            database = self.make_database(root)
            protect = lambda value: value.encode("utf-8")[::-1]
            unprotect = lambda value: bytes(value)[::-1].decode("utf-8")
            store = SecretStore(database, protect, unprotect)
            source = Path(root) / "secrets.env"
            source.write_text('API_KEY="sensitive-value"\nEMPTY=\n', encoding="utf-8")
            report = store.import_env_files([source])
            self.assertEqual(report, {"files": 1, "values": 2, "removed": 1})
            self.assertFalse(source.exists())
            self.assertEqual(store.get("API_KEY"), "sensitive-value")
            self.assertNotIn(b"sensitive-value", (Path(root) / "canvas.db").read_bytes())

    @unittest.skipUnless(os.name == "nt", "DPAPI 仅在 Windows 验证")
    def test_dpapi_round_trip(self):
        protector = DpapiProtector()
        protected = protector.protect("仅当前 Windows 用户可读取")
        self.assertNotIn("仅当前 Windows 用户可读取".encode("utf-8"), protected)
        self.assertEqual(protector.unprotect(protected), "仅当前 Windows 用户可读取")

    def test_desktop_bootstrap_token_is_single_use(self):
        with tempfile.TemporaryDirectory() as root:
            database = self.make_database(root)
            auth = AuthManager(database, desktop_token="desktop-once")
            desktop_session, desktop = auth.consume_desktop_token("desktop-once")
            self.assertEqual(desktop.client_type, "desktop")
            self.assertIsNotNone(auth.authenticate(desktop_session))
            with self.assertRaises(PermissionError):
                auth.consume_desktop_token("desktop-once")


if __name__ == "__main__":
    unittest.main()
