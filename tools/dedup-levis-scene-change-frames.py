from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent / "输出" / "李维斯广告风格分析"
RAW_ROOT = ROOT / "镜头变化帧"
LOG_ROOT = ROOT / "镜头变化日志"
OUTPUT_ROOT = ROOT / "镜头变化帧-去重"
MANIFEST = ROOT / "镜头变化帧-去重清单.json"
PTS_RE = re.compile(r"n:\s*(\d+)\s+pts:.*?pts_time:\s*([0-9.]+)")


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    items = []
    for video_id in range(1, 42):
        log_path = LOG_ROOT / f"video_{video_id:02d}.log"
        frames = sorted(RAW_ROOT.glob(f"video_{video_id:02d}_*.jpg"))
        last_time = -999.0
        for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = PTS_RE.search(line)
            if not match:
                continue
            frame_number = int(match.group(1))
            pts_time = float(match.group(2))
            if pts_time - last_time < 1.0:
                continue
            source = RAW_ROOT / f"video_{video_id:02d}_{frame_number + 1:05d}.jpg"
            if not source.is_file() or not frames:
                continue
            target = OUTPUT_ROOT / f"video_{video_id:02d}_{frame_number + 1:05d}_{round(pts_time):05d}s.jpg"
            shutil.copy2(source, target)
            items.append({
                "video_id": f"{video_id:02d}",
                "frame_number": frame_number,
                "pts_time": pts_time,
                "file": str(target),
            })
            last_time = pts_time
    MANIFEST.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"dedup_frames": len(items), "videos": len({item['video_id'] for item in items})}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
