from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .database import CanvasDatabase


SESSION_COOKIE = "canvas_session"
# WebView 在启动、恢复导航和设置 Cookie 的竞态期间可能重复请求 bootstrap。
# 令牌本身是每次桌面进程随机生成的，并且 bootstrap 仅允许 loopback，
# 因此在短窗口内允许有限重放比把正常启动误判为 401 更稳妥。
DESKTOP_TOKEN_REPLAY_WINDOW_SECONDS = 300.0
DESKTOP_TOKEN_REPLAY_LIMIT = 64


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
    def __init__(
        self,
        _database: CanvasDatabase,
        desktop_token: str = "",
        *,
        desktop_replay_window_seconds: float = DESKTOP_TOKEN_REPLAY_WINDOW_SECONDS,
        desktop_replay_limit: int = DESKTOP_TOKEN_REPLAY_LIMIT,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        raw_desktop_token = str(desktop_token or "")
        self._desktop_token_hash = token_hash(raw_desktop_token) if raw_desktop_token else ""
        self._consumed_desktop_token_hash = ""
        self._desktop_token_consumed_at = 0.0
        self._desktop_token_replays_remaining = 0
        self._desktop_replay_window_seconds = max(0.0, float(desktop_replay_window_seconds))
        self._desktop_replay_limit = max(0, int(desktop_replay_limit))
        self._clock = clock
        self._runtime_sessions: dict[str, AuthIdentity] = {}
        self._lock = threading.RLock()

    @staticmethod
    def new_token() -> str:
        return secrets.token_urlsafe(32)

    def consume_desktop_token(self, supplied: str) -> tuple[str, AuthIdentity]:
        supplied_hash = token_hash(str(supplied or ""))
        with self._lock:
            now = self._clock()
            first_exchange = bool(self._desktop_token_hash) and hmac.compare_digest(
                self._desktop_token_hash,
                supplied_hash,
            )
            replay_exchange = (
                bool(self._consumed_desktop_token_hash)
                and self._desktop_token_replays_remaining > 0
                and 0.0 <= now - self._desktop_token_consumed_at <= self._desktop_replay_window_seconds
                and hmac.compare_digest(self._consumed_desktop_token_hash, supplied_hash)
            )
            if not first_exchange and not replay_exchange:
                raise PermissionError("桌面启动令牌无效或已使用")
            if first_exchange:
                self._desktop_token_hash = ""
                self._consumed_desktop_token_hash = supplied_hash
                self._desktop_token_consumed_at = now
                self._desktop_token_replays_remaining = self._desktop_replay_limit
            else:
                self._desktop_token_replays_remaining -= 1
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
