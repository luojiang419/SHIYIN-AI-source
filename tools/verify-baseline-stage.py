"""验证全量分发目录不包含用户数据，且具备首次账号引导与必要运行组件。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


def verify(stage: Path, version: str) -> dict:
    stage = stage.resolve(strict=True)
    required = ["SHIYIN AI.exe", "app/VERSION", "app/web/login.html", "app/web/index.html",
                "app/backend/canvas-backend/canvas-backend.exe", "README.md", "LICENSE"]
    for relative in required:
        file = stage / relative
        if not file.is_file() or not file.stat().st_size:
            raise ValueError(f"缺少分发文件：{relative}")
    if (stage / "app/VERSION").read_text(encoding="utf-8").strip() != version:
        raise ValueError("分发目录版本不一致")
    if (stage / "data").exists():
        raise ValueError("正式分发目录不能包含用户 data 目录")
    forbidden = {"accounts.db", "canvas.db", "secrets.env", ".env", "fixed-models.json"}
    files = [file for file in stage.rglob("*") if file.is_file()]
    leaked = [file.relative_to(stage).as_posix() for file in files if file.name.lower() in forbidden]
    if leaked:
        raise ValueError(f"分发目录包含用户或分发中心数据：{leaked}")
    login = (stage / "app/web/login.html").read_text(encoding="utf-8")
    for marker in ("/api/account/setup", "confirmPassword", "首次在软件本机注册", "后续启动无需再登录"):
        if marker not in login:
            raise ValueError(f"缺少首次账号引导：{marker}")
    archive = CArchiveReader(str(stage / "app/backend/canvas-backend/canvas-backend.exe"))
    python_archive = archive.open_embedded_archive("PYZ.pyz")
    python_modules = python_archive.toc
    for module in ("main", "canvas_core.accounts", "canvas_core.ccswitch_import"):
        if module not in python_modules:
            raise ValueError(f"后端缺少模块：{module}")
    if "LOCAL_VISION_BUILTIN_API_KEY" in python_archive.extract("main").co_names:
        raise ValueError("冻结后端仍包含预置服务密钥")
    return {"version": version, "file_count": len(files), "bytes": sum(file.stat().st_size for file in files),
            "no_user_data": True, "account_onboarding": True, "backend_modules": True, "result": "pass"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.stage, args.version), ensure_ascii=False))
