import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import main
from canvas_core.pose_replicate_prompts import compile_pose_replicate_prompt


@pytest.mark.parametrize('mode', ['depth', 'skeleton'])
@pytest.mark.parametrize('model,scene', [(False, False), (True, False), (False, True), (True, True)])
@pytest.mark.parametrize('custom', [None, '使用已有参考 {{output_aspect_ratio}}'])
def test_fabric_appends_role_without_renumbering(mode, model, scene, custom):
    args = dict(has_model_subject=model, has_scene=scene, custom_template=custom)
    original = compile_pose_replicate_prompt(mode, **args)
    fabric = compile_pose_replicate_prompt(mode, has_fabric_detail=True, **args)
    assert fabric.reference_order[:-1] == original.reference_order
    assert fabric.reference_order[-1]['role'] == 'fabric_detail'
    assert fabric.reference_order[-1]['index'] == len(original.reference_order) + 1
    assert fabric.final_prompt.startswith(original.final_prompt)
    assert f'图{len(fabric.reference_order)}是服装面料' in fabric.final_prompt
    assert '放大倍率不能放大成衣图案或纤维' in fabric.final_prompt


@pytest.mark.parametrize('batch_size,batch_outfit,enabled', [(1, None, True), (2, None, False), (1, {'group_id':'test', 'style_name':'test'}, False)])
def test_endpoint_only_includes_fabric_in_single_image(batch_size, batch_outfit, enabled):
    ref = lambda name: main.AIReference(url=f'/assets/{name}.png', kind='image')
    payload = main.PoseReplicateTaskRequest(
        mode='skeleton', batch_size=batch_size, batch_outfit=batch_outfit,
        inputs=main.PoseReplicateInputs(pose_reference=ref('target'), control_map=ref('control'),
                                      target_image=ref('garment'), fabric_detail=ref('fabric')),
        generation=main.PoseReplicateGeneration(aspect_ratio='3:4'),
    )
    submit = AsyncMock(return_value={'task_id':'fabric-test', 'status':'queued'})
    with patch.object(main, 'create_canvas_image_task', submit), patch.object(
        main, 'resolve_image_generation_selection', return_value={'provider_id':'shiying', 'model':'gemini-3-pro-image-preview'}
    ):
        asyncio.run(main.create_pose_replicate_task(payload))
    actual = submit.await_args.args[0]
    assert ('fabric_detail' in [item.role for item in actual.reference_images]) is enabled
    assert ('【面料细节参考补充】' in actual.prompt) is enabled
    assert actual.prompt_context['assistant_calls'] == 0
    submit.assert_awaited_once()


def test_gemini_fabric_role_binding_preserves_material_scope():
    text = main.gemini_reference_role_text({'role':'fabric_detail', 'asset_index':6}, 1)
    assert '图6' in text and '放大倍率' in text
    refs = [{'role':role} for role in ['pose_reference', 'control_map', 'target_image']]
    original = main.gemini_reference_roles_anchor(refs)
    updated = main.gemini_reference_roles_anchor(refs + [{'role':'fabric_detail'}])
    assert updated.startswith(original)
    assert '微观质感' in updated
