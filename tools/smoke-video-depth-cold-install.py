"""冻结后端空目录联网补齐、真实视频提取和重启恢复验收。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import time

import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backend', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--lan-source', default='http://192.168.0.24:3011')
    parser.add_argument('--resume', action='store_true', help='仅继续本脚本创建的隔离验收目录')
    args = parser.parse_args()
    work = args.work_root.resolve()
    work.mkdir(parents=True, exist_ok=args.resume)
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=args.resume)
    app = work / 'app'
    (app / 'web').mkdir(parents=True, exist_ok=args.resume)
    (app / 'web/probe.html').write_text('<html><body></body></html>', encoding='utf-8')
    data = work / '全新数据 目录'
    report = {'isolatedData': str(data), 'isolatedApp': str(app), 'initialComponentsAbsent': not data.exists(),
              'backend': str(args.backend.resolve()), 'cases': []}
    if args.resume:
        report = json.loads((evidence / 'report.json').read_text(encoding='utf-8'))
        assert Path(report['isolatedData']) == data and report['initialComponentsAbsent']
    report['success'] = False
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    session = requests.Session()
    session.trust_env = False
    password = secrets.token_urlsafe(20)
    env = dict(os.environ, CANVAS_DWPOSE_AUTO_DOWNLOAD='0', CANVAS_DEPTH_AUTO_DOWNLOAD='0')
    for name in ['SHIYIN_DEPTH_MODEL_TIER', 'SHIYIN_VIDEO_DEPTH_SOURCE_ROOT', 'SHIYIN_VIDEO_DEPTH_MODEL_ROOT',
                 'CANVAS_PERSON_DEPTH_MANIFEST_PATH']:
        env.pop(name, None)
    process = None

    def api(method, path, **kwargs):
        response = session.request(method, base + path, timeout=30, **kwargs)
        response.raise_for_status()
        return response.json()

    def launch(cycle):
        with (evidence / f'backend-{cycle}.log').open('ab' if args.resume else 'wb') as log:
            child = subprocess.Popen([str(args.backend.resolve()), '--host', '127.0.0.1', '--port', str(port),
                '--data-dir', str(data), '--app-root', str(app), '--portable-root', str(work),
                '--runtime-mode', 'desktop'], cwd=work, env=env, stdout=log, stderr=log,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for _ in range(120):
            if child.poll() is not None:
                raise RuntimeError(f'backend exited; see backend-{cycle}.log')
            try:
                if session.get(base + '/api/health', timeout=1).ok:
                    return child
            except requests.RequestException:
                pass
            time.sleep(.5)
        child.terminate()
        child.wait(timeout=10)
        raise TimeoutError('backend startup timeout')

    def stop():
        nonlocal process
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            process = None

    def save_report():
        (evidence / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    def metadata_files():
        return [*data.glob('media/generated/depth_video_*/run-metadata.json'),
                *data.glob('accounts/*/media/generated/depth_video_*/run-metadata.json')]

    def authenticate(register=False):
        if args.resume:
            response = session.get(base + '/api/auth/bootstrap', allow_redirects=False, timeout=15)
            response.raise_for_status()
            api('GET', '/api/auth/status')
        else:
            api('POST', '/api/account/' + ('register' if register else 'login'),
                json={'account': 'DepthColdFixture', 'password': password})

    try:
        process = launch(0)
        authenticate(register=True)
        api('PUT', '/api/app-settings', json={'person_depth_lan_source': args.lan_source, 'depth_model_preference': 'auto'})
        if not args.resume:
            report['initialStatus'] = api('GET', '/api/video-depth/status')
            assert not report['initialStatus']['runtimeReady'] and not report['initialStatus']['ready']
            with args.input.open('rb') as source:
                report['uploaded'] = api('POST', '/api/video-depth/upload', files={'file': ('东京街景 实测.mp4', source, 'video/mp4')})['file']
        uploaded = report['uploaded']
        print(json.dumps({'phase': 'recorded-cold-start' if args.resume else 'cold-start',
                          'status': report['initialStatus']}, ensure_ascii=True), flush=True)
        for preference in ['auto', 'lite']:
            if any(case['preference'] == preference for case in report['cases']):
                continue
            api('PUT', '/api/app-settings', json={'depth_model_preference': preference})
            started = time.monotonic()
            expected_model = api('GET', '/api/video-depth/status')['model']
            existing = []
            if args.resume:
                for path in metadata_files():
                    meta = json.loads(path.read_text(encoding='utf-8'))
                    if meta['model']['key'] == expected_model and Path(meta['input']['path']).name == uploaded['url'].rsplit('/', 1)[-1]:
                        existing.append(path.parent.name.removeprefix('depth_video_'))
            task = (api('GET', '/api/video-depth/tasks/' + existing[0]) if existing else
                    api('POST', '/api/video-depth/tasks', json={'input_url': uploaded['url']}))
            task_id = task['id']
            report['pending'] = {'id': task_id, 'preference': preference}
            save_report()
            last_log = 0
            while time.monotonic() - started < 3600:
                task = api('GET', '/api/video-depth/tasks/' + task_id)
                if task['status'] in {'done', 'failed'}:
                    break
                if time.monotonic() - last_log > 10:
                    state = api('GET', '/api/video-depth/status')
                    print(json.dumps({'phase': preference, 'elapsed': round(time.monotonic() - started),
                                      'task': task['message'], 'progress': state['progress']}, ensure_ascii=True), flush=True)
                    last_log = time.monotonic()
                time.sleep(1)
            assert task['status'] == 'done', task
            downloaded = session.get(base + task['outputUrl'], timeout=60)
            downloaded.raise_for_status()
            output = evidence / f'{preference}-depth.mp4'
            output.write_bytes(downloaded.content)
            metadata_path = next(path for path in metadata_files() if path.parent.name == 'depth_video_' + task_id)
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            task['model'] = metadata['model']['key']
            assert metadata['input']['completeExtraction']
            assert metadata['input']['processedFrames'] == metadata['input']['frameCount']
            assert hashlib.sha256(output.read_bytes()).digest() != hashlib.sha256(args.input.read_bytes()).digest()
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(output), '-f', 'null', '-'], check=True, capture_output=True)
            probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-show_entries',
                'stream=width,height,avg_frame_rate,nb_read_frames:format=duration', '-of', 'json', str(output)]))
            assert int(probe['streams'][0]['nb_read_frames']) == metadata['input']['frameCount']
            ranged = session.get(base + task['outputUrl'], headers={'Range': 'bytes=0-1023'}, timeout=15)
            assert ranged.status_code == 206 and ranged.content == output.read_bytes()[:1024]
            case = {'preference': preference, 'task': task, 'elapsedSeconds': None if existing else round(time.monotonic()-started, 3),
                    'resumedCompletedTask': bool(existing),
                    'metadata': metadata, 'probe': probe, 'range': ranged.status_code}
            report['cases'].append(case)
            shutil.copy2(metadata_path, evidence / f'{preference}-metadata.json')
            print(json.dumps({'phase': preference, 'result': 'done', 'seconds': case['elapsedSeconds'],
                              'model': task['model'], 'frames': task['frameCount']}, ensure_ascii=True), flush=True)
            save_report()
        report['installed'] = {}
        for component in ['video-depth-runtime', 'video-depth']:
            component_root = data / 'system/components' / component
            current = json.loads((component_root / 'current.json').read_text(encoding='utf-8'))
            installation = component_root / 'installations' / current['installation']
            details = json.loads((installation / 'component-manifest.json').read_text(encoding='utf-8'))
            report['installed'][component] = {'current': current, 'packages': details['packages']}
            assert current['source'] == 'lan', current
        report['verifiedModelFiles'] = []
        for receipt in (data / 'system/components/video-depth/installations').glob('*/component-manifest.json'):
            details = json.loads(receipt.read_text(encoding='utf-8'))
            model_file = next(receipt.parent.glob('models/*/*.pth'))
            with model_file.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            assert digest == details['packages'][0]['sha256']
            report['verifiedModelFiles'].append({'variant': details['variant'], 'bytes': model_file.stat().st_size,
                                                'sha256': digest, 'source': details['source']})
        api('PUT', '/api/app-settings', json={'depth_model_preference': report['cases'][-1]['preference']})
        stop()
        session.cookies.clear()
        process = launch(1)
        authenticate()
        report['restartStatus'] = api('GET', '/api/video-depth/status')
        assert report['restartStatus']['ready']
        for case in report['cases']:
            recovered = api('GET', '/api/video-depth/tasks/' + case['task']['id'])
            assert recovered['status'] == 'done'
        report['restartRecovery'] = True
        browser = subprocess.run(['node', str(ROOT / 'tests/support/video_depth_media_playback.cjs')],
            input=json.dumps({'base': base, 'source': uploaded['url'],
                              'outputs': [case['task']['outputUrl'] for case in report['cases']],
                              'expected': {'width': report['cases'][0]['task']['width'],
                                           'height': report['cases'][0]['task']['height'],
                                           'duration': float(report['cases'][0]['probe']['format']['duration'])},
                              'cookies': [{'name': c.name, 'value': c.value} for c in session.cookies],
                              'screenshot': str(evidence / 'playback.png')}),
            capture_output=True, text=True, encoding='utf-8', timeout=90)
        assert browser.returncode == 0, browser.stdout + browser.stderr
        report['browser'] = json.loads(browser.stdout.strip().splitlines()[-1])
        report.pop('pending', None)
        report['success'] = True
        print(json.dumps({'success': True, 'report': str(evidence / 'report.json')}, ensure_ascii=True), flush=True)
    finally:
        stop()
        save_report()


if __name__ == '__main__':
    main()
