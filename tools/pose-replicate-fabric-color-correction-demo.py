"""仅作当前案例的第二阶段颜色校正实验，不修改节点默认次数。"""
import asyncio
import importlib.util
import io
import json
import os
from pathlib import Path
import time
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
os.environ['POSE_FABRIC_TEST_OUT'] = str(ROOT / '输出/一键复刻面料细节-20260911/color-correction')
spec = importlib.util.spec_from_file_location('fabric_demo', ROOT / 'tools/pose-replicate-fabric-detail-demo.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

async def generate(app, report):
    old = json.loads((ROOT / '输出/一键复刻服装保真-20260911/attempt-6-color-only/request-audit.json').read_text(encoding='utf-8'))
    refs = []
    for path in [demo.BASE_OUT / 'color-lock/result.png', demo.BASE_OUT / 'garment.png']:
        upload = await app.upload_ai_reference(files=[app.UploadFile(filename=path.name, file=io.BytesIO(path.read_bytes()))])
        refs.append(app.AIReference(**upload['files'][0]))
    prompt = old['prompt'].replace('(187,179,184) 至 (201,194,199)', '(195,191,195) 至 (201,195,200)')
    payload = app.OnlineImageRequest(prompt=prompt, operation='garment_color_correction',
        provider_id='shiying', model='gpt-image-2', size='1536x2048', quality='high', n=1,
        reference_images=refs, auto_optimize_prompt=False,
        prompt_context={'operation':'garment_color_correction', 'method':'case experiment; second pass; palette only'})
    demo.save('request-audit.json', payload.model_dump())
    submission = await app.create_canvas_image_task(payload)
    demo.save('submission.json',submission)
    task_id = submission['task_id']
    report.update(task_id=task_id, active_stage='color_correction', method='experimental second pass GPT Image 2; not default node flow')
    demo.save('report.json',report)
    deadline=time.monotonic()+1200
    while time.monotonic()<deadline:
        task=app.CANVAS_TASKS[task_id]
        demo.save('task.json',{k:v for k,v in task.items() if not k.startswith('_')})
        if task['status'] in {'succeeded','failed'}:break
        await asyncio.sleep(2)
    else:raise TimeoutError('do_not_resubmit_automatically')
    if task['status']!='succeeded':raise RuntimeError('generation_failed')
    source=app.output_file_from_url(task['result']['images'][0])
    with Image.open(source) as image:
        image.save(demo.OUT/'result.png',format='PNG')
        report['result_dimensions']=list(image.size)
    (demo.OUT/'prompt.txt').write_text(prompt,encoding='utf-8')
    report.update(status='succeeded',generation_seconds=round(task['updated_at']-task['created_at'],2))
    report.pop('active_stage',None)
    demo.save('report.json',report)

demo.generate=generate
if __name__=='__main__':demo.main()
