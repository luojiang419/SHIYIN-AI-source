"""Exercise the exact Windows PowerShell host used by the desktop executable."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
import zipfile


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell integration')
class ComponentBootstrapTests(unittest.TestCase):
    def test_extended_path_utf8_and_offline_component_install(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/prepare-components.ps1'
        with tempfile.TemporaryDirectory(prefix='depth-bootstrap-') as temp:
            root = Path(temp) / '中文路径 with spaces'
            cache = root / 'runtime/downloads'
            cache.mkdir(parents=True)
            archive = cache / 'fixture.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('runtime/video-depth-worker/video-depth-worker.exe', b'old worker')
                z.writestr('runtime/bin/ffmpeg.exe', b'ffmpeg fixture')
            raw = archive.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            package = {'id':'fixture', 'file':archive.name, 'size':len(raw), 'sha256':digest}
            variants = [{'id':'windows-x86_64-' + flavor, 'packages':['fixture'],
                         'required_paths':['runtime/video-depth-worker/video-depth-worker.exe', 'runtime/bin/ffmpeg.exe'],
                         'assemble_archive':{'size':len(raw), 'sha256':digest}}
                        for flavor in ['cpu', 'cuda126', 'cuda128']]
            (root / 'runtime-manifest.json').write_text(json.dumps({'message':'中文下载清单', 'packages':[package], 'variants':variants}, ensure_ascii=False), encoding='utf-8')
            overlays = root / 'worker-overlays'
            overlays.mkdir()
            updated = b'updated worker'
            (overlays / 'fixture.exe').write_bytes(updated)
            overlay = {'file':'fixture.exe', 'sha256':hashlib.sha256(updated).hexdigest()}
            (overlays / 'manifest.json').write_text(json.dumps({v:overlay for v in ['cpu', 'cuda126', 'cuda128']}), encoding='utf-8')
            model = root / 'runtime/models/test.pth'
            model.parent.mkdir()
            model_bytes = b'model fixture' * 10000
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *_args):
                    pass
                def do_GET(self):
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(model_bytes)))
                    self.end_headers()
                    self.wfile.write(model_bytes[:1000])
                    self.wfile.flush()
                    time.sleep(1.2)
                    self.wfile.write(model_bytes[1000:])
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            model_entry = {'id':'vda-small-model', 'target_path':'models/test.pth', 'size':len(model_bytes), 'sha256':hashlib.sha256(model_bytes).hexdigest(), 'domestic_url':f'http://127.0.0.1:{server.server_port}/model'}
            (root / 'model-download-manifest.json').write_text(json.dumps({'message':'中文模型清单', 'packages':[model_entry]}, ensure_ascii=False), encoding='utf-8')
            command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-Root', '\\\\?\\' + str(root), '-Model', 'vda_small_fp16_relative']
            env = os.environ.copy()
            # Do not import the invoking PowerShell 7 host's modules into 5.1.
            env.pop('PSModulePath', None)
            try:
                result = subprocess.run(command, capture_output=True, timeout=60, env=env)
            finally:
                server.shutdown()
                server.server_close()
            self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
            self.assertEqual((root / 'runtime/video-depth-worker/video-depth-worker.exe').read_bytes(), updated)
            self.assertEqual(model.read_bytes(), model_bytes)
            self.assertIn('Downloading vda-small-model:', result.stdout.decode('utf-8'))
            self.assertFalse(cache.exists())


if __name__ == '__main__':
    unittest.main()
