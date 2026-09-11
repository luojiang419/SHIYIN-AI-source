import asyncio
import threading
from unittest.mock import patch

import pytest

from canvas_core.account_storage import account_scope, current_account_id


@pytest.mark.parametrize('route,operation,args,value', [
    ('canvases', 'list_canvases', (), []),
    ('get_projects', 'list_projects', (), []),
    ('trashed_canvases', 'list_deleted_canvases', (), []),
    ('get_canvas_meta', 'load_canvas', ('fixture',), {'id': 'fixture'}),
    ('runtime_ai_config', 'runtime_api_providers', (), []),
])
def test_slow_entry_read_keeps_event_loop_responsive(route, operation, args, value):
    import main

    released = threading.Event()
    observed = []

    def slow_read(*_):
        observed.append(current_account_id())
        # 旧实现会占住事件循环直到超时；新实现能先运行 call_later。
        observed.append(released.wait(0.5))
        return value

    async def run():
        asyncio.get_running_loop().call_later(0.02, released.set)
        with account_scope('cold-start-account'):
            return await getattr(main, route)(*args)

    with patch.object(main, operation, side_effect=slow_read):
        result = asyncio.run(run())
    assert isinstance(result, dict)
    assert observed == ['cold-start-account', True]


def test_canvas_nodes_remain_readable_while_list_waits_for_cleanup_lock(tmp_path):
    import main
    from canvas_core.database import CanvasDatabase

    database = CanvasDatabase(tmp_path / 'canvas.db')
    database.initialize()
    database.save_canvas({'id': 'cold', 'nodes': [{'id': 'text', 'type': 'prompt'}]})
    lock = threading.Lock()
    lock.acquire()
    # 防止旧实现堵住事件循环后测试永久挂起。
    watchdog = threading.Timer(2, lock.release)
    watchdog.start()

    async def run():
        listing = asyncio.create_task(main.canvases())
        try:
            await asyncio.sleep(0.02)
            detail = await main.get_canvas('cold')
            assert detail['canvas']['nodes'][0]['id'] == 'text'
            assert lock.locked(), '列表清理锁等待阻塞了工程节点读取'
        finally:
            if lock.locked():
                lock.release()
            await listing

    try:
        with patch.object(main, 'DATABASE', database), patch.object(main, 'CANVAS_LOCK', lock), \
                patch.object(main, 'ACTIVE_CANVAS_ID', ''), patch.object(main, 'ACTIVE_CANVAS_LAST_SEEN', 0):
            asyncio.run(run())
    finally:
        watchdog.cancel()
