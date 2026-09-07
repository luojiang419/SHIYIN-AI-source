import asyncio
import base64
import io
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from PIL import Image

import main
from canvas_core.linkfox_video import MODEL_SPECS, LinkFoxVideoError, unified_request
from canvas_core.video_prompt_registry import PROFILES
from canvas_core.video_prompt_adapter import validate_adapted_prompt

ROOT = Path(__file__).resolve().parents[1]
TEXT = '图片1中的女子向左走，镜头跟随，保持衣服与光线一致，无配乐。'


@pytest.fixture
def services(monkeypatch):
    llm = AsyncMock(return_value={'text': TEXT})
    video = AsyncMock(return_value={'videos': ['/output/result.mp4']})
    monkeypatch.setattr(main, 'canvas_llm', llm)
    monkeypatch.setattr(main, 'linkfox_video', video)
    monkeypatch.setattr(main, 'linkfox_configured_key', lambda: 'fixture-only')
    monkeypatch.setattr(main, 'VIDEO_PROMPT_ADAPT_CACHE', {})
    monkeypatch.setattr(main, 'get_api_provider', lambda value: {'id': value, 'protocol': value})
    monkeypatch.setattr(main, 'configured_image_prompt_optimizer_route', lambda *args: {'provider_id': 'assistant', 'model': 'vision'})
    return llm, video


def request(model='seedance2.0', **extra):
    spec = MODEL_SPECS[model]
    return main.CanvasVideoRequest(**{
        'provider_id': 'linkfox', 'model': model, 'prompt': '女子向左走，无配乐。', 'auto_adapt_prompt': True,
        'duration': spec['durations'][0], 'resolution': spec['resolutions'][0] if spec['resolutions'] else '',
        'aspect_ratio': spec['ratios'][0] if spec['ratios'] else '',
        'linkfox_mode': 'first_last_frame' if model == '可灵2.6' else 'reference',
        'images': [main.AIReference(url='/assets/ref.png')], **extra,
    })


def test_provider_is_in_default_and_saved_provider_lists():
    for providers in (main.default_api_providers(), main.merge_default_api_providers([])):
        provider = next(item for item in providers if item['id'] == 'linkfox')
        assert set(provider['video_models']) == set(MODEL_SPECS)
        assert provider['image_models'] == provider['chat_models'] == []


def test_missing_linkfox_key_is_detected_before_text_conversion(services, monkeypatch):
    monkeypatch.setattr(main, 'linkfox_configured_key', lambda: '')
    with pytest.raises(HTTPException):
        asyncio.run(main.canvas_video(request()))
    services[0].assert_not_awaited()
    services[1].assert_not_awaited()


def test_same_model_uses_last_successful_prompt_without_text_or_visual_calls(services):
    asyncio.run(main.canvas_video(request(prompt=TEXT, auto_adapt_prompt=False, prompt_origin_key='fixture',
        prompt_source_provider='linkfox', prompt_source_model='seedance2.0')))
    services[0].assert_not_awaited()
    assert services[1].await_args.args[0].prompt == TEXT


@pytest.mark.parametrize('model', MODEL_SPECS)
def test_every_linkfox_model_uses_unified_video_endpoint_and_its_own_rules(services, model):
    llm, video = services
    payload = request(model)
    expected = TEXT.replace('图片1', '[Image1]') if model == 'HappyHorse' else TEXT
    llm.return_value = {'text': expected}
    result = asyncio.run(main.canvas_video(payload))
    sent = video.await_args.args[0]
    assert sent.videoType == model
    assert sent.prompt == expected
    assert sent.imageList == ['/assets/ref.png']
    assert not sent.promptOptimizer  # 已适配文本不交给网关二次随机优化
    assert result['request']['original_prompt'] == payload.prompt
    assert result['request']['prompt'] == expected
    assert result['request']['prompt_adaptation']['version'] == 2
    skill, profile = main._video_prompt_skill('linkfox', model)
    assert profile in PROFILES
    assert skill in llm.await_args.args[0].system_prompt
    assert main.video_prompt_limit('linkfox', model) <= 2000


def test_long_local_prompt_is_adapted_before_linkfox_length_validation(services):
    payload = request(prompt='local model scene: ' + 'woman walks left. ' * 210)
    assert len(payload.prompt) > 2000
    result = asyncio.run(main.canvas_video(payload))
    assert result['request']['prompt'] == TEXT


@pytest.mark.parametrize('model', ['海螺2.3', 'wan2.6'])
def test_single_image_model_does_not_silently_discard_extra_references(services, model):
    llm, video = services
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.canvas_video(request(model, images=[main.AIReference(url='/a.png'), main.AIReference(url='/b.png')])) )
    assert '1 张' in error.value.detail
    llm.assert_not_awaited()
    video.assert_not_awaited()


def test_incompatible_first_last_frame_parameters_fail_before_any_model_call(services):
    llm, video = services
    with pytest.raises(HTTPException):
        asyncio.run(main.canvas_video(request('可灵2.6', resolution='720p', images=[
            main.AIReference(url='/first.png', role='first_frame'), main.AIReference(url='/last.png', role='last_frame')])) )
    llm.assert_not_awaited()
    video.assert_not_awaited()


