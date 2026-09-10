"""用真实后端账号契约驱动浏览器启动回归，避免 fixture 字段偏离 API。"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from canvas_core.accounts import AccountIdentity

ROOT = Path(__file__).resolve().parents[1]


def test_studio_boot_with_real_account_contract():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser runtime regression")
    accounts = [
        AccountIdentity("admin", "fixture-admin", "admin", "").public(),
        AccountIdentity("fixture-user", "fixture-user", "user", "fixture-user").public(),
    ]
    env = {**os.environ, "STUDIO_TEST_ACCOUNTS": json.dumps(accounts)}
    result = subprocess.run(
        [node, "tests/support/studio_boot_runtime_check.cjs"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
