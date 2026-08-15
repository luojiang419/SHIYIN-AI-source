from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import secrets
import sqlite3
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .data_layout import DataLayout
from .secrets import DpapiProtector


ACCOUNT_SESSION_COOKIE = "canvas_account_session"
ADMIN_ACCOUNT = "jiang"
ADMIN_PASSWORD = "jiang"
MAX_ACCOUNT_CHARS = 4096
SESSION_TTL_SECONDS = 30 * 24 * 60 * 60


def now_ms() -> int:
    return int(time.time() * 1000)


def session_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def account_lookup_key(value: str) -> str:
    text = str(value if value is not None else "")
    return unicodedata.normalize("NFKC", text).casefold()


def _is_chinese_character(value: str) -> bool:
    codepoint = ord(value)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2FA1F
    )


def validate_account(value: str, label: str = "账号") -> str:
    text = unicodedata.normalize("NFKC", str(value if value is not None else ""))
    if not text:
        raise ValueError(f"{label}至少需要 1 个字符")
    if len(text) > MAX_ACCOUNT_CHARS:
        raise ValueError(f"{label}不能超过 {MAX_ACCOUNT_CHARS} 个字符")
    if not all((character.isascii() and character.isalnum()) or _is_chinese_character(character) for character in text):
        raise ValueError(f"{label}只能包含中文、英文字母和数字")
    if account_lookup_key(text) == account_lookup_key(ADMIN_ACCOUNT):
        raise ValueError(f"{label} {ADMIN_ACCOUNT} 为管理员专用")
    return text


def validate_password(value: str, label: str = "密码") -> str:
    text = str(value if value is not None else "")
    if not text:
        raise ValueError(f"{label}不能为空")
    return text


def is_admin_account(value: str) -> bool:
    return account_lookup_key(value) == account_lookup_key(ADMIN_ACCOUNT)


def is_loopback_address(value: str) -> bool:
    text = str(value or "").strip().split("%", 1)[0]
    if not text:
        return False
    try:
        address = ipaddress.ip_address(text)
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return bool(address.is_loopback)
    except ValueError:
        return text.lower() == "localhost"


