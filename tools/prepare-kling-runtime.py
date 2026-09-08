"""构建可灵组件并执行空 PATH 冒烟；不读取或打包用户凭据。"""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canvas_core.kling_cli import default_kling_process_runner
from canvas_core.kling_runtime import cli_entry, node_entry, prepare_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    prepare_runtime(root, ("china", "global"))
    env = {**os.environ, "PATH": "", "KLING_HOME": str(root / ".smoke-home")}
    for region in ("china", "global"):
        result = default_kling_process_runner(
            str(node_entry(root)), [str(cli_entry(root, region)), "--version"],
            env=env, capture_output=True, check=True, timeout=20,
        )
        print(f"Kling {region}, empty PATH: {result.stdout.decode().strip()}")


if __name__ == "__main__":
    main()
