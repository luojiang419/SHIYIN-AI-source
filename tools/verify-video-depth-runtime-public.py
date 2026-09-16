"""Verify pinned public runtime resources before shipping an installer."""

import json
from pathlib import Path

import requests
from modelscope.hub.api import HubApi


MODEL_ID = "jiangjiang419/shiyin-video-depth-runtime"
MANIFEST = Path("canvas_core/video_depth_runtime_manifest.json")


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = {item["Path"]: item for item in HubApi().get_model_files(MODEL_ID, recursive=True)}
    packages = manifest["packages"]
    for package in packages:
        remote = files.get(package["file"])
        if not remote or int(remote["Size"]) != package["size"] or remote["Sha256"].lower() != package["sha256"]:
            raise ValueError(f"ModelScope resource mismatch: {package['file']}")
        with requests.get(package["domestic_url"], headers={"Range": "bytes=0-31"},
                          stream=True, timeout=30) as response:
            expected_range = f"bytes 0-31/{package['size']}"
            if response.status_code != 206 or response.headers.get("Content-Range") != expected_range:
                raise ValueError(f"Anonymous Range download failed: {package['file']}")
    print(f"Verified {len(packages)} public resources: SHA-256, size, and anonymous Range")


if __name__ == "__main__":
    main()
