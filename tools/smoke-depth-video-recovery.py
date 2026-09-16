"""Validate recovered depth results using a frozen backend and a real browser."""
import argparse
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--port', type=int, default=3197)
    args = parser.parse_args()
    stage = Path(args.stage).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='深度恢复-', dir=output))
    helpers = runpy.run_path(str(Path(__file__).with_name('smoke-canvas-cold-packaged.py')))
    data = root / '中文数据 目录'
    sample = root / 'sample.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=gray:s=160x90:r=12',
                    '-t', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(sample)], check=True)
    base = f'http://127.0.0.1:{args.port}'
    report = {'stage': str(stage), 'cycles': []}
    for cycle in range(2):
        process, elapsed, health = helpers['launch'](stage, data, args.port, root / f'backend-{cycle}.log')
        try:
            with helpers['login'](base, register=cycle == 0) as session:
                if cycle == 0:
                    with sample.open('rb') as file:
                        response = session.post(base + '/api/video-depth/upload', files={'file': ('input.mp4', file, 'video/mp4')}, timeout=15)
                    response.raise_for_status()
                    source = response.json()['file']
                    generated = next(data.glob('accounts/*/media/generated'))
                    directory = generated / ('depth_video_' + 'a' * 32)
                    directory.mkdir()
                    shutil.copyfile(sample, directory / 'depth-preview.mp4')
                    # Recreate an old worker's damaged path with an intact output and metadata.
                    (directory / 'run-metadata.json').write_text(json.dumps({
                        'schema': 'shiyin.video-depth-lab/v1', 'outputVideoPath': 'Z:/旧路径/乱码/depth-preview.mp4',
                        'input': {'processedWidth': 160, 'processedHeight': 90, 'processedFps': 12},
                    }, ensure_ascii=False), encoding='utf-8')
                    response = session.post(base + '/api/canvases', json={'title': '深度恢复验收'}, timeout=15)
                    response.raise_for_status()
                    canvas_id = response.json()['canvas']['id']
                    node = {'id': 'recovery-node', 'type': 'depthVideo', 'x': 80, 'y': 80, 'w': 620, 'h': 390,
                            'depthVideoTaskId': 'a' * 32, 'depthVideoStatus': 'failed', 'depthVideoError': '深度视频已生成，但无法注册输出文件',
                            'depthVideoManualInput': source,
                            'depthVideoInputSignature': source['url'] + '|' + source['name'] + '|x'}
                    response = session.put(base + '/api/canvases/' + canvas_id, json={
                        'title': '深度恢复验收', 'nodes': [node], 'connections': [], 'viewport': {'x': 0, 'y': 0, 'scale': 1}}, timeout=15)
                    response.raise_for_status()
                response = session.get(base + '/api/video-depth/tasks/' + 'a' * 32, timeout=15)
                response.raise_for_status()
                task = response.json()
                assert task['status'] == 'done', task
                video = session.get(base + task['outputUrl'], headers={'Range': 'bytes=0-31'}, timeout=15)
                assert video.status_code == 206, video.status_code
                assert video.content == sample.read_bytes()[:32]
                browser = subprocess.run(['node', 'tests/support/depth_video_packaged_check.cjs'], input=json.dumps({
                    'base': base, 'id': canvas_id, 'cookies': [{'name': c.name, 'value': c.value} for c in session.cookies],
                    'screenshot': str(root / f'node-{cycle}.png'),
                }), capture_output=True, text=True, encoding='utf-8', timeout=90)
                assert browser.returncode == 0, browser.stdout + browser.stderr
                report['cycles'].append({'cycle': cycle, 'health': health, 'startupMs': elapsed,
                                         'range': video.status_code, 'task': task,
                                         'browser': json.loads(browser.stdout.strip().splitlines()[-1])})
        finally:
            helpers['stop'](process)
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
