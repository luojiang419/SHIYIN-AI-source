"""Split immutable video-depth runtime archives into upload-safe byte ranges."""

import argparse
import hashlib
import json
from pathlib import Path


CHUNK_BYTES = 500_000_000


def sha256_file(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(4 * 1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def split_archive(source, destination, profile):
    chunks = []
    with source.open("rb") as input_file:
        index = 0
        while input_file.tell() < source.stat().st_size:
            index += 1
            target = destination / f"video-depth-runtime-1.0.0-{profile}-chunk-{index:03d}.bin"
            remaining = CHUNK_BYTES
            with target.open("wb") as output_file:
                while remaining:
                    data = input_file.read(min(4 * 1024 * 1024, remaining))
                    if not data:
                        break
                    output_file.write(data)
                    remaining -= len(data)
            chunks.append({"id": f"runtime-{profile}-chunk-{index:03d}", "file": target.name,
                           "size": target.stat().st_size, "sha256": sha256_file(target)})
    return {"archive": {"size": source.stat().st_size, "sha256": sha256_file(source)},
            "packages": chunks}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("dist/video-depth-runtime"))
    parser.add_argument("--output", type=Path, default=Path("dist/video-depth-runtime-chunks"))
    parser.add_argument("--profiles", nargs="+", default=("windows-x86_64-cuda128", "windows-x86_64-cuda126"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = {}
    for profile in args.profiles:
        source = args.source / f"video-depth-runtime-1.0.0-{profile}.zip"
        result[profile] = split_archive(source, args.output, profile)
    (args.output / "packages.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: [part["size"] for part in value["packages"]]
                      for key, value in result.items()}, indent=2))


if __name__ == "__main__":
    main()
