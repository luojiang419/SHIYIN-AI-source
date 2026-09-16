import io
import json
import os
import subprocess
import threading
from pathlib import Path

import pytest

from canvas_core.account_storage import account_scope, current_account_id
from canvas_core.video_depth import VideoDepthTaskService, decode_worker_output, output_url_mapper


def completed(root, task_id='a' * 32):
    directory = root / f'depth_video_{task_id}'
    directory.mkdir(parents=True)
    video = directory / 'depth-preview.mp4'
    video.write_bytes(b'video-fixture')
    metadata = {'schema': 'shiyin.video-depth-lab/v1', 'outputVideoPath': str(video),
                'input': {'processedWidth': 320, 'processedHeight': 180, 'processedFps': 24}}
    (directory / 'run-metadata.json').write_text(json.dumps(metadata), encoding='utf-8')
    return directory, metadata


def mapper(root):
    def url(path):
        try:
            relative = Path(path).relative_to(root)
        except ValueError:
            return None
        return '/assets/output/' + relative.as_posix()
    return url


@pytest.mark.parametrize('encoding', ['utf-8', 'gbk'])
def test_worker_chinese_path_survives_pipe_encoding(tmp_path, monkeypatch, encoding):
    service = VideoDepthTaskService(tmp_path)
    directory = tmp_path / '客户 视频' / 'depth_video_task'
    directory.mkdir(parents=True)
    video = directory / 'depth-preview.mp4'
    video.write_bytes(b'video')
    event = json.dumps({'type': 'result', 'result': {'outputVideoPath': str(video)}}, ensure_ascii=False)
    raw = event.encode(encoding)
    assert json.loads(decode_worker_output(raw))['result']['outputVideoPath'] == str(video)
    if encoding == 'gbk':
        assert json.loads(raw.decode('utf-8', errors='replace'))['result']['outputVideoPath'] != str(video)

    class Process:
        stdout = io.BytesIO(raw + b'\n')
        stderr = io.BytesIO(b'x' * 300000)

        def wait(self):
            return 0

    monkeypatch.setattr(service, '_runtime', lambda: {'command': ['worker'], 'cwd': tmp_path, 'env': None, 'modelReady': True})
    monkeypatch.setattr('canvas_core.video_depth.subprocess.Popen', lambda *args, **kwargs: Process())
    service._tasks['task'] = {'id': 'task', 'userId': 'admin'}
    service._run('task', tmp_path / 'input.mp4', directory, mapper(tmp_path))
    assert service.get('task')['status'] == 'done'
    assert '客户 视频' in service.get('task')['outputUrl']


def test_junction_output_maps_to_configured_root(tmp_path):
    real = tmp_path / '真实目录'
    real.mkdir()
    alias = tmp_path / 'configured'
    if os.name == 'nt':
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(real)], check=True, capture_output=True)
    else:
        alias.symlink_to(real, target_is_directory=True)
    try:
        directory, result = completed(real)
        assert mapper(alias)(result['outputVideoPath']) is None
        mapped = output_url_mapper(alias, mapper(alias))
        assert mapped(result['outputVideoPath']) == '/assets/output/' + directory.name + '/depth-preview.mp4'
        assert mapped(str(tmp_path / 'other.mp4')) is None
    finally:
        if os.name == 'nt':
            alias.rmdir()  # Remove only the junction, never its target.
        else:
            alias.unlink()


def test_recover_legacy_result_after_restart_and_relocated_install(tmp_path):
    root = tmp_path / '用户 视频'
    directory, result = completed(root)
    result['outputVideoPath'] = 'Z:/old-install/乱码/depth-preview.mp4'
    (directory / 'run-metadata.json').write_text(json.dumps(result), encoding='utf-8')
    service = VideoDepthTaskService(tmp_path)
    recovered = service.get('a' * 32, root, mapper(root), 'alice')
    assert recovered['status'] == 'done'
    assert recovered['width'] == 320
    assert recovered['userId'] == 'alice'
    assert recovered['outputUrl'].endswith('/depth-preview.mp4')
    assert service.get('a' * 32, tmp_path / 'bob', mapper(tmp_path / 'bob'), 'bob') is None


def test_failed_task_recovers_but_active_and_other_account_do_not(tmp_path):
    directory, result = completed(tmp_path)
    service = VideoDepthTaskService(tmp_path)
    service._tasks['a' * 32] = {'id': 'a' * 32, 'status': 'failed', 'userId': 'alice', 'error': 'old error'}
    assert service.get('a' * 32, tmp_path, mapper(tmp_path), 'bob') is None
    assert service.get('a' * 32, tmp_path, mapper(tmp_path), 'alice')['error'] == ''
    service._tasks['a' * 32]['status'] = 'running'
    assert service.get('a' * 32, tmp_path, mapper(tmp_path), 'alice')['status'] == 'running'


@pytest.mark.parametrize('damage', ['empty', 'missing', 'bad-json', 'wrong-schema', 'escape'])
def test_recovery_rejects_incomplete_or_invalid_result(tmp_path, damage):
    directory, result = completed(tmp_path)
    metadata = directory / 'run-metadata.json'
    video = directory / 'depth-preview.mp4'
    if damage == 'empty':
        video.write_bytes(b'')
    elif damage == 'missing':
        video.unlink()
    elif damage == 'bad-json':
        metadata.write_text('{')
    elif damage == 'wrong-schema':
        metadata.write_text('{}')
    else:
        outside = tmp_path / 'outside.mp4'
        outside.write_bytes(b'outside')
        video.unlink()
        result['outputVideoPath'] = str(outside)
        metadata.write_text(json.dumps(result))
    service = VideoDepthTaskService(tmp_path)
    assert service.get('a' * 32, tmp_path, mapper(tmp_path), 'admin') is None
    assert service.get('../escape', tmp_path, mapper(tmp_path), 'admin') is None


def test_background_worker_keeps_account_and_setup_failure_is_terminal(tmp_path, monkeypatch):
    service = VideoDepthTaskService(tmp_path)
    seen = []
    service._tasks['task'] = {'id': 'task', 'userId': 'alice'}

    def worker(*args):
        seen.append(current_account_id())
        raise RuntimeError('runtime setup failed')

    monkeypatch.setattr(service, '_run_worker', worker)
    with account_scope('bob'):
        thread = threading.Thread(target=service._run, args=('task', tmp_path, tmp_path, lambda p: p))
        thread.start()
        thread.join(timeout=5)
        assert current_account_id() == 'bob'
    assert seen == ['alice']
    assert service.get('task')['status'] == 'failed'


def test_missing_file_and_mapping_error_are_distinct(tmp_path):
    directory, result = completed(tmp_path)
    with pytest.raises(RuntimeError, match='媒体地址映射失败'):
        VideoDepthTaskService._output_result(directory, result, lambda p: None)
    (directory / 'depth-preview.mp4').unlink()
    with pytest.raises(RuntimeError, match='输出文件缺失'):
        VideoDepthTaskService._output_result(directory, result, lambda p: None)
