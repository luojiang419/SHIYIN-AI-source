"""Pin verified domestic chunks without changing the fixed person-depth archives."""

import argparse
import json
from pathlib import Path


MODEL_ID = "jiangjiang419/shiyin-person-depth-component"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path("dist/person-depth-public/packages.json"))
    parser.add_argument("--manifest", type=Path, default=Path("canvas_core/person_depth_manifest.json"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    for package in manifest["packages"]:
        generated = report[package["id"]]
        if generated["archive"] != {"size": package["size"], "sha256": package["sha256"]}:
            raise ValueError(f"Fixed package changed: {package['id']}")
        package["domestic_url"] = ""
        package["domestic_parts"] = [
            {"id": item["id"], "size": item["size"], "sha256": item["sha256"],
             "domestic_url": f"https://modelscope.cn/models/{MODEL_ID}/resolve/master/{item['file']}"}
            for item in generated["parts"]
        ]
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Pinned {sum(len(item['domestic_parts']) for item in manifest['packages'])} domestic chunks")


if __name__ == "__main__":
    main()
