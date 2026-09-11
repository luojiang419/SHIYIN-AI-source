"""独立目录验证冻结画布后端首次进入、重启和旧版本数据升级，不触碰用户安装。"""
import argparse
import io
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import requests
from PIL import Image


BROWSER = r"""
const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.addCookies(input.cookies.map(c=>({name:c.name,value:c.value,url:input.base})));
  const page=await context.newPage(); const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const started=Date.now();
  await page.goto(input.base+'/static/canvas-list.html');
  await page.waitForFunction(()=>!window.canvasListEntryOverlay && document.querySelectorAll('.ws-card').length>0,{},{timeout:30000});
  const listMs=Date.now()-started;
  await page.evaluate(id=>openCanvas({id,project:'default'}),input.id);
  let frame;
  for(let i=0;i<100;i++){
   frame=page.frames().find(f=>f.url().includes('canvas.html?id='+input.id));
   if(frame)break;
   await new Promise(r=>setTimeout(r,50));
  }
  assert(frame,'画布工程 iframe 未打开');
  await frame.waitForFunction(()=>window.CanvasSessionLifecycle?.state().id && !window.canvasEntryOverlay,{},{timeout:30000});
  const state=await frame.evaluate(()=>({count:nodes.length,id:canvas.id,
   pixels:[...document.querySelectorAll('img')].filter(x=>x.naturalWidth>0).length}));
  assert.equal(state.count,301);assert.equal(state.id,input.id);assert(state.pixels>0);
  assert.deepEqual(errors,[]);
  await page.screenshot({path:input.screenshot});
  console.log(JSON.stringify({list_ms:listMs,entry_ms:Date.now()-started,...state,page_errors:errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
"""


def launch(stage, data, port, logs):
    backend = stage / 'app/backend/canvas-backend/canvas-backend.exe'
    env = dict(os.environ, CANVAS_DWPOSE_AUTO_DOWNLOAD='0', CANVAS_DEPTH_AUTO_DOWNLOAD='0')
    started = time.monotonic()
    with logs.open('wb') as log:
        process = subprocess.Popen([str(backend), '--host', '127.0.0.1', '--port', str(port),
            '--data-dir', str(data), '--app-root', str(stage / 'app'),
            '--portable-root', str(stage), '--runtime-mode', 'desktop'],
            cwd=stage, env=env, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        for _ in range(200):
            assert process.poll() is None, f'冻结后端提前退出，见 {logs}'
            try:
                health = requests.get(f'http://127.0.0.1:{port}/api/health', timeout=1)
                if health.ok:
                    return process, round((time.monotonic()-started)*1000), health.json()
            except requests.RequestException:
                pass
            time.sleep(.1)
        raise TimeoutError('冻结后端启动超时')
    except BaseException:
        stop(process)
        raise


def stop(process):
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def login(base, register=False):
    session = requests.Session()
    response = session.post(base + '/api/account/' + ('register' if register else 'login'),
        json={'account': 'ColdFixture', 'password': 'fixture-only'}, timeout=15)
    response.raise_for_status()
    return session


def seed(session, base):
    png = io.BytesIO()
    Image.new('RGB', (256, 160), 'steelblue').save(png, format='PNG')
    result = session.post(base + '/api/ai/upload',
        files={'files': ('cold.png', png.getvalue(), 'image/png')}, timeout=15)
    result.raise_for_status()
    url = result.json()['files'][0]['url']
    result = session.post(base + '/api/canvases', json={'title': '冷启动301节点'}, timeout=15)
    result.raise_for_status()
    canvas_id = result.json()['canvas']['id']
    nodes = [{'id': f'image-{i}', 'type': 'image', 'url': url,
        'x': (i % 10)*360, 'y': (i//10)*300, 'w': 320, 'h': 240} for i in range(300)]
    nodes.append({'id': 'prompt', 'type': 'prompt', 'text': '重启后保持', 'x': 0, 'y': -300})
    result = session.put(base + '/api/canvases/' + canvas_id, json={
        'title': '冷启动301节点', 'nodes': nodes, 'connections': [],
        'viewport': {'x': 40, 'y': 40, 'scale': .7}}, timeout=15)
    result.raise_for_status()
    return canvas_id


def run(args):
    stage = Path(args.stage).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='cold-', dir=output))
    browser_script = root / 'browser.cjs'
    browser_script.write_text(BROWSER, encoding='utf-8')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))
    base = f'http://127.0.0.1:{args.port}'
    results = []
    scenarios = [('fresh', stage)]
    if args.previous_stage:
        scenarios.append(('upgrade', Path(args.previous_stage).resolve()))
    for scenario, seed_stage in scenarios:
        data = root / scenario / 'data'
        process, startup_ms, health = launch(seed_stage, data, args.port, root / f'{scenario}-seed.log')
        try:
            with login(base, register=True) as session:
                initial = session.get(base + '/api/canvases', timeout=15)
                initial.raise_for_status()
                assert initial.json()['canvases'] == []
                canvas_id = seed(session, base)
                if scenario == 'fresh':
                    results.append(check(session, base, canvas_id, root, browser_script,
                        scenario+'-first', startup_ms, health))
        finally:
            stop(process)
        for cycle in range(args.cycles):
            label = f'{scenario}-restart-{cycle+1}'
            process, startup_ms, health = launch(stage, data, args.port, root / f'{label}.log')
            try:
                with login(base) as session:
                    results.append(check(session, base, canvas_id, root, browser_script,
                        label, startup_ms, health))
            finally:
                stop(process)
    report = {'stage': str(stage), 'results': results, 'logs': str(root)}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


def check(session, base, canvas_id, root, browser_script, label, startup_ms, health):
    started = time.monotonic()
    for endpoint in ['/api/projects', '/api/canvases', '/api/runtime/config']:
        session.get(base + endpoint, timeout=15).raise_for_status()
    response = session.get(base + '/api/canvases/' + canvas_id, timeout=15)
    response.raise_for_status()
    assert len(response.json()['canvas']['nodes']) == 301
    assert response.json()['canvas']['nodes'][-1]['text'] == '重启后保持'
    api_ms = round((time.monotonic()-started)*1000)
    options = root / (label+'.json')
    options.write_text(json.dumps({'base': base, 'id': canvas_id,
        'cookies': [{'name': c.name, 'value': c.value} for c in session.cookies],
        'screenshot': str(root / (label+'.png'))}), encoding='utf-8')
    result = subprocess.run(['node', str(browser_script), str(options)], capture_output=True,
        text=True, encoding='utf-8', timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    return {'scenario': label, 'health': health.get('status'), 'startup_ms': startup_ms,
        'api_ms': api_ms, 'browser': json.loads(result.stdout.strip().splitlines()[-1])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True)
    parser.add_argument('--previous-stage')
    parser.add_argument('--output', required=True)
    parser.add_argument('--port', type=int, default=3137)
    parser.add_argument('--cycles', type=int, default=3)
    run(parser.parse_args())
