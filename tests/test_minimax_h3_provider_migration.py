"""本地 H3 与优云智算H3 配置、密钥和路由隔离回归。"""
import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import main


def by_id(items, provider_id):
    return next(item for item in items if item['id'] == provider_id)


def test_saved_local_provider_keeps_address_name_and_parameters():
    saved = {'id': 'minimax-h3', 'name': 'MiniMax H3', 'base_url': 'http://115.231.35.105:7866',
             'protocol': 'minimax-h3', 'enabled': False, 'video_models': ['MiniMax H3']}
    with patch.object(main.ADMIN_DATABASE, 'load_providers', return_value=[saved]):
        loaded = main.load_api_providers()
    local = by_id(loaded, 'minimax-h3')
    for field, value in saved.items():
        assert local[field] == value
    cloud = by_id(loaded, 'youyun-h3')
    assert cloud['name'] == '优云智算H3'
    assert cloud['protocol'] == 'youyun-h3'
    assert cloud['base_url'] == 'https://cp.compshare.cn'
    assert cloud['video_models'] == ['MiniMax-H3']
    assert main.merge_default_api_providers(loaded) == loaded


def test_misconfigured_cloud_record_is_split_without_mutating_input():
    wrong = {'id': 'minimax-h3', 'name': '优云智算 MiniMax H3', 'base_url': 'https://cp.compshare.cn',
             'enabled': False, 'video_models': ['MiniMax-H3']}
    loaded = main.merge_default_api_providers([wrong])
    assert by_id(loaded, 'minimax-h3')['base_url'] == main.MINIMAX_H3_DEFAULT_BASE_URL
    assert by_id(loaded, 'minimax-h3')['name'] == 'MiniMax H3'
    assert by_id(loaded, 'minimax-h3')['video_models'] == ['MiniMax H3']
    assert by_id(loaded, 'youyun-h3')['enabled'] is False
    assert wrong['base_url'] == 'https://cp.compshare.cn'
    assert main.merge_default_api_providers(loaded) == loaded


def test_existing_independent_cloud_config_wins_during_recovery():
    loaded = main.merge_default_api_providers([
        {'id':'minimax-h3','base_url':'https://cp.compshare.cn'},
        {'id':'youyun-h3','base_url':'https://gateway.example','enabled':False},
    ])
    assert by_id(loaded,'youyun-h3')['base_url'] == 'https://gateway.example'
    assert by_id(loaded,'youyun-h3')['enabled'] is False
    assert len([p for p in loaded if p['id']=='youyun-h3']) == 1


@pytest.mark.parametrize('provider_id', ['minimax-h3','youyun-h3'])
def test_fixed_protocol_cannot_be_overridden_by_saved_cloud_or_local_protocol(provider_id):
    item = main.normalize_provider({'id':provider_id, 'protocol':'openai'})
    assert item['protocol'] == provider_id
    assert main.is_youyun_h3_provider(item) == (provider_id == 'youyun-h3')
    assert main.is_minimax_h3_provider(item) == (provider_id == 'minimax-h3')


def test_cloud_key_uses_independent_slot_and_only_recovers_known_bad_record():
    local_key = main.provider_key_env('minimax-h3')
    with patch.dict(main.os.environ, {}, clear=True), patch.object(main, 'read_api_env_value', side_effect=lambda key: 'old-cloud-test-key' if key == local_key else ''), patch.object(main.ADMIN_DATABASE, 'load_providers', return_value=[{'id':'minimax-h3','base_url':'http://h3.local'}]):
        assert main.provider_env_key_value('youyun-h3') == ''
        with patch.object(main.ADMIN_DATABASE, 'load_providers', return_value=[{'id':'minimax-h3','base_url':'https://cp.compshare.cn'}]):
            assert main.provider_env_key_value('youyun-h3') == 'old-cloud-test-key'
        with patch.dict(main.os.environ, {main.provider_key_env('youyun-h3'):'independent-test-key'}):
            assert main.provider_env_key_value('youyun-h3') == 'independent-test-key'


