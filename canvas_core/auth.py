from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from dataclasses import dataclass
from typing import Optional

from .database import CanvasDatabase


SESSION_COOKIE = "canvas_session"


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthIdentity:
    device_id: str
    name: str
    client_type: str
    persistent: bool

    def public(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "client_type": self.client_type,
            "persistent": self.persistent,
        }


class AuthManager:
    def __init__(self, _database: CanvasDatabase, desktop_token: str = "") -> None:
        self._desktop_token = str(desktop_token or "")
        self._runtime_sessions: dict[str, AuthIdentity] = {}
        self._lock = threading.RLock()

    @staticmethod
    def new_token() -> str:
        return secrets.token_urlsafe(32)

    def consume_desktop_token(self, supplied: str) -> tuple[str, AuthIdentity]:
        with self._lock:
            expected = self._desktop_token
            if not expected or not hmac.compare_digest(expected, str(supplied or "")):
                raise PermissionError("桌面启动令牌无效或已使用")
            self._desktop_token = ""
            token = self.new_token()
            identity = AuthIdentity("desktop-runtime", "Canvas 桌面端", "desktop", False)
            self._runtime_sessions[token_hash(token)] = identity
            return token, identity

    def authenticate(self, token: str) -> Optional[AuthIdentity]:
        raw = str(token or "").strip()
        if not raw:
            return None
        digest = token_hash(raw)
        with self._lock:
            runtime = self._runtime_sessions.get(digest)
        return runtime

    @staticmethod
    def bearer_token(authorization: str) -> str:
        scheme, _, value = str(authorization or "").partition(" ")
        return value.strip() if scheme.lower() == "bearer" else ""
