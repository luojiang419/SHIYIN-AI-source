"""执行真实同步函数，覆盖保存已完成但旧请求才返回等驻留缓存竞态。"""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_canvas_session_sync_never_overwrites_newer_edits():
    result = subprocess.run(
        ['node', '--unhandled-rejections=strict', 'tests/js/canvas_session_sync.test.cjs'],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
