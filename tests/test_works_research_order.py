from unittest.mock import patch

import main


def canvas(updated_at):
    return {"id": "ordering", "created_at": 1700000000000, "updated_at": updated_at,
            "nodes": [{"id": "lookbook-1", "type": "lookbook",
                       "lookbookResearchImages": [{"image_url": "https://example.test/research.jpg"}],
                       "generatedOutputs": [{"url": "https://example.test/result.jpg"}]}]}


def test_research_stays_in_canvas_assets_but_not_works():
    assets = main.extract_canvas_assets(canvas(1800000000000))
    assert len(assets) == 2
    with patch.object(main, 'canvas_assets_index', return_value={'items': assets}):
        works = main.canvas_generated_work_items({})
    assert [w['url'] for w in works] == ['https://example.test/result.jpg']


def test_canvas_save_does_not_make_old_remote_work_new():
    before = main.extract_canvas_assets(canvas(1800000000000))
    after = main.extract_canvas_assets(canvas(1900000000000))
    assert [x['created_at'] for x in before] == [x['created_at'] for x in after]
    with patch.object(main, 'canvas_assets_index', return_value={'items': after}):
        works = main.canvas_generated_work_items({})
    newer = {'id': 'new-work', 'created_at': 1750000000}
    assert sorted([*works, newer], key=lambda x: x['created_at'], reverse=True)[0] == newer


def test_explicit_node_creation_time_survives():
    value = canvas(1900000000000)
    value['nodes'][0]['created_at'] = 1720000000000
    assert all(x['created_at'] == 1720000000000 for x in main.extract_canvas_assets(value))


def test_adapter_never_uses_canvas_modification_as_creation_time():
    item = {'id': 'remote', 'url': 'https://example.test/result.jpg', 'kind': 'image',
            'canvas_created_at': 1700000000000, 'canvas_updated_at': 1900000000000}
    with patch.object(main, 'canvas_assets_index', return_value={'items': [item]}):
        assert main.canvas_generated_work_items({})[0]['created_at'] == 1700000000


def test_research_image_promoted_to_real_node_is_still_a_work():
    value = canvas(1800000000000)
    value['nodes'].append({'id': 'real-image', 'type': 'image', 'url': 'https://example.test/research.jpg'})
    for reverse in (False, True):
        if reverse:
            value['nodes'].reverse()
        assets = main.extract_canvas_assets(value)
        assert len(assets) == 2
        with patch.object(main, 'canvas_assets_index', return_value={'items': assets}):
            works = main.canvas_generated_work_items({})
        assert {w['url'] for w in works} == {'https://example.test/research.jpg', 'https://example.test/result.jpg'}
