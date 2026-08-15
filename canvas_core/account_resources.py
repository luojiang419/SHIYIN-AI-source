from __future__ import annotations

import heapq
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .account_storage import AccountStorageRegistry
from .accounts import AccountStore


RESOURCE_SCOPE_ATTRIBUTES = {
    "generated": "media_generated",
    "exports": "exports",
    "uploads": "media_uploads",
    "library": "media_library",
    "inputs": "media_input",
}


class AccountResourceService:
    def __init__(self, account_store: AccountStore, storage: AccountStorageRegistry) -> None:
        self.account_store = account_store
        self.storage = storage

    def _identity_record(self, account_id: str) -> dict[str, object]:
        record = self.account_store.account_by_id(str(account_id or ""))
        if not record:
            raise KeyError("账号不存在")
        return record

    def scope_root(self, account_id: str, scope: str) -> Path:
        self._identity_record(account_id)
        attribute = RESOURCE_SCOPE_ATTRIBUTES.get(str(scope or "").strip().lower())
        if not attribute:
            raise KeyError("资源分类不存在")
        return Path(getattr(self.storage.layout_for(account_id), attribute)).resolve()

    def resolve_file(self, account_id: str, scope: str, relative_path: str) -> Path:
        root = self.scope_root(account_id, scope)
        candidate = (root / str(relative_path or "")).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PermissionError("资源路径越界") from exc
        if not candidate.is_file() or candidate.is_symlink():
            raise FileNotFoundError("资源不存在")
        return candidate

    def list_resources(self, account_id: str, scope: str = "", limit: int = 300) -> dict[str, Any]:
        record = self._identity_record(account_id)
        safe_limit = max(1, min(1000, int(limit or 300)))
        selected_scope = str(scope or "").strip().lower()
        scopes = [selected_scope] if selected_scope else list(RESOURCE_SCOPE_ATTRIBUTES)
        for item in scopes:
            if item not in RESOURCE_SCOPE_ATTRIBUTES:
                raise KeyError("资源分类不存在")

        newest: list[tuple[int, int, dict[str, Any]]] = []
        sequence = 0
        total_files = 0
        total_bytes = 0
        layout = self.storage.layout_for(account_id)
        for scope_name in scopes:
            root = Path(getattr(layout, RESOURCE_SCOPE_ATTRIBUTES[scope_name])).resolve()
            if not root.is_dir():
                continue
            for directory, directory_names, file_names in os.walk(root, followlinks=False):
                directory_names[:] = [
                    name for name in directory_names
                    if not (Path(directory) / name).is_symlink()
                ]
                for file_name in file_names:
                    path = Path(directory) / file_name
                    if path.is_symlink():
                        continue
                    try:
                        resolved = path.resolve()
                        relative = resolved.relative_to(root).as_posix()
                        stat = resolved.stat()
                    except (OSError, ValueError):
                        continue
                    total_files += 1
                    total_bytes += int(stat.st_size)
                    sequence += 1
                    mime = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
                    item = {
                        "scope": scope_name,
                        "name": resolved.name,
                        "relative_path": relative,
                        "size": int(stat.st_size),
                        "modified_at": int(stat.st_mtime * 1000),
                        "mime": mime,
                        "kind": mime.split("/", 1)[0] if "/" in mime else "file",
                        "url": (
                            f"/api/admin/accounts/{quote(str(account_id), safe='')}/resource-file/"
                            f"{quote(scope_name, safe='')}/{quote(relative, safe='/')}"
                        ),
                    }
                    entry = (item["modified_at"], sequence, item)
                    if len(newest) < safe_limit:
                        heapq.heappush(newest, entry)
                    elif entry[:2] > newest[0][:2]:
                        heapq.heapreplace(newest, entry)

        database = self.storage.database_for(account_id)
        projects = database.load_projects()
        canvases = database.list_canvas_records(include_deleted=False)
        work_page = database.list_work_items(limit=min(safe_limit, 500), include_trashed=False)
        files = [entry[2] for entry in sorted(newest, reverse=True)]
        return {
            "account": {
                "id": str(record["id"]),
                "account": str(record["account"]),
                "disabled": bool(record["disabled"]),
            },
            "summary": {
                "file_count": total_files,
                "total_bytes": total_bytes,
                "project_count": len(projects),
                "canvas_count": len(canvases),
                "work_count": int(work_page.get("total") or 0),
            },
            "files": files,
            "projects": projects,
            "canvases": canvases,
            "works": work_page.get("items") or [],
            "scopes": list(RESOURCE_SCOPE_ATTRIBUTES),
        }
