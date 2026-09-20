"""只读归档软件牛仔复测任务，原样复制输出，不修改生成结果。"""
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '案例/批量复刻培训-20260920'
DATA = Path('D:/Program Files/SHIYIN AI/data')
STYLE = '培训-C-牛仔纹理复测-0920'


def main():
    records = []
    with sqlite3.connect((DATA/'database/canvas.db').as_uri()+'?mode=ro', uri=True) as conn:
        rows = conn.execute('SELECT id,payload_json FROM generation_history ORDER BY created_at')
        for identifier, raw in rows:
            p = json.loads(raw)
            if p.get('batch_outfit', {}).get('style_name') != STYLE:
                continue
            index = len(records)+1
            params = p.get('params', {})
            entry = {k: p.get(k) for k in ('model', 'provider_id', 'generation_elapsed_seconds',
                     'fabric_enhancement', 'original_images', 'batch_outfit_archive')}
            entry.update(id=identifier, style=STYLE, settings={k:params.get(k) for k in ('size','quality','aspect_ratio')},
                         references=[{k:r.get(k) for k in ('role','name','url')} for r in params.get('reference_images', [])],
                         source='已安装软件批量换款页面实际提交；原样复制最终输出', images=[])
            for j, url in enumerate(p.get('images', [])):
                source = DATA/'media/generated'/Path(url).name
                dest = OUT/'assets'/f'denim-software-rerun-{index}-{j+1}{source.suffix}'
                shutil.copy2(source, dest)
                with Image.open(dest) as im:
                    size = list(im.size)
                entry['images'].append({'url':url, 'local':str(dest.relative_to(OUT)).replace('\\','/'),
                                        'dimensions':size, 'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
            records.append(entry)
    (OUT/'evidence/denim-software-reruns.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(records,ensure_ascii=False,indent=2))
    canvas_id = '5cb247a0e8aa42dbbf0b71953c85c32f'
    node_id = 'replicate_ad592cf976eed8_1789909639648'
    with sqlite3.connect((DATA/'database/canvas.db').as_uri()+'?mode=ro', uri=True) as conn:
        raw = conn.execute('SELECT payload_json FROM canvases WHERE id=?',(canvas_id,)).fetchone()
        canvas = json.loads(raw[0])
        node = next(n for n in canvas['nodes'] if n['id']==node_id)
        output = next(n for n in canvas['nodes'] if n.get('poseReplicateSourceId')==node_id)
        audit = {'canvas_id':canvas_id, 'node_id':node_id,
                 'current_node_settings':{k:node.get(k) for k in ('poseReplicatePrompt','poseReplicateProvider','poseReplicateModel','poseReplicateResolution','poseReplicateRatio','poseReplicateMode')},
                 'references':{k:node.get(k) for k in ('poseReferenceUrl','targetImages','fabricDetailUrl')},
                 'preflight_failures':[{'error':item.get('error'),'prompt':item.get('run',{}).get('prompt'),
                                        'started_at':item.get('startedAt')}
                                       for item in output.get('_pending',[]) if item.get('failed')], 'images':[]}
        for i, image in enumerate(output.get('images', [])):
            source = DATA/'media/generated'/Path(image['url']).name
            dest = OUT/'assets'/f'denim-software-node-{i+1}{source.suffix}'
            shutil.copy2(source,dest)
            history = None
            for (raw_history,) in conn.execute('SELECT payload_json FROM generation_history ORDER BY created_at DESC LIMIT 30'):
                parsed = json.loads(raw_history)
                if image['url'] in parsed.get('images', []):
                    history = {k:parsed.get(k) for k in ('original_images','fabric_enhancement','generation_elapsed_seconds')}
                    break
            with Image.open(dest) as im: size=list(im.size)
            run = image.get('run', {})
            audit['images'].append({'url':image['url'],'run_ms':image.get('runMs'),
                                    'run_prompt':run.get('prompt'), 'run_references':run.get('refs'),
                                    'local':str(dest.relative_to(OUT)).replace('\\','/'),
                                    'dimensions':size,'history':history,
                                    'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
    (OUT/'evidence/denim-software-node.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'node_images':audit['images']},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
