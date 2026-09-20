import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from canvas_core.ecommerce import build_prompt, universal_style_references


def references():
    return [dict(role=role, reference_type=role, reference_id=role, url=f"/assets/input/{role}.jpg",
                 **({"detail_target_id": "lower_garment", "label": "后腰细节"} if role == "detail" else {}))
            for role in ["subject", "model_identity", "lower_garment", "detail", "pose", "scene"]]


@pytest.mark.parametrize("style", ["standard_product", "lookbook"])
def test_styles_preserve_product_and_face_ownership_without_base_scene_conflicts(style):
    prompt = build_prompt("universal", references(), {"generation_style": style})
    assert "FACE ONLY OWNER" in prompt
    assert "LOCAL DETAIL" in prompt and f"product Image {4 if style == 'standard_product' else 3}" in prompt
    assert "ENVIRONMENT OWNER" in prompt
    assert "never paste them onto the front" in prompt
    assert "MATERIAL EVIDENCE LOCK" in prompt
    assert "BODY AND BASE SCENE OWNER" not in prompt
    assert ("STRICT POSE OWNER" in prompt) == (style == "standard_product")
    assert ("Pose reference is inspiration only" in prompt) == (style == "lookbook")


def test_invalid_style_rejected_and_free_creation_unaffected():
    with pytest.raises(ValueError, match="生成风格"):
        build_prompt("universal", references(), {"generation_style": "unknown"})
    assert build_prompt("universal", references(), {"generation_style": "lookbook", "prompt_policy": "free", "instruction": "exact brief"}) == "exact brief"


def test_depth_append_preserves_indices_and_actual_bytes(tmp_path):
    import main
    from PIL import Image
    source = tmp_path / "pose.jpg"
    Image.new("RGB", (32, 48)).save(source)
    snapshot = {"operation": "universal", "options": {"generation_style": "standard_product"}, "inputs": references(), "prompt": "base"}
    worker = SimpleNamespace(estimate=lambda content, bit_depth: SimpleNamespace(content=b"real-depth-result"))
    with patch.object(main, "output_file_from_url", return_value=str(source)), patch.object(main, "sync_depth_model_preference", return_value=SimpleNamespace(quality=True, tier="quality")), patch.object(main, "PERSON_DEPTH_COMPONENT_MANAGER") as manager, patch.object(main, "PERSON_DEPTH_WORKER", worker), patch.object(main, "OUTPUT_OUTPUT_DIR", str(tmp_path)), patch.object(main, "media_url_from_path", side_effect=lambda p: "/assets/output/" + Path(p).name):
        manager.public_status.return_value = {"ready": True}
        refs, prompt, audit = asyncio.run(main.prepare_universal_pose_depth(snapshot))
    assert len(snapshot["inputs"]) == 6 and len(refs) == 7
    assert {r['reference_id'] for r in refs} == {r['reference_id'] for r in snapshot['inputs']} | {'derived_pose_depth'}
    assert "Image 4" in prompt and "pose Image 3" in prompt
    assert audit["status"] == "succeeded"
    assert next(tmp_path.glob("universal_pose_depth_*.png")).read_bytes() == b"real-depth-result"


def test_lookbook_does_not_lock_creative_pose():
    import main
    with patch.object(main, "sync_depth_model_preference") as selection:
        refs, prompt, audit = asyncio.run(main.prepare_universal_pose_depth({"operation": "universal", "options": {"generation_style": "lookbook"}, "inputs": references(), "prompt": "creative"}))
    selection.assert_not_called()
    assert audit["status"] == "not_required" and len(refs) == 5
    assert not any(ref.get("reference_type") == "pose" for ref in refs)


def test_missing_depth_stops_standard_instead_of_silent_downgrade(tmp_path):
    import main
    from PIL import Image
    source = tmp_path / "pose.jpg"
    Image.new("RGB", (32, 48)).save(source)
    with patch.object(main, "output_file_from_url", return_value=str(source)), patch.object(main, "sync_depth_model_preference", return_value=SimpleNamespace(quality=True)), patch.object(main, "PERSON_DEPTH_COMPONENT_MANAGER") as manager:
        manager.public_status.return_value = {"ready": False}
        with pytest.raises(ValueError, match="尚未就绪"):
            asyncio.run(main.prepare_universal_pose_depth({"operation": "universal", "options": {"generation_style": "standard_product"}, "inputs": references(), "prompt": "base"}))


@pytest.mark.parametrize("role", ["lower_garment", "upper_garment", "full_garment", "detail", "subject", "model_subject", "model_identity"])
def test_gemini_product_references_keep_full_resolution(role):
    import main
    with patch.object(main, "reference_to_data_url", return_value="data:image/png;base64,eA==") as encode:
        main.gemini_reference_part({"role": role, "url": "/assets/input/product.jpg"})
    assert encode.call_args.kwargs == {"max_size": None, "lossless": True}


def test_deferred_recovery_does_not_reload_live_ecommerce_tasks():
    import main
    with patch.object(main, "STARTUP_RECOVERY_DELAY_SECONDS", 0), patch.object(main, "ACTIVE_CANVAS_ID", ""), patch.object(main, "load_online_image_tasks_from_disk"), patch.object(main, "load_canvas_video_tasks_from_disk"), patch.object(main, "resume_canvas_video_tasks"), patch.object(main, "ensure_ecommerce_tasks_loaded") as ensure, patch.object(main, "load_ecommerce_tasks_from_disk") as reload_tasks:
        asyncio.run(main.run_deferred_task_recovery())
    ensure.assert_called_once()
    reload_tasks.assert_not_called()


