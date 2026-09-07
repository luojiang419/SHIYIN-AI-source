import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import main
from canvas_core.video_prompt_adapter import (
    SEMANTIC_EQUIVALENCE_CONTRACT, adaptation_message, build_adaptation_system,
    needs_video_prompt_adaptation, target_profile, validate_adapted_prompt,
)
from canvas_core.video_prompt_registry import PROFILES, registered_profile


H3 = 'integrated_multimodal_description:\nA woman walks left and says <d>[Chinese]你好</d>.\noverall_soundscape:\nFootsteps.\nnon_diegetic_music:\nN/A'
ADAPTED = '女子向左走，镜头跟随，她说“你好”，脚步声清晰，无配乐。'


@pytest.fixture
def service(monkeypatch):
    llm = AsyncMock(return_value={'text': ADAPTED})
    monkeypatch.setattr(main, 'canvas_llm', llm)
    monkeypatch.setattr(main, 'configured_image_prompt_optimizer_route', lambda *args: {
        'provider_id': 'assistant', 'model': 'test-chat',
    })
    monkeypatch.setattr(main, 'get_api_provider', lambda provider_id: {
        'id': provider_id, 'protocol': provider_id,
    })
    return llm


@pytest.mark.parametrize('provider,model,expected', [
    ('kling-cli', 'kling-v3-omni', 'kling-omni'),
    ('gateway', 'Kling VIDEO 3.0', 'kling'),
    ('jimeng', 'video-3.0', 'generic'),
    ('jimeng', 'seedance2.0_vip', 'seedance'),
    ('gateway', 'doubao-seedance-2-0', 'seedance'),
    ('gateway', 'doubao-seedance-2-0-260128', 'seedance'),
    ('gateway', 'seedance2.5', 'seedance-2.5'),
    ('gateway', 'seedance2.5_vip', 'seedance-2.5'),
    ('gateway', 'doubao-seedance-2-5-pro-260901', 'seedance-2.5'),
    ('gateway', 'seedance-1.0-pro', 'generic'),
    ('gateway', 'seedance-2.50-pro', 'generic'),
    ('linkfox', '海螺2.3', 'generic'),
    ('linkfox', 'wan2.6', 'generic'),
    ('linkfox', 'HappyHorse', 'generic'),
    ('gateway', 'veo3', 'generic'),
])
def test_target_model_profiles(provider, model, expected):
    assert target_profile(provider, model) == expected


def test_detection_includes_old_six_section_prompts_and_source_metadata():
    assert needs_video_prompt_adaptation('retention_analysis: ...', 'jimeng', '')
    assert needs_video_prompt_adaptation('资产映射：图1\n<Subject 1> runs', 'kling-cli', '')
    assert needs_video_prompt_adaptation('A woman walks.', 'jimeng', '', 'MiniMax H3')
    assert not needs_video_prompt_adaptation(H3, 'gateway', 'MiniMax H3')
    assert not needs_video_prompt_adaptation('A woman walks.', 'jimeng', '')


def test_only_core_model_families_have_specialized_skills():
    assert set(PROFILES) == {'minimax-h3', 'kling-cli', 'kling-linkfox', 'seedance', 'seedance-2.5'}
    for model in ('海螺2.3', 'wan2.6', 'HappyHorse', 'veo3-fast', 'unknown-video'):
        assert registered_profile('linkfox', model) == 'generic'
        skill, profile = main._video_prompt_skill('linkfox', model)
        assert profile == 'generic'
        assert '通用视频提示词规范' in skill
        assert '通用视频模型' in build_adaptation_system(model, 2000)


@pytest.mark.parametrize('profile,required', [
    ('minimax-h3', '三字段或六字段模式'),
    ('kling-omni', '<<<image_N>>> / <<<video_N>>>'),
    ('kling', '不得输出 Omni 标签'),
    ('kling-linkfox', '不得伪造三角括号主体绑定'),
    ('seedance', '优先相对节拍'),
    ('seedance-2.5', '只在用户原文已有数字时间段'),
    ('generic', '不得输出 H3 字段/XML'),
])
def test_all_targets_share_semantic_equivalence_and_keep_their_own_format(profile, required):
    system = build_adaptation_system(profile, 7000)
    assert SEMANTIC_EQUIVALENCE_CONTRACT in system
    assert required in system
    for invariant in ('素材与身份', '首尾状态与空间', '动作与物理', '摄影与光影', '声音与文字', '叙事与约束'):
        assert invariant in system


