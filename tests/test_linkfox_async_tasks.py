import asyncio
import json
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

import main
from canvas_core import linkfox_video as lf


@pytest.mark.parametrize('mode,path', [('reference', '/aigc/multiImageVideoGenAsync'), ('first_last_frame', '/aigc/videoGenAsync')])
def test_native_submit_query_uses_verified_protocol(mode, path):
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(request.url.path)
        assert request.headers['Authorization'] == 'test-only'
        if request.url.path == path:
            assert body['videoType'] == 'SEED' and body['videoTime'] == 5
            assert 'entry' not in body and 'mode' not in body
            return httpx.Response(200, json={'errcode': 200, 'taskId': 'upstream-1', 'costToken': 7})
        assert body == {'taskId': 'upstream-1'}
        return httpx.Response(200, json={'errcode': 200, 'taskId': 'upstream-1', 'status': 'SUCCESS',
            'resultList': [{'type': 'video', 'url': 'https://example.com/video.mp4'}]})
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            submitted = await lf.submit_task({'entry': 'img2video', 'mode': mode, 'imageList': ['https://example.com/input.png'],
                'videoType': 'seedance2.0', 'videoTime': 5}, client=client, api_key='test-only', gateway='https://gateway.invalid')
            assert submitted['upstream_task_id'] == 'upstream-1'
            queried = await lf.query_task('upstream-1', client=client, api_key='test-only', gateway='https://gateway.invalid')
            assert queried['status'] == 'succeeded'
    asyncio.run(exercise())
    assert calls == [path, '/aigc/taskQuery']


@pytest.mark.parametrize('body,expected', [
    ({'errcode': 401, 'errmsg': 'authorized error'}, 'authorized error'),
    ({'errcode': 200}, '未知任务状态'),
    ({'errcode': 200, 'taskId': 'wrong', 'status': 'PROCESSING'}, '不一致'),
])
def test_query_rejects_business_errors_instead_of_polling_forever(body, expected):
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as client:
            with pytest.raises(lf.LinkFoxVideoError, match=expected):
                await lf.query_task('task', client=client, api_key='test-only', gateway='https://gateway.invalid')
    asyncio.run(exercise())


@pytest.fixture
def task_state(monkeypatch):
    monkeypatch.setattr(main, 'CANVAS_VIDEO_TASKS', {})
    monkeypatch.setattr(main, 'CANVAS_VIDEO_TASKS_LOADED_ACCOUNTS', set())
    monkeypatch.setattr(main, 'ensure_canvas_video_tasks_loaded', lambda: None)
    monkeypatch.setattr(main, 'write_canvas_video_tasks_locked', lambda *args: None)
    monkeypatch.setattr(main, 'start_canvas_video_task_runner', lambda *args: None)
    monkeypatch.setattr(main, 'get_api_provider', lambda value: {'id': value})
    monkeypatch.setattr(main, 'linkfox_configured_key', lambda: 'test-only')
    monkeypatch.setattr(main, 'prepare_video_generation_prompt', AsyncMock(side_effect=lambda payload, provider: (payload, {})))
    return main.CANVAS_VIDEO_TASKS


def test_duplicate_local_id_never_submits_again(task_state, monkeypatch):
    submit = AsyncMock(return_value={'upstream_task_id': 'upstream-1', 'base_url': 'https://gateway.invalid',
        'status': 'PROCESSING', 'raw': {'taskId': 'upstream-1'}})
    monkeypatch.setattr(main, 'submit_canvas_video_upstream', submit)
    payload = main.CanvasVideoTaskRequest(task_id='canvas_video_linkfox_test', provider_id='linkfox', model='seedance2.0')
    first = asyncio.run(main.create_canvas_video_task(payload))
    second = asyncio.run(main.create_canvas_video_task(payload))
    assert first['upstream_task_id'] == second['upstream_task_id'] == 'upstream-1'
    assert first['submission_response'] == {'taskId': 'upstream-1'}
    assert submit.await_count == 1


