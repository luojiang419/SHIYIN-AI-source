"""检查李维斯人工复核联系图是否仍为可放大的原尺寸证据。"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent / "输出" / "李维斯广告风格分析"
SHEET_ROOT = ROOT / "人工高清复核联系图"
MANIFEST = ROOT / "人工高清复核联系图清单.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []
    if len(manifest) != 41:
        errors.append(f"manifest videos={len(manifest)} (expected 41)")
    for item in manifest:
        video_id = str(item.get("video_id") or "")
        path = SHEET_ROOT / f"video_{video_id}.jpg"
        if not path.is_file():
            errors.append(f"missing sheet {path.name}")
            continue
        with Image.open(path) as image:
            width, height = image.size
            if width < 2880:
                errors.append(f"{path.name}: width={width} < 2880")
            if image.format != "JPEG":
                errors.append(f"{path.name}: format={image.format}")
        if list(item.get("source_dimensions") or []) != [720, 406]:
            errors.append(f"{path.name}: source dimensions are not 720x406")
        if int(item.get("selected_count") or 0) < 1:
            errors.append(f"{path.name}: no selected source frames")
    if errors:
        print("\n".join(errors))
        return 1
    print(json.dumps({"status": "ok", "videos": len(manifest), "rule": "no thumbnail-only evidence; source cells kept at 720x406"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
