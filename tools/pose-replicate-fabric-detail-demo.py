"""用用户提供的三张图片实测面料细节端口；隔离数据、单次提交、审计原尺寸像素。"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE_OUT = ROOT / '输出/一键复刻面料细节-20260911'
OUT = Path(os.environ.get('POSE_FABRIC_TEST_OUT') or BASE_OUT)
INSTALLED = Path('D:/Program Files/SHIYIN AI/data')
sys.path.insert(0, str(ROOT))


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


async def generate(app, report):
    # 使用安装组件为本次目标图片重新提取深度。
    from canvas_core.person_depth_components import PersonDepthComponentManager
    app.PERSON_DEPTH_COMPONENT_MANAGER = PersonDepthComponentManager(INSTALLED / 'system/components/person-depth')
    if not app.PERSON_DEPTH_COMPONENT_MANAGER.public_status().get('ready'):
        raise RuntimeError('installed_depth_component_not_ready')
    verified_depth = os.environ.get('POSE_FABRIC_TEST_DEPTH')
    if verified_depth:
        depth_path = Path(verified_depth)
        with Image.open(depth_path.parent / 'target.png') as previous, Image.open(OUT / 'target.png') as current:
            assert previous.size == current.size and previous.convert('RGB').tobytes() == current.convert('RGB').tobytes()
        shutil.copy2(depth_path, OUT / 'depth.png')
        with Image.open(depth_path) as depth:
            report['depth_dimensions'] = list(depth.size)
        report['depth_reused_from'] = str(depth_path)
    else:
        from canvas_core.person_depth_client import PersonDepthWorkerClient
        app.PERSON_DEPTH_WORKER = PersonDepthWorkerClient(app.PERSON_DEPTH_COMPONENT_MANAGER)
        result = await asyncio.to_thread(app.PERSON_DEPTH_WORKER.estimate, (OUT / 'target.png').read_bytes(), bit_depth=8)
        (OUT / 'depth.png').write_bytes(result.content)
        report['depth_dimensions'] = [result.width, result.height]
    save('report.json', report)
    refs = {}
    for role, name in [('pose_reference', 'target.png'), ('control_map', 'depth.png'), ('target_image', 'garment.png'), ('fabric_detail', 'fabric.png')]:
        upload = await app.upload_ai_reference(files=[app.UploadFile(filename=name, file=io.BytesIO((OUT / name).read_bytes()))])
        refs[role] = app.AIReference(**upload['files'][0])

    original_part = app.gemini_reference_part
    reference_audit = []

    def audit_part(ref):
        part = original_part(ref)
        inline = (part or {}).get('inlineData') or {}
        if inline.get('data'):
            with Image.open(io.BytesIO(base64.b64decode(inline['data']))) as image:
                rgb = image.convert('RGB')
                entry = {'role': ref.get('role'), 'mime': inline.get('mimeType'),
                         'dimensions': list(image.size), 'rgb_sha256': hashlib.sha256(rgb.tobytes()).hexdigest()}
            reference_audit.append(entry)
            save('sent-reference-audit.json', reference_audit)
            if ref.get('role') in {'target_image', 'fabric_detail'}:
                with Image.open(OUT / ('fabric.png' if ref.get('role') == 'fabric_detail' else 'garment.png')) as source:
                    assert entry['dimensions'] == list(source.size)
                    assert entry['rgb_sha256'] == hashlib.sha256(source.convert('RGB').tobytes()).hexdigest()
                assert entry['mime'] == 'image/png'
        return part

    app.gemini_reference_part = audit_part
    payload = app.PoseReplicateTaskRequest(
        mode='depth', inputs=app.PoseReplicateInputs(**refs),
        generation=app.PoseReplicateGeneration(provider_id='shiying', model='gemini-3-pro-image-preview',
                                              resolution='2k', aspect_ratio='3:4', count=1),
        control_signature='fresh-depth-sha256:' + hashlib.sha256((OUT / 'depth.png').read_bytes()).hexdigest(),
    )
    save('request-audit.json', payload.model_dump())
    submission = await app.create_pose_replicate_task(payload)
    save('submission.json', submission)
    task_id = submission['task_id']
    report.update(task_id=task_id, active_stage='generation')
    save('report.json', report)
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        task = app.CANVAS_TASKS[task_id]
        save('task.json', {k: v for k, v in task.items() if not k.startswith('_')})
        if task['status'] in {'succeeded', 'failed'}:
            break
        await asyncio.sleep(2)
    else:
        raise TimeoutError('generation_timeout_do_not_resubmit_automatically')
    if task['status'] != 'succeeded':
        raise RuntimeError('generation_failed:' + str(task.get('status_code')))
    result = task['result']
    images = result.get('images') or []
    if len(images) != 1:
        raise RuntimeError('expected_one_result')
    source = app.output_file_from_url(images[0])
    if not source:
        raise RuntimeError('result_file_missing')
    with Image.open(source) as generated:
        generated.save(OUT / 'result.png', format='PNG')
    audit = task['pose_replicate']
    (OUT / 'prompt.txt').write_text(audit['final_prompt'], encoding='utf-8')
    with Image.open(OUT / 'result.png') as result_image:
        result_dimensions = list(result_image.size)
    report.update(status='succeeded', template_id=audit['template_id'], prompt_source=audit['prompt_source'],
                  generation_seconds=round(task['updated_at']-task['created_at'], 2),
                  garment_pixels_preserved=any(e['role']=='target_image' for e in reference_audit),
                  fabric_pixels_preserved=any(e['role']=='fabric_detail' for e in reference_audit),
                  result_dimensions=result_dimensions)
    report.pop('active_stage', None)
    save('report.json', report)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'submission.json').exists() or (OUT / 'result.png').exists():
        raise RuntimeError('existing_attempt_retained_do_not_duplicate')
    for source, name in [('目标图.jpg', 'target.png'), ('服装参考.jpg', 'garment.png'), ('纹理细节.jpg', 'fabric.png')]:
        with Image.open(Path('D:/data/图片') / source) as image:
            image.save(OUT / name, format='PNG')
    report = {'status': 'running', 'active_stage': 'depth', 'method': 'current source task entry + fabric detail port + original-size lossless garment and fabric; single generation'}
    save('report.json', report)
    print('Starting isolated image test; inspect report.json for the active stage.', flush=True)
    runtime = ROOT / '.codex-artifacts/pose-fabric-detail-runtime'
    os.environ.update(CANVAS_DATA_DIR=str(runtime/'data'), CANVAS_PORTABLE_ROOT=str(runtime), CANVAS_APP_ROOT=str(ROOT),
                      CANVAS_DWPOSE_AUTO_DOWNLOAD='0', CANVAS_DEPTH_AUTO_DOWNLOAD='0')
    from canvas_core.secrets import DpapiProtector
    key_name = 'API_PROVIDER_SHIYING_KEY'
    with sqlite3.connect((INSTALLED/'database/canvas.db').as_uri()+'?mode=ro', uri=True) as db:
        provider = json.loads(db.execute('SELECT payload_json FROM providers WHERE id=?', ('shiying',)).fetchone()[0])
        secret = db.execute('SELECT encrypted_value FROM secret_values WHERE key=?', (key_name,)).fetchone()
        if not secret:
            raise RuntimeError('saved_provider_credential_missing')
        os.environ[key_name] = DpapiProtector().unprotect(bytes(secret[0]))
    try:
        # 底层调试输出可能含多模态载荷，不写入终端或日志。
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import main as app
            app.ADMIN_DATABASE.save_providers([provider])
            asyncio.run(generate(app, report))
    except Exception as exc:
        report.update(status='failed', error_type=type(exc).__name__)
        save('report.json', report)
        print(json.dumps(report, ensure_ascii=True), flush=True)
        raise SystemExit(1) from None
    finally:
        if 'app' in locals():
            app.PERSON_DEPTH_WORKER.close()
        os.environ.pop(key_name, None)
    print(json.dumps(report, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
