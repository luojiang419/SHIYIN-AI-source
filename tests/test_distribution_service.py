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
from distribution.service import Center, atomic_json, relative_path


def snapshot(root, content=b'new', version='20260914180000'):
    path=root/'files/app/web/index.html'
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    atomic_json(root/'manifest.json', {'protocol_version':2,'version':version,'min_desktop_version':'1.0.446',
        'prune_roots':['app/web'],'files':[{'path':'app/web/index.html','size':len(content),'sha256':hashlib.sha256(content).hexdigest()}]})
    return root


def package_snapshot(root, content=b'packaged-update', version='20260915130001'):
    root.mkdir(parents=True)
    name=f'SHIYIN-Hot-Update-{version}.shiyin-update'
    package=root/name
    path='app/web/index.html'
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(path,content)
    atomic_json(root/'manifest.json', {'protocol_version':3,'version':version,'min_desktop_version':'1.0.447',
        'prune_roots':['app/web'],'files':[{'path':path,'size':len(content),'sha256':hashlib.sha256(content).hexdigest()}],
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


def test_signed_catalog_range_and_legacy_guard(server,tmp_path):
    c,url=server;c.import_release(snapshot(tmp_path/'snapshot'),'hot','说明')
    with get(url+'/v1/catalog',{'X-Shiyin-Version':'1.0.446'}) as r: env=json.load(r)
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(env['public_key'])).verify(bytes.fromhex(env['signature']),env['payload'].encode())
    manifest=json.loads(env['payload']);assert manifest['notes']=='说明'
    sha=manifest['files'][0]['sha256']
    with get(url+'/v1/blobs/'+sha,{'Range':'bytes=1-2'}) as r:
        assert r.status==206 and r.read()==b'ew'
        assert r.headers['Content-Range']=='bytes 1-2/3'
    with pytest.raises(urllib.error.HTTPError) as err: get(url+'/hot-update/manifest.json')
    assert err.value.code==409
    assert len(c.status()['clients'])==1


def test_package_capability_routes_new_and_legacy_clients(server,tmp_path):
    c,url=server
    packaged=package_snapshot(tmp_path/'package')
    c.import_release(packaged,'hot','单包')
    with get(url+'/v1/catalog') as response:
        assert json.load(response)=={'release':None}
    with get(url+'/v1/catalog',{'X-Shiyin-Capabilities':'package-v3'}) as response:
        envelope=json.load(response)
    manifest=json.loads(envelope['payload'])
    assert manifest['protocol_version']==3 and manifest['package']['name'].endswith('.shiyin-update')
    package=manifest['package']
    with get(url+'/v1/blobs/'+package['sha256'],{'Range':'bytes=1-'}) as response:
        assert response.status==206 and len(response.read())==package['size']-1
    c.import_release(bootstrap_snapshot(tmp_path/'bootstrap'),'hot-bootstrap','引导')
    with get(url+'/v1/catalog') as response:
        legacy=json.loads(json.load(response)['payload'])
    with get(url+'/v1/catalog',{'X-Shiyin-Capabilities':'package-v3'}) as response:
        modern=json.loads(json.load(response)['payload'])
    assert legacy['protocol_version']==2 and legacy['files'][0]['path']=='SHIYIN AI.exe'
    assert modern['protocol_version']==3


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
