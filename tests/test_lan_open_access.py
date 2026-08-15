import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class LanAccountAccessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = (ROOT / "main.py").read_text(encoding="utf-8")
        cls.auth = (ROOT / "canvas_core" / "auth.py").read_text(encoding="utf-8")
        cls.tray = (ROOT / "src-tauri" / "src" / "lib.rs").read_text(encoding="utf-8")
        cls.runtime_sync = (ROOT / "static" / "js" / "runtime-sync.js").read_text(encoding="utf-8")
        cls.accounts = (ROOT / "canvas_core" / "accounts.py").read_text(encoding="utf-8")
        cls.storage = (ROOT / "canvas_core" / "account_storage.py").read_text(encoding="utf-8")
        cls.index = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
        cls.login = (ROOT / "static" / "login.html").read_text(encoding="utf-8")
        cls.admin = (ROOT / "static" / "admin.html").read_text(encoding="utf-8")

    def test_http_and_websocket_use_account_sessions_without_pairing(self):
        self.assertIn("account_authentication_middleware", self.main)
        self.assertNotIn("设备尚未配对或会话已失效", self.main)
        self.assertIn('ACCOUNT_STORE.resolve_session', self.main)
        self.assertIn('"type": "connection.ready", "account": identity.public()', self.main)
        self.assertIn("type:'hello'", self.runtime_sync)
        self.assertNotIn("type:'auth'", self.runtime_sync)

    def test_accounts_support_chinese_english_and_use_dedicated_data_roots(self):
        self.assertIn("validate_account", self.accounts)
        self.assertIn("validate_password", self.accounts)
        self.assertIn("account_key", self.accounts)
        self.assertIn('self.accounts_root = self.data_root / "accounts"', self.accounts)
        self.assertIn("ScopedDatabaseProxy", self.storage)
        self.assertIn("ScopedDataLayoutProxy", self.storage)

    def test_login_and_admin_pages_do_not_force_numeric_credentials(self):
        self.assertNotIn("纯数字账号", self.login)
        self.assertNotIn("数字账号和密码", self.login)
        self.assertNotIn("input.inputMode='numeric'", self.admin)

    def test_admin_is_local_only_and_user_config_is_hidden(self):
        self.assertIn("create_admin_session", self.main)
        self.assertIn("is_loopback_address", self.main)
        self.assertIn('"/api/config"', self.main)
        self.assertIn('"/api/providers"', self.main)
        self.assertIn('@app.get("/api/runtime/config")', self.main)
        self.assertNotIn('"base_url": AI_BASE_URL', self.main.split('@app.get("/api/runtime/config")', 1)[1].split('@app.get("/api/models")', 1)[0])
        self.assertIn('data-admin-only hidden', self.index)
        self.assertIn("USER_PREFERENCE_KEYS = {\"theme\", \"language\"}", self.main)

    def test_pairing_routes_and_code_generator_are_removed(self):
        self.assertNotIn('@app.post("/api/auth/pair")', self.main)
        self.assertNotIn('@app.post("/api/auth/pair-code")', self.main)
        self.assertNotIn('@app.get("/api/auth/devices")', self.main)
        self.assertNotIn("create_pair_code", self.auth)
        self.assertNotIn("def pair(", self.auth)

    def test_pairing_pages_and_tray_entry_are_removed(self):
        self.assertFalse((ROOT / "static" / "pair.html").exists())
        self.assertFalse((ROOT / "static" / "devices.html").exists())
        self.assertNotIn('"devices", "配对设备"', self.tray)


if __name__ == "__main__":
    unittest.main()
