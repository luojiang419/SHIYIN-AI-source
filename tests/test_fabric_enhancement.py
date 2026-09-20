from pathlib import Path
import asyncio
from unittest.mock import AsyncMock, patch

import numpy as np
from PIL import Image
import main
from canvas_core.fabric_enhancement import enhance_fabric_image, garment_mask, refine_garment_boundary


def test_flat_material_skips_without_writing(tmp_path):
    src = tmp_path/'base.png'
    Image.new('RGB', (640, 800), (90, 60, 55)).save(src)
    out = tmp_path/'result.png'
    assert enhance_fabric_image(src, src, out)['status'] == 'skipped'
    assert not out.exists()


def test_missing_foreground_never_changes_background():
    assert garment_mask(np.zeros((400, 400, 3), dtype='uint8'), np.array([0, 128, 128]), None) is None


def test_woven_transfer_keeps_outside_pixels_and_hem(tmp_path):
    h, w = 1000, 700
    base = np.full((h, w, 3), 225, dtype='uint8')
    base[100:930, 180:510] = [96, 66, 60]
    y, x = np.mgrid[:800, :640]
    signal = (np.sin((x+y*.7)*2.1)*16).astype('int16')
    detail = np.clip(np.array([96,66,60])[None,None]+signal[:,:,None], 0,255).astype('uint8')
    foreground = np.zeros((h, w), 'uint8'); foreground[80:960, 140:550] = 160
    src, ref, control, out = [tmp_path/name for name in ('base.png','detail.png','depth.png','out.png')]
    for array,path in ((base,src),(detail,ref),(foreground,control)):
        Image.fromarray(array).save(path)
    result = enhance_fabric_image(src, ref, out, control)
    assert result['status'] == 'applied'
    image = np.asarray(Image.open(out))
    assert np.array_equal(image[:80], base[:80])
    assert np.array_equal(image[950:], base[950:])
    assert np.array_equal(image[:, :120], base[:, :120])
    assert np.any(image[895:920, 200:480] != base[895:920,200:480])


def payload():
    return main.OnlineImageRequest(prompt='test',operation='pose_replicate',
        reference_images=[main.AIReference(url='/detail',role='fabric_detail'),main.AIReference(url='/control',role='control_map')],
        prompt_context={'fabric_enhancement':True,'control_mode':'depth','scenario_id':'base-wardrobe'})


def test_postprocessor_failure_preserves_original():
    batch={'images':['/original'],'image_items':[{'url':'/original'}]}
    with patch.object(main,'output_file_from_url',return_value='test.png'), patch('canvas_core.fabric_enhancement.enhance_fabric_image',side_effect=ValueError('bad')):
        result=asyncio.run(main.apply_pose_fabric_enhancement(payload(),batch))
    assert result['images']==['/original']
    assert result['original_images']==['/original']
    assert result['fabric_enhancement'][0]['status']=='skipped'


def test_postprocessor_updates_both_image_lists():
    batch={'images':['/original'],'image_items':[{'url':'/original'}]}
    with patch.object(main,'output_file_from_url',return_value='test.png'), patch('canvas_core.fabric_enhancement.enhance_fabric_image',return_value={'status':'applied'}), patch.object(main,'media_url_from_path',return_value='/enhanced'), patch.object(main,'image_output_meta',return_value={'url':'/enhanced'}):
        result=asyncio.run(main.apply_pose_fabric_enhancement(payload(),batch))
    assert result['images']==['/enhanced']
    assert result['image_items']==[{'url':'/enhanced'}]
    assert result['original_images']==['/original']


def test_all_ecommerce_workspaces_select_their_garment_owner_as_texture_evidence():
    cases = {
        'universal': ([{'role':'full_garment','url':'/garment'}], ['/garment']),
        'try_on': ([{'role':'upper_garment','url':'/upper'}, {'role':'source','url':'/person'}], ['/upper']),
        'pose_transfer': ([{'role':'source','url':'/person'}], ['/person']),
    }
    for operation, (references, expected) in cases.items():
        assert main.ecommerce_fabric_reference_urls(operation, references) == expected


def test_shared_ecommerce_postprocessor_keeps_original_when_mask_is_ambiguous():
    batch = {'images':['/original'], 'image_items':[{'url':'/original'}]}
    references = [{'role':'full_garment', 'url':'/garment'}]
    with patch.object(main, 'output_file_from_url', return_value='test.png'), patch(
        'canvas_core.fabric_enhancement.enhance_fabric_image', return_value={'status':'skipped', 'reason':'garment_mask_ambiguous'}
    ):
        result = asyncio.run(main.apply_fabric_enhancement('universal', references, batch))
    assert result['images'] == ['/original']
    assert result['original_images'] == ['/original']
    assert result['fabric_enhancement'][0]['reason'] == 'garment_mask_ambiguous'


def test_universal_texture_reuses_bound_detail_without_double_overlay():
    refs = [
        {'reference_type':'lower_garment', 'reference_id':'pants', 'url':'/pants'},
        {'reference_type':'upper_garment', 'reference_id':'shirt', 'url':'/shirt'},
        {'reference_type':'detail', 'detail_target_id':'pants', 'url':'/pants-detail'},
        {'reference_type':'detail', 'detail_target_id':'missing', 'url':'/unbound'},
    ]
    assert main.ecommerce_fabric_reference_urls('universal', refs) == ['/pants-detail', '/shirt']


