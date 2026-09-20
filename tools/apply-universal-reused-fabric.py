"""对 imgx 成图运行应用原有面料后处理，保留原生图片和可追溯审计。"""
import asyncio
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.environ.setdefault('CANVAS_DATA_DIR',str(ROOT/'.codex-tmp/universal-fabric-validation'))
import main as app
from canvas_core.depth_models import DepthModelManager
from canvas_core.person_depth_components import PersonDepthComponentManager
from canvas_core.person_depth_client import PersonDepthWorkerClient


async def main():
    case=ROOT/'案例/全能双风格/imgx-20260920'
    app.DEPTH_MODEL_MANAGER=DepthModelManager(ROOT/'data/system/models/depth')
    app.PERSON_DEPTH_COMPONENT_MANAGER=PersonDepthComponentManager(ROOT/'data/system/components/person-depth')
    app.PERSON_DEPTH_WORKER=PersonDepthWorkerClient(app.PERSON_DEPTH_COMPONENT_MANAGER)
    results=[]
    for name in ['reuse-standard','reuse-lookbook','integrated-standard']:
        manifest_path=case/name/'manifest.json'
        if not manifest_path.exists():continue
        if (case/name/'fabric-depth-audit.json').exists():
            results.append(json.loads((case/name/'fabric-depth-audit.json').read_text(encoding='utf-8')))
            continue
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        refs=[{'reference_type':'lower_garment','role':'lower_garment','reference_id':'pants','url':'D:/data/图片/服装参考 (2).jpg'},
              {'reference_type':'detail','role':'detail','detail_target_id':'pants','url':'D:/data/图片/腰头细节.jpg'}]
        for item in manifest['results']:
            if item['status']!='succeeded':continue
            source=str(Path(item['file']).resolve())
            batch={'images':[source],'image_items':[{'url':source}]}
            # 仅将应用的 URL/输出目录适配到离线案例路径；算法、选材和失败回退完全复用。
            with patch.object(app,'output_file_from_url',side_effect=lambda p:p if Path(p).is_file() else None), patch.object(app,'OUTPUT_OUTPUT_DIR',str(case/name)), patch.object(app,'media_url_from_path',side_effect=lambda p:p), patch.object(app,'image_output_meta',side_effect=lambda p:{'url':p}):
                outcome=await app.apply_fabric_enhancement('universal',refs,batch,{'infer_output_depth':True})
            final=Path(outcome['images'][0])
            if final!=Path(source):
                stable=case/name/'fabric-depth-final.png'
                final.replace(stable)
                outcome['images']=[str(stable)]
                outcome['image_items']=[{'url':str(stable)}]
            entry={'name':name,'source':source,'result':outcome,'selected_fabric_references':app.ecommerce_fabric_reference_urls('universal',refs),'function':'main.apply_fabric_enhancement','algorithm':'canvas_core.fabric_enhancement.enhance_fabric_image'}
            (case/name/'fabric-depth-audit.json').write_text(json.dumps(entry,ensure_ascii=False,indent=2),encoding='utf-8')
            results.append(entry)
            print(name,json.dumps(outcome['fabric_enhancement'],ensure_ascii=False))
    (case/'fabric-summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':asyncio.run(main())