def test_first_last_frame_order_is_explicit_and_preserved():
    raw = request('seedance2.0', images=[main.AIReference(url='/end.png', role='last_frame'),
                                      main.AIReference(url='/start.png', role='first_frame')]).model_dump()
    mapped = unified_request(raw)
    assert mapped['imageUrl'] == '/start.png'
    assert mapped['lastFrameImageUrl'] == '/end.png'


def test_unchanged_prompt_uses_verified_cache_but_model_or_references_invalidate_it(services):
    llm, _ = services
    first = asyncio.run(main.canvas_video(request()))
    again = asyncio.run(main.canvas_video(request(prompt_source_model='seedance2.0', prompt_source_provider='linkfox')))
    assert llm.await_count == 1
    assert first['request']['prompt'] == again['request']['prompt']
    assert again['request']['prompt_adaptation']['cache_hit']
    asyncio.run(main.canvas_video(request('seedance2.0fast')))
    asyncio.run(main.canvas_video(request(images=[main.AIReference(url='/different.png')])) )
    assert llm.await_count == 3


def test_cache_is_account_scoped(services, monkeypatch):
    monkeypatch.setattr(main, 'current_account_id', lambda: 'a')
    asyncio.run(main.canvas_video(request()))
    monkeypatch.setattr(main, 'current_account_id', lambda: 'b')
    asyncio.run(main.canvas_video(request()))
    assert services[0].await_count == 2


def test_any_source_model_and_unknown_local_prompts_can_convert_back_to_h3(services):
    h3 = 'integrated_multimodal_description:\n<Picture 1> shows a woman walking left.\n\noverall_soundscape:\nFootsteps.\n\nnon_diegetic_music:\nN/A'
    services[0].return_value = {'text': h3}
    payload = main.CanvasVideoRequest(provider_id='minimax-h3', model='MiniMax H3', auto_adapt_prompt=True,
        prompt_source_provider='linkfox', prompt_source_model='wan2.6', prompt=TEXT,
        images=[main.AIReference(url='/ref.png')])
    prepared, _ = asyncio.run(main.prepare_video_generation_prompt(payload, {'protocol': 'minimax-h3'}))
    assert prepared.prompt == h3
    assert payload.prompt == TEXT
    assert '官方字段' in services[0].await_args.args[0].system_prompt


def test_source_video_is_analyzed_and_start_frame_is_used_when_target_is_image_only(services, monkeypatch):
    frame = 'data:image/png;base64,cGljdHVyZQ=='
    extract = AsyncMock(return_value=[frame])
    monkeypatch.setattr(main, 'video_reference_to_frame_data_urls', extract)
    result = asyncio.run(main.canvas_video(request(images=[], videos=['/output/any-model.mp4'], prompt='')))
    llm, video = services
    assert llm.await_args.args[0].videos == ['/output/any-model.mp4']
    assert llm.await_args.args[0].images == [frame]
    assert video.await_args.args[0].imageList == [frame]
    assert result['request']['video_count'] == 0
    assert result['request']['prompt_adaptation']['video_transfer'] == 'analysis-and-image'
    extract.assert_awaited_once()


def test_source_video_does_not_replace_user_supplied_identity_image(services, monkeypatch):
    extract = AsyncMock()
    monkeypatch.setattr(main, 'video_reference_to_frame_data_urls', extract)
    asyncio.run(main.canvas_video(request(videos=['/clip.mp4'])))
    extract.assert_not_awaited()
    assert services[1].await_args.args[0].imageList == ['/assets/ref.png']
    assert services[0].await_args.args[0].images == []
    assert services[0].await_args.args[0].videos == []


def test_switching_with_previous_parsed_prompt_only_calls_text_model(services):
    payload = request(prompt='图片1中的女子向左走，镜头跟随，保持衣服与光线一致，无配乐。',
                      prompt_source_provider='local', prompt_source_model='local-video-v1')
    result = asyncio.run(main.canvas_video(payload))
    sent = services[0].await_args.args[0]
    assert sent.images == sent.videos == []
    assert json.loads(sent.message)['original_prompt'] == payload.prompt
    assert result['request']['prompt_adaptation']['source_model'] == 'local-video-v1'
    assert not result['request']['prompt_adaptation']['visual_analysis']
    services[0].assert_awaited_once()


def test_video_auto_parse_endpoint_never_generates_a_paid_video(services, monkeypatch):
    monkeypatch.setattr(main, 'video_reference_to_frame_data_urls', AsyncMock(return_value=['data:image/png;base64,eA==']))
    result = asyncio.run(main.canvas_video_auto_parse(main.CanvasVideoAutoParseRequest(
        video_provider='linkfox', video_model='seedance2.0', videos=['/clip.mp4'], duration=5)))
    assert result['text'] == TEXT
    services[1].assert_not_awaited()


def test_empty_prompt_analyzes_images_instead_of_submitting_empty_text(services):
    result = asyncio.run(main.canvas_video(request(prompt='')))
    assert services[0].await_args.args[0].images == ['/assets/ref.png']
    assert result['request']['original_prompt'] == ''


