"""直接执行路由函数，覆盖账号隔离及实际目录写入校验。"""
import ast
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi import HTTPException
from canvas_core.database import CanvasDatabase


def test_personal_defaults_are_account_scoped_and_save_directory_is_validated(tmp_path):
    source = ast.parse((Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8"))
    names = {"personal_preferences_key", "get_personal_preferences", "save_personal_preferences", "get_quick_save_settings", "quick_save_configured_directory"}
    functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
    for node in functions:
        node.decorator_list = []
    account = ["alice"]
    database = CanvasDatabase(tmp_path / "preferences.db")
    database.initialize()
    env = dict(DATABASE=database, current_account_id=lambda: account[0], Dict=Dict, Any=Any, Path=Path, HTTPException=HTTPException, tempfile=tempfile, os=os)
    exec(compile(ast.Module(body=functions, type_ignores=[]), "preferences", "exec"), env)
    save = env["save_personal_preferences"]
    save({"video": {"h3": {"duration": 12}}, "quickSave": {"mode": "silent", "directory": str(tmp_path / "downloads")}})
    assert env["quick_save_configured_directory"]() == tmp_path / "downloads"
    account[0] = "bob"
    assert env["get_personal_preferences"]() == {}
    save({"video": {"kling": {"duration": 5}}})
    account[0] = "alice"
    assert env["get_personal_preferences"]()["video"] == {"h3": {"duration": 12}}
    with pytest.raises(HTTPException):
        save({"quickSave": {"mode": "silent", "directory": "relative/path"}})
    with pytest.raises(HTTPException):
        save({"video": []})
