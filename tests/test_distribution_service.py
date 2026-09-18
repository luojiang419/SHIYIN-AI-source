import hashlib
import json
from pathlib import Path
import threading
import urllib.request
import urllib.error
import zipfile
from http.server import ThreadingHTTPServer

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from distribution.service import Center, MAX_SERVICE_LOGS, atomic_json, relative_path


def snapshot(root, content=b'new', version='20260914180000'):
    path=root/'files/app/web/index.html'
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    atomic_json(root/'manifest.json', {'protocol_version':2,'version':version,'min_desktop_version':'1.0.446',
        'prune_roots':['app/web'],'files':[{'path':'app/web/index.html','size':len(content),'sha256':hashlib.sha256(content).hexdigest()}]})
    return root


def package_snapshot(root, content=b'packaged-update', version='20260915130001', full=False):
    root.mkdir(parents=True)
    name=f'SHIYIN-Hot-Update-{version}.shiyin-update'
    package=root/name
    contents={'app/web/index.html':content}
    if full:
        contents.update({'SHIYIN AI.exe':b'desktop-'+content,
                         'app/backend/canvas-backend/canvas-backend.exe':b'backend-'+content})
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path, value in contents.items(): archive.writestr(path,value)
    atomic_json(root/'manifest.json', {'protocol_version':3,'version':version,'min_desktop_version':'2.0.0',
        'prune_roots':['app/web'] + (['app/backend/canvas-backend'] if full else []),
        'files':[{'path':path,'size':len(value),'sha256':hashlib.sha256(value).hexdigest()} for path,value in contents.items()],
        'package':{'name':name,'size':package.stat().st_size,'sha256':hashlib.sha256(package.read_bytes()).hexdigest()}})
    return root


def bootstrap_snapshot(root, content=b'new-updater', version='20260915130000'):
    path=root/'files/SHIYIN AI.exe'
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    atomic_json(root/'manifest.json', {'protocol_version':2,'version':version,'min_desktop_version':'1.0.447',
        'prune_roots':[],'files':[{'path':'SHIYIN AI.exe','size':len(content),'sha256':hashlib.sha256(content).hexdigest()}]})
    return root


@pytest.fixture
def server(tmp_path):
    center=Center(tmp_path/'data')
    http=ThreadingHTTPServer(('127.0.0.1',0),center.handler(False))
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    yield center, f'http://127.0.0.1:{http.server_port}'
    http.shutdown();http.server_close();thread.join()


def get(url,headers=None):
    return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(urllib.request.Request(url,headers=headers or {}))


def test_service_logs_are_bounded_and_trimmed_on_startup(tmp_path):
    data = tmp_path / 'data'
    center = Center(data)
    for index in range(MAX_SERVICE_LOGS + 25):
        center.log(f'entry-{index}')
    with center.db() as db:
        assert db.execute('SELECT COUNT(*) FROM logs').fetchone()[0] == MAX_SERVICE_LOGS
        assert db.execute('SELECT message FROM logs ORDER BY created ASC LIMIT 1').fetchone()[0] == 'entry-25'

    # Simulate an older build that left excess rows behind; startup trims them.
    with center.db() as db:
        db.executemany('INSERT INTO logs VALUES (?, ?)', [(0, f'old-{i}') for i in range(30)])
    restarted = Center(data)
    with restarted.db() as db:
        assert db.execute('SELECT COUNT(*) FROM logs').fetchone()[0] == MAX_SERVICE_LOGS