@pytest.mark.parametrize('provider,model,prompt', [
    ('minimax-h3', 'MiniMax H3', H3),
    ('jimeng', 'video-3.0', '女子走向门口'),
])
def test_unchanged_requests_do_not_call_optimizer(service, provider, model, prompt):
    payload = main.CanvasVideoRequest(prompt=prompt, provider_id=provider, model=model)
    prepared, info = asyncio.run(main.prepare_video_generation_prompt(payload, {'protocol': provider}))
    assert prepared is payload
    assert info == {}
    service.assert_not_awaited()


@pytest.mark.parametrize('provider,model,profile', [
    ('kling-cli', 'kling-v3-omni', 'kling-omni'),
    ('jimeng', 'seedance2.0_vip', 'seedance'),
    ('gateway', 'veo3', 'generic'),
])
def test_sync_endpoint_sends_adapted_prompt_and_keeps_original(service, monkeypatch, provider, model, profile):
    upstream = AsyncMock(return_value={'videos': ['/output/test.mp4'], 'request': {'command': 'video'}})
    monkeypatch.setattr(main, 'generate_canvas_video', upstream)
    payload = main.CanvasVideoRequest(prompt=H3, provider_id=provider, model=model, duration=8)
    result = asyncio.run(main.canvas_video(payload))
    sent = upstream.await_args.args[0]
    assert sent.prompt == ADAPTED
    assert sent.duration == 8
    assert payload.prompt == H3
    assert result['request']['original_prompt'] == H3
    assert result['request']['prompt'] == ADAPTED
    assert result['request']['prompt_adaptation']['profile'] == profile
    assert result['request']['command'] == 'video'
    request = service.await_args.args[0]
    assert not request.web_search
    assert request.images == []
    assert json.loads(request.message)['generation_settings']['duration'] == 8
    assert json.loads(request.message)['generation_settings']['source_model'] == ''


def test_h3_longer_than_kling_limit_is_converted_before_limit_check(service):
    original = H3.replace('A woman', 'A detailed scene. ' * 210 + 'A woman')
    assert len(original) > main.video_prompt_limit('kling-cli', '')
    payload = main.CanvasVideoRequest(prompt=original, provider_id='kling-cli')
    prepared, info = asyncio.run(main.prepare_video_generation_prompt(payload, {'protocol': 'kling-cli'}))
    assert prepared.prompt == ADAPTED
    assert info['original_prompt'] == original


def test_invalid_result_is_repaired_once(service):
    service.side_effect = [{'text': H3}, {'text': ADAPTED}]
    prepared, info = asyncio.run(main.prepare_video_generation_prompt(
        main.CanvasVideoRequest(prompt=H3, provider_id='jimeng'), {'protocol': 'jimeng'}))
    assert prepared.prompt == ADAPTED
    assert info['prompt_adaptation']['attempts'] == 2
    assert '上次校验失败' in service.await_args.args[0].message


@pytest.mark.parametrize('bad', ['', H3, '女子走开。', ADAPTED * 1000, '女子说“再见”，无配乐。'],
                         ids=['empty', 'h3', 'missing-dialogue', 'too-long', 'changed-dialogue'])
def test_invalid_conversion_never_calls_video_upstream(service, monkeypatch, bad):
    service.return_value = {'text': bad}
    upstream = AsyncMock()
    monkeypatch.setattr(main, 'generate_canvas_video', upstream)
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.canvas_video(main.CanvasVideoRequest(prompt=H3, provider_id='kling-cli')))
    assert error.value.status_code == 422
    assert '尚未提交' in error.value.detail
    assert service.await_count == 2
    upstream.assert_not_awaited()


def test_service_failure_never_calls_video_upstream(service, monkeypatch):
    service.side_effect = TimeoutError()
    upstream = AsyncMock()
    monkeypatch.setattr(main, 'generate_canvas_video', upstream)
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.canvas_video(main.CanvasVideoRequest(prompt=H3, provider_id='jimeng')))
    assert error.value.status_code == 502
    upstream.assert_not_awaited()


