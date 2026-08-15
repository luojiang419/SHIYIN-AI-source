import sqlite3
import tempfile
import unittest
from pathlib import Path

from canvas_core.accounts import (
    ADMIN_ACCOUNT,
    ADMIN_PASSWORD,
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
            identity = store.register("用户AbC001", "任意 Password !@#")
            self.assertEqual(identity.account, "用户AbC001")
            self.assertTrue((Path(root) / "accounts" / identity.folder_name / "database").is_dir())
            self.assertEqual(store.authenticate("用户aBc001", "任意 Password !@#").account_id, identity.account_id)
            self.assertIsNone(store.authenticate("用户ABC001", "错误密码"))
            token = store.create_session(identity, ttl_seconds=60)
            self.assertEqual(store.resolve_session(token).account_id, identity.account_id)
            store.logout(token)
            self.assertIsNone(store.resolve_session(token))

    def test_admin_is_fixed_and_loopback_only(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            token = store.create_admin_session(ADMIN_ACCOUNT, ADMIN_PASSWORD, "127.0.0.1")
            self.assertTrue(store.resolve_session(token).is_admin)
            with self.assertRaises(PermissionError):
                store.create_admin_session(ADMIN_ACCOUNT, ADMIN_PASSWORD, "192.168.1.20")
            with self.assertRaises(PermissionError):
                store.create_admin_session(ADMIN_ACCOUNT, "wrong", "127.0.0.1")

    def test_admin_can_read_and_update_recoverable_password(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            identity = store.register("测试User8", "原 密码!@#")
            session = store.create_session(identity)
            listed = store.list_accounts(include_passwords=True)
            self.assertEqual(listed[0]["password"], "原 密码!@#")
            store.update_account(identity.account_id, account="新User88", password="新密码 A-a_123", disabled=True)
            self.assertIsNone(store.resolve_session(session))
            updated = store.list_accounts(include_passwords=True)[0]
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

    def test_duplicate_account_is_case_insensitive_and_admin_name_is_reserved(self):
        with tempfile.TemporaryDirectory() as root:
            store = self.make_store(root)
            store.register("User用户1", "2")
            with self.assertRaisesRegex(ValueError, "账号已存在"):
                store.register("uSER用户1", "3")
            for reserved in ("jiang", "JIANG", "Jiang"):
                with self.assertRaisesRegex(ValueError, "管理员专用"):
                    store.register(reserved, "任意密码")

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