def test_signed_catalog_range_and_legacy_guard(server,tmp_path):
    c,url=server;c.import_release(package_snapshot(tmp_path/'snapshot',b'new'),'hot','说明')
    assert c.status()['releases'][0]['notes'] == '说明'
    assert 'manifest' not in c.status()['releases'][0]
    with get(url+'/v1/catalog',{'X-Shiyin-Version':'2.0.0 / 20260914170000','X-Shiyin-Capabilities':'package-v3,fast-extract-v1'}) as r: env=json.load(r)
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(env['public_key'])).verify(bytes.fromhex(env['signature']),env['payload'].encode())
    manifest=json.loads(env['payload']);assert manifest['notes']=='说明'
    sha=manifest['package']['sha256']
    package=(tmp_path/'snapshot'/manifest['package']['name']).read_bytes()
    with get(url+'/v1/blobs/'+sha,{'Range':'bytes=1-2'}) as r:
        assert r.status==206 and r.read()==package[1:3]
        assert r.headers['Content-Range']==f'bytes 1-2/{len(package)}'
    with pytest.raises(urllib.error.HTTPError) as err: get(url+'/hot-update/manifest.json')
    assert err.value.code==409
    assert len(c.status()['clients'])==1
    assert c.status()['clients'][0]['update_state']=='outdated'


def test_status_includes_notes_for_archived_releases(tmp_path):
    center = Center(tmp_path/'data')
    center.import_release(package_snapshot(tmp_path/'first', version='20260914180000'), 'hot', '首版说明')
    center.import_release(package_snapshot(tmp_path/'second', version='20260914190000'), 'hot', '新版说明')
    releases = center.status()['releases']
    assert [(item['state'], item['notes']) for item in releases] == [
        ('published', '新版说明'), ('archived', '首版说明')]


def test_v2_baseline_replaces_legacy_upgrade_chain(server,tmp_path):
    c,url=server
    c.import_release(package_snapshot(tmp_path/'package'),'hot','2.0完整更新')
    exe=tmp_path/'SHIYIN-AI-Setup-2.0.0.exe';exe.write_bytes(b'installer-fixture');c.import_release(exe,'full')
    for desktop,capability in [('', ''),('1.0.447','package-v3,fast-extract-v1'),('2.0.0','package-v3'),('bad','package-v3,fast-extract-v1')]:
        with get(url+'/v1/catalog',{'X-Shiyin-Version':desktop,'X-Shiyin-Capabilities':capability}) as r:
            assert json.load(r)=={'release':None}
    with get(url+'/update/manifest.json') as r:
        assert json.load(r)['tag_name']=='v2.0.0'
    with get(url+'/') as r:
        html=r.read().decode();assert exe.name in html and '/SHIYIN-Hot-Update.exe' not in html
    with pytest.raises(urllib.error.HTTPError) as error:get(url+'/SHIYIN-Hot-Update.exe')
    assert error.value.code==410
    with get(url+'/v1/catalog',{'X-Shiyin-Version':'2.0.0 / 20260914170000','X-Shiyin-Capabilities':'package-v3,fast-extract-v1'}) as r:
        env=json.load(r)
    key=Ed25519PublicKey.from_public_bytes(bytes.fromhex(env['public_key']))
    key.verify(bytes.fromhex(env['signature']),env['payload'].encode())
    key.verify(bytes.fromhex(env['plan_signature']),env['plan_payload'].encode())
    manifest=json.loads(env['payload']);assert manifest['min_desktop_version']=='2.0.0'
    assert json.loads(env['plan_payload'])['target_version']==manifest['version']
    with get(url+'/v1/blobs/'+manifest['package']['sha256'],{'Range':'bytes=1-'}) as r:
        assert r.status==206 and len(r.read())==manifest['package']['size']-1
    for kind in ('hot-bootstrap','hot-updater'):
        with pytest.raises(ValueError,match='旧更新器发布路线已停用'):c.import_release(tmp_path/'package',kind)


