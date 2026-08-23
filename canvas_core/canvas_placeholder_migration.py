from __future__ import annotations

import time
from typing import Any


ORPHAN_OUTPUT_PENDING_MIGRATION_SETTING = "canvas_orphan_output_pending_cleanup_v1"
RECOVERABLE_TASK_FIELDS = ("canvasTaskId", "recoverTaskId")


def has_recoverable_output_task(item: Any) -> bool:
    """Return whether a saved output placeholder still has a task to resume/query."""
    return isinstance(item, dict) and any(str(item.get(field) or "").strip() for field in RECOVERABLE_TASK_FIELDS)


def prune_orphan_output_pending(canvas: dict[str, Any]) -> int:
    """Remove only classic output placeholders that cannot ever be resumed.

    This mirrors the client-side load cleanup.  A placeholder that lacks both a
    local canvas task id and a recoverable upstream id cannot receive a result
    after an application restart, so keeping it only leaves a permanent spinner.
    """
    nodes = canvas.get("nodes")
    if not isinstance(nodes, list):
        return 0

    removed = 0
    for node in nodes:
        if not isinstance(node, dict) or node.get("type") != "output":
            continue
        pending = node.get("_pending")
        if not isinstance(pending, list):
            continue
        retained = [item for item in pending if has_recoverable_output_task(item)]
        removed += len(pending) - len(retained)
        if len(retained) != len(pending):
            node["_pending"] = retained
    return removed


def migrate_orphan_output_pending_once(database: Any, app_version: str = "") -> dict[str, Any]:
    """Persistently remove legacy non-recoverable output placeholders once."""
    marker = database.get_setting(ORPHAN_OUTPUT_PENDING_MIGRATION_SETTING, {})
    previous = marker.get("value") if isinstance(marker, dict) else {}
    if isinstance(previous, dict) and previous.get("done"):
        return {
            "removed": 0,
            "canvases": 0,
            "skipped": True,
            "completed_version": str(previous.get("completed_version") or ""),
        }

    removed = 0
    changed_canvases = 0
    # include_deleted=None intentionally covers the recycle bin as well, so a
    # restored legacy canvas cannot bring a permanent placeholder back.
    for canvas in database.list_canvases(include_deleted=None):
        canvas_removed = prune_orphan_output_pending(canvas)
        if not canvas_removed:
            continue
        database.save_canvas(canvas, touch=False)
        removed += canvas_removed
        changed_canvases += 1

    completed_at = int(time.time() * 1000)
    database.save_setting(
        ORPHAN_OUTPUT_PENDING_MIGRATION_SETTING,
        {
            "done": True,
            "completed_at": completed_at,
            "completed_version": str(app_version or ""),
            "removed": removed,
            "canvases": changed_canvases,
        },
    )
    return {
        "removed": removed,
        "canvases": changed_canvases,
        "skipped": False,
        "completed_version": str(app_version or ""),
    }