def test_save_copies_recovered_key_before_replacing_legacy_metadata():
    calls=[]
    with patch.dict(main.os.environ, {}, clear=True), patch.object(main, 'read_api_env_value', return_value=''), patch.object(main, 'provider_env_key_value', return_value='test-key'), patch.object(main, 'update_env_values', side_effect=lambda values:calls.append(('key',values))), patch.object(main.ADMIN_DATABASE, 'save_providers', side_effect=lambda values:calls.append(('providers',values))), patch.object(main, 'publish_entity_changed'):
        main.save_api_providers([{'id':'youyun-h3'}])
    assert [item[0] for item in calls] == ['key','providers']
    assert calls[0][1] == {main.provider_key_env('youyun-h3'):'test-key'}


@pytest.mark.parametrize('provider_id,endpoint', [('minimax-h3','/api/generate'),('youyun-h3','/minimax/v2/video_generation')])
def test_async_submission_routes_to_matching_protocol(provider_id, endpoint):
    requests=[]
    async def run():
        async def handle(request):
            requests.append(request)
            return httpx.Response(200,json={'id':'local-job','task_id':'cloud-job'})
        real_client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch.object(main.httpx,'AsyncClient', return_value=real_client), patch.object(main,'provider_env_key_value', return_value='cloud-test-key'):
            return await main.submit_canvas_video_upstream(main.CanvasVideoRequest(provider_id=provider_id,prompt='test',duration=8,steps=2), {'id':provider_id,'protocol':provider_id,'base_url':'https://example.test'})
    result=asyncio.run(run())
    assert requests[0].url.path == endpoint
    assert ('authorization' in requests[0].headers) == (provider_id=='youyun-h3')
    body=result['request']
    assert ('steps' in body) == (provider_id=='minimax-h3')
    assert ('content' in body) == (provider_id=='youyun-h3')


@pytest.mark.parametrize('provider_id,base,endpoint', [
    ('minimax-h3','http://h3.local','/api/jobs/job-1'),
    ('youyun-h3','https://cp.compshare.cn','/minimax/v2/query/video_generation/job-1'),
    ('minimax-h3','https://cp.compshare.cn','/minimax/v2/query/video_generation/job-1'),
])
def test_persisted_query_routes_local_cloud_and_legacy_cloud_tasks(provider_id,base,endpoint):
    requests=[]
    async def run():
        async def handle(request):
            requests.append(request)
            return httpx.Response(200,json={'status':'done','output':'/out.mp4','task':{'status':'succeeded','content':{'url':'https://cdn.test/out.mp4'}}})
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch.object(main.httpx,'AsyncClient',return_value=client),patch.object(main,'get_api_provider',return_value={'id':provider_id,'protocol':provider_id}),patch.object(main,'provider_env_key_value',return_value='test-key'):
            return await main.query_canvas_video_upstream({'provider_id':provider_id,'upstream_base_url':base,'upstream_task_id':'job-1'})
    result=asyncio.run(run())
    assert requests[0].url.path == endpoint
    assert result['status'] == 'succeeded'


@pytest.mark.parametrize('provider_id,endpoint', [('minimax-h3','/api/config'),('youyun-h3','/minimax/v2/query/point_usage_summary')])
def test_status_queries_are_separate(provider_id,endpoint):
    requests=[]
    async def run():
        async def handle(request):
            requests.append(request)
            return httpx.Response(200,json={'resolutions':['local-preset'],'defaults':{'steps':2},'available_points':10})
        client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch.object(main.httpx,'AsyncClient',return_value=client),patch.object(main,'get_api_provider',return_value={'id':provider_id,'base_url':'https://example.test'}),patch.object(main,'provider_env_key_value',return_value='test-key'):
            return await (main.youyun_h3_status if provider_id=='youyun-h3' else main.minimax_h3_status)()
    result=asyncio.run(run())
    assert requests[0].url.path == endpoint
    assert result['generation_enabled'] is True
    assert result['resolutions'] == (['768P','1080P','2K','4K'] if provider_id=='youyun-h3' else ['local-preset'])
