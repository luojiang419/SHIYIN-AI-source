import hashlib
import json
from pathlib import Path

import pytest

from canvas_core.video_depth_overlay import prepare_worker


def fixture(tmp_path):
    worker = tmp_path / 'runtime' / 'video-depth-worker.exe'
    worker.parent.mkdir()
    worker.write_bytes(b'old worker')
    overlays = tmp_path / 'overlays'
    overlays.mkdir()
    (overlays / 'cpu.exe').write_bytes(b'updated worker')
    entry = {'file': 'cpu.exe', 'source_sha256': hashlib.sha256(worker.read_bytes()).hexdigest(),
             'sha256': hashlib.sha256(b'updated worker').hexdigest()}
    (overlays / 'manifest.json').write_text(json.dumps({'cpu': entry}))
    return worker, overlays


def test_overlay_preserves_fixed_runtime_and_repairs_corrupted_copy(tmp_path):
    worker, overlays = fixture(tmp_path)
    updated = prepare_worker(worker, overlays)
    assert updated.parent == worker.parent
    assert updated.read_bytes() == b'updated worker'
    assert worker.read_bytes() == b'old worker'
    modified = updated.stat().st_mtime_ns
    assert prepare_worker(worker, overlays).stat().st_mtime_ns == modified
    updated.write_bytes(b'corrupt')
    assert prepare_worker(worker, overlays).read_bytes() == b'updated worker'


@pytest.mark.parametrize('failure', ['missing', 'corrupt', 'unknown'])
def test_overlay_rejects_missing_corrupt_or_wrong_dependency_flavor(tmp_path, failure):
    worker, overlays = fixture(tmp_path)
    if failure == 'missing':
        (overlays / 'manifest.json').unlink()
    elif failure == 'corrupt':
        (overlays / 'cpu.exe').write_bytes(b'bad update')
    else:
        worker.write_bytes(b'other Python or torch runtime')
    with pytest.raises(RuntimeError):
        prepare_worker(worker, overlays)
    assert not list(worker.parent.glob('shiyin-*.exe'))


def test_accepts_already_updated_runtime(tmp_path):
    worker, overlays = fixture(tmp_path)
    worker.write_bytes(b'updated worker')
    assert prepare_worker(worker, overlays) == worker
