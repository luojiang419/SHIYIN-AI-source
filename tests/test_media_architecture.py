import asyncio
import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from starlette.requests import Request

import main
from canvas_core.account_storage import account_scope, current_account_id
from canvas_core.database import CanvasDatabase
from canvas_core.media_integrity import image_content_info
from canvas_core.works_snapshot import WorksSnapshotCache, database_stamp


def image_bytes(fmt='PNG'):
    buffer = io.BytesIO()
    Image.new('RGB', (32, 32), 'red').save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.mark.parametrize('body', [b'<html>expired</html>', b'{"error":"expired"}', b'', image_bytes()[:40]])
def test_invalid_image_never_published(tmp_path, body):
    with patch.object(main, 'OUTPUT_OUTPUT_DIR', str(tmp_path)):
        with pytest.raises(ValueError):
            main.write_image_bytes_to_output(body, '.png', prefix='', category='output', enterprise_filename=True)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('fmt,extension', [('PNG','.png'),('JPEG','.jpg'),('WEBP','.webp')])
def test_actual_bytes_override_false_extension_and_mime(tmp_path, fmt, extension):
    with patch.object(main, 'OUTPUT_OUTPUT_DIR', str(tmp_path)), patch.object(main, 'register_internal_media_object'):
        url = main.write_image_bytes_to_output(image_bytes(fmt), '.html', prefix='', category='output', enterprise_filename=True)
        path = tmp_path / Path(url).name
        assert path.suffix == extension
        assert image_content_info(path.read_bytes())[0] == extension
    assert not list(tmp_path.glob('*.tmp'))


@pytest.mark.parametrize('extension,expected', [('.html','.png'),('.png_x','.png'),('.jpeg_x','.jpg'),('.mp4','.mp4')])
def test_work_names_use_standard_media_extensions(extension, expected):
    work = {'url':'/assets/output/a'+extension,'original_name':'SHIYIN-000002-20260910'+extension}
    assert main.work_file_extension(work) == expected
    assert main.work_display_name(work).endswith(expected)


def test_preview_executor_inherits_owner_and_creates_owner_cache(tmp_path):
    source = tmp_path/'source.png'
    source.write_bytes(image_bytes())
    owner_cache = tmp_path/'new-owner'/'previews'/'one.webp'
    original = main.build_media_preview
    def build(*args):
        assert current_account_id() == 'owner-b'
        return original(*args)
    async def run():
        with account_scope('owner-b'), patch.object(main,'build_media_preview',side_effect=build):
            return await main.get_or_build_media_preview(str(source),512,str(owner_cache),str(owner_cache.with_suffix('.png')))
    assert asyncio.run(run())[0] == str(owner_cache)
    assert owner_cache.is_file()


def test_cancelled_consumer_does_not_cancel_shared_preview(tmp_path):
    calls = []
    def build(*args):
        calls.append(1)
        time.sleep(.08)
        return ('ok','image/webp')
    async def run():
        with patch.object(main,'build_media_preview',side_effect=build):
            args = ('source',512,str(tmp_path/'shared.webp'),'shared.png')
            first = asyncio.create_task(main.get_or_build_media_preview(*args))
            second = asyncio.create_task(main.get_or_build_media_preview(*args))
            await asyncio.sleep(.01)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            assert await second == ('ok','image/webp')
    asyncio.run(run())
    assert len(calls) == 1


def test_works_route_does_not_block_event_loop_and_keeps_owner():
    caller = threading.get_ident()
    def query(*args):
        assert threading.get_ident() != caller
        assert current_account_id() == 'owner-b'
        time.sleep(.06)
        return {'works':[]}
    async def run():
        with account_scope('owner-b'), patch.object(main,'list_generated_works_sync',side_effect=query):
            task = asyncio.create_task(main.list_generated_works())
            await asyncio.sleep(.005)
            assert not task.done()
            return await task
    assert asyncio.run(run()) == {'works':[]}


def test_snapshot_is_single_flight_copy_isolated_and_invalidates():
    cache = WorksSnapshotCache()
    version = [1]
    calls = []
    def build():
        calls.append(1)
        time.sleep(.015)
        return [{'name':'original'}]
    def get():
        return cache.get('a',lambda:version[0],build)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _:get(),range(8)))
    assert len(calls) == 1
    results[0][0]['name'] = 'changed'
    assert get()[0]['name'] == 'original'
    version[0] = 2
    get()
    assert len(calls) == 2
    cache.get('b',lambda:2,build)
    assert len(calls) == 3


def test_snapshot_stamp_changes_after_database_commit(tmp_path):
    db = CanvasDatabase(tmp_path/'canvas.db')
    db.initialize()
    before = database_stamp(db.path)
    db.put_document('test','test',{'value':1})
    assert database_stamp(db.path) != before


def test_same_canvas_id_and_revision_are_isolated_by_database(tmp_path):
    db_a, db_b = CanvasDatabase(tmp_path/'a.db'), CanvasDatabase(tmp_path/'b.db')
    main.CANVAS_ASSETS_INDEX_CACHE['items_by_canvas'] = {}
    for db, url in [(db_a,'a.png'),(db_b,'b.png')]:
        db.initialize()
        db.save_canvas({'id':'same','nodes':[{'id':'n','type':'image','url':'/assets/output/'+url}],'connections':[]})
    with patch.object(main,'DATABASE',db_a):
        first = main.canvas_assets_index()['items']
    with patch.object(main,'DATABASE',db_b):
        second = main.canvas_assets_index()['items']
    assert any(item['url'].endswith('a.png') for item in first)
    assert any(item['url'].endswith('b.png') for item in second)
    assert not any(item['url'].endswith('a.png') for item in second)


