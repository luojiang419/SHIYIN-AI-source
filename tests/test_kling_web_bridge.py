import time
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from canvas_core.kling_web_bridge import DraftQueue, WebResult, create_router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(create_router(lambda request: SimpleNamespace(account_id=request.headers.get('x-test-account', 'one'))))
    return TestClient(app)


def test_draft_fill_roundtrip_and_owner_isolation(client):
    draft = client.post('/api/kling-web/drafts', json={'prompt': '参考视频1和图片1', 'references': [
        {'url': '/assets/uploads/a.mp4', 'kind': 'video'}, {'url': '/assets/uploads/b.png', 'kind': 'image'}]}).json()
    key = draft['id']
    assert 'owner' not in draft and 'lease' not in draft
    assert client.get(f'/api/kling-web/drafts/{key}', headers={'x-test-account':'two'}).status_code == 404
    assert client.post('/api/kling-web/claim', headers={'x-test-account':'two'}).json()['draft'] is None
    claimed = client.post('/api/kling-web/claim').json()['draft']
    assert claimed['id'] == key
    assert client.post('/api/kling-web/claim').json()['draft'] is None
    assert client.delete(f'/api/kling-web/drafts/{key}').status_code == 409
    assert client.post(f'/api/kling-web/drafts/{key}/result', json={'lease':'wrong', 'status':'filled'}).status_code == 409
    assert client.post(f'/api/kling-web/drafts/{key}/result', json={'lease':claimed['lease'], 'status':'generated'}).status_code == 422
    assert client.post(f'/api/kling-web/drafts/{key}/result', json={'lease':claimed['lease'], 'status':'filled'}).json()['status'] == 'filled'
    assert client.get(f'/api/kling-web/drafts/{key}').json()['status'] == 'filled'


@pytest.mark.parametrize('url,kind', [
    ('https://example.com/a.mp4','video'), ('file:///C:/private.png','image'),
    ('//example.com/a.mp4','video'), ('/api/admin/secret','image'),
    ('/assets/../secret','image'), ('/assets/a.mp3','audio')])
def test_reject_unscoped_media(client, url, kind):
    assert client.post('/api/kling-web/drafts', json={'prompt':'test','references':[{'url':url,'kind':kind}]}).status_code == 422


def test_pending_conflict_and_cancel(client):
    draft = client.post('/api/kling-web/drafts', json={'prompt':'first'}).json()
    assert client.post('/api/kling-web/drafts', json={'prompt':'second'}).status_code == 409
    assert client.delete(f"/api/kling-web/drafts/{draft['id']}").json()['status'] == 'cancelled'
    assert client.post('/api/kling-web/claim').json()['draft'] is None
    assert client.post('/api/kling-web/drafts', json={'prompt':'second'}).status_code == 200


def test_atomic_claim_and_timeout_does_not_retry():
    queue = DraftQueue()
    item = queue.create('one', {'prompt':'test'})
    with ThreadPoolExecutor(max_workers=8) as pool:
        claims = list(pool.map(lambda _: queue.claim('one'), range(8)))
    assert sum(x is not None for x in claims) == 1
    queue.items[item['id']]['claimed_at'] = time.time() - 301
    assert queue.claim('one') is None
    assert queue.get('one', item['id'])['status'] == 'failed'