def test_missing_optimizer_fails_before_video(monkeypatch, service):
    monkeypatch.setattr(main, 'configured_image_prompt_optimizer_route', lambda *args: None)
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.canvas_video(main.CanvasVideoRequest(prompt=H3, provider_id='jimeng')))
    assert 'AI 助手' in error.value.detail
    service.assert_not_awaited()


def test_missing_source_asset_fails_before_conversion(service):
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.canvas_video(main.CanvasVideoRequest(prompt=H3 + '\n<Picture 2>', provider_id='jimeng')))
    assert '未提交的图片2' in error.value.detail
    service.assert_not_awaited()


def test_reference_roles_and_subject_numbers_do_not_get_reindexed():
    message = json.loads(adaptation_message('<Subject 3> from <Picture 1>', 'seedance', [
        {'url': '/ref.png', 'role': 'first_frame', 'role_label': '演员'},
        {'url': '/end.png', 'role': 'last_frame'},
    ], ['video'], ['audio'], {'duration': 10}))
    assert message['reference_manifest'][0] == {
        'tag': '图片1', 'source': '<Picture 1>', 'source_aliases': ['图片1', '<<<image_1>>>', '[Image1]'], 'role': 'first_frame', 'label': '演员'}
    assert message['reference_manifest'][1]['role'] == 'last_frame'
    assert message['reference_manifest'][-1]['tag'] == '音频1'
    assert message['target_profile'] == 'seedance'
    assert '<Subject 3>' in message['original_prompt']
    assert SEMANTIC_EQUIVALENCE_CONTRACT in main.video_prompt_polish_system_prompt('gateway', 'seedance2.5')
    assert SEMANTIC_EQUIVALENCE_CONTRACT in main._video_auto_parse_system_prompt('gateway', 'seedance2.5', '')


def test_seedance_2_skill_contains_official_task_and_prompt_rules():
    skill, profile = main._video_prompt_skill('linkfox', 'seedance2.0')
    assert profile == 'seedance'
    assert len(skill) > 4000
    for required in ('全模态参考', '编辑视频', '延长或补全视频', '主体定义与素材绑定',
                     '分镜与时间层', '一个镜头尽量只指定一种主要运镜', '声音、台词和文字',
                     '不要强制写 `0–3秒`', 'LinkFox 当前图转视频接口只提交图片'):
        assert required in skill
    system = main.video_prompt_polish_system_prompt('linkfox', 'seedance2.0')
    assert skill in system
    assert '复杂内容使用镜头1、镜头2等相对时序' in system
    assert '整体保持简洁，通常 1-4 句即可' not in system
    reference_context, _, _ = main.video_prompt_reference_manifest('seedance', 2, 0)
    auto_parse = main._video_auto_parse_system_prompt('linkfox', 'seedance2.0', reference_context)
    assert '官方规范引用就是图片1、图片2、视频1、音频1' in auto_parse
    assert '禁止残留‘图1’‘图片2’‘视频1’' not in auto_parse


def test_seedance_25_skill_contains_official_task_and_prompt_rules():
    skill, profile = main._video_prompt_skill('gateway', 'doubao-seedance-2-5-pro-260901')
    assert profile == 'seedance-2.5'
    assert len(skill) > 5000
    for required in ('name: sd25-pe', '参数分离', '最多 50 份参考素材', '多素材生成',
                     '白模参考与渲染', '宫格分镜与故事板', '以@图片1至@图片N的顺序作为关键帧',
                     '长视频与时间段', '视频编辑', '声音编辑', '视频延长'):
        assert required in skill
    system = main.video_prompt_polish_system_prompt('gateway', 'seedance2.5')
    assert skill in system
    assert '仅有节点时长时使用无数字阶段组织' in system
    assert '复杂内容使用镜头1、镜头2等相对时序' not in system
    reference_context, _, _ = main.video_prompt_reference_manifest('seedance-2.5', 2, 1)
    assert '图片1' in reference_context and '视频1' in reference_context
    auto_parse = main._video_auto_parse_system_prompt('gateway', 'seedance2.5', reference_context)
    assert 'Seedance 2.5 的官方规范引用就是图片1、图片2、视频1、音频1' in auto_parse
    assert '禁止残留‘图1’‘图片2’‘视频1’' not in auto_parse


