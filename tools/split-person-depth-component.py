"""Split the unchanged person-depth release archives for a domestic mirror."""

import argparse
import hashlib
import json
from pathlib import Path


CHUNK_BYTES = 500_000_000


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path(".build/182-person-download/downloads/1.0.0"))
    parser.add_argument("--output", type=Path, default=Path("dist/person-depth-public"))
    args = parser.parse_args()
    manifest = json.loads(Path("canvas_core/person_depth_manifest.json").read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    report = {}
    for package in manifest["packages"]:
        source = args.source / f"official-{package['id']}.zip"
        if source.stat().st_size != package["size"] or sha256_file(source) != package["sha256"]:
            raise ValueError(f"Original archive does not match the fixed release: {package['id']}")
        parts = []
        with source.open("rb") as input_file:
            index = 0
            while input_file.tell() < package["size"]:
                index += 1
                target = args.output / f"person-depth-{package['id']}-chunk-{index:03d}.bin"
                remaining = CHUNK_BYTES
                with target.open("wb") as output_file:
                    while remaining:
                        chunk = input_file.read(min(4 * 1024 * 1024, remaining))
                        if not chunk:
                            break
                        output_file.write(chunk)
                        remaining -= len(chunk)
                parts.append({"id": f"{package['id']}-chunk-{index:03d}", "file": target.name,
                              "size": target.stat().st_size, "sha256": sha256_file(target)})
        report[package["id"]] = {"archive": {"size": package["size"], "sha256": package["sha256"]},
                                 "parts": parts}
    (args.output / "packages.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print({key: len(value["parts"]) for key, value in report.items()})


if __name__ == "__main__":
    main()