def test_catalog_uses_latest_full_checkpoint_before_current_web_release(server,tmp_path):
    center,url=server
    checkpoint='20260915130001';target='20260915140000'
    center.import_release(package_snapshot(tmp_path/'checkpoint',b'checkpoint',checkpoint,full=True),'hot')
    center.import_release(package_snapshot(tmp_path/'target',b'latest-web',target),'hot')
    headers={'X-Shiyin-Version':'2.0.1 / 20260915120000','X-Shiyin-Capabilities':'package-v3,fast-extract-v1'}
    with get(url+'/v1/catalog',headers) as response: first=json.load(response)
    assert json.loads(first['payload'])['version']==checkpoint
    assert json.loads(first['plan_payload'])['target_version']==target
    headers['X-Shiyin-Version']='2.0.1 / '+checkpoint
    with get(url+'/v1/catalog',headers) as response: second=json.load(response)
    assert json.loads(second['payload'])['version']==target
    assert json.loads(second['plan_payload'])['target_version']==target
    headers['X-Shiyin-Version']='2.0.1 / '+target
    with get(url+'/v1/catalog',headers) as response: assert json.load(response)=={'release':None}


def test_package_import_rejects_corruption(server,tmp_path):
    c,_=server
    source=package_snapshot(tmp_path/'corrupt')
    package=next(source.glob('*.shiyin-update'))
    package.write_bytes(package.read_bytes()+b'corrupt')
    with pytest.raises(ValueError,match='增量包'):
        c.import_release(source,'hot')


def test_public_api_cannot_mutate(server):
    c,url=server
    req=urllib.request.Request(url+'/api/stop',data=b'{}',headers={'Authorization':'Bearer '+c.token})
    with pytest.raises(urllib.error.HTTPError) as err: urllib.request.urlopen(req)
    assert err.value.code==403


def test_bug_reports_are_partitioned_and_admin_only(server, tmp_path):
    center, url = server
    payload = {'clientId': 'client_12345678', 'kind': 'error', 'summary': 'CUDA failed',
               'version': '1.0.447', 'details': {'error': 'no kernel image'},
               'machine': {'cpu': [{'Name': 'Test CPU'}], 'nvidiaGpus': ['Test GPU, 555.55, 8192, 7.5']}}
    request = urllib.request.Request(url+'/v1/bug-reports', data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request) as response:
        assert response.status == 201
        report_id = json.load(response)['id']
    file = center.data/'bug-logs/admin/client_12345678'/f'{report_id}.json'
    assert json.loads(file.read_text('utf-8'))['details']['error'] == 'no kernel image'
    assert center.bug_reports('client_12345678')[0]['summary'] == 'CUDA failed'
    device = center.bug_device('admin', 'client_12345678')
    assert device['machine']['nvidiaGpus'][0].startswith('Test GPU')
    assert (file.parent/'device.json').is_file()
    bad = dict(payload, clientId='../secret')
    request = urllib.request.Request(url+'/v1/bug-reports', data=json.dumps(bad).encode(), method='POST')
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request)
    assert error.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as error: get(url+'/api/bug-reports/'+report_id)
    assert error.value.code == 404


def test_bug_device_admin_endpoint_requires_token(tmp_path):
    center = Center(tmp_path/'data')
    center.receive_bug_report({'clientId': 'client_12345678', 'userId': 'user_abc',
        'kind': 'heartbeat', 'machine': {'memory': {'totalBytes': 123}}}, '127.0.0.1')
    http = ThreadingHTTPServer(('127.0.0.1', 0), center.handler(True))
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        url = f'http://127.0.0.1:{http.server_port}/api/bug-devices/user_abc/client_12345678'
        with pytest.raises(urllib.error.HTTPError) as error: get(url)
        assert error.value.code == 403
        with get(url, {'Authorization': 'Bearer '+center.token}) as response:
            assert json.load(response)['machine']['memory']['totalBytes'] == 123
    finally:
        http.shutdown(); http.server_close(); thread.join()


def test_import_rejects_corruption_without_changing_active(tmp_path):
    c=Center(tmp_path/'data');first=snapshot(tmp_path/'one');c.import_release(first,'hot')
    before=c.active('hot')['id']
    second=snapshot(tmp_path/'two',version='20260914180001')
    (second/'files/app/web/index.html').write_bytes(b'bad')
    with pytest.raises(ValueError):c.import_release(second,'hot')
    assert c.active('hot')['id']==before
    with pytest.raises(ValueError):c.import_release(first,'hot')


