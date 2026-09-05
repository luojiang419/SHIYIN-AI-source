import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import main
from canvas_core.pose_replicate_prompts import (
    PoseReplicatePromptError, compile_pose_replicate_prompt, pose_replicate_template_catalog,
)
from tests.test_pose_replicate_prompts import task_request


def test_catalog_is_the_actual_compiler_for_all_eight_combinations():
    entries = pose_replicate_template_catalog()
    assert len(entries) == len({entry['key'] for entry in entries}) == 8
    for entry in entries:
        roles = {item['role'] for item in entry['reference_order']}
        params = dict(has_model_subject='model_subject' in roles, has_scene='scene' in roles)
        default = compile_pose_replicate_prompt(entry['mode'], output_aspect_ratio='3:4', **params)
        custom = compile_pose_replicate_prompt(entry['mode'], output_aspect_ratio='3:4', custom_template=entry['prompt'], **params)
        assert default.final_prompt == custom.final_prompt
        assert default.reference_order == custom.reference_order
        assert '{{output_aspect_ratio}}' in entry['prompt']


@pytest.mark.parametrize('text', ['', '   ', 'x' * 30001])
def test_invalid_custom_templates_do_not_silently_fall_back(text):
    with pytest.raises(PoseReplicatePromptError):
        compile_pose_replicate_prompt('depth', custom_template=text)


def test_custom_prompt_is_literal_and_replaces_all_hidden_defaults():
    result = compile_pose_replicate_prompt('depth', custom_template='测试 {json:1}\n{{output_aspect_ratio}}\n{{user_instruction}}', user_instruction='调整\n受力', output_aspect_ratio='3:4')
    assert result.final_prompt == '测试 {json:1}\n3:4\n调整\n受力'
    assert result.prompt_source == 'custom-template'
    assert result.normalized_instruction == ''


def test_custom_api_submits_exact_prompt_without_assistant_or_optimizer():
    payload = task_request(instruction='补充', model=True, scene=True)
    payload.prompt_policy.custom_template = '仅使用我的规则\n{{user_instruction}}'
    payload.prompt_policy.custom_template_key = 'skeleton:model-full-look-scene'
    normalize = AsyncMock()
    submit = AsyncMock(return_value={'task_id':'custom-test', 'status':'queued'})
    with patch.object(main, 'normalize_pose_replicate_instruction', normalize), patch.object(main, 'create_canvas_image_task', submit), patch.object(main, 'resolve_image_generation_selection', return_value={'provider_id':payload.generation.provider_id, 'model':payload.generation.model}):
        result = asyncio.run(main.create_pose_replicate_task(payload))
    normalize.assert_not_called()
    actual = submit.await_args.args[0]
    assert actual.prompt == '仅使用我的规则\n补充'
    assert actual.auto_optimize_prompt is False
    assert result['pose_replicate']['prompt_source'] == 'custom-template'
    assert len(actual.reference_images) == 5


def test_stale_combination_is_rejected_before_submission():
    payload = task_request()
    payload.prompt_policy.custom_template = '自定义规则'
    payload.prompt_policy.custom_template_key = 'depth:base-wardrobe'
    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.create_pose_replicate_task(payload))
    assert exc.value.status_code == 400


def test_custom_without_instruction_slot_keeps_node_supplement():
    result = compile_pose_replicate_prompt('skeleton', custom_template='我的规则', user_instruction='补充')
    assert result.final_prompt == '我的规则\n\n【用户补充要求】\n补充'


def test_expanded_template_limit_returns_actionable_client_error():
    payload = task_request(instruction='补充' * 2000)
    payload.prompt_policy.custom_template = '{{user_instruction}}' * 10
    payload.prompt_policy.custom_template_key = 'skeleton:base-wardrobe'
    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.create_pose_replicate_task(payload))
    assert exc.value.status_code == 400
    assert '展开后超过' in exc.value.detail
