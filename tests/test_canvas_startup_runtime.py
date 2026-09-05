"""执行真实启动脚本，验证冷启动请求时序及页面初始化回退。"""
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_canvas_startup_lifecycle_and_data_integrity():
    result = subprocess.run(
        ["node", "--unhandled-rejections=strict", "tests/js/canvas_startup.test.cjs"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_canvas_scripts_keep_order_without_document_write():
    import re

    html = (ROOT / "static/canvas.html").read_text(encoding="utf-8")
    scripts = re.findall(r'<script([^>]*?)src="([^\"]+)"[^>]*>', html)
    assert scripts[0][1].startswith('/static/js/canvas-startup.js?')
    assert html.index('canvas-startup.js') < html.index('rel="stylesheet"')
    assert all('defer' in attrs for attrs, _ in scripts[1:])
    paths = [url.split('?')[0] for _, url in scripts]
    assert '/static/js/i18n.js' not in paths
    assert paths.index('/static/js/i18n-core.js') < paths.index('/static/js/i18n/canvas.js')
    assert paths.index('/static/js/canvas-special-nodes.js') < paths.index('/static/js/canvas.js')
    assert paths.index('/static/js/canvas-legacy-migration.js') < paths.index('/static/js/canvas.js')
    assert '/static/js/i18n/smart-canvas.js' in paths  # 提示词库仍使用 smart.* 翻译。
    assert paths[-1] == '/static/js/canvas.js'
    for path in paths:
        assert (ROOT / path.lstrip('/')).is_file()
