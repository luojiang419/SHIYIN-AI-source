"""运行偏好同步真实脚本，验证启动/重连/并发保存不会回退用户输入。"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_preferences_preserve_latest_edit_during_boot_and_reconnect():
    result = subprocess.run(
        ['node', '--unhandled-rejections=strict', 'tests/js/runtime_preferences_order.test.cjs'],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
