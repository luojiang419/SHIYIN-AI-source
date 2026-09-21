"""优云多模态参考的实际请求结构和边界验证，不提交付费任务。"""
import asyncio
import base64
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import main


def payload(**kwargs):
    return main.CanvasVideoRequest(provider_id='youyun-h3', model='MiniMax-H3', **kwargs)


def request(**kwargs):
    return asyncio.run(main.youyun_h3_video_request(object(), payload(**kwargs)))


def test_image_video_audio_are_all_in_the_outgoing_http_request():
    captured=[]
    async def run():
        async def handle(req):
            captured.append(req)
            return httpx.Response(200,json={'task_id':'mock-job'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with patch.object(main,'provider_env_key_value',return_value='test-only'):
                return await main.submit_youyun_h3_video(client,payload(
                    prompt='图1的人物，参考视频1的运镜和音频1的节奏',
                    images=[{'url':'https://assets.example/person.png'}],
                    videos=['https://assets.example/motion.mp4'],
                    audios=['https://assets.example/music.wav'],
                    multimodal=True,
                ),{'id':'youyun-h3','base_url':'https://cp.compshare.cn'})
    result=asyncio.run(run())
    assert result['upstream_task_id']=='mock-job'
    assert captured[0].url.path=='/minimax/v2/video_generation'
    body=json.loads(captured[0].content)
    assert [item['type'] for item in body['content']]==['text','image_url','video_url','audio_url']
    assert [item['role'] for item in body['content'][1:]]==['reference_image','reference_video','reference_audio']
    assert body['content'][0]['text']=='<Picture 1>的人物，<Video 1>的运镜和<Audio 1>的节奏'
    assert body['content'][-1]['audio_url']['url']=='https://assets.example/music.wav'
    assert 'steps' not in body


def test_video_and_audio_without_image_is_supported():
    body=request(videos=['https://assets.example/a.mp4'],audios=['https://assets.example/a.mp3'])
    assert [item['role'] for item in body['content']]==['reference_video','reference_audio']


@pytest.mark.parametrize('counts',[(9,0,3),(6,3,3),(9,3,0)])
def test_all_twelve_allowed_references_are_preserved(counts):
    i,v,a=counts
    body=request(images=[{'url':f'https://assets.example/{n}.png'} for n in range(i)],videos=[f'https://assets.example/{n}.mp4' for n in range(v)],audios=[f'https://assets.example/{n}.mp3' for n in range(a)],multimodal=True)
    assert len(body['content'])==12
    assert sum(item['type']=='audio_url' for item in body['content'])==a


@pytest.mark.parametrize('counts',[(10,0,0),(1,4,0),(1,0,4),(9,3,1),(7,3,3)])
def test_over_limit_is_rejected_before_reading_media(counts):
    i,v,a=counts
    with patch.object(main,'youyun_h3_reference_value',new=AsyncMock()) as read:
        with pytest.raises(main.HTTPException) as exc:
            request(images=[{'url':f'https://a.test/{n}.png'} for n in range(i)],videos=['https://a.test/v.mp4']*v,audios=['https://a.test/a.mp3']*a,multimodal=True)
        assert '合计最多 12' in exc.value.detail
        read.assert_not_awaited()


def test_audio_alone_is_rejected_before_reading_media():
    with patch.object(main,'youyun_h3_reference_value',new=AsyncMock()) as read:
        with pytest.raises(main.HTTPException) as exc:
            request(prompt='listen',audios=['https://a.test/a.mp3'])
        assert '同时提供' in exc.value.detail
        read.assert_not_awaited()


@pytest.mark.parametrize('refs',[{'videos':['https://a.test/v.mp4']},{'audios':['https://a.test/a.mp3']}])
def test_explicit_frames_cannot_silently_become_reference_mode(refs):
    with pytest.raises(main.HTTPException) as exc:
        request(images=[{'url':'https://a.test/i.png','role':'first_frame'}],**refs)
    assert '首尾帧模式不能混用' in exc.value.detail


def test_last_frame_is_not_duplicated_as_first_frame():
    body=request(images=[{'url':'https://a.test/i.png','role':'last_frame'}])
    assert [item['role'] for item in body['content']]==['last_frame']


@pytest.mark.parametrize('kind,ext,mime',[('image','png','image/png'),('video','mp4','video/mp4'),('audio','mp3','audio/mpeg')])
def test_local_material_is_encoded_with_the_right_type(tmp_path,kind,ext,mime):
    file=tmp_path/f'asset.{ext}'
    file.write_bytes(b'reference-test-bytes')
    with patch.object(main,'output_file_from_url',return_value=str(file)):
        value=asyncio.run(main.youyun_h3_reference_value(object(),f'/assets/input/asset.{ext}',kind))
    assert value==f'data:{mime};base64,'+base64.b64encode(file.read_bytes()).decode()


def test_invalid_data_url_mime_and_oversized_audio_are_rejected():
    for value in ['data:video/mp4;base64,AA==','data:audio/mpeg;base64,%%%']:
        with pytest.raises(main.HTTPException):
            asyncio.run(main.youyun_h3_reference_value(object(),value,'audio'))
    value='data:audio/mpeg;base64,'+base64.b64encode(b'x'*(15*1024*1024+1)).decode()
    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.youyun_h3_reference_value(object(),value,'audio'))
    assert '15 MiB' in exc.value.detail


def test_aggregate_request_size_is_checked():
    assert main.YOUYUN_H3_MAX_REQUEST_BYTES == 72*1024*1024
    with patch.object(main,'YOUYUN_H3_MAX_REQUEST_BYTES',100):
        with pytest.raises(main.HTTPException) as exc:
            request(prompt='A scene',videos=['https://assets.example/video.mp4'])
    assert '72 MiB' in exc.value.detail


def test_current_api_does_not_accept_4k():
    with pytest.raises(main.HTTPException) as exc:
        request(prompt='A scene',resolution='4K')
    assert '768P、1080P、2K' in exc.value.detail

@pytest.fixture(scope='module')
def frontend_payloads():
    import subprocess
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(['node','tests/support/youyun_reference_submission_runtime.cjs'],cwd=root,capture_output=True,check=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize('surface',['classic','film','smart','smartFilm'])
def test_canvas_payload_reaches_upstream_with_all_reference_types(frontend_payloads,surface):
    captured=[]
    async def encode(client,url,kind):
        mime={'image':'image/png','video':'video/mp4','audio':'audio/mpeg'}[kind]
        return f'data:{mime};base64,'+base64.b64encode(url.encode()).decode()
    async def run():
        async def handle(req):
            captured.append(json.loads(req.content))
            return httpx.Response(200,json={'task_id':'mock-'+surface})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with patch.object(main,'youyun_h3_reference_value',side_effect=encode),patch.object(main,'provider_env_key_value',return_value='test-only'):
                await main.submit_youyun_h3_video(client,main.CanvasVideoRequest(**frontend_payloads[surface]),{'id':'youyun-h3','base_url':'https://cp.compshare.cn'})
    asyncio.run(run())
    media=[item for item in captured[0]['content'] if item['type']!='text']
    assert len(media)==12
    assert [item['role'] for item in media]==['reference_image']*6+['reference_video']*3+['reference_audio']*3
    assert all(item['audio_url']['url'].startswith('data:audio/mpeg;base64,') for item in media[-3:])