def test_remote_download_never_uses_same_local_basename():
    class Remote:
        headers = {'content-type':'text/html'}
        closed = False
        def raise_for_status(self): pass
        def close(self): self.closed = True
    remote = Remote()
    request = Request({'type':'http','headers':[]})
    with patch.object(main,'local_media_file_by_basename') as fallback, patch.object(main.requests,'get',return_value=remote):
        with pytest.raises(main.HTTPException) as error:
            main.download_output(request,'https://example.test/a.png',inline=True)
    assert error.value.status_code == 415
    fallback.assert_not_called()
    assert remote.closed


def test_research_websites_are_not_canvas_image_assets():
    canvas = {'id':'research','nodes':[{'id':'n','type':'image','url':'/assets/output/real.png',
        'research':[{'url':'https://example.test/campaign.html','kind':'image'},
                    {'url':'https://example.test/campaigns'},
                    {'url':'https://example.test/valid.png_x'}]}]}
    items = main.extract_canvas_assets(canvas)
    assert {item['url'] for item in items} == {'/assets/output/real.png','https://example.test/valid.png_x'}


@pytest.mark.parametrize('timestamp',[1789020631.2760246,1789020631.2760243])
def test_fractional_timestamp_pagination_never_repeats_or_skips(tmp_path,timestamp):
    db = CanvasDatabase(tmp_path/'page.db')
    db.initialize()
    db.prepend_history({'id':'many','timestamp':timestamp,'images':[f'/assets/output/{i}.png' for i in range(1250)]})
    ids = []
    cursor = ''
    for _ in range(10):
        page = db.list_work_items(limit=120,cursor=cursor)
        ids.extend(item['id'] for item in page['items'])
        cursor = page['next_cursor']
    page = db.list_work_items(limit=120,cursor=cursor)
    ids.extend(item['id'] for item in page['items'])
    assert not page['next_cursor']
    assert len(ids) == len(set(ids)) == 1250


def test_real_http_preview_isolated_for_two_accounts_and_supports_304(tmp_path):
    import httpx
    from canvas_core.accounts import AccountStore
    from canvas_core.data_layout import DataLayout
    from canvas_core.account_storage import AccountStorageRegistry, ScopedDatabaseProxy, ScopedDataLayoutProxy, ScopedPath
    layout = DataLayout.from_root(tmp_path)
    layout.ensure()
    db = CanvasDatabase(layout.database_file)
    db.initialize()
    store = AccountStore(tmp_path)
    store.initialize()
    registry = AccountStorageRegistry(store, layout, db)
    identities = [store.register('fixtureA','test'), store.register('fixtureB','test')]
    for identity, color in zip(identities,['red','blue']):
        path = registry.layout_for(identity.account_id).media_generated/'same.png'
        Image.new('RGB',(80,80),color).save(path)
    async def run():
        with patch.multiple(main, ACCOUNT_STORE=store, ACCOUNT_STORAGE=registry,
            DATABASE=ScopedDatabaseProxy(registry), DATA_LAYOUT=ScopedDataLayoutProxy(registry),
            OUTPUT_OUTPUT_DIR=ScopedPath(lambda item:item.media_generated,registry),
            MEDIA_PREVIEW_DIR=ScopedPath(lambda item:item.cache_previews,registry)):
            results=[]
            for identity in identities:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://127.0.0.1') as client:
                    client.cookies.set(main.ACCOUNT_SESSION_COOKIE,store.create_session(identity))
                    response=await client.get('/api/media-preview',params={'url':'/assets/output/same.png','w':64})
                    assert response.status_code == 200
                    assert 'Cookie' in response.headers['vary']
                    results.append((Image.open(io.BytesIO(response.content)).getpixel((0,0)),response.headers['x-media-account']))
                    cached=await client.get('/api/media-preview',params={'url':'/assets/output/same.png','w':64},headers={'If-None-Match':response.headers['etag']})
                    assert cached.status_code == 304
            assert results[0][0][0]>200 and results[1][0][2]>200
            assert results[0][1] != results[1][1]
    asyncio.run(run())


def test_cache_budget_covers_accounts_without_deleting_originals(tmp_path):
    from canvas_core.data_layout import DataLayout
    from canvas_core.maintenance import MaintenanceManager
    layout = DataLayout.from_root(tmp_path)
    layout.ensure()
    layout.app_config.write_text('{"cache_max_bytes":1}')
    for root in [layout.cache,tmp_path/'accounts'/'owner'/'cache']:
        root.mkdir(parents=True,exist_ok=True)
        (root/'preview.webp').write_bytes(b'cache')
    original = tmp_path/'accounts'/'owner'/'media'/'generated'/'keep.png'
    original.parent.mkdir(parents=True)
    original.write_bytes(b'original')
    report = MaintenanceManager(layout)._trim_cache()
    assert report['remaining_bytes'] <= 1
    assert report['removed'] == 2
    assert original.read_bytes() == b'original'
