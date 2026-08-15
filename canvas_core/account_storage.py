from __future__ import annotations

import contextvars
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from .accounts import AccountStore
from .data_layout import DataLayout
from .database import CanvasDatabase


ADMIN_ACCOUNT_ID = "admin"
_CURRENT_ACCOUNT_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "canvas_current_account_id", default=ADMIN_ACCOUNT_ID
)


def current_account_id() -> str:
    return str(_CURRENT_ACCOUNT_ID.get() or ADMIN_ACCOUNT_ID)


def set_current_account(account_id: str):
    return _CURRENT_ACCOUNT_ID.set(str(account_id or ADMIN_ACCOUNT_ID))


def reset_current_account(token) -> None:
    _CURRENT_ACCOUNT_ID.reset(token)


@contextmanager
def account_scope(account_id: str) -> Iterator[None]:
    token = set_current_account(account_id)
    try:
        yield
    finally:
        reset_current_account(token)


class AccountStorageRegistry:
    def __init__(
        self,
        account_store: AccountStore,
        admin_layout: DataLayout,
        admin_database: CanvasDatabase,
    ) -> None:
        self.account_store = account_store
        self.admin_layout = admin_layout
        self.admin_database = admin_database
        self._layouts: dict[str, DataLayout] = {ADMIN_ACCOUNT_ID: admin_layout}
        self._databases: dict[str, CanvasDatabase] = {ADMIN_ACCOUNT_ID: admin_database}
        self._lock = threading.RLock()

    def layout_for(self, account_id: str) -> DataLayout:
        clean_id = str(account_id or ADMIN_ACCOUNT_ID)
        with self._lock:
            cached = self._layouts.get(clean_id)
            if cached:
                return cached
            layout = self.account_store.account_layout(clean_id)
            layout.ensure()
            self._layouts[clean_id] = layout
            return layout

    def database_for(self, account_id: str) -> CanvasDatabase:
        clean_id = str(account_id or ADMIN_ACCOUNT_ID)
        with self._lock:
            cached = self._databases.get(clean_id)
            if cached:
                return cached
            database = CanvasDatabase(self.layout_for(clean_id).database_file)
            database.initialize()
            self._databases[clean_id] = database
            return database

    def current_layout(self) -> DataLayout:
        return self.layout_for(current_account_id())

    def current_database(self) -> CanvasDatabase:
        return self.database_for(current_account_id())

    def forget(self, account_id: str) -> None:
        clean_id = str(account_id or "")
        if not clean_id or clean_id == ADMIN_ACCOUNT_ID:
            return
        with self._lock:
            self._layouts.pop(clean_id, None)
            self._databases.pop(clean_id, None)


class ScopedDatabaseProxy:
    def __init__(self, registry: AccountStorageRegistry) -> None:
        object.__setattr__(self, "_registry", registry)

    def __getattr__(self, name: str):
        return getattr(self._registry.current_database(), name)

    def __repr__(self) -> str:
        return f"ScopedDatabaseProxy(account_id={current_account_id()!r})"


class ScopedDataLayoutProxy:
    def __init__(self, registry: AccountStorageRegistry) -> None:
        object.__setattr__(self, "_registry", registry)

    def __getattr__(self, name: str):
        return getattr(self._registry.current_layout(), name)

    def __repr__(self) -> str:
        return f"ScopedDataLayoutProxy(account_id={current_account_id()!r})"


class ScopedPath:
    def __init__(self, resolver: Callable[[DataLayout], Path], registry: AccountStorageRegistry) -> None:
        self._resolver = resolver
        self._registry = registry

    def path(self) -> Path:
        return Path(self._resolver(self._registry.current_layout()))

    def __fspath__(self) -> str:
        return str(self.path())

    def __str__(self) -> str:
        return str(self.path())

    def __repr__(self) -> str:
        return f"ScopedPath({self.path()!s})"

    def __truediv__(self, value):
        return self.path() / value
