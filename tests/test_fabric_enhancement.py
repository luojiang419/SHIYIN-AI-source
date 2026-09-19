from pathlib import Path
import asyncio
from unittest.mock import patch

import numpy as np
from PIL import Image
import main
from canvas_core.fabric_enhancement import enhance_fabric_image, garment_mask


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
