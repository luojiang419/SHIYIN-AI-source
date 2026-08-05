from __future__ import annotations

import json
import hashlib
import os
import re
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _payload(raw: Optional[str], default: Any = None) -> Any:
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def _text(value: Any, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def _number(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_number(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _work_item_id(history_id: str, index: int, url: str) -> str:
    identity = f"{history_id}\0{int(index)}\0{url}".encode("utf-8")
    return "work_" + hashlib.sha256(identity).hexdigest()[:24]


def _history_images(record: dict[str, Any]) -> list[str]:
    return [_text(url, 2000) for url in record.get("images") or [] if _text(url, 2000)]


def _history_params(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("params") if isinstance(record.get("params"), dict) else {}


def _history_references(record: dict[str, Any]) -> list[dict[str, Any]]:
    params = _history_params(record)
    values = record.get("inputs") or params.get("reference_images") or record.get("reference_images") or []
    return [dict(item) for item in values if isinstance(item, dict) and _text(item.get("url"), 2000)]


def _history_source_url(record: dict[str, Any]) -> str:
    params = _history_params(record)
    explicit = _text(record.get("comparison_reference_url") or params.get("comparison_reference_url"), 2000)
    if explicit:
        return explicit
    for item in _history_references(record):
        role = _text(item.get("role") or item.get("type"), 80).lower()
        if role in {"source", "reference", "input", ""}:
            return _text(item.get("url"), 2000)
    return ""


def _history_index(record: dict[str, Any]) -> dict[str, Any]:
    params = _history_params(record)
    images = _history_images(record)
    prompt = _text(record.get("prompt") or params.get("prompt"), 1000)
    model = _text(record.get("model") or params.get("model"), 240)
    operation = _text(record.get("operation") or params.get("operation"), 120)
    provider_id = _text(record.get("provider_id") or params.get("provider_id"), 160)
    search_text = " ".join([prompt, model, operation, provider_id, " ".join(images[:3])]).lower()[:4000]
    return {
        "kind": _text(record.get("type") or "zimage", 80) or "zimage",
        "created_at": _number(record.get("timestamp") or record.get("created_at") or time.time()),
        "prompt": prompt,
        "model": model,
        "operation": operation,
        "provider_id": provider_id,
        "first_url": images[0] if images else "",
        "image_count": len(images),
        "search_text": search_text,
    }


def _canvas_summary(canvas: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": _text(canvas.get("project") or "default", 160) or "default",
        "kind": _text(canvas.get("kind") or "classic", 40) or "classic",
        "title": _text(canvas.get("title"), 160),
        "created_at": _int_number(canvas.get("created_at")),
        "icon": _text(canvas.get("icon"), 64),
        "owner": _text(canvas.get("owner"), 80),
        "color": _text(canvas.get("color"), 40),
        "pinned": 1 if canvas.get("pinned") else 0,
        "board_x": canvas.get("board_x"),
        "board_y": canvas.get("board_y"),
        "node_count": len(canvas.get("nodes") or []),
    }


def _work_rows_from_history(record: dict[str, Any], history_id: str = "") -> list[dict[str, Any]]:
    history_id = _text(history_id or record.get("_history_id") or record.get("id"), 240)
    if not history_id:
        return []
    index = _history_index(record)
    images = _history_images(record)
    image_items = record.get("image_items") if isinstance(record.get("image_items"), list) else []
    references = _history_references(record)
    references_json = _json(references)
    source_url = _history_source_url(record)
    params = _history_params(record)
    rows = []
    for output_index, url in enumerate(images):
        item_meta = image_items[output_index] if output_index < len(image_items) and isinstance(image_items[output_index], dict) else {}
        original_name = os.path.basename(url.split("?", 1)[0].split("#", 1)[0].replace("\\", "/")) or f"作品-{output_index + 1}"
        name = original_name
        task_id = _text(record.get("ecommerce_task_id") or record.get("task_id"), 160)
        rows.append({
            "id": _work_item_id(history_id, output_index, url),
            "history_id": history_id,
            "output_index": output_index,
            "url": url,
            "kind": index["kind"],
            "operation": index["operation"],
            "created_at": index["created_at"],
            "prompt": index["prompt"],
            "provider_id": index["provider_id"],
            "provider_name": _text(record.get("provider_name"), 240),
            "model": index["model"],
            "width": _int_number(item_meta.get("width")),
            "height": _int_number(item_meta.get("height")),
            "task_id": task_id,
            "source_url": source_url,
            "original_name": original_name,
            "name": name,
            "favorite": 0,
            "favorite_updated_at": 0,
            "trashed": 0,
            "trashed_at": 0,
            "metadata_updated_at": 0,
            "search_text": " ".join([
                name, original_name, index["prompt"], index["model"], index["operation"],
                _text(params.get("operation"), 120), url,
            ]).lower()[:4000],
            "references_json": references_json,
        })
    return rows


class RevisionConflict(RuntimeError):
    def __init__(self, revision: int, value: Any):
        super().__init__("revision conflict")
        self.revision = int(revision)
        self.value = value


class ClosingSqliteConnection(sqlite3.Connection):
    """Make ``with connection`` close the file handle after commit/rollback."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class CanvasDatabase:
    SCHEMA_VERSION = 4

    def __init__(self, path: Path):
        self.path = Path(path)
        self._schema_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.path),
            timeout=5.0,
            isolation_level=None,
            factory=ClosingSqliteConnection,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    @contextmanager
    def transaction(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._schema_lock, self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS providers (
                    id TEXT PRIMARY KEY,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    payload_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS canvases (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL DEFAULT 'default',
                    kind TEXT NOT NULL DEFAULT 'classic',
                    title TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL DEFAULT 0,
                    icon TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    color TEXT NOT NULL DEFAULT '',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    board_x REAL,
                    board_y REAL,
                    node_count INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL,
                    deleted_at INTEGER NOT NULL DEFAULT 0,
                    revision INTEGER NOT NULL DEFAULT 1,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_canvases_project ON canvases(project_id, deleted_at, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_canvases_kind ON canvases(kind, deleted_at, updated_at DESC);
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    updated_at INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY(user_id, id)
                );
                CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, updated_at DESC);
                CREATE TABLE IF NOT EXISTS generation_history (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL DEFAULT 'zimage',
                    created_at REAL NOT NULL,
                    prompt TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    operation TEXT NOT NULL DEFAULT '',
                    provider_id TEXT NOT NULL DEFAULT '',
                    first_url TEXT NOT NULL DEFAULT '',
                    image_count INTEGER NOT NULL DEFAULT 0,
                    search_text TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_generation_history_kind ON generation_history(kind, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_generation_history_created ON generation_history(created_at DESC, id DESC);
                CREATE TABLE IF NOT EXISTS work_items (
                    id TEXT PRIMARY KEY,
                    history_id TEXT NOT NULL,
                    output_index INTEGER NOT NULL DEFAULT 0,
                    url TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT 'image',
                    operation TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL DEFAULT 0,
                    prompt TEXT NOT NULL DEFAULT '',
                    provider_id TEXT NOT NULL DEFAULT '',
                    provider_name TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    task_id TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL DEFAULT '',
                    original_name TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL DEFAULT '',
                    favorite INTEGER NOT NULL DEFAULT 0,
                    favorite_updated_at REAL NOT NULL DEFAULT 0,
                    trashed INTEGER NOT NULL DEFAULT 0,
                    trashed_at REAL NOT NULL DEFAULT 0,
                    metadata_updated_at REAL NOT NULL DEFAULT 0,
                    search_text TEXT NOT NULL DEFAULT '',
                    references_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE INDEX IF NOT EXISTS idx_work_items_visible ON work_items(trashed, favorite, kind, created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_work_items_history ON work_items(history_id);
                CREATE TABLE IF NOT EXISTS local_asset_items (
                    id TEXT PRIMARY KEY,
                    file TEXT NOT NULL DEFAULT '',
                    folder TEXT NOT NULL DEFAULT '',
                    name TEXT NOT NULL DEFAULT '',
                    url TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT '',
                    size INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0,
                    search_text TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_local_asset_folder ON local_asset_items(folder, created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_local_asset_kind ON local_asset_items(kind, created_at DESC, id DESC);
                CREATE TABLE IF NOT EXISTS media_objects (
                    url TEXT PRIMARY KEY,
                    path TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL DEFAULT '',
                    size INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL DEFAULT 0,
                    last_seen_at REAL NOT NULL DEFAULT 0,
                    ref_count INTEGER NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_media_objects_category ON media_objects(category, ref_count, last_seen_at);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '',
                    updated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_kind_status ON tasks(kind, status, updated_at DESC);
                CREATE TABLE IF NOT EXISTS library_documents (
                    kind TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shared_folders (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paired_devices (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    revoked_at INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS kv_documents (
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY(namespace, key)
                );
                CREATE TABLE IF NOT EXISTS secret_values (
                    key TEXT PRIMARY KEY,
                    encrypted_value BLOB NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
                (1, "initial-desktop-schema", int(time.time() * 1000)),
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
                (2, "dpapi-secrets-and-device-auth", int(time.time() * 1000)),
            )
            has_v4 = connection.execute("SELECT 1 FROM schema_migrations WHERE version=?", (4,)).fetchone() is not None
            self._ensure_v3_schema(connection)
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
                (3, "million-scale-indexes", int(time.time() * 1000)),
            )
            self._ensure_work_items_fts(connection, force_rebuild=not has_v4)
            if self._has_work_items_fts(connection):
                connection.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)",
                    (4, "work-items-fts-search", int(time.time() * 1000)),
                )

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        return {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}

    @staticmethod
    def _add_column(connection: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
        if column not in CanvasDatabase._columns(connection, table):
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def _ensure_v3_schema(self, connection: sqlite3.Connection) -> None:
        for column, declaration in (
            ("created_at", "INTEGER NOT NULL DEFAULT 0"),
            ("icon", "TEXT NOT NULL DEFAULT ''"),
            ("owner", "TEXT NOT NULL DEFAULT ''"),
            ("color", "TEXT NOT NULL DEFAULT ''"),
            ("pinned", "INTEGER NOT NULL DEFAULT 0"),
            ("board_x", "REAL"),
            ("board_y", "REAL"),
            ("node_count", "INTEGER NOT NULL DEFAULT 0"),
        ):
            self._add_column(connection, "canvases", column, declaration)
        for column, declaration in (
            ("prompt", "TEXT NOT NULL DEFAULT ''"),
            ("model", "TEXT NOT NULL DEFAULT ''"),
            ("operation", "TEXT NOT NULL DEFAULT ''"),
            ("provider_id", "TEXT NOT NULL DEFAULT ''"),
            ("first_url", "TEXT NOT NULL DEFAULT ''"),
            ("image_count", "INTEGER NOT NULL DEFAULT 0"),
            ("search_text", "TEXT NOT NULL DEFAULT ''"),
        ):
            self._add_column(connection, "generation_history", column, declaration)
        connection.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_generation_history_created ON generation_history(created_at DESC, id DESC);
            CREATE TABLE IF NOT EXISTS work_items (
                id TEXT PRIMARY KEY,
                history_id TEXT NOT NULL,
                output_index INTEGER NOT NULL DEFAULT 0,
                url TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT 'image',
                operation TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL DEFAULT 0,
                prompt TEXT NOT NULL DEFAULT '',
                provider_id TEXT NOT NULL DEFAULT '',
                provider_name TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',
                width INTEGER NOT NULL DEFAULT 0,
                height INTEGER NOT NULL DEFAULT 0,
                task_id TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                original_name TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '',
                favorite INTEGER NOT NULL DEFAULT 0,
                favorite_updated_at REAL NOT NULL DEFAULT 0,
                trashed INTEGER NOT NULL DEFAULT 0,
                trashed_at REAL NOT NULL DEFAULT 0,
                metadata_updated_at REAL NOT NULL DEFAULT 0,
                search_text TEXT NOT NULL DEFAULT '',
                references_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE INDEX IF NOT EXISTS idx_work_items_visible ON work_items(trashed, favorite, kind, created_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_work_items_history ON work_items(history_id);
            CREATE TABLE IF NOT EXISTS local_asset_items (
                id TEXT PRIMARY KEY,
                file TEXT NOT NULL DEFAULT '',
                folder TEXT NOT NULL DEFAULT '',
                name TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL DEFAULT 0,
                search_text TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_local_asset_folder ON local_asset_items(folder, created_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_local_asset_kind ON local_asset_items(kind, created_at DESC, id DESC);
            CREATE TABLE IF NOT EXISTS media_objects (
                url TEXT PRIMARY KEY,
                path TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                kind TEXT NOT NULL DEFAULT '',
                size INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL DEFAULT 0,
                last_seen_at REAL NOT NULL DEFAULT 0,
                ref_count INTEGER NOT NULL DEFAULT 0,
                source TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_media_objects_category ON media_objects(category, ref_count, last_seen_at);
            """
        )

    @staticmethod
    def _has_work_items_fts(connection: sqlite3.Connection) -> bool:
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='work_items_fts'"
        ).fetchone() is not None

    def _ensure_work_items_fts(self, connection: sqlite3.Connection, *, force_rebuild: bool = False) -> None:
        try:
            connection.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS work_items_fts
                USING fts5(id UNINDEXED, search_text, tokenize='unicode61');
                CREATE TRIGGER IF NOT EXISTS trg_work_items_fts_ai
                AFTER INSERT ON work_items BEGIN
                    DELETE FROM work_items_fts WHERE id = new.id;
                    INSERT INTO work_items_fts(id, search_text) VALUES (new.id, new.search_text);
                END;
                CREATE TRIGGER IF NOT EXISTS trg_work_items_fts_ad
                AFTER DELETE ON work_items BEGIN
                    DELETE FROM work_items_fts WHERE id = old.id;
                END;
                CREATE TRIGGER IF NOT EXISTS trg_work_items_fts_au
                AFTER UPDATE OF id, search_text ON work_items BEGIN
                    DELETE FROM work_items_fts WHERE id = old.id;
                    INSERT INTO work_items_fts(id, search_text) VALUES (new.id, new.search_text);
                END;
                """
            )
        except sqlite3.OperationalError:
            return
        work_count = int(connection.execute("SELECT COUNT(*) FROM work_items").fetchone()[0])
        fts_count = int(connection.execute("SELECT COUNT(*) FROM work_items_fts").fetchone()[0])
        if force_rebuild or work_count != fts_count:
            connection.execute("DELETE FROM work_items_fts")
            connection.execute(
                "INSERT INTO work_items_fts(id, search_text) SELECT id, search_text FROM work_items"
            )

    @staticmethod
    def _work_items_fts_query(search: str) -> str:
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", str(search or "").lower(), flags=re.UNICODE)
        return " AND ".join(token for token in tokens if token)[:300]

    def pragma_summary(self) -> dict[str, Any]:
        with self.connect() as connection:
            return {
                "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                "foreign_keys": connection.execute("PRAGMA foreign_keys").fetchone()[0],
                "busy_timeout": connection.execute("PRAGMA busy_timeout").fetchone()[0],
                "synchronous": connection.execute("PRAGMA synchronous").fetchone()[0],
                "schema_version": self.SCHEMA_VERSION,
            }

    def get_document(self, namespace: str, key: str, default: Any = None) -> Any:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM kv_documents WHERE namespace=? AND key=?", (namespace, key)
            ).fetchone()
        return _payload(row["payload_json"], default) if row else default

    def put_document(self, namespace: str, key: str, value: Any) -> int:
        now = int(time.time() * 1000)
        with self.transaction(immediate=True) as connection:
            row = connection.execute(
                "SELECT revision FROM kv_documents WHERE namespace=? AND key=?", (namespace, key)
            ).fetchone()
            revision = int(row["revision"] if row else 0) + 1
            connection.execute(
                """INSERT INTO kv_documents(namespace,key,payload_json,revision,updated_at) VALUES(?,?,?,?,?)
                   ON CONFLICT(namespace,key) DO UPDATE SET payload_json=excluded.payload_json,
                   revision=excluded.revision,updated_at=excluded.updated_at""",
                (namespace, key, _json(value), revision, now),
            )
        return revision

    def get_setting(self, key: str, default: Any = None) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT value_json,revision,updated_at FROM app_settings WHERE key=?", (key,)
            ).fetchone()
        if not row:
            return {"value": default, "revision": 0, "updated_at": 0}
        return {
            "value": _payload(row["value_json"], default),
            "revision": int(row["revision"]),
            "updated_at": int(row["updated_at"]),
        }

    def save_setting(self, key: str, value: Any, base_revision: int = 0, only_if_empty: bool = False) -> dict[str, Any]:
        now = int(time.time() * 1000)
        with self.transaction(immediate=True) as connection:
            row = connection.execute(
                "SELECT value_json,revision,updated_at FROM app_settings WHERE key=?", (key,)
            ).fetchone()
            current_revision = int(row["revision"] if row else 0)
            current_value = _payload(row["value_json"], None) if row else None
            if only_if_empty and row and current_value not in (None, {}, [], ""):
                return {"value": current_value, "revision": current_revision, "updated_at": int(row["updated_at"])}
            if base_revision and base_revision != current_revision:
                raise RevisionConflict(current_revision, current_value)
            revision = current_revision + 1
            connection.execute(
                """INSERT INTO app_settings(key,value_json,revision,updated_at) VALUES(?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,
                   revision=excluded.revision,updated_at=excluded.updated_at""",
                (key, _json(value), revision, now),
            )
        return {"value": value, "revision": revision, "updated_at": now}

    def next_revision(self, topic: str, entity_id: str = "global") -> int:
        key = f"_revision:{topic}:{entity_id}"
        with self.transaction(immediate=True) as connection:
            row = connection.execute("SELECT revision FROM app_settings WHERE key=?", (key,)).fetchone()
            revision = int(row["revision"] if row else 0) + 1
            connection.execute(
                """INSERT INTO app_settings(key,value_json,revision,updated_at) VALUES(?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,
                   revision=excluded.revision,updated_at=excluded.updated_at""",
                (key, _json({"topic": topic, "entity_id": entity_id}), revision, int(time.time() * 1000)),
            )
        return revision

    def save_secret_blob(self, key: str, encrypted_value: bytes) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT INTO secret_values(key,encrypted_value,updated_at) VALUES(?,?,?)
                   ON CONFLICT(key) DO UPDATE SET encrypted_value=excluded.encrypted_value,
                   updated_at=excluded.updated_at""",
                (key, sqlite3.Binary(encrypted_value), int(time.time() * 1000)),
            )

    def load_secret_blob(self, key: str) -> Optional[bytes]:
        with self.connect() as connection:
            row = connection.execute("SELECT encrypted_value FROM secret_values WHERE key=?", (key,)).fetchone()
        return bytes(row["encrypted_value"]) if row else None

    def list_secret_blobs(self) -> dict[str, bytes]:
        with self.connect() as connection:
            rows = connection.execute("SELECT key,encrypted_value FROM secret_values ORDER BY key").fetchall()
        return {str(row["key"]): bytes(row["encrypted_value"]) for row in rows}

    def delete_secret(self, key: str) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM secret_values WHERE key=?", (key,))

    def create_paired_device(self, device_id: str, name: str, token_hash: str, payload: dict[str, Any]) -> None:
        now = int(time.time() * 1000)
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT INTO paired_devices(id,name,token_hash,created_at,last_seen_at,revoked_at,payload_json)
                   VALUES(?,?,?,?,?,0,?)""",
                (device_id, name, token_hash, now, now, _json(payload or {})),
            )

    def paired_device_by_hash(self, token_hash: str) -> Optional[dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM paired_devices WHERE token_hash=? AND revoked_at=0", (token_hash,)
            ).fetchone()
        return self._paired_device_record(row) if row else None

    def paired_device(self, device_id: str) -> Optional[dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM paired_devices WHERE id=?", (device_id,)).fetchone()
        return self._paired_device_record(row) if row else None

    def list_paired_devices(self, include_revoked: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM paired_devices" if include_revoked else "SELECT * FROM paired_devices WHERE revoked_at=0"
        with self.connect() as connection:
            rows = connection.execute(query + " ORDER BY created_at DESC").fetchall()
        return [self._paired_device_record(row) for row in rows]

    def touch_paired_device(self, device_id: str, timestamp: Optional[int] = None) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute(
                "UPDATE paired_devices SET last_seen_at=? WHERE id=? AND revoked_at=0",
                (int(timestamp or time.time() * 1000), device_id),
            )

    def revoke_paired_device(self, device_id: str) -> bool:
        with self.transaction(immediate=True) as connection:
            cursor = connection.execute(
                "UPDATE paired_devices SET revoked_at=? WHERE id=? AND revoked_at=0",
                (int(time.time() * 1000), device_id),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _paired_device_record(row: sqlite3.Row) -> dict[str, Any]:
        payload = _payload(row["payload_json"], {})
        return {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "created_at": int(row["created_at"]),
            "last_seen_at": int(row["last_seen_at"]),
            "revoked_at": int(row["revoked_at"]),
            "client_type": str((payload or {}).get("client_type") or "browser"),
        }

    def load_providers(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM providers ORDER BY sort_order,id").fetchall()
        return [_payload(row["payload_json"], {}) for row in rows]

    def save_providers(self, providers: Iterable[dict[str, Any]]) -> None:
        now = int(time.time() * 1000)
        values = list(providers)
        with self.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM providers")
            for index, provider in enumerate(values):
                connection.execute(
                    "INSERT INTO providers(id,sort_order,enabled,payload_json,updated_at) VALUES(?,?,?,?,?)",
                    (str(provider.get("id") or f"provider-{index}"), index, int(provider.get("enabled", True)), _json(provider), now),
                )

    def load_projects(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM projects ORDER BY sort_order,updated_at").fetchall()
        return [_payload(row["payload_json"], {}) for row in rows]

    def save_projects(self, projects: Iterable[dict[str, Any]]) -> None:
        now = int(time.time() * 1000)
        values = list(projects)
        with self.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM projects")
            for index, project in enumerate(values):
                connection.execute(
                    "INSERT INTO projects(id,sort_order,payload_json,updated_at) VALUES(?,?,?,?)",
                    (str(project.get("id") or f"project-{index}"), int(project.get("order") or index), _json(project), now),
                )

    def save_canvas(self, canvas: dict[str, Any], touch: bool = True) -> dict[str, Any]:
        value = dict(canvas)
        now = int(time.time() * 1000)
        if touch:
            value["updated_at"] = now
        else:
            value["updated_at"] = int(value.get("updated_at") or now)
        summary = _canvas_summary(value)
        if not summary["created_at"]:
            summary["created_at"] = int(value.get("updated_at") or now)
        with self.transaction(immediate=True) as connection:
            row = connection.execute("SELECT revision FROM canvases WHERE id=?", (value["id"],)).fetchone()
            revision = int(row["revision"] if row else 0) + 1
            value["revision"] = revision
            connection.execute(
                """INSERT INTO canvases(id,project_id,kind,title,created_at,icon,owner,color,pinned,board_x,board_y,node_count,updated_at,deleted_at,revision,payload_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                   project_id=excluded.project_id,kind=excluded.kind,title=excluded.title,
                   created_at=excluded.created_at,icon=excluded.icon,owner=excluded.owner,color=excluded.color,
                   pinned=excluded.pinned,board_x=excluded.board_x,board_y=excluded.board_y,node_count=excluded.node_count,
                   updated_at=excluded.updated_at,deleted_at=excluded.deleted_at,
                   revision=excluded.revision,payload_json=excluded.payload_json""",
                (
                    value["id"], summary["project_id"], summary["kind"], summary["title"],
                    int(summary["created_at"]), summary["icon"], summary["owner"], summary["color"],
                    int(summary["pinned"]), summary["board_x"], summary["board_y"], int(summary["node_count"]),
                    int(value["updated_at"]), int(value.get("deleted_at") or 0),
                    revision, _json(value),
                ),
            )
        canvas.clear()
        canvas.update(value)
        return canvas

    def get_canvas(self, canvas_id: str) -> Optional[dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM canvases WHERE id=?", (canvas_id,)).fetchone()
        return _payload(row["payload_json"], None) if row else None

    def list_canvases(self, include_deleted: Optional[bool] = None) -> list[dict[str, Any]]:
        query = "SELECT payload_json FROM canvases"
        params: tuple[Any, ...] = ()
        if include_deleted is True:
            query += " WHERE deleted_at>0"
        elif include_deleted is False:
            query += " WHERE deleted_at=0"
        query += " ORDER BY updated_at DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_payload(row["payload_json"], {}) for row in rows]

    def list_canvas_records(self, include_deleted: Optional[bool] = None) -> list[dict[str, Any]]:
        query = """SELECT id,project_id,kind,title,created_at,icon,owner,color,pinned,board_x,board_y,
                          node_count,updated_at,deleted_at,revision
                   FROM canvases"""
        params: tuple[Any, ...] = ()
        if include_deleted is True:
            query += " WHERE deleted_at>0"
        elif include_deleted is False:
            query += " WHERE deleted_at=0"
        query += " ORDER BY pinned DESC, updated_at DESC, id DESC"
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        records = []
        for row in rows:
            records.append({
                "id": str(row["id"]),
                "title": str(row["title"] or ""),
                "icon": str(row["icon"] or ""),
                "kind": str(row["kind"] or "classic"),
                "owner": str(row["owner"] or ""),
                "color": str(row["color"] or ""),
                "pinned": bool(row["pinned"]),
                "project": str(row["project_id"] or "default"),
                "board_x": row["board_x"],
                "board_y": row["board_y"],
                "created_at": int(row["created_at"] or 0),
                "updated_at": int(row["updated_at"] or 0),
                "deleted_at": int(row["deleted_at"] or 0),
                "revision": int(row["revision"] or 0),
                "node_count": int(row["node_count"] or 0),
            })
        return records

    def canvas_project_counts(self) -> dict[str, int]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT project_id,COUNT(*) AS count FROM canvases WHERE deleted_at=0 GROUP BY project_id"
            ).fetchall()
        return {str(row["project_id"] or "default"): int(row["count"] or 0) for row in rows}

    def purge_canvas(self, canvas_id: str) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM canvases WHERE id=?", (canvas_id,))

    def reassign_project(self, project_id: str, target_project_id: str) -> int:
        moved = 0
        for canvas in self.list_canvases(include_deleted=None):
            if str(canvas.get("project") or "") == project_id:
                canvas["project"] = target_project_id
                self.save_canvas(canvas, touch=False)
                moved += 1
        return moved

    def save_conversation(self, user_id: str, conversation: dict[str, Any]) -> None:
        now = int(conversation.get("updated_at") or time.time() * 1000)
        with self.transaction(immediate=True) as connection:
            row = connection.execute(
                "SELECT revision FROM conversations WHERE user_id=? AND id=?", (user_id, conversation["id"])
            ).fetchone()
            revision = int(row["revision"] if row else 0) + 1
            connection.execute(
                """INSERT INTO conversations(id,user_id,title,updated_at,revision,payload_json) VALUES(?,?,?,?,?,?)
                   ON CONFLICT(user_id,id) DO UPDATE SET title=excluded.title,updated_at=excluded.updated_at,
                   revision=excluded.revision,payload_json=excluded.payload_json""",
                (conversation["id"], user_id, str(conversation.get("title") or ""), now, revision, _json(conversation)),
            )

    def get_conversation(self, user_id: str, conversation_id: str) -> Optional[dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM conversations WHERE user_id=? AND id=?", (user_id, conversation_id)
            ).fetchone()
        return _payload(row["payload_json"], None) if row else None

    def list_conversations(self, user_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM conversations WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
            ).fetchall()
        return [_payload(row["payload_json"], {}) for row in rows]

    def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        with self.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM conversations WHERE user_id=? AND id=?", (user_id, conversation_id))

    def prepend_history(self, record: dict[str, Any], limit: int = 5000) -> None:
        timestamp = float(record.get("timestamp") or time.time())
        record["timestamp"] = timestamp
        history_id = str(record.get("id") or f"{timestamp:.6f}-{abs(hash(_json(record))) & 0xFFFFFFFF:08x}")
        record["id"] = history_id
        index = _history_index(record)
        work_rows = _work_rows_from_history(record, history_id)
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT OR REPLACE INTO generation_history(
                       id,kind,created_at,prompt,model,operation,provider_id,first_url,image_count,search_text,payload_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    history_id, index["kind"], index["created_at"], index["prompt"], index["model"],
                    index["operation"], index["provider_id"], index["first_url"], index["image_count"],
                    index["search_text"], _json(record),
                ),
            )
            connection.execute("DELETE FROM work_items WHERE history_id=?", (history_id,))
            self._insert_work_rows(connection, work_rows)
            connection.execute(
                "DELETE FROM generation_history WHERE id IN (SELECT id FROM generation_history ORDER BY created_at DESC LIMIT -1 OFFSET ?)",
                (limit,),
            )
            connection.execute("DELETE FROM work_items WHERE history_id NOT IN (SELECT id FROM generation_history)")

    def list_history(self, kind: str = "", limit: int = 0, cursor: str = "") -> list[dict[str, Any]]:
        query = "SELECT id,payload_json FROM generation_history"
        filters = []
        params: list[Any] = []
        if kind:
            filters.append("kind=?")
            params.append(kind)
        cursor_created, cursor_id = self._decode_cursor(cursor)
        if cursor_created is not None and cursor_id:
            filters.append("(created_at<? OR (created_at=? AND id<?))")
            params.extend([cursor_created, cursor_created, cursor_id])
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY created_at DESC"
        if limit:
            query += " LIMIT ?"
            params.append(max(1, int(limit)))
        with self.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        records = []
        for row in rows:
            payload = _payload(row["payload_json"], {})
            if not isinstance(payload, dict):
                payload = {}
            payload.setdefault("_history_id", str(row["id"]))
            records.append(payload)
        return records

    def list_history_page(self, kind: str = "", limit: int = 100, cursor: str = "") -> dict[str, Any]:
        safe_limit = max(1, min(1000, int(limit or 100)))
        records = self.list_history(kind, safe_limit + 1, cursor)
        next_cursor = ""
        if len(records) > safe_limit:
            last = records[safe_limit - 1]
            next_cursor = self._encode_cursor(float(last.get("timestamp") or last.get("created_at") or 0), str(last.get("_history_id") or last.get("id") or ""))
            records = records[:safe_limit]
        return {"items": records, "next_cursor": next_cursor}

    def delete_history_timestamp(self, timestamp: float) -> Optional[dict[str, Any]]:
        with self.transaction(immediate=True) as connection:
            row = connection.execute(
                "SELECT id,payload_json FROM generation_history WHERE ABS(created_at-?)<0.001 ORDER BY created_at DESC LIMIT 1",
                (float(timestamp),),
            ).fetchone()
            if row:
                item = _payload(row["payload_json"], {})
                connection.execute("DELETE FROM generation_history WHERE id=?", (row["id"],))
                connection.execute("DELETE FROM work_items WHERE history_id=?", (row["id"],))
                return item
        return None

    def delete_history_ids(self, history_ids: Iterable[str]) -> list[dict[str, Any]]:
        clean_ids: list[str] = []
        seen: set[str] = set()
        for value in history_ids or []:
            history_id = str(value or "").strip()
            if not history_id or history_id in seen:
                continue
            seen.add(history_id)
            clean_ids.append(history_id)
        if not clean_ids:
            return []
        placeholders = ",".join("?" for _ in clean_ids)
        with self.transaction(immediate=True) as connection:
            rows = connection.execute(
                f"SELECT id,payload_json FROM generation_history WHERE id IN ({placeholders})",
                tuple(clean_ids),
            ).fetchall()
            connection.execute(
                f"DELETE FROM generation_history WHERE id IN ({placeholders})",
                tuple(clean_ids),
            )
            connection.execute(
                f"DELETE FROM work_items WHERE history_id IN ({placeholders})",
                tuple(clean_ids),
            )
        records = []
        for row in rows:
            payload = _payload(row["payload_json"], {})
            if not isinstance(payload, dict):
                payload = {}
            payload.setdefault("_history_id", str(row["id"]))
            records.append(payload)
        return records

    @staticmethod
    def _encode_cursor(created_at: float, item_id: str) -> str:
        if not item_id:
            return ""
        return f"{float(created_at):.6f}|{item_id}"

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[Optional[float], str]:
        text = str(cursor or "").split("#", 1)[0].strip()
        if not text or "|" not in text:
            return None, ""
        left, right = text.split("|", 1)
        try:
            return float(left), right.strip()
        except ValueError:
            return None, ""

    def _insert_work_rows(self, connection: sqlite3.Connection, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        for row in rows:
            connection.execute(
                """INSERT OR REPLACE INTO work_items(
                       id,history_id,output_index,url,kind,operation,created_at,prompt,provider_id,provider_name,
                       model,width,height,task_id,source_url,original_name,name,favorite,favorite_updated_at,
                       trashed,trashed_at,metadata_updated_at,search_text,references_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["id"], row["history_id"], int(row["output_index"]), row["url"], row["kind"],
                    row["operation"], float(row["created_at"]), row["prompt"], row["provider_id"],
                    row["provider_name"], row["model"], int(row["width"]), int(row["height"]),
                    row["task_id"], row["source_url"], row["original_name"], row["name"],
                    int(row.get("favorite") or 0), float(row.get("favorite_updated_at") or 0),
                    int(row.get("trashed") or 0), float(row.get("trashed_at") or 0),
                    float(row.get("metadata_updated_at") or 0), row["search_text"], row["references_json"],
                ),
            )

    def rebuild_work_items(self, metadata: Optional[dict[str, dict[str, Any]]] = None) -> int:
        metadata = metadata if isinstance(metadata, dict) else {}
        with self.transaction(immediate=True) as connection:
            rows = connection.execute("SELECT id,payload_json FROM generation_history ORDER BY created_at DESC").fetchall()
            connection.execute("DELETE FROM work_items")
            count = 0
            for row in rows:
                payload = _payload(row["payload_json"], {})
                if not isinstance(payload, dict):
                    continue
                payload.setdefault("_history_id", str(row["id"]))
                work_rows = _work_rows_from_history(payload, str(row["id"]))
                for work in work_rows:
                    saved = metadata.get(work["id"]) if isinstance(metadata.get(work["id"]), dict) else {}
                    if saved:
                        custom_name = _text(saved.get("name"), 160)
                        if custom_name:
                            work["name"] = custom_name
                        work["favorite"] = 1 if saved.get("favorite") else 0
                        work["favorite_updated_at"] = _number(saved.get("favorite_updated_at") or saved.get("updated_at"))
                        work["trashed"] = 1 if saved.get("trashed") else 0
                        work["trashed_at"] = _number(saved.get("trashed_at"))
                        work["metadata_updated_at"] = _number(saved.get("updated_at"))
                        work["search_text"] = " ".join([work["search_text"], custom_name]).lower()[:4000]
                self._insert_work_rows(connection, work_rows)
                count += len(work_rows)
        return count

    def ensure_work_items_indexed(self, metadata: Optional[dict[str, dict[str, Any]]] = None) -> int:
        with self.connect() as connection:
            history_count = int(connection.execute("SELECT COUNT(*) FROM generation_history").fetchone()[0])
            work_count = int(connection.execute("SELECT COUNT(*) FROM work_items").fetchone()[0])
        if history_count and not work_count:
            return self.rebuild_work_items(metadata)
        return work_count

    def list_work_items(
        self,
        *,
        favorite: Optional[bool] = None,
        kind: str = "",
        search: str = "",
        limit: int = 500,
        cursor: str = "",
        include_trashed: bool = False,
    ) -> dict[str, Any]:
        safe_limit = max(1, min(1000, int(limit or 500)))
        filters: list[str] = []
        params: list[Any] = []
        if not include_trashed:
            filters.append("work_items.trashed=0")
        normalized_kind = _text(kind, 80).lower()
        if normalized_kind:
            filters.append("LOWER(work_items.kind)=?")
            params.append(normalized_kind)
        if favorite is not None:
            filters.append("work_items.favorite=?")
            params.append(1 if favorite else 0)
        normalized_search = _text(search, 300).lower()
        total_filters = list(filters)
        total_params = list(params)
        cursor_created, cursor_id = self._decode_cursor(cursor)
        if cursor_created is not None and cursor_id:
            filters.append("(work_items.created_at<? OR (work_items.created_at=? AND work_items.id<?))")
            params.extend([cursor_created, cursor_created, cursor_id])
        with self.connect() as connection:
            fts_query = self._work_items_fts_query(normalized_search)
            use_fts = bool(fts_query and self._has_work_items_fts(connection))
            search_filter = ""
            search_params: list[Any] = []
            source = "work_items"
            if normalized_search:
                if use_fts:
                    source = "work_items JOIN work_items_fts ON work_items_fts.id=work_items.id"
                    search_filter = "work_items_fts MATCH ?"
                    search_params.append(fts_query)
                else:
                    search_filter = "work_items.search_text LIKE ?"
                    search_params.append(f"%{normalized_search}%")
            if search_filter:
                filters.append(search_filter)
                params.extend(search_params)
                total_filters.append(search_filter)
                total_params.extend(search_params)
            where = (" WHERE " + " AND ".join(filters)) if filters else ""
            total_where = (" WHERE " + " AND ".join(total_filters)) if total_filters else ""
            query = (
                "SELECT work_items.* FROM "
                + source
                + where
                + " ORDER BY work_items.created_at DESC,work_items.id DESC LIMIT ?"
            )
            count_query = "SELECT COUNT(*) FROM " + source + total_where
            total = int(connection.execute(count_query, tuple(total_params)).fetchone()[0])
            rows = connection.execute(query, tuple([*params, safe_limit + 1])).fetchall()
        items = [self._work_item_from_row(row) for row in rows[:safe_limit]]
        next_cursor = ""
        if len(rows) > safe_limit and items:
            last = items[-1]
            next_cursor = self._encode_cursor(float(last.get("created_at") or 0), str(last.get("id") or ""))
        return {"items": items, "total": total, "next_cursor": next_cursor}

    def get_work_item(self, work_id: str) -> Optional[dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM work_items WHERE id=?", (str(work_id or ""),)).fetchone()
        return self._work_item_from_row(row) if row else None

    def update_work_item_metadata(self, work_id: str, metadata: dict[str, Any]) -> Optional[dict[str, Any]]:
        work_id = str(work_id or "").strip()
        if not work_id:
            return None
        with self.transaction(immediate=True) as connection:
            row = connection.execute("SELECT * FROM work_items WHERE id=?", (work_id,)).fetchone()
            if not row:
                return None
            current = self._work_item_from_row(row)
            custom_name = _text(metadata.get("name"), 160)
            name = custom_name or str(current.get("original_name") or current.get("name") or "")
            favorite = 1 if metadata.get("favorite") else 0
            trashed = 1 if metadata.get("trashed") else 0
            favorite_updated_at = _number(metadata.get("favorite_updated_at") or metadata.get("updated_at"))
            trashed_at = _number(metadata.get("trashed_at"))
            metadata_updated_at = _number(metadata.get("updated_at"))
            search_text = " ".join([
                name, str(current.get("original_name") or ""), str(current.get("prompt") or ""),
                str(current.get("model") or ""), str(current.get("operation") or ""), str(current.get("url") or ""),
            ]).lower()[:4000]
            connection.execute(
                """UPDATE work_items SET name=?,favorite=?,favorite_updated_at=?,trashed=?,trashed_at=?,
                       metadata_updated_at=?,search_text=? WHERE id=?""",
                (name, favorite, favorite_updated_at, trashed, trashed_at, metadata_updated_at, search_text, work_id),
            )
        return self.get_work_item(work_id)

    @staticmethod
    def _work_item_from_row(row: sqlite3.Row) -> dict[str, Any]:
        references = _payload(row["references_json"], [])
        return {
            "id": str(row["id"]),
            "history_id": str(row["history_id"]),
            "output_index": int(row["output_index"] or 0),
            "url": str(row["url"] or ""),
            "kind": str(row["kind"] or "image"),
            "operation": str(row["operation"] or ""),
            "created_at": float(row["created_at"] or 0),
            "prompt": str(row["prompt"] or ""),
            "provider_id": str(row["provider_id"] or ""),
            "provider_name": str(row["provider_name"] or ""),
            "model": str(row["model"] or ""),
            "width": int(row["width"] or 0),
            "height": int(row["height"] or 0),
            "task_id": str(row["task_id"] or ""),
            "source_url": str(row["source_url"] or ""),
            "original_name": str(row["original_name"] or ""),
            "name": str(row["name"] or ""),
            "favorite": bool(row["favorite"]),
            "favorite_updated_at": float(row["favorite_updated_at"] or 0),
            "trashed": bool(row["trashed"]),
            "trashed_at": float(row["trashed_at"] or 0),
            "metadata_updated_at": float(row["metadata_updated_at"] or 0),
            "references": references if isinstance(references, list) else [],
        }

    def upsert_local_asset_item(self, item: dict[str, Any]) -> None:
        item_id = str(item.get("id") or item.get("file") or "").strip()
        if not item_id:
            return
        payload = dict(item)
        folder = str(payload.get("folder") or "").strip().replace("\\", "/")
        search_text = " ".join([
            str(payload.get("name") or ""),
            str(payload.get("file") or ""),
            str(payload.get("kind") or ""),
            str(payload.get("caption") or ""),
        ]).lower()[:4000]
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT OR REPLACE INTO local_asset_items(
                       id,file,folder,name,url,kind,size,created_at,updated_at,search_text,payload_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    item_id,
                    str(payload.get("file") or item_id),
                    folder,
                    str(payload.get("name") or ""),
                    str(payload.get("url") or ""),
                    str(payload.get("kind") or ""),
                    int(payload.get("size") or 0),
                    float(payload.get("created_at") or 0),
                    float(payload.get("updated_at") or payload.get("created_at") or 0),
                    search_text,
                    _json(payload),
                ),
            )

    def replace_local_asset_index(self, items: Iterable[dict[str, Any]]) -> int:
        values = [dict(item) for item in items if isinstance(item, dict)]
        with self.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM local_asset_items")
            for item in values:
                item_id = str(item.get("id") or item.get("file") or "").strip()
                if not item_id:
                    continue
                folder = str(item.get("folder") or "").strip().replace("\\", "/")
                search_text = " ".join([
                    str(item.get("name") or ""),
                    str(item.get("file") or ""),
                    str(item.get("kind") or ""),
                    str(item.get("caption") or ""),
                ]).lower()[:4000]
                connection.execute(
                    """INSERT OR REPLACE INTO local_asset_items(
                           id,file,folder,name,url,kind,size,created_at,updated_at,search_text,payload_json
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        item_id,
                        str(item.get("file") or item_id),
                        folder,
                        str(item.get("name") or ""),
                        str(item.get("url") or ""),
                        str(item.get("kind") or ""),
                        int(item.get("size") or 0),
                        float(item.get("created_at") or 0),
                        float(item.get("updated_at") or item.get("created_at") or 0),
                        search_text,
                        _json(item),
                    ),
                )
        return len(values)

    def delete_local_asset_items(self, ids: Iterable[str]) -> int:
        clean = [str(item or "").strip() for item in ids if str(item or "").strip()]
        if not clean:
            return 0
        placeholders = ",".join("?" for _ in clean)
        with self.transaction(immediate=True) as connection:
            cursor = connection.execute(f"DELETE FROM local_asset_items WHERE id IN ({placeholders})", tuple(clean))
            return int(cursor.rowcount or 0)

    def local_asset_count(self) -> int:
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM local_asset_items").fetchone()[0])

    def list_local_asset_items(self, *, folder: str = "", search: str = "", limit: int = 500, cursor: str = "") -> dict[str, Any]:
        safe_limit = max(1, min(1000, int(limit or 500)))
        filters: list[str] = []
        params: list[Any] = []
        folder = str(folder or "").strip().replace("\\", "/")
        if folder:
            filters.append("folder=?")
            params.append(folder)
        search = str(search or "").strip().lower()[:300]
        if search:
            filters.append("search_text LIKE ?")
            params.append(f"%{search}%")
        total_filters = list(filters)
        total_params = list(params)
        cursor_created, cursor_id = self._decode_cursor(cursor)
        if cursor_created is not None and cursor_id:
            filters.append("(created_at<? OR (created_at=? AND id<?))")
            params.extend([cursor_created, cursor_created, cursor_id])
        where = (" WHERE " + " AND ".join(filters)) if filters else ""
        count_where = (" WHERE " + " AND ".join(total_filters)) if total_filters else ""
        count_params = tuple(total_params)
        query = "SELECT payload_json,created_at,id FROM local_asset_items" + where + " ORDER BY created_at DESC,id DESC LIMIT ?"
        with self.connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM local_asset_items" + count_where, count_params).fetchone()[0])
            rows = connection.execute(query, tuple([*params, safe_limit + 1])).fetchall()
        items = []
        for row in rows[:safe_limit]:
            payload = _payload(row["payload_json"], {})
            if isinstance(payload, dict):
                items.append(payload)
        next_cursor = ""
        if len(rows) > safe_limit and items:
            last_row = rows[safe_limit - 1]
            next_cursor = self._encode_cursor(float(last_row["created_at"] or 0), str(last_row["id"] or ""))
        return {"items": items, "total": total, "next_cursor": next_cursor}

    def local_asset_folders(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT folder,COUNT(*) AS count FROM local_asset_items GROUP BY folder").fetchall()
        return [{"folder": str(row["folder"] or ""), "count": int(row["count"] or 0)} for row in rows]

    def upsert_media_object(self, *, url: str, path: str, category: str, kind: str = "", source: str = "", ref_count: int = 0, metadata: Optional[dict[str, Any]] = None) -> None:
        url = str(url or "").strip()
        path = str(path or "").strip()
        if not url or not path:
            return
        now = time.time()
        size = 0
        created_at = now
        try:
            stat = Path(path).stat()
            size = int(stat.st_size)
            created_at = float(stat.st_mtime or now)
        except OSError:
            pass
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT INTO media_objects(url,path,category,kind,size,created_at,last_seen_at,ref_count,source,metadata_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(url) DO UPDATE SET
                   path=excluded.path,category=excluded.category,kind=excluded.kind,size=excluded.size,
                   last_seen_at=excluded.last_seen_at,ref_count=MAX(media_objects.ref_count, excluded.ref_count),
                   source=excluded.source,metadata_json=excluded.metadata_json""",
                (
                    url, path, str(category or ""), str(kind or ""), size, created_at, now,
                    max(0, int(ref_count or 0)), str(source or ""), _json(metadata or {}),
                ),
            )

    def media_storage_summary(self) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT category,COUNT(*) AS count,COALESCE(SUM(size),0) AS bytes FROM media_objects GROUP BY category"
            ).fetchall()
            orphan_rows = connection.execute(
                "SELECT category,COUNT(*) AS count,COALESCE(SUM(size),0) AS bytes FROM media_objects WHERE ref_count<=0 GROUP BY category"
            ).fetchall()
        categories = {str(row["category"] or "unknown"): {"count": int(row["count"] or 0), "bytes": int(row["bytes"] or 0)} for row in rows}
        orphaned = {str(row["category"] or "unknown"): {"count": int(row["count"] or 0), "bytes": int(row["bytes"] or 0)} for row in orphan_rows}
        return {
            "categories": categories,
            "orphaned": orphaned,
            "total_count": sum(item["count"] for item in categories.values()),
            "total_bytes": sum(item["bytes"] for item in categories.values()),
        }

    def replace_media_object_index(self, objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
        values = [dict(item) for item in objects if isinstance(item, dict) and str(item.get("url") or "").strip()]
        now = time.time()
        with self.transaction(immediate=True) as connection:
            connection.execute("UPDATE media_objects SET ref_count=0")
            for item in values:
                path = str(item.get("path") or "").strip()
                size = 0
                created_at = now
                try:
                    stat = Path(path).stat()
                    size = int(stat.st_size)
                    created_at = float(stat.st_mtime or now)
                except OSError:
                    pass
                connection.execute(
                    """INSERT INTO media_objects(url,path,category,kind,size,created_at,last_seen_at,ref_count,source,metadata_json)
                       VALUES(?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(url) DO UPDATE SET
                       path=excluded.path,category=excluded.category,kind=excluded.kind,size=excluded.size,
                       created_at=excluded.created_at,last_seen_at=excluded.last_seen_at,
                       ref_count=excluded.ref_count,source=excluded.source,metadata_json=excluded.metadata_json""",
                    (
                        str(item.get("url") or "").strip(),
                        path,
                        str(item.get("category") or ""),
                        str(item.get("kind") or ""),
                        size,
                        created_at,
                        now,
                        max(0, int(item.get("ref_count") or 0)),
                        str(item.get("source") or "scan"),
                        _json(item.get("metadata") if isinstance(item.get("metadata"), dict) else {}),
                    ),
                )
        return self.media_storage_summary()

    def list_orphan_media_objects(
        self,
        *,
        categories: Iterable[str] = ("input", "output"),
        grace_seconds: int = 7 * 24 * 60 * 60,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        clean_categories = [str(item or "").strip() for item in categories if str(item or "").strip()]
        if not clean_categories:
            return []
        placeholders = ",".join("?" for _ in clean_categories)
        cutoff = time.time() - max(0, int(grace_seconds or 0))
        safe_limit = max(1, min(5000, int(limit or 500)))
        with self.connect() as connection:
            rows = connection.execute(
                f"""SELECT url,path,category,kind,size,created_at,last_seen_at,ref_count,source,metadata_json
                    FROM media_objects
                    WHERE category IN ({placeholders}) AND ref_count<=0 AND path<>'' AND created_at<=?
                    ORDER BY created_at ASC,url ASC LIMIT ?""",
                tuple([*clean_categories, cutoff, safe_limit]),
            ).fetchall()
        return [
            {
                "url": str(row["url"] or ""),
                "path": str(row["path"] or ""),
                "category": str(row["category"] or ""),
                "kind": str(row["kind"] or ""),
                "size": int(row["size"] or 0),
                "created_at": float(row["created_at"] or 0),
                "last_seen_at": float(row["last_seen_at"] or 0),
                "ref_count": int(row["ref_count"] or 0),
                "source": str(row["source"] or ""),
                "metadata": _payload(row["metadata_json"], {}),
            }
            for row in rows
        ]

    def delete_media_objects(self, urls: Iterable[str]) -> int:
        clean = [str(item or "").strip() for item in urls if str(item or "").strip()]
        if not clean:
            return 0
        placeholders = ",".join("?" for _ in clean)
        with self.transaction(immediate=True) as connection:
            cursor = connection.execute(f"DELETE FROM media_objects WHERE url IN ({placeholders})", tuple(clean))
            return int(cursor.rowcount or 0)

    def get_library(self, kind: str, default: Any = None) -> Any:
        with self.connect() as connection:
            row = connection.execute("SELECT payload_json FROM library_documents WHERE kind=?", (kind,)).fetchone()
        return _payload(row["payload_json"], default) if row else default

    def save_library(self, kind: str, value: Any) -> int:
        now = int(time.time() * 1000)
        with self.transaction(immediate=True) as connection:
            row = connection.execute("SELECT revision FROM library_documents WHERE kind=?", (kind,)).fetchone()
            revision = int(row["revision"] if row else 0) + 1
            connection.execute(
                """INSERT INTO library_documents(kind,payload_json,revision,updated_at) VALUES(?,?,?,?)
                   ON CONFLICT(kind) DO UPDATE SET payload_json=excluded.payload_json,
                   revision=excluded.revision,updated_at=excluded.updated_at""",
                (kind, _json(value), revision, now),
            )
        return revision

    def save_tasks(self, kind: str, tasks: Iterable[dict[str, Any]]) -> None:
        values = list(tasks)
        with self.transaction(immediate=True) as connection:
            connection.execute("DELETE FROM tasks WHERE kind=?", (kind,))
            for task in values:
                task_id = str(task.get("id") or task.get("task_id") or "")
                if not task_id:
                    continue
                connection.execute(
                    "INSERT INTO tasks(id,kind,status,updated_at,payload_json) VALUES(?,?,?,?,?)",
                    (task_id, kind, str(task.get("status") or ""), float(task.get("updated_at") or time.time()), _json(task)),
                )

    def upsert_task(self, kind: str, task: dict[str, Any]) -> None:
        task_id = str(task.get("id") or task.get("task_id") or "")
        if not task_id:
            return
        updated_at = task.get("updated_at")
        if updated_at is None:
            updated_at = time.time()
        with self.transaction(immediate=True) as connection:
            connection.execute(
                """INSERT INTO tasks(id,kind,status,updated_at,payload_json) VALUES(?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,status=excluded.status,
                   updated_at=excluded.updated_at,payload_json=excluded.payload_json""",
                (task_id, kind, str(task.get("status") or ""), float(updated_at), _json(task)),
            )

    def delete_task(self, kind: str, task_id: str) -> bool:
        task_id = str(task_id or "")
        if not task_id:
            return False
        with self.transaction(immediate=True) as connection:
            cursor = connection.execute("DELETE FROM tasks WHERE kind=? AND id=?", (kind, task_id))
            return cursor.rowcount > 0

    def prune_tasks(self, kind: str, keep: int = 5000) -> int:
        safe_keep = max(1, int(keep or 1))
        with self.transaction(immediate=True) as connection:
            before = int(connection.execute("SELECT COUNT(*) FROM tasks WHERE kind=?", (kind,)).fetchone()[0])
            connection.execute(
                """DELETE FROM tasks WHERE kind=? AND id NOT IN (
                       SELECT id FROM tasks WHERE kind=? ORDER BY updated_at DESC LIMIT ?
                   )""",
                (kind, kind, safe_keep),
            )
        return max(0, before - safe_keep)

    def load_tasks(self, kind: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM tasks WHERE kind=? ORDER BY updated_at DESC", (kind,)).fetchall()
        return [_payload(row["payload_json"], {}) for row in rows]

    def counts(self) -> dict[str, int]:
        tables = ("providers", "projects", "canvases", "conversations", "generation_history", "tasks", "library_documents")
        with self.connect() as connection:
            return {table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}

    def import_legacy(self, snapshot: dict[str, Any]) -> None:
        with self.transaction(immediate=True) as connection:
            now = int(time.time() * 1000)
            if not connection.execute("SELECT 1 FROM providers LIMIT 1").fetchone():
                for index, provider in enumerate(snapshot.get("providers") or []):
                    if isinstance(provider, dict) and provider.get("id"):
                        connection.execute(
                            "INSERT OR IGNORE INTO providers(id,sort_order,enabled,payload_json,updated_at) VALUES(?,?,?,?,?)",
                            (provider["id"], index, int(provider.get("enabled", True)), _json(provider), now),
                        )
            if not connection.execute("SELECT 1 FROM projects LIMIT 1").fetchone():
                for index, project in enumerate(snapshot.get("projects") or []):
                    if isinstance(project, dict) and project.get("id"):
                        connection.execute(
                            "INSERT OR IGNORE INTO projects(id,sort_order,payload_json,updated_at) VALUES(?,?,?,?)",
                            (project["id"], int(project.get("order") or index), _json(project), now),
                        )
            if not connection.execute("SELECT 1 FROM canvases LIMIT 1").fetchone():
                for canvas in snapshot.get("canvases") or []:
                    if not isinstance(canvas, dict) or not canvas.get("id"):
                        continue
                    canvas.setdefault("revision", 1)
                    connection.execute(
                        "INSERT OR IGNORE INTO canvases(id,project_id,kind,title,updated_at,deleted_at,revision,payload_json) VALUES(?,?,?,?,?,?,?,?)",
                        (canvas["id"], str(canvas.get("project") or "default"), str(canvas.get("kind") or "classic"),
                         str(canvas.get("title") or ""), int(canvas.get("updated_at") or now), int(canvas.get("deleted_at") or 0),
                         int(canvas.get("revision") or 1), _json(canvas)),
                    )
            if not connection.execute("SELECT 1 FROM conversations LIMIT 1").fetchone():
                for user_id, conversation in snapshot.get("conversations") or []:
                    if isinstance(conversation, dict) and conversation.get("id"):
                        connection.execute(
                            "INSERT OR IGNORE INTO conversations(id,user_id,title,updated_at,payload_json) VALUES(?,?,?,?,?)",
                            (conversation["id"], user_id, str(conversation.get("title") or ""), int(conversation.get("updated_at") or now), _json(conversation)),
                        )
            if not connection.execute("SELECT 1 FROM generation_history LIMIT 1").fetchone():
                for index, record in enumerate(snapshot.get("history") or []):
                    if not isinstance(record, dict):
                        continue
                    created = float(record.get("timestamp") or (time.time() - index / 1000))
                    history_id = f"legacy-{index}-{created:.6f}"
                    connection.execute(
                        "INSERT OR IGNORE INTO generation_history(id,kind,created_at,payload_json) VALUES(?,?,?,?)",
                        (history_id, str(record.get("type") or "zimage"), created, _json(record)),
                    )
            libraries = snapshot.get("libraries") or {}
            for kind, value in libraries.items():
                if value is not None:
                    connection.execute(
                        "INSERT OR IGNORE INTO library_documents(kind,payload_json,updated_at) VALUES(?,?,?)",
                        (kind, _json(value), now),
                    )
            if not connection.execute("SELECT 1 FROM tasks LIMIT 1").fetchone():
                for task in snapshot.get("online_image_tasks") or []:
                    if not isinstance(task, dict):
                        continue
                    task_id = str(task.get("id") or task.get("task_id") or "")
                    if task_id:
                        connection.execute(
                            "INSERT OR IGNORE INTO tasks(id,kind,status,updated_at,payload_json) VALUES(?,?,?,?,?)",
                            (task_id, "online_image", str(task.get("status") or ""), float(task.get("updated_at") or time.time()), _json(task)),
                        )
