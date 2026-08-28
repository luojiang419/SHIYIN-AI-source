"""原始 Infinite-Canvas 后端的桌面侧车入口。

该入口只负责读取当前桌面壳传入的运行参数，并把原始代码的数据根目录
指向安装包中的 app 目录；业务代码仍来自 E:\\Infinite-Canvas-main 的原始 main.py。
"""

from __future__ import annotations

import argparse
import os
import sys


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--host", default=os.getenv("CANVAS_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CANVAS_PORT", "3001")))
    parser.add_argument("--app-root", default=os.getenv("CANVAS_APP_ROOT", ""))
    parser.add_argument("--data-dir", default=os.getenv("CANVAS_DATA_DIR", ""))
    parsed, _ = parser.parse_known_args()
    return parsed


args = _parse_args()
app_root = os.path.abspath(args.app_root or os.path.dirname(os.path.abspath(__file__)))
os.environ["CANVAS_APP_ROOT"] = app_root
os.environ["CANVAS_PORT"] = str(args.port)
os.environ["CANVAS_HOST"] = str(args.host)
if args.data_dir:
    os.environ["CANVAS_DATA_DIR"] = os.path.abspath(args.data_dir)
os.chdir(app_root)
if app_root not in sys.path:
    sys.path.insert(0, app_root)

from main import app  # noqa: E402


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, ws_ping_interval=None, ws_ping_timeout=None)
