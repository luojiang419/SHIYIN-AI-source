"""复用一键复刻编译器与人物深度组件，准备 imgx 的双风格验证任务。"""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from canvas_core.pose_replicate_prompts import compile_pose_replicate_prompt
from canvas_core.universal_photography import build_universal_photography_contract
from canvas_core.person_depth_components import PersonDepthComponentManager
from canvas_core.person_depth_client import PersonDepthWorkerClient


def main():
    case=ROOT/'案例/全能双风格/imgx-20260920'
    lookbook=case/'lookbook/image-00001.jpg'
    manager=PersonDepthComponentManager(ROOT/'data/system/components/person-depth')
    worker=PersonDepthWorkerClient(manager)
    depth_path=case/'lookbook-base-depth.png'
    if not depth_path.exists():
        result=worker.estimate(lookbook.read_bytes(),bit_depth=8)
        depth_path.write_bytes(result.content)
    roles={
        'model_subject':Path('D:/data/图片/选用/B/XSY_9373.JPG'),
        'pose_reference':Path('C:/Users/jiang/Desktop/人物形象/动作.png'),
        'control_map':ROOT/'案例/全能双风格/20260920/round-7-standard_product-depth-2.png',
        'target_image':Path('D:/data/图片/服装参考 (2).jpg'),
        'fabric_detail':Path('D:/data/图片/腰头细节.jpg'),
        'scene':Path('C:/Users/jiang/Desktop/西部小镇/【西部小镇WildWestTown】场景/page-004_img-004.jpeg'),
    }
    for style in ['standard','lookbook']:
        with_model=style=='standard'
        current=roles if with_model else {**roles,'pose_reference':lookbook,'control_map':depth_path}
        compiled=compile_pose_replicate_prompt('depth',has_model_subject=with_model,has_scene=with_model,has_fabric_detail=True,output_aspect_ratio='2:3')
        ownership=('本次只替换下装；图1模特的金色齐下颌短发、黑色背心、透明带透明粗跟凉鞋必须保留。动作图的红色乐福鞋、牛仔服和白栅栏都不迁移。头朝画面右，画面右侧膝向外弯、小腿交叉向左，抱臂并保持倾斜重心。'
            if with_model else '这是已确定创意机位的 Lookbook 局部商品还原阶段。保留图1脸、短发、动作、鞋、摄影机位及现场光，尤其保留远景虚化。只改裤装：使用商品参考的后腰双扣、相邻双腰耳、橙棕皮牌及后育克和后袋的真实空间顺序；不要镜像、重排或让手遮住它们。不因为复用复刻模板把创意姿势改回标准站姿。')
        prompt=compiled.final_prompt+'\n【全能模式适配说明】\n'+ownership+'\n商品参考提供固有色，保持中间调色相与织物组织；人物和衣服使用同一现场光场。局部受光变化不是任意改色，不能把棚拍原曝光贴到人物上。细节图提供后侧结构，正面不可见时绝不把后腰扣、后袋或皮牌复制到前侧。'
        if with_model: prompt+='\n'+build_universal_photography_contract('standard_product',5)
        name='reuse-'+style
        spec={'name':name,'aspect_ratio':'2:3','resolution':'4K','count':1,'prompts':[prompt],
              'references':[str(current[r['role']].resolve()) for r in compiled.reference_order],
              'output_dir':str(case/name),'model':'gemini-3-pro-image-preview','transport':'imgx',
              'reuse':compiled.audit_payload(),'postprocess':'main.apply_fabric_enhancement / canvas_core.fabric_enhancement.enhance_fabric_image'}
        (case/(name+'.json')).write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,compiled.template_variant)


if __name__=='__main__':main()
