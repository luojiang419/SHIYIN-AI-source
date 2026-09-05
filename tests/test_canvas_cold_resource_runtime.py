import asyncio
from concurrent.futures import Future
from contextvars import ContextVar
from pathlib import Path
import threading
import time
from unittest.mock import patch

import pytest
import main


@pytest.mark.parametrize('failed', [False, True])
def test_already_completed_preview_cannot_reenter_lock(tmp_path, failed):
    source = tmp_path / 'source.png'
    source.write_bytes(b'source')
    class CompletedFuture(Future):
        def add_done_callback(self, callback):
            # 精确命中 Future 已完成的同步回调路径；旧实现确定性失败而不会挂住测试进程。
            assert main.MEDIA_PREVIEW_INFLIGHT_LOCK.acquire(blocking=False), 'completion callback registered while holding non-reentrant lock'
            main.MEDIA_PREVIEW_INFLIGHT_LOCK.release()
            return super().add_done_callback(callback)
    future = CompletedFuture()
    if failed:
        future.set_exception(ValueError('bad preview'))
    else:
        future.set_result(('preview.webp', 'image/webp'))
    async def run():
        with patch.object(main.MEDIA_PREVIEW_EXECUTOR, 'submit', return_value=future):
            return await main.get_or_build_media_preview(str(source), 512, str(tmp_path/'p.webp'), str(tmp_path/'p.png'))
    try:
        if failed:
            with pytest.raises(ValueError, match='bad preview'):
                asyncio.run(run())
        else:
            assert asyncio.run(run()) == ('preview.webp', 'image/webp')
        assert str(tmp_path/'p.webp') not in main.MEDIA_PREVIEW_INFLIGHT
    finally:
        main.MEDIA_PREVIEW_FAILURES.clear()


def test_canvas_database_read_does_not_block_event_loop_and_keeps_account_context():
    account = ContextVar('test_account')
    main_thread = threading.get_ident()
    def load(canvas_id):
        assert threading.get_ident() != main_thread
        assert account.get() == 'owner'
        time.sleep(.05)
        return {'id':canvas_id}
    async def run():
        account.set('owner')
        with patch.object(main, 'load_canvas', side_effect=load):
            task = asyncio.create_task(main.get_canvas('fixture'))
            await asyncio.sleep(.005)
            assert not task.done()
            return await task
    assert asyncio.run(run()) == {'canvas':{'id':'fixture'}}


def test_preview_reuses_disk_cache_after_memory_cache_reset(tmp_path):
    source = tmp_path/'source.png'
    source.write_bytes(b'source')
    with patch.object(main, 'MEDIA_PREVIEW_DIR', str(tmp_path)), patch.object(main, 'output_file_from_url', return_value=str(source)):
        webp, _ = main.media_preview_cache_paths(str(source), 512)
        Path(webp).write_bytes(b'cached-preview')
        main.MEDIA_PREVIEW_INFLIGHT.clear()
        with patch.object(main, 'get_or_build_media_preview') as build:
            response = asyncio.run(main.media_preview('/assets/input/source.png', 512))
        assert response.path == webp
        build.assert_not_called()


def test_preview_filesystem_lookup_runs_outside_event_loop():
    caller = threading.get_ident()
    def resolve(url, width):
        assert threading.get_ident() != caller
        return 'source', 'cache.webp', 'cache.png', ('cache.webp','image/webp')
    with patch.object(main, 'resolve_media_preview_request', side_effect=resolve):
        assert asyncio.run(main.media_preview('/assets/input/source.png',512)).path == 'cache.webp'
