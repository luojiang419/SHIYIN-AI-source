"""任务222：严格使用用户三张图进行动作/版型分离实验，不修改默认路由。"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / '.codex-artifacts/pose-transfer-222/depth-fit-exact-three-20260928'
SOURCES = {
    'pose': Path('//192.168.0.188/^0^ Lookbook Store/时颖新品/LC787/LC7876675/LC7876675-P605.jpg'),
    'source': Path('//192.168.0.188/摄影/100拍摄/人台图/LC78/LC7876670/LC7876670-P105/XSY_2074.jpg'),
    'source_view_1': Path('//192.168.0.188/摄影/100拍摄/人台图/LC78/LC7876670/LC7876670-P105/XSY_2081.jpg'),
}


def ref(path, role):
    mime = 'image/png' if path.suffix == '.png' else 'image/jpeg'
    return {'role': role, 'url': f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode(),
            'garment_design_owner': role == 'source', 'name': path.name}


async def run(round_name):
    import main
    OUT.mkdir(parents=True, exist_ok=True)
    for role, path in SOURCES.items():
        dest = OUT / (role + '.jpg')
        if not dest.exists():
            dest.write_bytes(path.read_bytes())
    depth = OUT / 'depth.png'
    if not depth.exists():
        print('Extracting registered person depth from exact A input', flush=True)
        content, tier = await main.render_universal_person_depth(str(OUT / 'pose.jpg'))
        depth.write_bytes(content)
        (OUT / 'depth-audit.json').write_text(json.dumps({'tier': tier, 'source_sha256': hashlib.sha256((OUT / 'pose.jpg').read_bytes()).hexdigest()}, indent=2))
    paths = [(OUT/'source.jpg', 'source'), (OUT/'pose.jpg', 'pose'), (depth, 'control_map'), (OUT/'source_view_1.jpg', 'source_view_1')]
    if round_name == 'baseline':
        refs = [ref(path, role) for path, role in paths]
        prompt = main.build_ecommerce_prompt('pose_transfer', refs, {'pose_source': 'reference'})
    else:
        prompt = (
            'Create one realistic product photograph at 4:5. Image 1 and Image 4 show the SAME B jeans from two real angles. '
            'Use B as the sole garment design: blue washed denim, original waist height and rise, five-pocket construction, '
            'silver button, ochre stitching, curved front/outer-thigh panel seams visible on BOTH legs in the front view, '
            'fitted thighs and knees opening into WIDE FLARED hems. Preserve the exact seam topology visible across the two views; '
            'do not invent or remove a seam based on its being occluded in one view. Keep B white crop top and blue open-toe sandals. '
            'Image 2 provides the target pose and crop; Image 3 is its registered near-white/far-gray depth. '
            'Match A body joint centers and occlusion order exactly: screen-right hand tucked into the pocket, screen-left arm down, '
            'screen-right leg straight and weight-bearing in FRONT, screen-left knee bent to the left and its lower leg crossing BEHIND '
            'toward the screen-right ankle. Front foot points to screen-left. Keep the cropped torso, no head, white background. '
            'The depth constrains the BODY INSIDE the clothing only. Its clothed boundary is NOT the body and MUST NOT constrain '
            'B garment width, hems, panel shape, cloth ease or folds. Reconstruct B around the fixed joint centers. '
            'The B flare fabric must extend OUTSIDE A depth silhouette on both sides below the knee; this is required, not a pose error. '
            'Preserve B actual knee-to-hem expansion, trouser length and broad lower-leg volume. '
            'Only articulated draping and physically necessary occlusion may change; product construction, color and material stay B. '
            'Output one photo with no captions, diagrams or comparison panels.'
        )
        refs = [ref(path, role) for path, role in paths]
        if round_name in {'depth_only', 'body_depth', 'flare_ratio'}:
            paths = [paths[0], paths[2], paths[3]]
            refs = [ref(path, role) for path, role in paths]
            prompt = prompt.replace('Image 1 and Image 4', 'Image 1 and Image 3').replace(
                'Image 2 provides the target pose and crop; Image 3 is its registered near-white/far-gray depth.',
                'Image 2 is the target pose near-white/far-gray registered depth map; derive the exact body pose and crop from it.')
    if round_name == 'body_depth' and not (OUT/'neutralize.png').is_file():
        raise ValueError('请先执行 neutralize 并人工检查中间图；生成式深度不是实测人体几何')
    if round_name == 'neutralize':
        paths = [(OUT/'pose.jpg', 'pose'), (depth, 'control_map')]
        refs = [ref(path, role) for path, role in paths]
        prompt = ('Produce a grayscale anatomical pose depth CONTROL MAP, not a photograph. Image 2 is the registered depth of image 1. '
                  'Keep the exact frame, cropped torso, hip center, arm and hand joint locations, knee centers, ankle centers, bent left-screen knee and lower leg crossing BEHIND the straight right-screen leg. '
                  'White is near and dark gray is far, black background. Render smooth neutral solid mannequin anatomy with no garment or surface details. '
                  'Remove trouser and boot geometry: lower legs are smooth tapered anatomical calf cylinders, feet plain anatomical blocks at the original foot angles. '
                  'Retain the hand inserted at hip and hanging other arm. Do not include clothing hems, seams, folds, pockets, shoes, accessories, fabric silhouette or colors. '
                  'No head beyond the existing crop. Exact same joint centers and occlusions, smooth grayscale depth only.')
    elif round_name == 'body_depth':
        paths[1] = (OUT/'neutralize.png', 'control_map')
        refs = [ref(path, role) for path, role in paths]
        prompt += (' This depth map depicts the unclothed neutral body INSIDE B trousers, not the garment envelope. '
                   'Preserve the broad bell-shaped B hems seen in both garment photos. The front hem must be substantially wider than the knee, '
                   'and must project outside the anatomical depth calf. Keep the original B fabric allowance around calf and original floor-length hems. '
                   'Do not narrow the garment to fit the control map. Plain white background.')
    if round_name == 'flare_ratio':
        prompt += (' PRODUCT PATTERN MEASUREMENT PRIORITY: These are flared jeans, never straight jeans. '
                   'For each leg the opening measured perpendicular to its own leg axis should visually be about 1.6 times the knee width, '
                   'as the supplied B product evidence shows; this is an approximate image-space check, not a tailoring measurement. '
                   'Preserve the fitted knee and widen both outer and inner edges progressively below it. '
                   'The front leg hem must cover most of the sandal upper and extend sideways beyond it; retain the original long inseam. '
                   'Use B side image to reproduce the hem depth, flare profile and the topstitched side seam exactly. '
                   'Move anatomical joints to the target depth but NEVER force garment boundaries to coincide with depth boundaries. '
                   'The rear bent leg keeps its own full flare even where hidden behind the front leg. '
                   'Do not make lower legs slim or straight. Match B product color. White background.')
    audit = {'round': round_name, 'model': 'gemini-3-pro-image-preview', 'size': '2560x3200', 'prompt': prompt,
             'references': [{'role': role, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path, role in paths]}
    (OUT/f'{round_name}-request.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Generating', round_name, flush=True)
    started = time.monotonic()
    result, _ = await main.generate_gemini_provider_image(prompt, audit['size'], audit['model'], reference_images=refs, provider=main.get_api_provider_exact('shiying'))
    if result.get('type') != 'b64':
        raise RuntimeError('Unexpected image result type: ' + str(result.get('type')))
    output = OUT/f'{round_name}.png'
    output.write_bytes(base64.b64decode(result['value']))
    (OUT/f'{round_name}-result.json').write_text(json.dumps({'path': str(output), 'elapsed_s': round(time.monotonic()-started, 2), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}, indent=2))
    print('Saved', output, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('round', choices=['baseline', 'separated', 'depth_only', 'neutralize', 'body_depth', 'flare_ratio'])
    asyncio.run(run(parser.parse_args().round))
