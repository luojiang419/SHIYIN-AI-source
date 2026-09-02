from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
SOURCE_ROOT = PROJECT_ROOT / "输出" / "李维斯广告风格分析" / "环境矩阵-20260902"
TARGET_ROOT = PROJECT_ROOT / "输出" / "李维斯广告风格分析" / "环境矩阵-后处理-20260902"


def main() -> int:
    os.environ["CANVAS_DWPOSE_AUTO_DOWNLOAD"] = "0"
    os.environ["CANVAS_DEPTH_AUTO_DOWNLOAD"] = "0"
    import main as canvas_main

    source_report = json.loads((SOURCE_ROOT / "环境矩阵测试报告.json").read_text(encoding="utf-8"))
    report = {**source_report, "groups": [], "finish": {"function": "apply_lookbook_organic_film_grain", "amount": 0.025}}
    original_resolver = canvas_main.output_file_from_url
    try:
        canvas_main.output_file_from_url = lambda value: str(value) if Path(str(value)).is_file() else None
        for group in source_report.get("groups") or []:
            images = []
            for item in group.get("images") or []:
                source = Path(item["path"])
                target = TARGET_ROOT / str(group["id"]) / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                applied = canvas_main.apply_lookbook_organic_film_grain(str(target), amount=0.025)
                images.append({**item, "path": str(target), "finish_applied": bool(applied)})
            report["groups"].append({**group, "images": images})
    finally:
        canvas_main.output_file_from_url = original_resolver
    TARGET_ROOT.mkdir(parents=True, exist_ok=True)
    (TARGET_ROOT / "环境矩阵测试报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "images": sum(len(group["images"]) for group in report["groups"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
