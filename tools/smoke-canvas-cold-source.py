"""使用独立数据目录验证真实源码后端、磁盘预览与浏览器首开；不操作安装实例。"""
import argparse
import io
import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import requests
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import importlib.util
spec = importlib.util.spec_from_file_location('cold_packaged', ROOT / 'tools/smoke-canvas-cold-packaged.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def run(rounds, port):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',port))
    work = Path(tempfile.mkdtemp(prefix='canvas-cold-source-'))
    env = dict(os.environ, CANVAS_DATA_DIR=str(work / 'data'), CANVAS_DWPOSE_AUTO_DOWNLOAD='0',
               CANVAS_DEPTH_AUTO_DOWNLOAD='0', PYTHONUTF8='1')
    base = f'http://127.0.0.1:{port}'
    process = None
    results = []
    try:
        for turn in range(rounds):
            started = time.monotonic()
            with (work / f'backend-{turn}.log').open('wb') as log:
                process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(port)],
                    cwd=ROOT, env=env, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            for _ in range(150):
                if process.poll() is not None:
                    raise RuntimeError(f'测试后端退出，参见 {work}')
                try:
                    if requests.get(base+'/api/health', timeout=.5).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(.1)
            else:
                raise TimeoutError('测试后端启动超时')
            startup_ms = round((time.monotonic()-started)*1000)
            session = helpers.login(base, register=turn == 0)
            if turn == 0:
                urls = []
                for i in range(60):
                    size = [(1920,1080),(1080,1920),(3840,2160)][i % 3]
                    image = Image.effect_noise((256,256), 50).convert('RGB').resize(size)
                    ImageDraw.Draw(image).rectangle((100,100,500,400), fill=(i*3 % 256,i*7 % 256,i*11 % 256))
                    buffer = io.BytesIO();image.save(buffer, format='JPEG', quality=85)
                    response = session.post(base+'/api/ai/upload', files={'files':(f'fixture-{i}.jpg',buffer.getvalue(),'image/jpeg')}, timeout=15)
                    response.raise_for_status();urls.append(response.json()['files'][0]['url'])
                video = work / 'fixture.mp4'
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=12','-t','1','-pix_fmt','yuv420p',str(video)], check=True, capture_output=True)
                with video.open('rb') as stream:
                    response = session.post(base+'/api/ai/upload', files={'files':('fixture.mp4',stream,'video/mp4')}, timeout=15)
                response.raise_for_status();video_url = response.json()['files'][0]['url']
                response = session.post(base+'/api/canvases', json={'title':'冷启动混合媒体验证'}, timeout=15)
                response.raise_for_status();canvas_id = response.json()['canvas']['id']
                nodes = [{'id':f'image-{i}','type':'image','url':urls[i % 60], 'x':(i%10)*360,'y':(i//10)*300,'w':320,'h':240} for i in range(299)]
                nodes.insert(1, {'id':'video','type':'image','mediaKind':'video','url':video_url,'x':360,'y':-320,'w':320,'h':240})
                nodes.append({'id':'prompt','type':'prompt','text':'重启后保持','x':0,'y':-300})
                response = session.put(base+'/api/canvases/'+canvas_id, json={'title':'冷启动混合媒体验证','nodes':nodes,'connections':[], 'viewport':{'x':40,'y':240,'scale':.65}}, timeout=15)
                response.raise_for_status()
            script = work / 'check.cjs'
            browser = helpers.BROWSER.replace("require('playwright')", 'require('+json.dumps(str(ROOT/'node_modules/playwright'))+')')
            browser = browser.replace('const state=await frame.evaluate', 'const entryMs=Date.now()-started-listMs;\n  const state=await frame.evaluate')
            browser = browser.replace('await page.screenshot', '''await frame.waitForFunction(()=>{
                const node=document.querySelector('[data-id="video"]');
                return node?.querySelector('img')?.naturalWidth>0 || node?.querySelector('video')?.readyState>=2;
            });
            await page.screenshot''')
            browser = browser.replace('entry_ms:Date.now()-started', 'entry_ms:entryMs')
            script.write_text(browser, encoding='utf-8')
            input_file = work / 'input.json'
            input_file.write_text(json.dumps({'base':base,'id':canvas_id,'cookies':[{'name':c.name,'value':c.value} for c in session.cookies], 'screenshot':str(work/f'round-{turn}.png')}), encoding='utf-8')
            checked = subprocess.run(['node',str(script),str(input_file)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=60)
            if checked.returncode:
                raise RuntimeError(checked.stdout+checked.stderr)
            result = dict(json.loads(checked.stdout),startup_ms=startup_ms,round=turn+1,video_verified=True)
            results.append(result);print(json.dumps(result),flush=True)
            helpers.stop(process);process=None
        (work/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(f'报告与截图：{work}',flush=True)
    finally:
        if process is not None:helpers.stop(process)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds',type=int,default=3)
    parser.add_argument('--port',type=int,default=13098)
    args=parser.parse_args()
    run(args.rounds,args.port)