def test_universal_legacy_single_product_detail_and_other_pages_are_preserved():
    refs = [{'role':'lower_garment','url':'/pants'}, {'role':'detail','url':'/detail'}]
    assert main.ecommerce_fabric_reference_urls('universal', refs) == ['/detail']
    assert main.ecommerce_fabric_reference_urls('pose_replicate', [
        {'role':'fabric_detail','url':'/detail'}, {'role':'target_image','url':'/pants'}
    ]) == ['/detail']


def test_pose_uses_garment_only_when_no_bound_detail():
    assert main.ecommerce_fabric_reference_urls('pose_replicate', [
        main.AIReference(url='/pants', role='target_image')
    ]) == ['/pants']


def test_pose_bound_detail_is_applied_once_not_followed_by_full_garment():
    refs = [main.AIReference(url='/detail', role='fabric_detail'),
            main.AIReference(url='/pants', role='target_image')]
    batch = {'images':['/original'], 'image_items':[{'url':'/original'}]}
    with patch.object(main, 'output_file_from_url', return_value='source.png'), patch(
        'canvas_core.fabric_enhancement.enhance_fabric_image', return_value={'status':'applied'}
    ) as enhance, patch.object(main, 'media_url_from_path', return_value='/enhanced'), patch.object(
        main, 'image_output_meta', return_value={'url':'/enhanced'}
    ):
        result = asyncio.run(main.apply_fabric_enhancement('pose_replicate', refs, batch))
    assert enhance.call_count == 1
    assert len(result['fabric_enhancement'][0]['steps']) == 1


def test_boundary_guard_removes_connected_skin_shadow_and_keeps_cloth():
    base = np.full((1000, 700, 3), 210, dtype='uint8')
    base[120:800, 180:520] = [65, 39, 40]
    base[800:950, 210:480] = [155, 110, 121]
    # 紧贴裤脚的皮肤阴影在旧颜色容差内，粗掩膜会连同阴影一起选中。
    base[800:815, 290:380] = [89, 56, 65]
    mask = np.zeros((1000, 700), dtype='uint8')
    mask[120:800, 180:520] = 255
    mask[800:815, 290:380] = 255
    refined = refine_garment_boundary(base, mask)
    assert refined is not None
    assert not np.any(refined[800:])
    assert np.all(refined[760:790, 210:480] == 255)
    assert not np.any(refined[mask == 0])


def test_uncertain_boundary_skips_instead_of_using_unprotected_mask():
    with patch('canvas_core.fabric_enhancement.cv2.grabCut', side_effect=__import__('cv2').error('failure')):
        base = np.full((400, 400, 3), 90, dtype='uint8')
        mask = np.zeros((400, 400), dtype='uint8')
        mask[80:320, 100:300] = 255
        assert refine_garment_boundary(base, mask) is None


def test_universal_material_mask_uses_depth_of_actual_output(tmp_path):
    batch={'images':['/output'],'image_items':[{'url':'/output'}]}
    refs=[{'role':'lower_garment','reference_id':'pants','url':'/pants'}, {'role':'detail','detail_target_id':'pants','url':'/detail'}]
    with patch.object(main,'output_file_from_url',side_effect=lambda url:'output.png' if url=='/output' else 'detail.png'), patch.object(main,'render_universal_person_depth',AsyncMock(return_value=(b'depth','quality'))) as depth, patch.object(main,'OUTPUT_OUTPUT_DIR',str(tmp_path)), patch.object(main,'media_url_from_path',side_effect=lambda path:path), patch.object(main,'image_output_meta',return_value={}), patch('canvas_core.fabric_enhancement.enhance_fabric_image',return_value={'status':'applied'}) as enhance:
        result=asyncio.run(main.apply_fabric_enhancement('universal',refs,batch,{'infer_output_depth':True}))
    depth.assert_awaited_once_with('output.png')
    assert Path(enhance.call_args.args[3]).read_bytes()==b'depth'
    assert enhance.call_count==1
    assert result['fabric_enhancement'][0]['output_depth']['source_url']=='/output'


def test_universal_output_depth_failure_keeps_existing_mask_fallback():
    batch={'images':['/output'],'image_items':[{'url':'/output'}]}
    with patch.object(main,'output_file_from_url',return_value='output.png'), patch.object(main,'render_universal_person_depth',AsyncMock(side_effect=ValueError('not ready'))), patch('canvas_core.fabric_enhancement.enhance_fabric_image',return_value={'status':'skipped','reason':'garment_mask_ambiguous'}) as enhance:
        result=asyncio.run(main.apply_fabric_enhancement('universal',[{'role':'lower_garment','url':'/pants'}],batch,{'infer_output_depth':True}))
    assert enhance.call_args.args[3] is None
    assert result['images']==['/output']
    assert result['fabric_enhancement'][0]['output_depth']['status']=='skipped'
