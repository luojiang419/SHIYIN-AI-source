"""用固定发行运行时复现旧错误，并验证主程序的真实 Small/Base 推理。"""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from canvas_core.video_depth import VideoDepthTaskService, decode_worker_output
from canvas_core.video_depth_runtime import probe_video_depth_capabilities
from canvas_core.component_profiles import select_variant


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', action='append', choices=['cpu', 'cuda126', 'cuda128'])
    parser.add_argument('--auto', action='store_true', help='按本机硬件自动选择运行时并实测')
    parser.add_argument('--output', type=Path, default=ROOT / '.codex-tmp/video-depth-217')
    args = parser.parse_args()
    capabilities = probe_video_depth_capabilities()
    if args.auto:
        if args.variant:
            parser.error('--auto 不能与 --variant 同时使用')
        manifest = json.loads((ROOT / 'canvas_core/video_depth_runtime_manifest.json').read_text(encoding='utf-8'))
        selected = select_variant(manifest['variants'], capabilities)['id']
        args.variant = [selected.removeprefix('windows-x86_64-')]
        print(f'Automatic runtime: {selected}', flush=True)
    report = []
    for variant in args.variant or ['cpu', 'cuda126', 'cuda128']:
        print(f'{variant}: preparing fixed runtime', flush=True)
        component = args.output.resolve() / variant
        runtime = component / 'runtime'
        worker = runtime / 'video-depth-worker/video-depth-worker.exe'
        if not worker.is_file():
            with zipfile.ZipFile(ROOT / f'dist/video-depth-runtime/video-depth-runtime-1.0.0-windows-x86_64-{variant}.zip') as bundle:
                bundle.extractall(component)
        source = args.output.resolve() / '客户 视频.mp4'
        subprocess.run([str(runtime / 'bin/ffmpeg.exe'), '-y', '-f', 'lavfi', '-i',
                        'testsrc2=size=160x120:rate=4', '-t', '1', '-pix_fmt', 'yuv420p', str(source)],
                       check=True, capture_output=True)
        old = subprocess.run([str(worker), 'infer', '--model', 'vda_small_fp16_relative',
                              '--input', str(source), '--output-dir', str(component / 'old'), '--input-size', '322'],
                             capture_output=True, timeout=90)
        assert old.returncode == 2 and 'invalid choice' in decode_worker_output(old.stderr)

        class Runtime:
            selected_variant_id = 'windows-x86_64-' + variant
            def installation_path(self): return component

        class Model:
            selected_variant_id = 'lite'
            def installation_path(self): return ROOT / 'tools/video-depth-lab/runtime'

        model = Model()
        runtime_manager = Runtime()
        runtime_manager.capabilities = capabilities
        service = VideoDepthTaskService(ROOT, model_manager=model, runtime_manager=runtime_manager)
        service._source_runtime = lambda: None
        try:
            for tier in ['lite', 'quality']:
                model.selected_variant_id = tier
                task_id = f'{variant}-{tier}'
                service._tasks[task_id] = {'id': task_id, 'userId': 'admin'}
                service._run(task_id, source, component / tier, lambda path: '/output/' + Path(path).name)
                task = service.get(task_id)
                assert task['status'] == 'done', task
                metadata = json.loads((component / tier / 'run-metadata.json').read_text(encoding='utf-8'))
                assert metadata['model']['key'] == service._model_key()
                assert metadata['input']['processedFrames'] == 4
                subprocess.run([str(runtime / 'bin/ffmpeg.exe'), '-v', 'error', '-i',
                                str(component / tier / 'depth-preview.mp4'), '-f', 'null', '-'],
                               check=True, capture_output=True)
                report.append({'variant': variant, 'tier': tier, 'status': task['status'],
                               'frames': task['frameCount'], 'worker': service._worker_process.args[0]})
                print(f'{variant}/{tier}: real inference and MP4 decode passed', flush=True)
        finally:
            service.close()
    destination = args.output / ('auto-report.json' if args.auto else 'report.json')
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(destination)


if __name__ == '__main__':
    main()
