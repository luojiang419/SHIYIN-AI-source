#!/usr/bin/env python3
"""计算 SHIYIN AI 的下一个三段式正式版本。"""

from __future__ import annotations

import argparse
import re


VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"无效的正式版本号: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def next_version(latest: str | None, minimum: str) -> str:
    minimum_parts = parse_version(minimum)
    if not latest or not latest.strip():
        return ".".join(map(str, minimum_parts))
    latest_parts = parse_version(latest)
    if latest_parts < minimum_parts:
        return ".".join(map(str, minimum_parts))
    major, minor, patch = latest_parts
    return f"{major}.{minor}.{patch + 1}"


def self_test() -> None:
    assert next_version(None, "v1.0.79") == "1.0.79"
    assert next_version("", "v1.0.79") == "1.0.79"
    assert next_version("v1.0.78", "v1.0.79") == "1.0.79"
    assert next_version("v1.0.79", "v1.0.79") == "1.0.80"
    try:
        next_version("v1.0.79-beta", "v1.0.79")
    except ValueError:
        return
    raise AssertionError("预发布标签不得作为正式版本基线")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest")
    parser.add_argument("--minimum", default="v1.0.79")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("resolve_release_version self-test passed")
        return
    print(next_version(args.latest, args.minimum))


if __name__ == "__main__":
    main()