def test_manual_numbered_standard_brief_preserves_input_order():
    refs = references()[::-1]
    assert universal_style_references(refs, 'standard_product', True) == refs
    prompt = build_prompt('universal', refs, {'generation_style': 'standard_product', 'instruction': '图1保留场景'})
    assert 'ENVIRONMENT OWNER: Image 1' in prompt


def test_manual_lookbook_keeps_reference_numbers_while_default_ignores_pose():
    refs=references()[::-1]
    assert universal_style_references(refs,'lookbook',True) == refs
    prompt=build_prompt('universal',refs,{'generation_style':'lookbook','instruction':'图1为场景'})
    assert 'ENVIRONMENT OWNER: Image 1' in prompt
    assert 'BODY OWNER: Image 6' in prompt
    assert 'STRICT POSE OWNER' not in prompt


def test_standard_reserves_model_capacity_for_depth():
    import main
    provider = {'id': 'shiying', 'name': 'shiying', 'enabled': True, 'image_models': ['gemini-3-pro-image-preview']}
    payload = main.EcommerceTaskRequest(operation='universal', mode='standard', inputs=references(), options={'generation_style': 'standard_product'}, provider_id='shiying', model='gemini-3-pro-image-preview', aspect_ratio='2:3', resolution='2k', quality='high', count=1)
    with patch.object(main, 'configured_ecommerce_providers', return_value=[provider]), patch.object(main, 'validate_ecommerce_local_inputs', return_value=(references(), (640,960))), patch.object(main, 'ecommerce_route_candidates', return_value=[{'max_reference_images':6}]):
        with pytest.raises(main.HTTPException, match='7'):
            main.prepare_ecommerce_request(payload)


def test_standard_two_stage_excludes_product_pose_contamination(tmp_path):
    import main
    refs = references() + [{'role':'control_map','reference_type':'control_map','url':'/assets/output/depth.png'}]
    snapshot = {'operation':'universal','options':{'generation_style':'standard_product', 'reference_analysis':{'subject':{'status':'succeeded','face_direction':'old base direction'}}},'size':'2560x3840','quality':'high'}
    generate = AsyncMock(return_value={'images':['/assets/output/anchor.png'],'generation_elapsed_seconds':12})
    with patch.object(main,'execute_ai_image_batch',generate), patch.object(main,'render_universal_person_depth',AsyncMock(return_value=(b'depth','quality'))) as depth, patch.object(main,'OUTPUT_OUTPUT_DIR',str(tmp_path)), patch.object(main,'output_file_from_url',return_value='anchor.png'), patch.object(main,'media_url_from_path',return_value='/assets/output/edit-depth.png'):
        final_refs, prompt, audit = asyncio.run(main.prepare_universal_product_anchor(snapshot, {'provider_id':'shiying','model':'gemini-3-pro-image-preview'},refs,'old'))
    sent=generate.call_args.kwargs
    assert [r['reference_type'] for r in sent['references']] == ['pose','control_map','subject','model_identity','scene']
    assert [r['reference_type'] for r in final_refs] == ['subject','control_map','lower_garment','detail']
    assert final_refs[0]['url'] == '/assets/output/anchor.png'
    assert 'old base direction' not in prompt
    assert 'FINAL LOCAL PRODUCT EDIT' in prompt and '不可重构' in prompt
    assert 'UNIVERSAL PRODUCT COMPOSITION' not in prompt
    assert final_refs[0]['role'] == 'source'
    assert audit['status'] == 'succeeded' and sent['count'] == 1
    assert audit['product_edit_template'] == 'pose-replicate.v3.5.base-wardrobe.depth.zh-CN'
    assert audit['edit_depth']['source_url'] == '/assets/output/anchor.png'
    depth.assert_awaited_once_with('anchor.png')
    assert '真正更换面料' in prompt and '图4是服装面料' in prompt


@pytest.mark.parametrize('options', [{'generation_style':'lookbook'}, {'generation_style':'standard_product','instruction':'保留图1'}])
def test_anchor_skips_creative_or_explicit_numbered_requests(options):
    import main
    refs = references() + [{'role':'control_map','reference_type':'control_map','url':'/assets/output/depth.png'}]
    with patch.object(main,'execute_ai_image_batch',AsyncMock()) as generate:
        result = asyncio.run(main.prepare_universal_product_anchor({'operation':'universal','options':options},{},refs,'original'))
    generate.assert_not_called()
    assert result[:2] == (refs,'original')


def test_pose_anchor_is_transmitted_losslessly_at_original_resolution():
    import main
    with patch.object(main,'reference_to_data_url',return_value='data:image/png;base64,eA==') as encode:
        main.gemini_reference_part({'role':'source','reference_id':'universal_pose_anchor'})
    assert encode.call_args.kwargs == {'max_size':None,'lossless':True}


@pytest.mark.parametrize('style',['standard_product','lookbook'])
def test_scene_photography_separates_sku_albedo_from_reference_exposure(style):
    prompt=build_prompt('universal', references(), {'generation_style':style})
    assert 'INTRINSIC COLOR' in prompt
    assert 'scene-color contamination' not in prompt
    assert 'exact observed product color, hue, saturation, value, white balance' not in prompt
    assert '删除模特参考原有的棚拍补光' in prompt
    assert '远处窗格和树叶不能与衣服织纹同样锐利' in prompt
    assert '焦点堆栈' in prompt
    assert '商品' in prompt and '焦平面' in prompt
