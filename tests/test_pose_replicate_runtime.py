from pathlib import Path
import shutil
import subprocess

import pytest


def test_pose_replicate_javascript_runtime():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js unavailable')
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, 'tests/js/pose_replicate_runtime.test.cjs'], cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
