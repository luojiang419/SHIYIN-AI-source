import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from canvas_core import linkfox_video


@pytest.mark.parametrize('encoding', ['utf-8', 'gbk'])
@pytest.mark.parametrize('frozen', [False, True])
def test_upstream_error_from_windows_path_preserves_reason_and_task_id(tmp_path, monkeypatch, encoding, frozen):
    result_path = tmp_path / 'Program Files' / 'SHIYIN AI' / '生成结果.json'
    result_path.parent.mkdir(parents=True)
    body = {'errcode': 200, 'errmsg': 'ok', 'status': 'FAILED',
            'errorMsg': '图片审核不通过', 'taskId': '2096848468580376576'}
    result_path.write_text(json.dumps(body, ensure_ascii=False), encoding=encoding)
    stdout = f'Saved full response: {result_path} (156 bytes)\nTop-level keys: []\n'

    def run(command, **options):
        if frozen:
            Path(options['env']['LINKFOX_SKILL_RESULT_FILE']).write_text(
                json.dumps({'stdout': stdout, 'stderr': 'Polling...'}), encoding='utf-8')
        return SimpleNamespace(returncode=0, stdout='' if frozen else stdout, stderr='Polling...')

    monkeypatch.setattr(linkfox_video.sys, 'frozen', frozen, raising=False)
    monkeypatch.setattr(linkfox_video.subprocess, 'run', run)
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(linkfox_video.LinkFoxVideoError) as caught:
        linkfox_video.run_skill({'entry': 'img2video', 'mode': 'reference',
            'videoType': 'seedance2.0', 'videoTime': 5, 'imageList': ['https://example.com/test.png']},
            project_root=root, output_dir=tmp_path, api_key='fixture-key')
    assert str(caught.value) == '图片审核不通过（LinkFox taskId: 2096848468580376576）'


@pytest.mark.parametrize('kind', ['single', 'multi'])
def test_skill_persists_task_response_as_utf8(tmp_path, monkeypatch, kind):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('linkfox_test_' + kind, linkfox_video._skill_path(root, kind))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    destination = tmp_path / 'task.json'
    monkeypatch.setattr(module, '_resolve_output_path', lambda ts: str(destination))
    body = {'taskId': 'task-1', 'errorMsg': '图片审核不通过'}
    assert module.save_response(body) == str(destination)
    assert json.loads(destination.read_text(encoding='utf-8')) == body
    def disk_failure(ts):
        raise OSError('disk full')
    monkeypatch.setattr(module, '_resolve_output_path', disk_failure)
    assert module.save_response(body) == ''