def _password_hash(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    salt_text = base64.urlsafe_b64encode(salt).decode("ascii")
    derived_text = base64.urlsafe_b64encode(derived).decode("ascii")
    return f"scrypt$16384$8$1${salt_text}${derived_text}"


def _password_matches(password: str, encoded: str) -> bool:
    try:
        scheme, raw_n, raw_r, raw_p, raw_salt, raw_expected = str(encoded or "").split("$", 5)
        if scheme != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(raw_salt.encode("ascii"))
        expected = base64.urlsafe_b64decode(raw_expected.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(raw_n),
            r=int(raw_r),
            p=int(raw_p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class AccountIdentity:
    account_id: str
    account: str
    role: str
    folder_name: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def public(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "account": self.account,
            "role": self.role,
            "is_admin": self.is_admin,
        }


class LoginRateLimiter:
    def __init__(self, attempts: int = 8, window_seconds: int = 60, block_seconds: int = 300) -> None:
        self.attempts = max(1, int(attempts))
        self.window_seconds = max(1, int(window_seconds))
        self.block_seconds = max(1, int(block_seconds))
        self._entries: dict[str, tuple[list[float], float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        current = time.monotonic()
        with self._lock:
            values, blocked_until = self._entries.get(key, ([], 0.0))
            if current < blocked_until:
                raise PermissionError("登录尝试过多，请稍后再试")
            values = [stamp for stamp in values if current - stamp <= self.window_seconds]
            self._entries[key] = (values, 0.0)

    def fail(self, key: str) -> None:
        current = time.monotonic()
        with self._lock:
            values, blocked_until = self._entries.get(key, ([], 0.0))
            values = [stamp for stamp in values if current - stamp <= self.window_seconds]
            values.append(current)
            if len(values) >= self.attempts:
                blocked_until = current + self.block_seconds
            self._entries[key] = (values, blocked_until)

    def success(self, key: str) -> None:
        with self._lock:
            self._entries.pop(key, None)


class ClosingAccountConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class AccountStore:
    def __init__(
        self,
        data_root: Path,
        protect: Optional[Callable[[str], bytes]] = None,
        unprotect: Optional[Callable[[bytes], str]] = None,
    ) -> None:
        self.data_root = Path(data_root).expanduser().resolve()
        self.system_root = self.data_root / "system"
        self.accounts_root = self.data_root / "accounts"
        self.database_path = self.system_root / "accounts.db"
        if protect is None or unprotect is None:
            protector = DpapiProtector()
            protect = protector.protect
            unprotect = protector.unprotect
        self._protect = protect
        self._unprotect = unprotect
        self._lock = threading.RLock()
        self.rate_limiter = LoginRateLimiter()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.database_path), timeout=5.0, isolation_level=None, factory=ClosingAccountConnection
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def initialize(self) -> None:
        self.system_root.mkdir(parents=True, exist_ok=True)
        self.accounts_root.mkdir(parents=True, exist_ok=True)
        with self._lock, self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    account TEXT NOT NULL UNIQUE,
                    account_key TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_encrypted BLOB NOT NULL,
                    folder_name TEXT NOT NULL UNIQUE,
                    disabled INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    last_login_at INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
                """
            )
            account_columns = {
                str(row["name"]) for row in connection.execute("PRAGMA table_info(accounts)").fetchall()
            }
            if "account_key" not in account_columns:
                connection.execute("ALTER TABLE accounts ADD COLUMN account_key TEXT NOT NULL DEFAULT ''")
            existing_keys: dict[str, str] = {}
            for row in connection.execute("SELECT id,account,account_key FROM accounts ORDER BY created_at,id"):
                key = account_lookup_key(str(row["account"]))
                duplicate_id = existing_keys.get(key)
                if duplicate_id and duplicate_id != str(row["id"]):
                    raise RuntimeError("账号数据库存在仅大小写不同的重复账号，无法完成唯一性迁移")
                existing_keys[key] = str(row["id"])
                if str(row["account_key"] or "") != key:
                    connection.execute("UPDATE accounts SET account_key=? WHERE id=?", (key, row["id"]))
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_account_key ON accounts(account_key)")
            connection.execute("DELETE FROM sessions WHERE expires_at<?", (now_ms(),))

    def account_layout(self, account_id: str) -> DataLayout:
        if account_id == "admin":
            return DataLayout.from_root(self.data_root)
        record = self.account_by_id(account_id)
        if not record:
            raise KeyError("账号不存在")
        return DataLayout.from_root(self.accounts_root / str(record["folder_name"]))

    def register(self, account: str, password: str) -> AccountIdentity:
        clean_account = validate_account(account)
        clean_password = validate_password(password)
        clean_account_key = account_lookup_key(clean_account)
        account_id = uuid.uuid4().hex
        folder_name = account_id
        timestamp = now_ms()
        with self._lock, self.connect() as connection:
            try:
                connection.execute(
                    """INSERT INTO accounts(
                           id,account,account_key,password_hash,password_encrypted,folder_name,disabled,created_at,updated_at,last_login_at
                       ) VALUES(?,?,?,?,?,?,0,?,?,0)""",
                    (
                        account_id,
                        clean_account,
                        clean_account_key,
                        _password_hash(clean_password),
                        self._protect(clean_password),
                        folder_name,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("账号已存在，请直接登录") from exc
        layout = DataLayout.from_root(self.accounts_root / folder_name)
        layout.ensure()
        return AccountIdentity(account_id, clean_account, "user", folder_name)

    def authenticate(self, account: str, password: str) -> Optional[AccountIdentity]:
        clean_account = validate_account(account)
        clean_password = validate_password(password)
        clean_account_key = account_lookup_key(clean_account)
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM accounts WHERE account_key=?", (clean_account_key,)).fetchone()
            if not row or int(row["disabled"] or 0) or not _password_matches(clean_password, row["password_hash"]):
                return None
            connection.execute("UPDATE accounts SET last_login_at=? WHERE id=?", (now_ms(), row["id"]))
        return AccountIdentity(str(row["id"]), str(row["account"]), "user", str(row["folder_name"]))

    def create_session(self, identity: AccountIdentity, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
        token = secrets.token_urlsafe(32)
        timestamp = now_ms()
        expires_at = timestamp + max(60, int(ttl_seconds)) * 1000
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(token_hash,account_id,role,created_at,expires_at,last_seen_at) VALUES(?,?,?,?,?,?)",
                (session_hash(token), identity.account_id, identity.role, timestamp, expires_at, timestamp),
            )
        return token

    def resolve_session(self, token: str) -> Optional[AccountIdentity]:
        digest = session_hash(token)
        if not token:
            return None
        timestamp = now_ms()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE token_hash=?", (digest,)).fetchone()
            if not row or int(row["expires_at"] or 0) < timestamp:
                if row:
                    connection.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
                return None
            if str(row["role"]) == "admin":
                identity = AccountIdentity("admin", ADMIN_ACCOUNT, "admin", "")
            else:
                account = connection.execute("SELECT * FROM accounts WHERE id=?", (row["account_id"],)).fetchone()
                if not account or int(account["disabled"] or 0):
                    connection.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
                    return None
                identity = AccountIdentity(
                    str(account["id"]), str(account["account"]), "user", str(account["folder_name"])
                )
            if timestamp - int(row["last_seen_at"] or 0) >= 60_000:
                connection.execute("UPDATE sessions SET last_seen_at=? WHERE token_hash=?", (timestamp, digest))
            return identity

    def logout(self, token: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash=?", (session_hash(token),))

    def create_admin_session(self, account: str, password: str, remote_address: str) -> str:
        if not is_loopback_address(remote_address):
            raise PermissionError("管理员只能在安装软件的本机登录")
        if not hmac.compare_digest(str(account or ""), ADMIN_ACCOUNT) or not hmac.compare_digest(
            str(password or ""), ADMIN_PASSWORD
        ):
            raise PermissionError("管理员账号或密码错误")
        return self.create_session(AccountIdentity("admin", ADMIN_ACCOUNT, "admin", ""), ttl_seconds=12 * 60 * 60)

    def account_by_id(self, account_id: str) -> Optional[dict[str, object]]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM accounts WHERE id=?", (str(account_id or ""),)).fetchone()
        return dict(row) if row else None

    def list_accounts(self, include_passwords: bool = False) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM accounts ORDER BY created_at,id").fetchall()
        result = []
        for row in rows:
            item = {
                "id": str(row["id"]),
                "account": str(row["account"]),
                "disabled": bool(row["disabled"]),
                "created_at": int(row["created_at"]),
                "updated_at": int(row["updated_at"]),
                "last_login_at": int(row["last_login_at"]),
                "folder_name": str(row["folder_name"]),
            }
            if include_passwords:
                item["password"] = self._unprotect(bytes(row["password_encrypted"]))
            result.append(item)
        return result

    def update_account(
        self,
        account_id: str,
        *,
        account: Optional[str] = None,
        password: Optional[str] = None,
        disabled: Optional[bool] = None,
    ) -> dict[str, object]:
        updates: list[str] = []
        values: list[object] = []
        if account is not None:
            clean_account = validate_account(account)
            updates.extend(["account=?", "account_key=?"])
            values.extend([clean_account, account_lookup_key(clean_account)])
        if password is not None:
            clean_password = validate_password(password)
            updates.extend(["password_hash=?", "password_encrypted=?"])
            values.extend([_password_hash(clean_password), self._protect(clean_password)])
        if disabled is not None:
            updates.append("disabled=?")
            values.append(1 if disabled else 0)
        if not updates:
            record = self.account_by_id(account_id)
            if not record:
                raise KeyError("账号不存在")
            return record
        updates.append("updated_at=?")
        values.append(now_ms())
        values.append(str(account_id or ""))
        with self._lock, self.connect() as connection:
            try:
                cursor = connection.execute(
                    f"UPDATE accounts SET {','.join(updates)} WHERE id=?",
                    tuple(values),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("账号已存在") from exc
            if cursor.rowcount <= 0:
                raise KeyError("账号不存在")
            if password is not None or disabled:
                connection.execute("DELETE FROM sessions WHERE account_id=?", (str(account_id or ""),))
        record = self.account_by_id(account_id)
        if not record:
            raise KeyError("账号不存在")
        return record
