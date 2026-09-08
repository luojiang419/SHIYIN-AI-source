import json

import pytest

from canvas_core.app_config import read_app_config, update_app_settings
from tests.test_adaptive_arrange_grid import (
    CANVAS_JS, SMART_JS, _extract_javascript_function, _run_javascript,
)


def test_spacing_settings_persist_independently_and_accept_zero(tmp_path):
    assert read_app_config(tmp_path)['canvas_arrange_spacing'] == 56
    assert read_app_config(tmp_path)['canvas_group_arrange_spacing'] == 28
    update_app_settings(tmp_path, close_behavior='exit', canvas_arrange_spacing=0)
    update_app_settings(tmp_path, canvas_group_arrange_spacing=240)
    config = read_app_config(tmp_path)
    assert config['canvas_arrange_spacing'] == 0
    assert config['canvas_group_arrange_spacing'] == 240
    assert config['close_behavior'] == 'exit'


@pytest.mark.parametrize('value', [-1, 241, 2.5, True, '56', float('nan'), float('inf')])
@pytest.mark.parametrize('key', ['canvas_arrange_spacing', 'canvas_group_arrange_spacing'])
def test_invalid_spacing_does_not_modify_saved_config(tmp_path, key, value):
    update_app_settings(tmp_path, canvas_arrange_spacing=64)
    path = tmp_path / 'config' / 'app.json'
    before = path.read_bytes()
    with pytest.raises(ValueError):
        update_app_settings(tmp_path, **{key: value})
    assert path.read_bytes() == before


def test_corrupt_spacing_falls_back_without_losing_other_settings(tmp_path):
    path = tmp_path / 'config' / 'app.json'
    path.parent.mkdir()
    path.write_text(json.dumps({'canvas_arrange_spacing': -1, 'canvas_group_arrange_spacing': None, 'close_behavior': 'exit'}))
    config = read_app_config(tmp_path)
    assert (config['canvas_arrange_spacing'], config['canvas_group_arrange_spacing']) == (56, 28)
    assert config['close_behavior'] == 'exit'


@pytest.mark.parametrize('gap', [0, 37, 240])
@pytest.mark.parametrize('prefix', ['Canvas', 'Smart'])
def test_selected_grid_and_single_column_use_equal_pixel_gaps(prefix, gap):
    source = CANVAS_JS if prefix == "Canvas" else SMART_JS
    shape = _extract_javascript_function(source, f'{prefix.lower()}ArrangeGridShape')
    layout = _extract_javascript_function(source, f'arrange{prefix}LayerItems')
    actual = _run_javascript(f'''
        globalThis.CanvasArrangeSpacing = {{gap:()=>{gap}}};
        const nodeRect = n => ({{x:n.x,y:n.y,w:320,h:180,width:320,height:180}});
        const move{prefix}NodeAtom = (n,x,y) => {{n.x=x;n.y=y;}};
        {shape}
        {layout}
        const run = count => {{
            const items = Array.from({{length:count}},(_,id)=>({{id,x:0,y:0}}));
            const rects = new Map(items.map(n=>[n.id,nodeRect(n)]));
            arrange{prefix}LayerItems(items,rects,10,20);
            return items;
        }};
        console.log(JSON.stringify([run(4),run(2)]));
    ''')
    grid, column = actual
    assert grid[1]['x'] - grid[0]['x'] - 320 == gap
    assert grid[2]['y'] - grid[0]['y'] - 180 == gap
    assert column[1]['y'] - column[0]['y'] - 180 == gap


@pytest.mark.parametrize('gap', [0, 37, 240])
def test_classic_group_uses_equal_gaps_and_expands_bounds(gap):
    layout = CANVAS_JS[CANVAS_JS.index('function arrangeCanvasGroupContents'):CANVAS_JS.index('function arrangeSelectedCanvasGroup')]
    result = _run_javascript(f'''
        globalThis.CanvasArrangeSpacing = {{groupGap:()=>{gap}}};
        const CANVAS_GROUP_ARRANGE_PADDING=24, CANVAS_GROUP_ARRANGE_HEADER=58, CANVAS_GROUP_ARRANGE_GAP=28;
        const group = {{id:'g',type:'group',x:0,y:0,items:['0','1','2','3']}};
        const nodes = [group,...group.items.map(id=>({{id,x:0,y:0,w:320,h:180}}))];
        const nodeRect = n => n;
        const moveCanvasNodeAtom = (n,x,y)=>{{n.x=x;n.y=y;}};
        const pushUndo = ()=>{{}};
        {layout}
        arrangeCanvasGroupContents('g');
        console.log(JSON.stringify(nodes));
    ''')
    group, first, second, third, fourth = result
    assert second['x'] - first['x'] - 320 == gap
    assert third['y'] - first['y'] - 180 == gap
    assert group['w'] == 640 + gap + 48
    assert group['h'] == 360 + gap + 82


@pytest.mark.parametrize('gap', [0, 37, 240])
def test_smart_group_members_and_thumbnail_layout_use_equal_gaps(gap):
    layout = SMART_JS[SMART_JS.index('function arrangeSmartGroupMembers'):SMART_JS.index('function mediaLayoutSize')]
    thumbs = _extract_javascript_function(SMART_JS, 'smartGroupThumbLayout')
    result = _run_javascript(f'''
        globalThis.CanvasArrangeSpacing = {{groupGap:()=>{gap}}};
        const SMART_GROUP_ARRANGE_PADDING=18, SMART_GROUP_ARRANGE_HEADER=44;
        const SMART_GROUP_MIN_WIDTH=100, SMART_GROUP_MIN_HEIGHT=100, SMART_GROUP_MAX_VISIBLE_ROWS=3;
        const MEDIA_GROUP_THUMB_BASE=96;
        const members=Array.from({{length:4}},(_,id)=>({{id,x:0,y:0}}));
        let refs=[];
        const smartGroupImageRefs=()=>refs;
        const smartGroupCompactMembers=()=>[];
        const mediaNodeDefaultScale=()=>1;
        const smartMediaGridColumns=()=>2;
        const isSmartGroupNode=()=>true, isSmartImageNode=()=>false;
        const smartGroupMembers=()=>members;
        const nodeRect=n=>({{x:n.x,y:n.y,width:320,height:180}});
        const pushUndo=()=>{{}};
        {thumbs}
        {layout}
        const group={{x:0,y:0}};
        arrangeSmartGroupMembers(group);
        refs=Array.from({{length:4}},()=>({{item:{{url:'fixture.png'}}}}));
        arrangeSmartGroupMembers(group);
        console.log(JSON.stringify({{members,group}}));
    ''')
    first, second, third, fourth = result['members']
    assert second['x'] - first['x'] - 320 == gap
    assert third['y'] - first['y'] - 180 == gap
    assert result['group']['arrangeGap'] == gap
    assert result['group']['w'] == 192 + gap + 32
    assert result['group']['h'] == 192 + gap + 60
