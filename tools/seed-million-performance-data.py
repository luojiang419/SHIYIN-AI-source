from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from canvas_core.database import CanvasDatabase  # noqa: E402


WORK_ITEMS_FTS_TRIGGERS = (
    "trg_work_items_fts_ai",
    "trg_work_items_fts_ad",
    "trg_work_items_fts_au",
)


def work_item_id(history_id: str, index: int, url: str) -> str:
    import hashlib

    identity = f"{history_id}\0{int(index)}\0{url}".encode("utf-8")
    return "work_" + hashlib.sha256(identity).hexdigest()[:24]


def seed_database(path: Path, histories: int, canvases: int, local_assets: int, batch: int) -> None:
    database = CanvasDatabase(path)
    database.initialize()
    now = time.time()
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        for trigger in WORK_ITEMS_FTS_TRIGGERS:
            connection.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        connection.execute("DELETE FROM work_items_fts")
        for start in range(0, histories, batch):
            history_rows = []
            work_rows = []
            for index in range(start, min(start + batch, histories)):
                history_id = f"synthetic-history-{index:09d}"
                created_at = now - index
                url = f"/assets/output/synthetic-{index:09d}.png"
                payload = {
                    "id": history_id,
                    "timestamp": created_at,
                    "type": "online",
                    "prompt": f"synthetic prompt {index}",
                    "model": "perf-model",
                    "images": [url],
                }
                history_rows.append((
                    history_id, "online", created_at, payload["prompt"], payload["model"], "",
                    "synthetic", url, 1, f"{payload['prompt']} perf-model {url}".lower(),
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                ))
                work_rows.append((
                    work_item_id(history_id, 0, url), history_id, 0, url, "online", "", created_at,
                    payload["prompt"], "synthetic", "", "perf-model", 0, 0, "", "", f"synthetic-{index:09d}.png",
                    f"synthetic-{index:09d}.png", 0, 0, 0, 0, 0,
                    f"synthetic-{index:09d}.png {payload['prompt']} perf-model {url}".lower(), "[]",
                ))
            connection.executemany(
                """INSERT OR REPLACE INTO generation_history(
                       id,kind,created_at,prompt,model,operation,provider_id,first_url,image_count,search_text,payload_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                history_rows,
            )
            connection.executemany(
                """INSERT OR REPLACE INTO work_items(
                       id,history_id,output_index,url,kind,operation,created_at,prompt,provider_id,provider_name,
                       model,width,height,task_id,source_url,original_name,name,favorite,favorite_updated_at,
                       trashed,trashed_at,metadata_updated_at,search_text,references_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                work_rows,
            )
            connection.commit()
        for start in range(0, canvases, batch):
            rows = []
            for index in range(start, min(start + batch, canvases)):
                canvas_id = f"synthetic-canvas-{index:07d}"
                payload = {
                    "id": canvas_id,
                    "title": f"Canvas {index}",
                    "kind": "smart" if index % 2 else "classic",
                    "project": "default",
                    "created_at": int((now - index) * 1000),
                    "updated_at": int((now - index) * 1000),
                    "nodes": [{"id": f"n{index}", "type": "image", "url": f"/assets/output/synthetic-{index:09d}.png"}],
                }
                rows.append((
                    canvas_id, "default", payload["kind"], payload["title"], payload["created_at"], "layers",
                    "", "", 0, None, None, 1, payload["updated_at"], 0, 1,
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                ))
            connection.executemany(
                """INSERT OR REPLACE INTO canvases(
                       id,project_id,kind,title,created_at,icon,owner,color,pinned,board_x,board_y,node_count,
                       updated_at,deleted_at,revision,payload_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            connection.commit()
        for start in range(0, local_assets, batch):
            rows = []
            for index in range(start, min(start + batch, local_assets)):
                rel = f"folder-{index % 100:03d}/asset-{index:09d}.png"
                item = {
                    "id": rel,
                    "file": rel,
                    "folder": f"folder-{index % 100:03d}",
                    "name": f"asset-{index:09d}.png",
                    "url": f"/assets/uploads/{rel}",
                    "kind": "image",
                    "size": 1024,
                    "created_at": now - index,
                }
                rows.append((
                    rel, rel, item["folder"], item["name"], item["url"], "image", 1024,
                    item["created_at"], item["created_at"], f"{item['name']} {rel}".lower(),
                    json.dumps(item, ensure_ascii=False, separators=(",", ":")),
                ))
            connection.executemany(
                """INSERT OR REPLACE INTO local_asset_items(
                       id,file,folder,name,url,kind,size,created_at,updated_at,search_text,payload_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            connection.commit()
        connection.execute("INSERT INTO work_items_fts(id, search_text) SELECT id, search_text FROM work_items")
        connection.commit()
    database.initialize()


def measure(path: Path, repeats: int) -> dict[str, float]:
    database = CanvasDatabase(path)
    timings: dict[str, list[float]] = {"works_page": [], "works_search": [], "canvas_records": [], "local_assets_page": []}
    for _ in range(repeats):
        started = time.perf_counter()
        database.list_work_items(limit=120)
        timings["works_page"].append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        database.list_work_items(search="synthetic prompt 999999", limit=120)
        timings["works_search"].append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        database.list_canvas_records(include_deleted=False)
        timings["canvas_records"].append((time.perf_counter() - started) * 1000)
        started = time.perf_counter()
        database.list_local_asset_items(limit=240)
        timings["local_assets_page"].append((time.perf_counter() - started) * 1000)
    result: dict[str, float] = {}
    for key, values in timings.items():
        ordered = sorted(values)
        p95_index = min(len(ordered) - 1, int(len(ordered) * 0.95))
        result[key + "_median_ms"] = ordered[len(ordered) // 2]
        result[key + "_p95_ms"] = ordered[p95_index]
        result[key + "_max_ms"] = ordered[-1]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed and measure SHIYIN AI million-scale performance data.")
    parser.add_argument("--db", required=True, type=Path, help="Target SQLite database path. Use a throwaway path for tests.")
    parser.add_argument("--histories", type=int, default=10000)
    parser.add_argument("--canvases", type=int, default=1000)
    parser.add_argument("--local-assets", type=int, default=10000)
    parser.add_argument("--batch", type=int, default=5000)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    seed_database(args.db, max(0, args.histories), max(0, args.canvases), max(0, args.local_assets), max(100, args.batch))
    print(json.dumps({"db": str(args.db), **measure(args.db, max(1, args.repeats))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
