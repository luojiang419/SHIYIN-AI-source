#!/usr/bin/env python3
"""Bounded-retention cleanup for the remote clip directory."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path


def cleanup(root: Path, max_bytes: int, min_age_seconds: int, target_ratio: float = 0.92) -> dict[str, int]:
    now = time.time()
    files = [path for path in root.rglob("*.mp4") if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    deleted = 0
    deleted_bytes = 0
    if total <= max_bytes:
        return {"files": len(files), "bytes": total, "deleted": 0, "deleted_bytes": 0}
    target = int(max_bytes * min(0.99, max(0.5, target_ratio)))
    candidates = sorted(
        (
            path
            for path in files
            if now - path.stat().st_mtime >= max(0, min_age_seconds)
        ),
        key=lambda path: path.stat().st_mtime,
    )
    for path in candidates:
        if total <= target:
            break
        size = path.stat().st_size
        try:
            path.unlink()
        except OSError as exc:
            print(f"cleanup failed: {path}: {exc}", flush=True)
            continue
        total -= size
        deleted += 1
        deleted_bytes += size
        print(f"cleanup deleted: {path} ({size} bytes)", flush=True)
    for directory in sorted((item for item in root.rglob("*") if item.is_dir()), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass
    return {"files": len(files), "bytes": total, "deleted": deleted, "deleted_bytes": deleted_bytes}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.getenv("CLIPDATA_ROOT", "/opt/clipdata"))
    parser.add_argument("--max-bytes", type=int, default=int(os.getenv("CLIPDATA_MAX_BYTES", str(10 * 1024**3))))
    parser.add_argument("--min-age-seconds", type=int, default=int(os.getenv("CLIPDATA_MIN_AGE_SECONDS", "3600")))
    args = parser.parse_args()
    result = cleanup(Path(args.root).expanduser().resolve(), max(1, args.max_bytes), max(0, args.min_age_seconds))
    print(result, flush=True)


if __name__ == "__main__":
    main()
