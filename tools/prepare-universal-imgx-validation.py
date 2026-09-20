"""生成 imgx 实测规格；不发送请求，不接触凭据。"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from canvas_core.ecommerce import build_universal_style_prompt, universal_style_references


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-dir', required=True)
    parser.add_argument('--finalize-anchor', action='store_true')
    args = parser.parse_args()
    case = Path(args.case_dir).resolve()
    case.mkdir(parents=True, exist_ok=True)
    previous = ROOT / '案例/全能双风格/20260920'
    standard = json.loads((previous/'round-7-standard_product-task.json').read_text(encoding='utf-8'))
    creative = json.loads((previous/'round-7-lookbook-task.json').read_text(encoding='utf-8'))
    files = {
        'subject': 'D:/data/图片/选用/B/XSY_9373.JPG',
        'lower_garment': 'D:/data/图片/服装参考 (2).jpg',
        'detail': 'D:/data/图片/腰头细节.jpg',
        'pose': 'C:/Users/jiang/Desktop/人物形象/动作.png',
        'scene': 'C:/Users/jiang/Desktop/西部小镇/【西部小镇WildWestTown】场景/page-004_img-004.jpeg',
        'control_map': str(previous/'round-7-standard_product-depth-2.png'),
    }
    def save(name, prompts, refs):
        spec = dict(name=name, aspect_ratio='2:3', resolution='4K', count=1,
                    prompts=prompts, references=[str(Path(p).resolve()) for p in refs],
                    output_dir=str(case/name), model='gemini-3-pro-image-preview', transport='imgx')
        (case/(name+'.json')).write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name)
    if args.finalize_anchor:
        manifest=json.loads((case/'standard-anchor/manifest.json').read_text(encoding='utf-8'))
        # The CLI manifest is the source of truth; callers inspect it before selecting the image.
        candidates=[p for p in (case/'standard-anchor').iterdir() if p.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}]
        if not candidates:
            raise RuntimeError('imgx 动作底图没有成功图片，不能启动商品编辑')
        save('standard-product', [standard['generation_prompt']], [str(sorted(candidates)[0]),files['lower_garment'],files['detail']])
        return
    save('standard-anchor',[standard['pose_anchor']['prompt']], [files[r['reference_type']] for r in standard['pose_anchor']['references']])
    depth={'url':'/assets/output/depth.png','role':'control_map','reference_type':'control_map','reference_id':'derived_pose_depth','label':'动作人物深度图'}
    options={**standard['options'],'generation_style':'standard_product'}
    refs=universal_style_references([*standard['inputs'],depth],'standard_product',bool(options.get('instruction')))
    save('standard-direct',[build_universal_style_prompt(standard['inputs'],options,depth)],[files[r['reference_type']] for r in refs])
    prompt=creative['generation_prompt']
    refined=prompt+'\n本次摄影编排：后侧三分之四全身视角，在原场景碎石路上停步回眸。保持模特齐下颌金色短发，不留长发。双臂自然离开后腰，手、头发和上衣均不遮挡后腰。依据商品参考中可见的顺序，完整展示后腰调节袢及两枚银扣、相邻双腰耳、橙棕皮牌、后育克与五角后袋；不能把两扣变一扣，不能移动皮牌到裤子侧前方。腰头与后袋处于主体焦平面。保持细密低对比斜纹的实际物理尺度，不能放大成粗绳、灯芯绒或锐化条纹。场景建筑与汽车在远处自然退焦，裤子织纹与缝线仍清晰。'
    save('lookbook',[prompt,refined],[files[r['reference_type']] for r in creative['generation_references']])
    (case/'validation-plan.json').write_text(json.dumps({'restart':'用户指定全部使用 imgx，GPT Image 2 不纳入本轮验收','parameters':'2:3 / 4K / 每个提示词 1 张','design':'标准单阶段对照、标准两阶段、Lookbook 原提示词与无遮挡编排；独立请求并发，两阶段依赖顺序执行','depth':'复用同一动作原图已经实际推理的 quality 深度图，不重新生成或替换固定模型','limits':'imgx 原始输出，不混入应用面料增强；直接验证提示词与素材组合，不等价于完整应用 HTTP 回归'},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
