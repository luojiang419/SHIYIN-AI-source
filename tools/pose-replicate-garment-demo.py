"""用户授权的服装复刻实测：重新提取深度，经真实节点接口生成并保存审计。"""
from __future__ import annotations

import argparse
import base64
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


def reference(name):
    path = OUT / name
    return {'url': 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode(),
            'name': name, 'kind': 'image'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--base-url', default='http://127.0.0.1:3000')
    args = parser.parse_args()
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
    if (OUT / 'submission.json').exists():
        raise RuntimeError('Existing submission found. Inspect its task id and retrieve that result; do not submit a duplicate paid task.')
    from canvas_core.pose_replicate_prompts import compile_pose_replicate_prompt
    session = requests.Session()
    response = session.post(args.base_url + '/api/account/login', json={'account': 'jiang', 'password': 'jiang'}, timeout=20)
    response.raise_for_status()
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
    payload = {'mode': 'depth', 'inputs': {'pose_reference': reference('target.png'), 'control_map': reference('depth.png'), 'target_image': reference('garment.png')},
               'generation': {'provider_id': 'shiying', 'model': 'gemini-3-pro-image-preview', 'resolution': '2k', 'aspect_ratio': '3:4', 'count': 1},
               'prompt_policy': {'template_id': catalog['template_id'], 'locale': 'zh-CN',
                                 'custom_template': compiled.final_prompt, 'custom_template_key': 'depth:base-wardrobe'},
               'control_signature': 'fresh-depth-sha256:' + report['depth']['sha256']}
    save('request-audit.json', {**payload, 'inputs': {k: {**v, 'url': v['name']} for k, v in payload['inputs'].items()}, 'source_template_id': compiled.template_id})
    response = session.post(args.base_url + '/api/canvas/pose-replicate-tasks', json=payload, timeout=60)
    response.raise_for_status()
    submission = response.json()
    save('submission.json', submission)
    task_id = submission['task_id']
    print('Submitted task: ' + task_id, flush=True)
    report['task_id'] = task_id
    save('report.json', report)
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        response = session.get(args.base_url + '/api/canvas-image-tasks/' + task_id, timeout=30)
        response.raise_for_status()
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
        raise RuntimeError('Task returned no images; inspect task.json')
    url = urls[0] if isinstance(urls[0], str) else urls[0]['url']
    response = session.get(url if url.startswith('http') else args.base_url + url, timeout=120)
    response.raise_for_status()
    (OUT / 'result.png').write_bytes(response.content)
    report['elapsed_s'] = round(time.monotonic()-started, 2)
    save('report.json', report)
    print('Result saved.', flush=True)


if __name__ == '__main__':
    main()