def test_source_video_missing_frames_stops_before_generation(services, monkeypatch):
    monkeypatch.setattr(main, 'video_reference_to_frame_data_urls', AsyncMock(return_value=[]))
    with pytest.raises(HTTPException):
        asyncio.run(main.canvas_video(request(images=[], videos=['/bad.mp4'])))
    services[0].assert_not_awaited()
    services[1].assert_not_awaited()


def test_registered_skills_have_traceable_sources_and_share_parse_polish_rules():
    for profile, item in PROFILES.items():
        folder = ROOT / 'skills/video-prompt-polish' / profile
        assert item['source'] in (folder / 'SOURCE.md').read_text(encoding='utf-8')
    for model in MODEL_SPECS:
        skill, _ = main._video_prompt_skill('linkfox', model)
        assert skill in main.video_prompt_polish_system_prompt('linkfox', model)
        assert skill in main._video_auto_parse_system_prompt('linkfox', model, '')


def test_hailuo_camera_syntax_must_be_translated_when_switching_model():
    text = '图片1中的女子向左走，无配乐。[Tracking shot]'
    counts = {'image': 1, 'video': 0, 'audio': 0}
    assert not validate_adapted_prompt(text, text, 'hailuo', counts, 2000)
    assert '海螺方括号运镜' in validate_adapted_prompt(text, text, 'seedance', counts, 2000)


def test_shared_frontend_renders_all_models_and_keeps_media_sources():
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const c={window:{}};
for(const file of ['canvas-linkfox-video.js','canvas-film-nodes.js']) vm.runInNewContext(fs.readFileSync('static/js/'+file,'utf8'),c);
const api=c.window.CanvasLinkfoxVideo,film=c.window.CanvasFilmNodes;
const node={type:'film-video',apiProvider:'linkfox',model:'海螺2.3',duration:10,resolution:'1080p',aspectRatio:'16:9'};
const html=api.unifiedSettingsHtml(node);
assert.equal(node.duration,6);assert.equal(node.generateAudio,false);assert(html.includes('1 张参考图'));
node.model='可灵2.6';api.normalizeUnified(node);assert.equal(node.linkfoxMode,'first_last_frame');
node.model='wan2.6';api.normalizeUnified(node);assert.equal(node.aspectRatio,'');assert.equal(node.linkfoxMode,'reference');
const built=film.buildPrompt(node,[{role:'storyboard',ref:{url:'/clip.mp4',kind:'video'}}]);
assert.equal(built.refs[0].kind,'video');assert(!built.prompt.includes('图片1'));
const payload=film.videoPromptSubmission(node,{prompt:'资产映射：图片1是演员。',provider_id:'linkfox',model:'wan2.6'});
assert.equal(payload.auto_parse_media,true);assert.equal(payload.auto_adapt_prompt,true);
const draft={type:'film-video'},base={prompt:'',images:[{url:'/ref.png'}],provider_id:'linkfox',model:'seedance2.0',duration:5};
const first=film.videoPromptSubmission(draft,base);
film.rememberVideoPromptResult(draft,{...first,prompt:'上一模型实际使用的解析词'});
const next=film.videoPromptSubmission(draft,{...base,model:'wan2.6'});
assert.equal(next.prompt,'上一模型实际使用的解析词');
assert.equal(next.prompt_source_model,'seedance2.0');
assert.equal(next.auto_parse_media,false);
assert.equal(next.auto_adapt_prompt,true);
const same=film.videoPromptSubmission(draft,base);
assert.equal(same.auto_adapt_prompt,false);
assert.equal(same.auto_parse_media,false);
film.rememberVideoPromptResult(draft,{...next,prompt:'Wan实际生成词'});
const third=film.videoPromptSubmission(draft,{...base,model:'海螺2.3'});
assert.equal(third.prompt,'Wan实际生成词');
assert.equal(third.prompt_source_model,'wan2.6');
assert.equal(third.auto_parse_media,false);
'''
    subprocess.run(['node', '-e', script], cwd=ROOT, check=True, capture_output=True, text=True)


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg unavailable')
def test_video_analysis_samples_beginning_and_ending_not_only_initial_seconds(tmp_path, monkeypatch):
    video = tmp_path / 'colors.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=64x64:r=10:d=3',
        '-f', 'lavfi', '-i', 'color=blue:s=64x64:r=10:d=3', '-filter_complex', '[0:v][1:v]concat=n=2:v=1:a=0',
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video)], check=True, capture_output=True)
    monkeypatch.setattr(main, 'output_file_from_url', lambda value: str(video))
    frames = asyncio.run(main.video_reference_to_frame_data_urls('/clip.mp4', max_frames=3, max_size=64))
    colors = [Image.open(io.BytesIO(base64.b64decode(frame.split(',')[1]))).getpixel((32,32)) for frame in frames]
    assert len(colors) == 3
    assert colors[0][0] > 200 and colors[0][2] < 50
    assert colors[-1][2] > 200 and colors[-1][0] < 50
