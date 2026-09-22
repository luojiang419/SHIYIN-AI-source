"""默认热更新构建：只编译发生变化的组件，不运行全量安装器。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from distribution.service import atomic_json, digest, DEFAULT_DATA

DEFAULT_HOT_UPDATE_MIN_DESKTOP_VERSION = '2.0.4'


def version_tuple(value):
    if not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('桌面版本格式无效')
    return tuple(map(int, value.split('.')))


def assert_active_client_compatibility(status, minimum_version):
    minimum = version_tuple(minimum_version)
    incompatible = []
    for client in status.get('clients', []):
        desktop = str(client.get('version') or '').split('/', 1)[0].strip()
        if re.fullmatch(r'\d+\.\d+\.\d+', desktop) and version_tuple(desktop) < minimum:
            incompatible.append(desktop)
    if incompatible:
        versions = ', '.join(sorted(set(incompatible)))
        raise ValueError(f'已联网客户端仍使用 {versions}，不能发布最低桌面版本为 {minimum_version} 的热更新；请先发布兼容更新或显式声明不兼容升级。')


def distribution_status(admin_port, token):
    request = urllib.request.Request(
        f'http://127.0.0.1:{admin_port}/api/status',
        headers={'Authorization': 'Bearer ' + token},
    )
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=15) as response:
        return json.load(response)


def fingerprint(paths):
    h = hashlib.sha256()
    for path in sorted(set(paths)):
        if path.is_file() and '__pycache__' not in path.parts:
            h.update(str(path.relative_to(ROOT)).encode()); h.update(path.read_bytes())
    return h.hexdigest()


def run(command):
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--version', default=time.strftime('%Y%m%d%H%M%S'))
    parser.add_argument('--notes', default='局域网热更新：功能优化与问题修复')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--web-only', action='store_true')
    parser.add_argument('--bootstrap', action='store_true', help='只发布兼容旧客户端的桌面更新器')
    parser.add_argument('--updater-only', action='store_true', help='发布新版客户端可用的更新器修复小包')
    parser.add_argument('--allow-incompatible-clients', action='store_true', help='允许高于已联网客户端宿主版本的不兼容升级')
    parser.add_argument('--admin-port', type=int, default=3013)
    parser.add_argument(
        '--min-desktop-version',
        default=DEFAULT_HOT_UPDATE_MIN_DESKTOP_VERSION,
        help='可应用此热更新的最低桌面宿主版本',
    )
    args=parser.parse_args()
    if len(args.version)!=14 or not args.version.isdigit(): raise ValueError('热更新版本需14位时间戳')
    version_tuple(args.min_desktop_version)
    cache=ROOT/'.build/hot-build.json'
    state=json.loads(cache.read_text('utf-8')) if cache.exists() else {}
    desktop_files=list((ROOT/'src-tauri/src').rglob('*.rs'))+list((ROOT/'src-tauri').glob('*.toml'))+list((ROOT/'src-tauri').glob('*.json'))+list((ROOT/'desktop-placeholder').rglob('*'))+[ROOT/'src-tauri/distribution-public-key.hex',ROOT/'src-tauri/build.rs']
    backend_files=list((ROOT/'canvas_core').rglob('*.py'))+list((ROOT/'canvas_core').glob('*.json'))+[ROOT/'main.py',ROOT/'backend_entry.py',ROOT/'canvas-backend.spec',ROOT/'canvas_core/distribution-public-key.hex']
    desktop_files.append(ROOT/'src-tauri/distribution-baseline.txt')
    desktop_hash=fingerprint(desktop_files); backend_hash=fingerprint(backend_files)
    desktop=ROOT/'src-tauri/target/release/SHIYIN-AI.exe'
    backend=ROOT/'dist/hot-backend/canvas-backend'
    if sum((args.bootstrap, args.updater_only, args.web_only)) > 1:
        raise ValueError('--bootstrap、--updater-only 与 --web-only 不能同时使用')
    if not args.web_only:
        if state.get('desktop')!=desktop_hash or not desktop.exists():
            run(['cargo','build','--release','--manifest-path','src-tauri/Cargo.toml']);state['desktop']=desktop_hash
        if not args.bootstrap and not args.updater_only and (state.get('backend')!=backend_hash or not (backend/'canvas-backend.exe').exists()):
            # PyInstaller可能把语法错误的main当成不可导入模块而继续产出EXE。
            run([sys.executable,'-m','compileall','-q','main.py','backend_entry.py','canvas_core'])
            run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath','dist/hot-backend','--workpath','.build/hot-backend','canvas-backend.spec']);state['backend']=backend_hash
    snapshot=ROOT/'dist/hot-update'/args.version
    snapshot.mkdir(parents=True,exist_ok=False)
    files=snapshot/'files'
    roots=[]
    if args.bootstrap:
        files.mkdir()
        shutil.copy2(desktop,files/'SHIYIN AI.exe')
    elif args.updater_only:
        files.mkdir()
        shutil.copy2(desktop,files/'SHIYIN AI.exe')
        target=files/'app/web/js/desktop-updater.js'
        target.parent.mkdir(parents=True)
        shutil.copy2(ROOT/'static/js/desktop-updater.js',target)
        for path in (ROOT/'static').rglob('*.html'):
            target=files/'app/web'/path.relative_to(ROOT/'static')
            target.parent.mkdir(parents=True,exist_ok=True)
            html=path.read_text('utf-8')
            html=re.sub(r'([?&]v=)[^\s\"\'&<>]+',lambda m:m[1]+args.version,html)
            target.write_text(html,encoding='utf-8')
    else:
        shutil.copytree(ROOT/'static',files/'app/web',ignore=shutil.ignore_patterns('prototypes'))
        # 用发布序号统一静态资源缓存参数，避免重启后 WebView 仍读取旧脚本。
        for path in (files/'app/web').rglob('*.html'):
            html=path.read_text('utf-8')
            html=re.sub(r'([?&]v=)[^\s\"\'&<>]+',lambda m:m[1]+args.version,html)
            path.write_text(html,encoding='utf-8')
        roots=['app/web']
        if not args.web_only:
            shutil.copytree(backend,files/'app/backend/canvas-backend')
            shutil.copy2(desktop,files/'SHIYIN AI.exe')
            roots.append('app/backend/canvas-backend')
    manifest={'protocol_version':2 if args.bootstrap else 3,'version':args.version,'min_desktop_version':args.min_desktop_version,'notes':args.notes,'prune_roots':roots,'files':[]}
    for path in sorted(files.rglob('*')):
        if path.is_file():manifest['files'].append({'path':path.relative_to(files).as_posix(),'size':path.stat().st_size,'sha256':digest(path)})
    if not args.bootstrap:
        package_name=f'SHIYIN-Hot-Update-{args.version}.shiyin-update'
        package=snapshot/package_name
        with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
            for item in manifest['files']:
                info=zipfile.ZipInfo(item['path'],date_time=(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                info.create_system=3
                info.external_attr=0o100644 << 16
                with (files/Path(item['path'])).open('rb') as source, archive.open(info,'w',force_zip64=True) as target:
                    shutil.copyfileobj(source,target,1024*1024)
        manifest['package']={'name':package_name,'size':package.stat().st_size,'sha256':digest(package)}
    atomic_json(snapshot/'manifest.json',manifest)
    atomic_json(cache,state)
    if args.publish:
        token=(DEFAULT_DATA/'admin-token').read_text('ascii')
        if not args.allow_incompatible_clients:
            assert_active_client_compatibility(distribution_status(args.admin_port, token), args.min_desktop_version)
        kind='hot-bootstrap' if args.bootstrap else 'hot-updater' if args.updater_only else 'hot'
        body=json.dumps({'source':str(snapshot),'kind':kind,'notes':args.notes}).encode()
        request=urllib.request.Request(f'http://127.0.0.1:{args.admin_port}/api/import',data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=15) as response: response.read()
    run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','tools/clean-development-cache.ps1'])
    print(json.dumps({'snapshot':str(snapshot),'files':len(manifest['files']),'version':args.version,'publish_requested':args.publish},ensure_ascii=False))


if __name__=='__main__': main()
