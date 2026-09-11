"""用户授权的服装复刻实测：重新提取深度，经真实节点接口生成并保存审计。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / '输出/一键复刻服装保真-20260911'


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def reference(name, session, base_url):
    path = OUT / name
    # 与节点上传相同：服务端随后按角色缩放/编码，深度图保持无损。
    with path.open('rb') as stream:
        response = session.post(base_url + '/api/ai/upload',
                                files={'files': (name, stream, 'image/png')}, timeout=60)
    response.raise_for_status()
    return response.json()['files'][0]


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Only poll/download the saved task; never resubmit')
    parser.add_argument('--base-url', default='http://127.0.0.1:3000')
    parser.add_argument('--output-dir', type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.output_dir.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.prepare:
        if not args.source:
            parser.error('--prepare requires --source')
        with Image.open(args.source) as im:
            if im.size != (4488, 2048):
                raise ValueError('This case requires the original 4488x2048 comparison image')
            # 仅拆分用户拼图，保留原始像素与角标，不修饰服装或人物。
            boxes = [(0, 0, 1530, 2048), (1562, 0, 2928, 2048), (2960, 0, 4488, 2048)]
            for name, box in zip(['target.png', 'garment.png', 'previous-result.png'], boxes):
                im.crop(box).save(OUT / name)
        dbpath = Path('D:/Program Files/SHIYIN AI/data/database/canvas.db')
        with sqlite3.connect(dbpath.as_uri() + '?mode=ro', uri=True) as db:
            rows = db.execute("SELECT payload_json FROM tasks WHERE payload_json LIKE '%pose_replicate%' ORDER BY updated_at DESC LIMIT 8").fetchall()
        audit = []
        for row in rows:
            task = json.loads(row[0])
            payload = task.get('payload') or task.get('request') or {}
            item = {k: task.get(k) for k in ('id', 'task_id', 'status', 'created_at', 'pose_replicate', 'images')}
            item['keys'] = list(task)
            item['request_keys'] = list(payload)
            audit.append(item)
        save('historical-audit.json', audit)
        print(json.dumps(audit, ensure_ascii=True)[:14000])
        return
    if (OUT / 'result.png').exists():
        print('Existing result retained; no duplicate paid generation.')
        return
    if (OUT / 'submission.json').exists() and not args.resume:
        raise RuntimeError('Existing submission found. Inspect its task id and retrieve that result; do not submit a duplicate paid task.')
    from canvas_core.pose_replicate_prompts import compile_pose_replicate_prompt
    session = requests.Session()
    response = session.post(args.base_url + '/api/account/login', json={'account': 'jiang', 'password': 'jiang'}, timeout=20)
    response.raise_for_status()
    if args.resume:
        submission = json.loads((OUT / 'submission.json').read_text(encoding='utf-8'))
        report = json.loads((OUT / 'report.json').read_text(encoding='utf-8'))
        collect_result(session, args.base_url, submission['task_id'], report, time.monotonic())
        return
    report = {'status': 'running', 'source': 'user comparison panels, lossless crops',
              'method': 'real person-depth estimate + real pose-replicate task endpoint; new built-in text submitted via custom template to running installed server'}
    save('report.json', report)
    started = time.monotonic()
    with (OUT / 'target.png').open('rb') as stream:
        response = session.post(args.base_url + '/api/person-depth/estimate',
                                files={'file': ('target.png', stream, 'image/png')}, data={'bit_depth': '8'}, timeout=600)
    response.raise_for_status()
    (OUT / 'depth.png').write_bytes(response.content)
    report['depth'] = {'elapsed_s': round(time.monotonic()-started, 2),
                       'headers': {k: v for k, v in response.headers.items() if k.lower().startswith('x-person-depth')},
                       'sha256': hashlib.sha256(response.content).hexdigest(), 'fresh_request': True}
    save('report.json', report)
    print('Fresh depth saved.', flush=True)
    compiled = compile_pose_replicate_prompt('depth', output_aspect_ratio='3:4')
    (OUT / 'prompt.txt').write_text(compiled.final_prompt, encoding='utf-8')
    catalog = session.get(args.base_url + '/api/canvas/pose-replicate-templates', timeout=20).json()
    payload = {'mode': 'depth', 'inputs': {'pose_reference': reference('target.png', session, args.base_url), 'control_map': reference('depth.png', session, args.base_url), 'target_image': reference('garment.png', session, args.base_url)},
               'generation': {'provider_id': 'shiying', 'model': 'gemini-3-pro-image-preview', 'resolution': '2k', 'aspect_ratio': '3:4', 'count': 1},
               'prompt_policy': {'template_id': catalog['template_id'], 'locale': 'zh-CN',
                                 'custom_template': compiled.final_prompt, 'custom_template_key': 'depth:base-wardrobe'},
               'control_signature': 'fresh-depth-sha256:' + report['depth']['sha256']}
    save('request-audit.json', {**payload, 'source_template_id': compiled.template_id})
    response = session.post(args.base_url + '/api/canvas/pose-replicate-tasks', json=payload, timeout=60)
    response.raise_for_status()
    submission = response.json()
    save('submission.json', submission)
    task_id = submission['task_id']
    print('Submitted task: ' + task_id, flush=True)
    report['task_id'] = task_id
    save('report.json', report)
    collect_result(session, args.base_url, task_id, report, started)


def collect_result(session, base_url, task_id, report, started):
    deadline = time.monotonic() + 900
    poll_failures = 0
    while time.monotonic() < deadline:
        try:
            response = session.get(base_url + '/api/canvas-image-tasks/' + task_id, timeout=30)
            response.raise_for_status()
            poll_failures = 0
        except (requests.ConnectionError, requests.Timeout):
            poll_failures += 1
            if poll_failures >= 3:
                raise
            time.sleep(2)
            continue
        state = response.json()
        save('task.json', state)
        task = state.get('task') or state
        status = task.get('status')
        if status in ('completed', 'succeeded', 'success', 'failed', 'error', 'cancelled'):
            report['status'] = status
            save('report.json', report)
            print(json.dumps({'status': status, 'keys': list(task)}, ensure_ascii=True), flush=True)
            break
        time.sleep(5)
    else:
        raise TimeoutError('Generation still pending; inspect saved task id before retrying')
    urls = task.get('images') or (task.get('result') or {}).get('images') or []
    if not urls:
        report.update(error=task.get('error'), status_code=task.get('status_code'))
        save('report.json', report)
        raise RuntimeError('Task returned no images; inspect report.json and task.json')
    url = urls[0] if isinstance(urls[0], str) else urls[0]['url']
    response = session.get(url if url.startswith('http') else base_url + url, timeout=120)
    response.raise_for_status()
    (OUT / 'result.png').write_bytes(response.content)
    report['generation_elapsed_s'] = round(time.time() - float(task['created_at']), 2)
    save('report.json', report)
    print('Result saved.', flush=True)


if __name__ == '__main__':
    main()