@pytest.mark.parametrize('path',['../secret','/absolute','app/web/../secret','app/web/a:stream','app/web/space.','data/config/app.json'])
def test_hot_paths_are_confined(path):
    with pytest.raises(ValueError):relative_path(path,hot=True)


def test_component_and_full_download(server,tmp_path):
    c,url=server
    folder=tmp_path/'component';folder.mkdir();(folder/'model.bin').write_bytes(b'model')
    c.import_release(folder,'video-depth')
    with get(url+'/video-depth/manifest.json') as r: assert json.load(r)['component']=='video-depth'
    with get(url+'/video-depth/files/model.bin') as r: assert r.read()==b'model'
    exe=tmp_path/'SHIYIN-AI-Setup-1.0.447.exe';exe.write_bytes(b'installer-fixture');c.import_release(exe,'full')
    with get(url+'/update/manifest.json') as r: release=json.load(r)
    assert release['tag_name']=='v1.0.447'
    with get(url+'/update/files/'+exe.name+'.sha256') as r: assert hashlib.sha256(exe.read_bytes()).hexdigest().encode() in r.read()


def test_admin_requires_token_and_restart_preserves_data(tmp_path):
    c=Center(tmp_path/'data');http=ThreadingHTTPServer(('127.0.0.1',0),c.handler(True));thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    try:
        url=f'http://127.0.0.1:{http.server_port}'
        with pytest.raises(urllib.error.HTTPError) as err:get(url+'/api/status')
        assert err.value.code==403
        with get(url+'/api/status',{'Authorization':'Bearer '+c.token}) as r: assert json.load(r)['releases']==[]
        c.import_release(snapshot(tmp_path/'snapshot'),'hot')
        restored=Center(tmp_path/'data');assert restored.public_key==c.public_key and restored.active('hot')
    finally:http.shutdown();http.server_close();thread.join()


def test_computer_identity_and_heartbeat_preserve_hardware(tmp_path):
    center = Center(tmp_path/'data')
    payload = {'clientId': 'client_identity01', 'userId': 'admin', 'kind': 'heartbeat',
               'computerUser': '江同学', 'computerName': 'OFFICE-PC',
               'machine': {'memory': {'totalBytes': 1024}}}
    center.receive_bug_report(payload, '192.168.0.24')
    first = center.bug_devices()[0]['updated']
    center.receive_bug_report({'clientId': 'client_identity01', 'kind': 'heartbeat'}, '192.168.0.25')
    row = center.bug_devices()[0]
    assert row['computer_user'] == '江同学'
    assert row['computer_name'] == 'OFFICE-PC'
    assert row['ip'] == '192.168.0.25'
    assert row['updated'] >= first
    assert center.bug_device('admin', 'client_identity01')['machine']['memory']['totalBytes'] == 1024
    # New installation IDs remain available for historical logs; the UI groups them.
    center.receive_bug_report(dict(payload, clientId='client_identity02'), '192.168.0.25')
    assert len(center.bug_devices()) == 2


def test_legacy_device_table_migrates_without_losing_records(tmp_path):
    import sqlite3
    root = tmp_path/'data'
    root.mkdir()
    with sqlite3.connect(root/'index.db') as db:
        db.execute('CREATE TABLE bug_devices (user_id TEXT,client_id TEXT,updated REAL,ip TEXT,file TEXT,PRIMARY KEY(user_id,client_id))')
        db.execute("INSERT INTO bug_devices VALUES ('admin','old_client_id',123,'192.168.0.53','old.json')")
    center = Center(root)
    row = center.bug_devices()[0]
    assert row['client_id'] == 'old_client_id'
    assert row['computer_user'] == row['computer_name'] == ''
