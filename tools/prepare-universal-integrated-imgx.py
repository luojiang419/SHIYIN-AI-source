"""用实际全能两阶段适配器编译已由 imgx 生成的底图，后续仍交给 imgx。"""
import asyncio
import json
import os
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
os.environ.setdefault('CANVAS_DATA_DIR',str(ROOT/'.codex-tmp/universal-integrated-validation'))
import main as app
from canvas_core.depth_models import DepthModelManager
from canvas_core.person_depth_components import PersonDepthComponentManager
from canvas_core.person_depth_client import PersonDepthWorkerClient


async def main():
    case=ROOT/'案例/全能双风格/imgx-20260920'
    source=ROOT/'案例/全能双风格/20260920/round-7-standard_product-task.json'
    snapshot=json.loads(source.read_text(encoding='utf-8'))
    manifest=json.loads((case/'standard-anchor-refined/manifest.json').read_text(encoding='utf-8'))
    result=next(r for r in manifest['results'] if r['status']=='succeeded')
    anchor=result['file']
    app.DEPTH_MODEL_MANAGER=DepthModelManager(ROOT/'data/system/models/depth')
    app.PERSON_DEPTH_COMPONENT_MANAGER=PersonDepthComponentManager(ROOT/'data/system/components/person-depth')
    app.PERSON_DEPTH_WORKER=PersonDepthWorkerClient(app.PERSON_DEPTH_COMPONENT_MANAGER)
    refs=snapshot['inputs']+[{'role':'control_map','reference_type':'control_map','url':str(source.parent/'round-7-standard_product-depth-2.png')}]
    # 生图桥接为已经由 imgx 完成的真实底图；并非模拟生成结果。编译和新深度走应用真实代码。
    with patch.object(app,'execute_ai_image_batch',AsyncMock(return_value={'images':[anchor],'generation_elapsed_seconds':0})), patch.object(app,'output_file_from_url',side_effect=lambda p:p), patch.object(app,'OUTPUT_OUTPUT_DIR',str(case)), patch.object(app,'media_url_from_path',side_effect=lambda p:p):
        final_refs,prompt,audit=await app.prepare_universal_product_anchor(snapshot,{'provider_id':'shiying','model':'gemini-3-pro-image-preview'},refs,'')
    paths={'lower_garment':'D:/data/图片/服装参考 (2).jpg','detail':'D:/data/图片/腰头细节.jpg'}
    name='integrated-standard'
    spec={'name':name,'aspect_ratio':'2:3','resolution':'4K','count':1,'prompts':[prompt],
          'references':[str(Path(paths.get(r['reference_type'],r['url'])).resolve()) for r in final_refs],
          'output_dir':str(case/name),'model':'gemini-3-pro-image-preview','transport':'imgx','reuse':audit}
    (case/(name+'.json')).write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
    print(audit['product_edit_template'])


if __name__=='__main__':asyncio.run(main())
