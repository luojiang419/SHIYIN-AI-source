"""Verify the fixed person-depth mirror before shipping a client manifest."""

import json
from pathlib import Path

import requests
from modelscope.hub.api import HubApi


MODEL_ID = "jiangjiang419/shiyin-person-depth-component"


def main():
    api = HubApi()
    if api.get_model(MODEL_ID).get("License") != "CC-BY-NC-4.0":
        raise ValueError("Person-depth mirror license metadata does not match the weights")
    files = {item["Path"]: item for item in api.get_model_files(MODEL_ID, recursive=True)}
    manifest = json.loads(Path("canvas_core/person_depth_manifest.json").read_text(encoding="utf-8"))
    count = 0
    for package in manifest["packages"]:
        parts = package.get("domestic_parts") or []
        if sum(item["size"] for item in parts) != package["size"]:
            raise ValueError(f"Part sizes do not reconstruct {package['id']}")
        for part in parts:
            name = part["domestic_url"].rsplit("/", 1)[-1]
            remote = files.get(name)
            if not remote or int(remote["Size"]) != part["size"] or remote["Sha256"].lower() != part["sha256"]:
                raise ValueError(f"ModelScope resource mismatch: {name}")
            with requests.get(part["domestic_url"], headers={"Range": "bytes=0-31"},
                              stream=True, timeout=30) as response:
                if response.status_code != 206 or response.headers.get("Content-Range") != f"bytes 0-31/{part['size']}":
                    raise ValueError(f"Anonymous Range download failed: {name}")
            count += 1
    print(f"Verified {count} person-depth mirror chunks and CC-BY-NC-4.0 metadata")


if __name__ == "__main__":
    main()
