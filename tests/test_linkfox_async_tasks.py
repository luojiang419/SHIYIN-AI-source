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


def test_mini_uses_official_v3_response_and_preserves_large_task_id():
    task_id = '2103060316882571264'
    calls = []
    def handler(request):
        body = json.loads(request.content)
        calls.append(request.url.path)
        assert request.headers['Authorization'] == 'Bearer test-only'
        if request.url.path == '/image/v3/make/imageToVideo':
            assert body['videoType'] == 'doubao-seedance-2-0-mini'
            assert body['imageList'] == ['https://example.com/input.png']
            assert 'isPro' not in body and 'camera' not in body
            return httpx.Response(200, json={'code': 200, 'data': {'id': task_id}})
        assert body == {'id': task_id}
        return httpx.Response(200, json={'code': 200, 'data': {'id': task_id, 'status': 3,
            'count': 35, 'resultList': [{'url': 'https://example.com/result.mp4'}]}})
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            submitted = await lf.submit_task({'entry': 'img2video', 'mode': 'reference',
                'imageList': ['https://example.com/input.png'], 'videoType': 'seedance2.0mini',
                'videoTime': 5, 'resolution': '480p', 'aspectRatio': '16:9'},
                client=client, api_key='test-only', gateway='https://tool-gateway.linkfox.com')
            assert submitted['upstream_task_id'] == task_id
            queried = await lf.query_task(task_id, client=client, api_key='test-only', gateway=submitted['base_url'])
            assert queried['status'] == 'succeeded'
            assert queried['credits_consumed'] == 35
            assert queried['url'] == 'https://example.com/result.mp4'
    asyncio.run(exercise())
    assert calls == ['/image/v3/make/imageToVideo', '/image/v2/make/info']


@pytest.mark.parametrize('body,expected', [
    ({'code': 200, 'data': {'total': 100, 'usage': 35, 'expireTime': 20270904}}, 65),
    ({'code': 200, 'data': {'total': 100, 'usage': 100}}, 0),
    ({'code': 401, 'msg': 'unauthorized'}, None),
    ({'code': 200, 'data': {'total': 100, 'usage': '35'}}, None),
])
def test_linkfox_balance_never_invents_unknown_points(monkeypatch, body, expected):
    original_client = httpx.AsyncClient
    def handler(request):
        assert request.url.path == '/v1/userPlan/info'
        assert request.headers['Authorization'] == 'Bearer test-only'
        return httpx.Response(200, json=body)
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(main, 'linkfox_configured_key', lambda: 'test-only')
    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **kwargs: original_client(transport=transport, **kwargs))
    result = asyncio.run(main.linkfox_balance())
    assert result['remaining_points'] == expected
    assert result['available'] == (expected is not None)


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


def test_dedicated_node_uses_shared_adapter_when_frontend_requests_it(task_state, monkeypatch):
    submit = AsyncMock(return_value={
        'upstream_task_id': 'adapted-1', 'base_url': 'https://gateway.invalid'})
    monkeypatch.setattr(main, 'submit_canvas_video_upstream', submit)
    async def adapt(payload, provider):
        return payload.model_copy(update={'prompt': 'Seedance 2.0 实际提交词'}), {
            'original_prompt': payload.prompt,
            'prompt_adaptation': {'profile': 'seedance', 'status': 'adapted'},
        }
    main.prepare_video_generation_prompt.side_effect = adapt
    payload = main.CanvasVideoTaskRequest(
        task_id='canvas_video_direct_adapt', provider_id='linkfox', model='seedance2.0',
        linkfox_direct=True, prompt='原始创意', auto_adapt_prompt=True,
        prompt_origin_key='direct-origin', images=[main.AIReference(url='/ref.png')],
    )
    task = asyncio.run(main.create_canvas_video_task(payload))
    main.prepare_video_generation_prompt.assert_awaited_once()
    assert submit.await_args.args[0].prompt == 'Seedance 2.0 实际提交词'
    assert task['request']['original_prompt'] == '原始创意'
    assert task['request']['prompt_adaptation']['profile'] == 'seedance'


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