@pytest.mark.parametrize('text,profile,error', [
    ('<<<image_1>>> 中的女人说“你好”，无配乐', 'kling-omni', ''),
    ('图片1中的女人说“你好”，无配乐', 'seedance', ''),
    ('图片1中的女人说“你好”，无配乐', 'seedance-2.5', ''),
    ('图片10中的女人说“你好”，无配乐', 'seedance', '遗漏'),
    ('图片1和图片2中的女人说“你好”，无配乐', 'seedance', '不存在'),
    ('<<<image_1>>> <<<element_1>>> 说“你好”，无配乐', 'kling-omni', '不支持'),
    ('<<<image_1>>> 中的女人说“你好”', 'kling-omni', '无配乐'),
    ('图片1中的女人说“你好”，无配乐', 'generic', ''),
    ('[Image1]中的女人说“你好”，无配乐', 'generic', 'HappyHorse'),
])
def test_reference_and_audio_validation(text, profile, error):
    result = validate_adapted_prompt(text, H3, profile, {'image': 1, 'video': 0, 'audio': 0}, 2500)
    assert error in result if error else result == ''


def test_no_subtitle_intent_must_survive_cross_model_translation():
    original = '图片1中的女人说“你好”，无配乐，不要字幕。'
    counts = {'image': 1, 'video': 0, 'audio': 0}
    missing = '图片1中的女人说“你好”，无配乐。'
    assert '无字幕' in validate_adapted_prompt(missing, original, 'seedance-2.5', counts, 2000)
    kept = '图片1中的女人说“你好”，无配乐，不要字幕。'
    assert validate_adapted_prompt(kept, original, 'seedance-2.5', counts, 2000) == ''


@pytest.fixture
def task_store(monkeypatch):
    monkeypatch.setattr(main, 'CANVAS_VIDEO_TASKS', {})
    monkeypatch.setattr(main, 'ensure_canvas_video_tasks_loaded', lambda: None)
    monkeypatch.setattr(main, 'write_canvas_video_tasks_locked', lambda *args: None)
    monkeypatch.setattr(main, 'start_canvas_video_task_runner', lambda *args: None)
    monkeypatch.setattr(main, 'current_account_id', lambda: 'admin')


def test_persistent_endpoint_adapts_once_and_stores_request(service, task_store, monkeypatch):
    upstream = AsyncMock(return_value={'upstream_task_id': 'upstream-1'})
    monkeypatch.setattr(main, 'submit_canvas_video_upstream', upstream)
    payload = main.CanvasVideoTaskRequest(prompt=H3, provider_id='kling-cli', model='kling-v3-omni', task_id='canvas_video_adapt')
    first = asyncio.run(main.create_canvas_video_task(payload))
    second = asyncio.run(main.create_canvas_video_task(payload))
    assert first['request']['prompt'] == ADAPTED
    assert first['request']['original_prompt'] == H3
    assert first['status'] == second['status'] == 'running'
    service.assert_awaited_once()
    upstream.assert_awaited_once()
    assert upstream.await_args.args[0].prompt == ADAPTED


def test_cancel_during_adaptation_prevents_paid_submission(service, task_store, monkeypatch):
    task_id = 'canvas_video_cancel_adapt'
    async def convert(request):
        main.CANVAS_VIDEO_TASKS[task_id]['cancel_requested'] = True
        main.CANVAS_VIDEO_TASKS[task_id]['status'] = 'canceled'
        return {'text': ADAPTED}
    service.side_effect = convert
    upstream = AsyncMock()
    monkeypatch.setattr(main, 'submit_canvas_video_upstream', upstream)
    result = asyncio.run(main.create_canvas_video_task(main.CanvasVideoTaskRequest(
        prompt=H3, provider_id='kling-cli', task_id=task_id)))
    assert result['status'] == 'canceled'
    upstream.assert_not_awaited()


def test_duplicate_during_conversion_does_not_submit_twice(service, task_store, monkeypatch):
    upstream = AsyncMock(return_value={'upstream_task_id': 'upstream-1'})
    monkeypatch.setattr(main, 'submit_canvas_video_upstream', upstream)
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        async def convert(request):
            entered.set()
            await release.wait()
            return {'text': ADAPTED}
        service.side_effect = convert
        payload = main.CanvasVideoTaskRequest(prompt=H3, provider_id='kling-cli', task_id='canvas_video_duplicate')
        first = asyncio.create_task(main.create_canvas_video_task(payload))
        await entered.wait()
        second = await main.create_canvas_video_task(payload)
        assert second['status'] == 'submitting'
        release.set()
        await first
    asyncio.run(scenario())
    upstream.assert_awaited_once()
    service.assert_awaited_once()


