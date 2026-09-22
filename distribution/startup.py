"""保留无控制台服务的启动异常，避免只留下通用超时提示。"""
import contextlib
import os
from datetime import datetime
import tempfile
import traceback
from pathlib import Path


def run_service():
    path = Path(os.environ.get('SHIYIN_DISTRIBUTION_DATA', 'D:/SHIYIN-Distribution')) / 'service-startup.log'
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > 2 * 1024 * 1024:
            path.replace(path.with_suffix('.previous.log'))
        output = path.open('a', encoding='utf-8', buffering=1)
    except OSError:
        path = Path(tempfile.gettempdir()) / 'SHIYIN-distribution-service-startup.log'
        output = path.open('a', encoding='utf-8', buffering=1)
    with output, contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        print(f'\n[{datetime.now().isoformat(timespec="seconds")}] 分发服务启动')
        try:
            from distribution.service import main
            main()
        except BaseException:
            traceback.print_exc()
            raise
