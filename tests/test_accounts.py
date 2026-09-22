import sqlite3
import tempfile
import unittest
from pathlib import Path

from canvas_core.accounts import (
    AccountStore,
    LoginRateLimiter,
    account_lookup_key,
    is_loopback_address,
    validate_account,
    validate_password,
    _password_hash,
)


class AccountStoreTests(unittest.TestCase):
    def make_store(self, root: str) -> AccountStore:
        protect = lambda value: b"TEST:" + value.encode("utf-8")[::-1]
        unprotect = lambda value: bytes(value)[5:][::-1].decode("utf-8")
        store = AccountStore(Path(root), protect=protect, unprotect=unprotect)
        store.initialize()
        return store

    def test_register_login_session_and_dedicated_folder(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            store.register("管理员", "自选密码")
            identity = store.register("用户AbC001", "任意 Password !@#")
            self.assertEqual(identity.account, "用户AbC001")
            self.assertTrue((Path(root) / "accounts" / identity.folder_name / "database").is_dir())
            self.assertEqual(store.authenticate("用户aBc001", "任意 Password !@#").account_id, identity.account_id)
            self.assertIsNone(store.authenticate("用户ABC001", "错误密码"))
            token = store.create_session(identity, ttl_seconds=60)
            self.assertEqual(store.resolve_session(token).account_id, identity.account_id)
            store.logout(token)
            self.assertIsNone(store.resolve_session(token))

    def test_first_account_is_admin_and_has_no_builtin_password(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            self.assertTrue(store.needs_setup())
            self.assertIsNone(store.authenticate("jiang", "jiang"))
            with self.assertRaises(PermissionError):
                store.register("远端", "密码", allow_admin_setup=False)
            admin = store.register("自选管理员", "自己的密码")
            self.assertTrue(admin.is_admin)
            self.assertEqual(admin.account_id, "admin")
            self.assertEqual(store.account_layout(admin.account_id).root, Path(root).resolve())
            self.assertFalse(store.needs_setup())
            self.assertTrue(store.authenticate("自选管理员", "自己的密码").is_admin)
            self.assertFalse(store.register("jiang", "非默认密码").is_admin)
            self.assertIsNone(store.authenticate("jiang", "jiang"))
            with self.assertRaisesRegex(ValueError, "不能禁用"):
                store.update_account(admin.account_id, disabled=True)

    def test_admin_can_read_and_update_recoverable_password(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            store.register("管理员", "自选密码")
            identity = store.register("测试User8", "原 密码!@#")
            session = store.create_session(identity)
            listed = [item for item in store.list_accounts(include_passwords=True) if item['id'] == identity.account_id]
            self.assertEqual(listed[0]["password"], "原 密码!@#")
            store.update_account(identity.account_id, account="新User88", password="新密码 A-a_123", disabled=True)
            self.assertIsNone(store.resolve_session(session))
            updated = next(item for item in store.list_accounts(include_passwords=True) if item['id'] == identity.account_id)
            self.assertEqual(
                (updated["account"], updated["password"], updated["disabled"]),
                ("新User88", "新密码 A-a_123", True),
            )
            self.assertIsNone(store.authenticate("新user88", "新密码 A-a_123"))
            store.update_account(identity.account_id, disabled=False)
            self.assertIsNotNone(store.authenticate("新USER88", "新密码 A-a_123"))

    def test_account_accepts_chinese_ascii_letters_and_digits(self):
        self.assertEqual(validate_account("中文AbC001"), "中文AbC001")
        self.assertEqual(validate_account("ＡＢＣ１２３"), "ABC123")
        self.assertEqual(account_lookup_key("中文AbC001"), account_lookup_key("中文aBc001"))
        for value in ("", " ", "name-1", "name_1", "用户🙂", "a.b"):
            with self.assertRaises(ValueError):
                validate_account(value)

    def test_password_has_no_length_or_complexity_limit_but_cannot_be_empty(self):
        for value in ("1", "a", " ", "中文 密码!?", "密" * 10000):
            self.assertEqual(validate_password(value), value)
        with self.assertRaises(ValueError):
            validate_password("")

    def test_duplicate_account_is_case_insensitive_and_old_admin_name_is_available(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            store.register("User用户1", "2")
            with self.assertRaisesRegex(ValueError, "账号已存在"):
                store.register("uSER用户1", "3")
            store.register("jiang", "任意密码")
            with self.assertRaisesRegex(ValueError, "账号已存在"):
                store.register("JIANG", "任意密码")

    def test_persistent_session_survives_restart_and_revocation(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            admin = store.register("持久账号", "密码")
            token = store.create_session(admin, persistent=True)
            store.remember_desktop_session(token)
            with store.connect() as connection:
                saved = connection.execute("SELECT * FROM desktop_login").fetchone()
                self.assertNotEqual(saved['token_encrypted'], token.encode())
                self.assertEqual(connection.execute("SELECT expires_at FROM sessions").fetchone()[0], 0)
            restarted = self.make_store(root)
            self.assertEqual(restarted.desktop_session(), (token, admin))
            restarted.update_account(admin.account_id, password="新密码")
            self.assertEqual(restarted.desktop_session(), ("", None))
            token = restarted.create_session(admin, persistent=True)
            restarted.remember_desktop_session(token)
            restarted.logout(token)
            self.assertEqual(self.make_store(root).desktop_session(), ("", None))

    def test_concurrent_first_registration_has_exactly_one_admin(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as root:
            stores = [self.make_store(root), self.make_store(root)]
            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(lambda pair: pair[1].register(f"账号{pair[0]}", "密码"), enumerate(stores)))
            self.assertEqual(sum(item.is_admin for item in results), 1)
            self.assertEqual(len({item.account_id for item in results}), 2)

    def test_existing_numeric_account_database_adds_case_insensitive_lookup_key(self):
        with tempfile.TemporaryDirectory() as root:
            store = AccountStore(
                Path(root),
                protect=lambda value: b"TEST:" + value.encode("utf-8")[::-1],
                unprotect=lambda value: bytes(value)[5:][::-1].decode("utf-8"),
            )
            store.system_root.mkdir(parents=True)
            connection = sqlite3.connect(store.database_path)
            try:
                connection.execute(
                    """CREATE TABLE accounts (
                        id TEXT PRIMARY KEY, account TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                        password_encrypted BLOB NOT NULL, folder_name TEXT NOT NULL UNIQUE,
                        disabled INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL,
                        updated_at INTEGER NOT NULL, last_login_at INTEGER NOT NULL DEFAULT 0
                    )"""
                )
                connection.execute(
                    "INSERT INTO accounts VALUES(?,?,?,?,?,0,1,1,0)",
                    ("legacy-id", "001", _password_hash("7"), store._protect("7"), "legacy-folder"),
                )
                connection.execute("CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,account_id TEXT,role TEXT,created_at INTEGER,expires_at INTEGER,last_seen_at INTEGER)")
                from canvas_core.accounts import session_hash
                connection.executemany("INSERT INTO sessions VALUES(?,?,?,1,9999999999999,1)", [
                    (session_hash('old-admin'), 'admin', 'admin'),
                    (session_hash('old-user'), 'legacy-id', 'user'),
                ])
                connection.commit()
            finally:
                connection.close()
            store.initialize()
            with store.connect() as connection:
                columns = {row["name"] for row in connection.execute("PRAGMA table_info(accounts)")}
                account_key = connection.execute(
                    "SELECT account_key FROM accounts WHERE id='legacy-id'"
                ).fetchone()["account_key"]
            self.assertIn("account_key", columns)
            self.assertEqual(account_key, "001")
            self.assertEqual(store.authenticate("001", "7").account_id, "legacy-id")
            self.assertFalse(store.authenticate("001", "7").is_admin)
            self.assertTrue(store.needs_setup())
            self.assertTrue(store.register("新管理员", "新密码").is_admin)
            self.assertIsNone(store.resolve_session('old-admin'))
            self.assertEqual(store.resolve_session('old-user').account_id, 'legacy-id')
            self.assertEqual(store.account_layout('legacy-id').root, Path(root).resolve() / 'accounts' / 'legacy-folder')

    def test_web_session_expires_and_database_role_is_authoritative(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            store.register('管理员', '密码')
            user = store.register('普通用户', '密码')
            token = store.create_session(user)
            with store.connect() as connection:
                connection.execute("UPDATE sessions SET role='admin'")
            self.assertFalse(store.resolve_session(token).is_admin)
            with store.connect() as connection:
                connection.execute("UPDATE sessions SET expires_at=1")
            self.assertIsNone(store.resolve_session(token))

    def test_loopback_detection_covers_ipv4_ipv6_and_mapped_ipv4(self):
        self.assertTrue(is_loopback_address("127.0.0.1"))
        self.assertTrue(is_loopback_address("::1"))
        self.assertTrue(is_loopback_address("::ffff:127.0.0.1"))
        self.assertFalse(is_loopback_address("192.168.1.8"))

    def test_rate_limiter_blocks_after_repeated_failures(self):
        limiter = LoginRateLimiter(attempts=2, window_seconds=60, block_seconds=60)
        limiter.check("client")
        limiter.fail("client")
        limiter.check("client")
        limiter.fail("client")
        with self.assertRaises(PermissionError):
            limiter.check("client")


if __name__ == "__main__":
    unittest.main()
