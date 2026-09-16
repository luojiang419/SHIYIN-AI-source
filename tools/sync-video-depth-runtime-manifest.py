"""Pin published runtime chunks in the built-in component manifest."""

import argparse
import json
from pathlib import Path


MODEL_ID = "jiangjiang419/shiyin-video-depth-runtime"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path("dist/video-depth-runtime-chunks/packages.json"))
    parser.add_argument("--manifest", type=Path, default=Path("canvas_core/video_depth_runtime_manifest.json"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    old_packages = {item["id"]: item for item in manifest["packages"]}
    packages = [old_packages["runtime-windows-x86_64-cpu-part-001"]]
    for profile in ("windows-x86_64-cuda128", "windows-x86_64-cuda126"):
        generated = report[profile]
        expected = manifest["legacy_offline_packages"][profile]
        if generated["archive"] != {"size": expected["size"], "sha256": expected["sha256"]}:
            raise ValueError(f"Original runtime digest changed: {profile}")
        variant = next(item for item in manifest["variants"] if item["id"] == profile)
        variant["packages"] = [item["id"] for item in generated["packages"]]
        variant["assemble_archive"] = generated["archive"]
        for item in generated["packages"]:
            packages.append({**item, "domestic_url":
                f"https://modelscope.cn/models/{MODEL_ID}/resolve/master/{item['file']}"})
    manifest["packages"] = packages
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Pinned {len(packages)} runtime resources")


if __name__ == "__main__":
    main()
