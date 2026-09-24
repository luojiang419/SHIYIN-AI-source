import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from canvas_core import component_profiles as profiles
from canvas_core.component_profiles import RuntimeCapabilities, select_variant
from canvas_core.video_depth import VideoDepthTaskService, VideoDepthUnavailable, smoke_video_depth_runtime
from canvas_core.video_depth_runtime import configure_video_depth_device, select_video_depth_device
from canvas_core.person_depth_components import PersonDepthComponentManager


VARIANTS = json.loads(Path('canvas_core/video_depth_runtime_manifest.json').read_text(encoding='utf-8'))['variants']


@pytest.mark.parametrize('compute,memory,driver,expected', [
    (0, 0, '', 'cpu'), (6.1, 8, '576.80', 'cpu'),
    (8.6, 3, '576.80', 'cpu'), (8.6, 8, '552.44', 'cpu'),
    (8.6, 4, '560.76', 'cuda126'), (8.9, 16, '576.80', 'cuda126'),
    (12.0, 8, '570.65', 'cuda128'), (12.0, 8, '560.76', 'cpu'),
    (10.0, 16, '576.80', 'cpu'),
])
def test_actual_manifest_selects_only_compatible_runtime(compute, memory, driver, expected):
    device = RuntimeCapabilities('windows', 'x86_64', 'cuda' if compute else 'cpu',
                                 compute_capability=compute, gpu_memory_bytes=memory * 1024**3,
                                 driver_version=driver)
    assert select_variant(VARIANTS, device)['id'] == 'windows-x86_64-' + expected


def test_probe_skips_bad_rows_and_selects_supported_gpu(monkeypatch):
    monkeypatch.setattr(profiles.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(profiles.platform, 'machine', lambda: 'AMD64')
    monkeypatch.setattr(profiles.shutil, 'which', lambda _: 'nvidia-smi')
    monkeypatch.delenv('CUDA_VISIBLE_DEVICES', raising=False)
    monkeypatch.setattr(profiles.subprocess, 'run', lambda *a, **k: SimpleNamespace(
        returncode=0, stdout='bad,row\nPascal, 24576, 6.1, 576.80, GPU-old, 0\nRTX, 16384, 8.9, 576.80, GPU-new, 1\n'))
    devices = profiles.probe_runtime_devices()
    selected = select_video_depth_device(devices, VARIANTS)
    assert selected.gpu_uuid == 'GPU-new'
    env = {}
    configure_video_depth_device(env, 'windows-x86_64-cuda126', selected)
    assert env['CUDA_VISIBLE_DEVICES'] == 'GPU-new'
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '0')
    assert profiles.probe_runtime_devices()[0].gpu_uuid == 'GPU-old'
    monkeypatch.setenv('CUDA_VISIBLE_DEVICES', '')
    assert profiles.probe_runtime_devices()[0].accelerator == 'cpu'


@pytest.mark.parametrize('failure', ['missing', 'timeout', 'error', 'unknown'])
def test_probe_failure_safely_chooses_cpu(monkeypatch, failure):
    monkeypatch.setattr(profiles.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(profiles.platform, 'machine', lambda: 'AMD64')
    monkeypatch.setattr(profiles.shutil, 'which', lambda _: None if failure == 'missing' else 'nvidia-smi')
    monkeypatch.setattr(profiles.os.path, 'isfile', lambda _: False)
    def run(*args, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired('nvidia-smi', 5)
        return SimpleNamespace(returncode=1 if failure == 'error' else 0, stdout='unsupported')
    monkeypatch.setattr(profiles.subprocess, 'run', run)
    assert profiles.probe_runtime_capabilities().accelerator == 'cpu'


def test_cpu_runtime_disables_cuda_and_cuda_smoke_requires_working_gpu(tmp_path, monkeypatch):
    env = {'CUDA_VISIBLE_DEVICES': 'GPU-other'}
    configure_video_depth_device(env, 'windows-x86_64-cpu', None)
    assert env['CUDA_VISIBLE_DEVICES'] == ''
    (tmp_path / 'component-manifest.json').write_text(json.dumps({'variant': 'windows-x86_64-cuda126'}))
    monkeypatch.setattr('canvas_core.video_depth.subprocess.run', lambda *a, **k: SimpleNamespace(
        returncode=0, stderr='', stdout=json.dumps({'type': 'result', 'result': {'runtimeReady': True, 'cudaAvailable': False}})))
    with pytest.raises(VideoDepthUnavailable, match='CUDA'):
        smoke_video_depth_runtime(['worker'], tmp_path)


def test_managed_runtime_does_not_bypass_selection_with_stale_bundle(tmp_path):
    service = VideoDepthTaskService(tmp_path, runtime_manager=SimpleNamespace(installation_path=lambda: None))
    worker = service.packaged_runtime / 'video-depth-worker/video-depth-worker.exe'
    source = service.packaged_runtime / 'sources/video-depth-anything/video_depth_anything/video_depth.py'
    worker.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    worker.write_bytes(b'old incompatible cuda')
    source.write_text('')
    assert service._packaged_runtime() is None


@pytest.mark.parametrize('saved_device,expected', [('same', 'cpu'), ('old-driver', 'cuda126'),
                                                 ('old-gpu', 'cuda126'), ('legacy', 'cuda126')])
def test_fallback_is_remembered_only_for_same_hardware_and_driver(tmp_path, saved_device, expected):
    device = RuntimeCapabilities('windows', 'x86_64', 'cuda', gpu_memory_bytes=16 * 1024**3,
                                 compute_capability=8.9, driver_version='576.80', gpu_uuid='GPU-test')
    manifest = json.loads(Path('canvas_core/video_depth_runtime_manifest.json').read_text(encoding='utf-8'))
    current = {'version': manifest['version'], 'variant': 'windows-x86_64-cpu',
               'capabilities': device.public_dict()}
    if saved_device == 'old-driver':
        current['capabilities']['driver_version'] = '552.44'
    elif saved_device == 'old-gpu':
        current['capabilities']['gpu_uuid'] = 'GPU-previous'
    elif saved_device == 'legacy':
        current.pop('capabilities')
    (tmp_path / 'current.json').write_text(json.dumps(current))
    manager = PersonDepthComponentManager(tmp_path, manifest=manifest, component_name='video-depth-runtime',
                                         capability_provider=lambda: device)
    assert manager.selected_variant_id == 'windows-x86_64-' + expected
