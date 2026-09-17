"""对真实冻结后端执行离线 SAM 分割/透明导出；数据与用户安装目录隔离。"""
import io
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
from PIL import Image

root = Path(__file__).resolve().parents[2]
binary = Path(sys.argv[1]).resolve()
data = root / ".codex-tmp" / "cutout-frozen-data"
env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
log = (root / '.codex-tmp' / 'cutout-frozen-check.log').open('wb')
process = subprocess.Popen(
    [str(binary), "--app-root", str(root), "--data-dir", str(data), "--host", "127.0.0.1", "--port", "8793"],
    env=env, cwd=root, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
)
try:
    with httpx.Client(base_url="http://127.0.0.1:8793", timeout=httpx.Timeout(180, connect=1), trust_env=False) as client:
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError(f"冻结后端启动失败：{process.returncode}")
            try:
                response = client.post('/api/account/login', json={'account': 'cutoutcheck', 'password': 'cutout-check-123'})
                if response.status_code == 401:
                    response = client.post('/api/account/register', json={'account': 'cutoutcheck', 'password': 'cutout-check-123'})
                response.raise_for_status()
                break
            except (httpx.ConnectError, httpx.ConnectTimeout):
                time.sleep(.5)
        else:
            raise RuntimeError("冻结后端启动超时")
        source = root / 'generated-images/20260830-open-mannequin-refs/ref-01.png'
        with source.open('rb') as image:
            response = client.post('/api/cutout/api/images', files={'image': ('test.png', image, 'image/png')})
        response.raise_for_status()
        session = response.json()
        body = {'session_id': session['session_id'], 'points': [{'x': 550, 'y': 420, 'label': 1}]}
        for endpoint in ['segment', 'export/cutout']:
            response = client.post('/api/cutout/api/' + endpoint, json=body)
            assert response.status_code == 200, (endpoint, response.status_code, response.text[:2000])
        image = Image.open(io.BytesIO(response.content))
        assert image.size == (session['width'], session['height'])
        assert image.mode == 'RGBA' and image.getextrema()[3] == (0, 255)
        response = client.delete('/api/cutout/api/images/' + session['session_id'])
        response.raise_for_status()
        print('PASS frozen offline SAM segmentation/export:', image.size, image.mode, image.getextrema()[3])
finally:
    process.terminate()
    process.wait(timeout=15)
    log.close()