def test_dedicated_node_keeps_optional_prompt_without_requiring_llm(task_state, monkeypatch):
    monkeypatch.setattr(main, 'submit_canvas_video_upstream', AsyncMock(return_value={
        'upstream_task_id': 'direct-1', 'base_url': 'https://gateway.invalid'}))
    payload = main.CanvasVideoTaskRequest(task_id='canvas_video_direct', provider_id='linkfox',
        model='seedance2.0', linkfox_direct=True, prompt='')
    assert asyncio.run(main.create_canvas_video_task(payload))['upstream_task_id'] == 'direct-1'
    main.prepare_video_generation_prompt.assert_not_awaited()


@pytest.mark.parametrize('status', ['succeeded', 'failed', 'protocol_error', 'timeout'])
def test_runner_preserves_result_or_clear_failure(task_state, monkeypatch, status):
    task_state['canvas_video_test'] = {'id': 'canvas_video_test', 'provider_id': 'linkfox', 'status': 'running',
        'upstream_task_id': 'upstream-1', 'created_at': time.time()-(4000 if status == 'timeout' else 0),
        '_account_id': main.current_account_id(), 'request': {'videoTime': 5}}
    queried = AsyncMock(return_value={'status': status, 'url': 'https://example.com/video.mp4', 'error': '图片审核不通过', 'raw': {'status': status}})
    if status == 'protocol_error': queried.side_effect = lf.LinkFoxVideoError('authorized error')
    monkeypatch.setattr(main, 'query_canvas_video_upstream', queried)
    download = AsyncMock(return_value='/assets/output/linkfox_result.mp4')
    monkeypatch.setattr(main, 'save_remote_video_to_output', download)
    asyncio.run(main.run_canvas_video_task('canvas_video_test'))
    task = task_state['canvas_video_test']
    if status == 'succeeded':
        assert task['result']['task_id'] == 'upstream-1'
        assert task['result']['videos'] == ['/assets/output/linkfox_result.mp4']
        download.assert_awaited_once_with('https://example.com/video.mp4', prefix='linkfox_')
    else:
        assert task['status'] in {'failed', 'interrupted'}
        assert 'upstream-1' in task['error']
        download.assert_not_awaited()


def test_linkfox_restart_keeps_unknown_submissions_and_failures(task_state, monkeypatch):
    rows = [dict(id='canvas_video_'+status, provider_id='linkfox', status=status, created_at=time.time(),
        upstream_task_id='upstream-1' if status != 'submitting' else '') for status in ['running','failed','submitting']]
    class Database:
        def load_tasks(self, kind): return rows
    monkeypatch.setattr(main, 'DATABASE', Database())
    main.load_canvas_video_tasks_from_disk()
    assert task_state['canvas_video_running']['status'] == 'recovery_pending'
    assert task_state['canvas_video_failed']['status'] == 'failed'
    assert task_state['canvas_video_submitting']['status'] == 'interrupted'


def test_download_failure_retries_same_upstream_without_reporting_success(task_state, monkeypatch):
    task_state['canvas_video_test'] = {'id': 'canvas_video_test', 'provider_id': 'linkfox', 'status': 'running',
        'upstream_task_id': 'upstream-1', 'created_at': time.time(), '_account_id': main.current_account_id()}
    monkeypatch.setattr(main, 'query_canvas_video_upstream', AsyncMock(return_value={
        'status': 'succeeded', 'url': 'https://example.com/video.mp4'}))
    monkeypatch.setattr(main, 'save_remote_video_to_output', AsyncMock(return_value='https://example.com/video.mp4'))
    async def stop(delay): raise asyncio.CancelledError
    monkeypatch.setattr(main.asyncio, 'sleep', stop)
    with pytest.raises(asyncio.CancelledError): asyncio.run(main.run_canvas_video_task('canvas_video_test'))
    assert task_state['canvas_video_test']['status'] == 'recovery_pending'
    assert task_state['canvas_video_test']['upstream_task_id'] == 'upstream-1'
    assert not task_state['canvas_video_test'].get('result')