@pytest.mark.parametrize('model,text', [
    ('kling-v3-omni', '<<<image_1>>> 中的主体1说“你好”，无配乐。'),
    ('kling-video-v3_0', '图片1中的主体1说“你好”，无配乐。'),
])
def test_kling_cli_preserves_validated_prompt_verbatim(service, monkeypatch, model, text):
    from types import SimpleNamespace
    captured = {}
    class FakeKling:
        def __init__(self, env):
            pass
        def capabilities(self):
            return {'image_to_video': [{'model': model, 'arguments': []}]}
        def submit(self, **kwargs):
            captured.update(kwargs)
            return {'generation_id': 'test'}
    service.return_value = {'text': text}
    monkeypatch.setattr(main, 'resolve_kling_cli', lambda: SimpleNamespace(is_ready=True))
    monkeypatch.setattr(main, 'KlingCliService', FakeKling)
    monkeypatch.setattr(main, 'kling_cli_reference_value', lambda *args: 'local-ref.png')
    payload = main.CanvasVideoRequest(prompt=H3, provider_id='kling-cli', model=model,
                                      images=[main.AIReference(url='/ref.png')])
    async def scenario():
        prepared, _ = await main.prepare_video_generation_prompt(payload, {'protocol': 'kling-cli'})
        await main.invoke_kling_cli_video(prepared, submit_only=True)
        assert '_prompt_adapted' not in prepared.model_dump()
    asyncio.run(scenario())
    assert captured['prompt'] == text
    assert '<<<element_1>>>' not in captured['prompt']


def test_persistent_adaptation_failure_is_visible_without_paid_submit(service, task_store, monkeypatch):
    service.return_value = {'text': ''}
    upstream = AsyncMock()
    monkeypatch.setattr(main, 'submit_canvas_video_upstream', upstream)
    with pytest.raises(HTTPException):
        asyncio.run(main.create_canvas_video_task(main.CanvasVideoTaskRequest(
            prompt=H3, provider_id='kling-cli', task_id='canvas_video_failed_adapt')))
    assert main.CANVAS_VIDEO_TASKS['canvas_video_failed_adapt']['status'] == 'failed'
    upstream.assert_not_awaited()


def test_frontend_shared_submission_contract_runs_in_node():
    import subprocess
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const context = {window:{}};
vm.runInNewContext(fs.readFileSync('static/js/canvas-film-nodes.js','utf8'),context);
const prepare = context.window.CanvasFilmNodes.videoPromptSubmission;
const node = {prompt:'A woman walks.',visionProvider:'assistant',visionModel:'model'};
prepare(node,{prompt:node.prompt,provider_id:'minimax-h3',model:'MiniMax H3'});
const result = prepare(node,{prompt:node.prompt,provider_id:'jimeng',model:'video-3.0'});
assert.equal(result.prompt_source_model,'MiniMax H3');
assert.equal(result.prompt_optimizer_provider,'assistant');
assert.equal(node.prompt,'A woman walks.');
assert.equal(prepare(node,{prompt:'new prompt',provider_id:'jimeng'}).prompt_source_model,'');
assert.equal(prepare(node,{prompt:node.prompt,provider_id:'kling-cli'}).prompt_source_model,'MiniMax H3');
prepare(node,{prompt:'资产映射：1号演员\n'+node.prompt,provider_id:'minimax-h3',model:'MiniMax H3'});
assert.equal(prepare(node,{prompt:'资产映射：图片1演员\n'+node.prompt,provider_id:'jimeng'}).prompt_source_model,'MiniMax H3');
'''
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
    classic = Path('static/js/canvas.js').read_text(encoding='utf-8')
    smart = Path('static/js/smart-canvas.js').read_text(encoding='utf-8')
    assert 'api.videoPromptSubmission(node,payload)' in classic  # 影视生成视频
    assert 'videoPromptSubmission(node,requestPayload)' in classic  # 视频生成/持久任务
    assert 'videoPromptSubmission(sourceNode,payload)' in smart
    assert 'runApiVideoGeneration(built.prompt,built.refs,videoSettings,node)' in smart
