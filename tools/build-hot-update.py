"""默认热更新构建：只编译发生变化的组件，不运行全量安装器。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from distribution.service import atomic_json, digest, DEFAULT_DATA


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
    parser.add_argument('--admin-port', type=int, default=3013)
    args=parser.parse_args()
    if len(args.version)!=14 or not args.version.isdigit(): raise ValueError('热更新版本需14位时间戳')
    cache=ROOT/'.build/hot-build.json'
    state=json.loads(cache.read_text('utf-8')) if cache.exists() else {}
    desktop_files=list((ROOT/'src-tauri/src').rglob('*.rs'))+list((ROOT/'src-tauri').glob('*.toml'))+list((ROOT/'src-tauri').glob('*.json'))+list((ROOT/'desktop-placeholder').rglob('*'))+[ROOT/'src-tauri/distribution-public-key.hex',ROOT/'src-tauri/build.rs']
    backend_files=list((ROOT/'canvas_core').rglob('*.py'))+list((ROOT/'canvas_core').glob('*.json'))+[ROOT/'main.py',ROOT/'backend_entry.py',ROOT/'canvas-backend.spec',ROOT/'canvas_core/distribution-public-key.hex']
    desktop_files.append(ROOT/'src-tauri/distribution-baseline.txt')
    desktop_hash=fingerprint(desktop_files); backend_hash=fingerprint(backend_files)
    desktop=ROOT/'src-tauri/target/release/SHIYIN-AI.exe'
    backend=ROOT/'dist/hot-backend/canvas-backend'
    if not args.web_only:
        if state.get('desktop')!=desktop_hash or not desktop.exists():
            run(['cargo','build','--release','--manifest-path','src-tauri/Cargo.toml']);state['desktop']=desktop_hash
        if state.get('backend')!=backend_hash or not (backend/'canvas-backend.exe').exists():
            run([sys.executable,'-m','PyInstaller','--noconfirm','--distpath','dist/hot-backend','--workpath','.build/hot-backend','canvas-backend.spec']);state['backend']=backend_hash
    snapshot=ROOT/'dist/hot-update'/args.version
    snapshot.mkdir(parents=True,exist_ok=False)
    files=snapshot/'files'
    shutil.copytree(ROOT/'static',files/'app/web',ignore=shutil.ignore_patterns('prototypes'))
    # 用发布序号统一静态资源缓存参数，避免重启后 WebView 仍读取旧脚本。
    for path in (files/'app/web').rglob('*.html'):
        import re
        html=path.read_text('utf-8')
        html=re.sub(r'([?&]v=)[^\s\"\'&<>]+',lambda m:m[1]+args.version,html)
        path.write_text(html,encoding='utf-8')
    roots=['app/web']
    if not args.web_only:
        shutil.copytree(backend,files/'app/backend/canvas-backend')
        shutil.copy2(desktop,files/'SHIYIN AI.exe')
        roots.append('app/backend/canvas-backend')
    manifest={'protocol_version':2,'version':args.version,'min_desktop_version':(ROOT/'VERSION').read_text().strip(),'notes':args.notes,'prune_roots':roots,'files':[]}
    for path in sorted(files.rglob('*')):
        if path.is_file():manifest['files'].append({'path':path.relative_to(files).as_posix(),'size':path.stat().st_size,'sha256':digest(path)})
    atomic_json(snapshot/'manifest.json',manifest)
    atomic_json(cache,state)
    if args.publish:
        token=(DEFAULT_DATA/'admin-token').read_text('ascii')
        body=json.dumps({'source':str(snapshot),'kind':'hot','notes':args.notes}).encode()
        request=urllib.request.Request(f'http://127.0.0.1:{args.admin_port}/api/import',data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=15) as response: response.read()
    print(json.dumps({'snapshot':str(snapshot),'files':len(manifest['files']),'version':args.version,'publish_requested':args.publish},ensure_ascii=False))


if __name__=='__main__': main()
