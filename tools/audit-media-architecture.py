"""只读检查安装态媒体与 SQLite 规模，不输出凭据或完整业务内容。"""
import collections
import json
import sqlite3
from pathlib import Path
from PIL import Image


def audit(root):
    result = {"root": str(root), "databases": [], "media": {}}
    for db in [root / "database/canvas.db", *root.glob("accounts/*/database/canvas.db")]:
        if not db.is_file():
            continue
        conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
        info = {"scope": str(db.relative_to(root).parent.parent), "tables": {}}
        for table in ("canvases", "generation_history", "work_items", "media_objects"):
            try:
                info["tables"][table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                pass
        try:
            rows = conn.execute("SELECT payload_json FROM canvases").fetchall()
            info["canvases"] = [{"nodes": len(p.get("nodes", [])), "bytes": len(row[0])} for row in rows for p in [json.loads(row[0])]]
        except (sqlite3.OperationalError, ValueError):
            pass
        conn.close()
        result["databases"].append(info)
    for media in [root / "media/generated", *root.glob("accounts/*/media/generated")]:
        counts = collections.Counter()
        suspicious = []
        for file in media.rglob("*"):
            if not file.is_file():
                continue
            counts[file.suffix.lower()] += 1
            if file.suffix.lower() in {".html", ".png_x", ".jpg_x"}:
                try:
                    with Image.open(file) as im:
                        kind = f"image:{im.format}:{im.size}"
                except Exception:
                    head = file.open("rb").read(200).lower()
                    kind = "html" if b"<html" in head or b"<!doctype" in head else "invalid"
                if len(suspicious) < 12:
                    suspicious.append({"name": file.name, "bytes": file.stat().st_size, "content": kind})
        result["media"][str(media.relative_to(root))] = {"extensions": dict(counts), "samples": suspicious}
    return result


if __name__ == "__main__":
    import sys
    print(json.dumps(audit(Path(sys.argv[1]).resolve()), ensure_ascii=False, indent=2))
