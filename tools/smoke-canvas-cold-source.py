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


def run(rounds, port, engine=False, node_count=301, direct=False, interactions=False):
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
                nodes = [{'id':f'image-{i}','type':'image','url':urls[i % 60], 'x':(i%10)*360,'y':(i//10)*300,'w':320,'h':240} for i in range(node_count-2)]
                nodes.insert(1, {'id':'video','type':'image','mediaKind':'video','url':video_url,'x':360,'y':-320,'w':320,'h':240})
                nodes.append({'id':'prompt','type':'prompt','text':'重启后保持','x':0,'y':-300})
                response = session.put(base+'/api/canvases/'+canvas_id, json={'title':'冷启动混合媒体验证','nodes':nodes,'connections':[], 'viewport':{'x':40,'y':240,'scale':.65}}, timeout=15)
                response.raise_for_status()
            script = work / 'check.cjs'
            browser = helpers.BROWSER.replace("require('playwright')", 'require('+json.dumps(str(ROOT/'node_modules/playwright'))+')')
            browser = browser.replace("assert(frame,'画布工程 iframe 未打开');", "assert(frame,'画布工程 iframe 未打开');\n  if(!input.engine) await frame.goto(frame.url()+'&canvasEngine=legacy');")
            if direct:
                start = browser.index("  await page.goto(input.base+'/static/canvas-list.html');")
                end = browser.index("  await frame.waitForFunction", start)
                browser = browser[:start] + "  await page.goto(input.base+'/static/canvas.html?id='+input.id+(input.engine?'&canvasEngine=upstream':'&canvasEngine=legacy'));\n  const listMs=0;\n  const frame=page.mainFrame();\n" + browser[end:]
            if engine or node_count > 500:
                browser = browser.replace("page.on('pageerror',e=>errors.push(e.message));", "page.on('pageerror',e=>{errors.push(e.message);console.error('[pageerror]',e.message)});")
                browser = browser.replace("await frame.waitForFunction(()=>window.CanvasSessionLifecycle?.state().id && !window.canvasEntryOverlay,{},{timeout:30000});", "try{await frame.waitForFunction(()=>window.CanvasSessionLifecycle?.state().id && !window.canvasEntryOverlay,{},{timeout:120000})}catch(error){console.error('[canvas-state]',JSON.stringify(await frame.evaluate(()=>({engine:!!window.CanvasEngine,bridge:!!window.CanvasEngineBridge,world:!!document.getElementById('world'),nodes:document.querySelectorAll('.node').length,notice:document.getElementById('canvasStartupNotice')?.textContent,overlay:!!window.canvasEntryOverlay}))));throw error}")
            browser = browser.replace('const state=await frame.evaluate', 'const entryMs=Date.now()-started-listMs;\n  const state=await frame.evaluate')
            browser = browser.replace('pixels:[...document.querySelectorAll', 'engine_active:!!window.CanvasEngine?.active,pixels:[...document.querySelectorAll')
            browser = browser.replace('assert.equal(state.count,301)', 'assert.equal(state.count,input.nodes)')
            browser = browser.replace('assert.equal(state.id,input.id);', 'assert.equal(state.id,input.id);assert.equal(state.engine_active,input.engine);')
            browser = browser.replace('await page.screenshot', '''await frame.waitForFunction(()=>{
                const node=document.querySelector('[data-id="video"]');
                return node?.querySelector('img')?.naturalWidth>0 || node?.querySelector('video')?.readyState>=2;
            });
            await page.screenshot''')
            browser = browser.replace('entry_ms:Date.now()-started', 'entry_ms:entryMs')
            if interactions:
                if not direct:
                    raise ValueError('交互验证需要 --direct')
                browser = browser.replace('console.log(JSON.stringify({list_ms:', '''const before=await frame.evaluate(()=>({...viewport}));
            await page.mouse.move(1320,360);await page.mouse.wheel(0,-200);
            await page.waitForTimeout(120);
            const afterWheel=await frame.evaluate(()=>({...viewport}));
            assert(afterWheel.scale>before.scale,'滚轮缩放未更新画布比例');
            await frame.locator('#canvasPanTool').click();
            await page.mouse.move(1320,180);await page.mouse.down();
            await page.mouse.move(1010,280,{steps:12});await page.mouse.up();
            const afterPan=await frame.evaluate(()=>({...viewport}));
            if(Math.abs(afterPan.x-afterWheel.x)<=200) console.error('[pan-state]',JSON.stringify({before:afterWheel,after:afterPan,target:await frame.evaluate(()=>document.elementFromPoint(1320,180)?.outerHTML.slice(0,250)),tool:await frame.evaluate(()=>canvasToolMode)}));
            assert(Math.abs(afterPan.x-afterWheel.x)>200,'移动工具未平移画布');
            const mounted=await frame.evaluate(()=>document.querySelectorAll('#nodes .node').length);
            if(input.engine) assert(mounted<input.nodes/4,'新引擎挂载了过多视口外节点');
            else assert.equal(mounted,input.nodes);
            await frame.locator('#canvasSelectTool').click();
            await page.mouse.click(1320,180,{button:'right'});
            assert(await frame.evaluate(()=>document.getElementById('createMenu')?.classList.contains('open')),'空白画布右键菜单未打开');
            await frame.locator('#createMenu .menu-btn').filter({hasText:'提示词'}).first().click();
            await frame.waitForFunction(()=>document.querySelector(`.node[data-id="${CSS.escape(nodes.at(-1)?.id||'')}"]`),{},{timeout:5000});
            const created=await frame.evaluate(()=>({models:nodes.length,dom:document.querySelectorAll('#nodes .node').length,last:{id:nodes.at(-1)?.id,type:nodes.at(-1)?.type,x:nodes.at(-1)?.x,y:nodes.at(-1)?.y},mounted:!!document.querySelector(`.node[data-id="${CSS.escape(nodes.at(-1)?.id||'')}"]`)}));
            assert.equal(created.models,input.nodes+1,'右键创建未加入工程节点');
            if(!created.mounted) console.error('[create-state]',JSON.stringify({created,viewport:await frame.evaluate(()=>({...viewport})),visible:await frame.evaluate(()=>window.CanvasEngine?.visibleIds().slice(-5))}));
            assert(created.mounted,'新建提示词节点未显示');
            if(input.engine) assert(created.dom<input.nodes/4,'新增节点后挂载量异常');
            else assert.equal(created.dom,input.nodes+1);
            await frame.locator(`.node[data-id="${created.last.id}"] .node-title`).click();
            assert(await frame.evaluate(id=>selected.has(id),created.last.id),'新节点无法选中');
            await frame.evaluate(()=>performUndo());
            await frame.waitForFunction(total=>nodes.length===total,input.nodes);
            assert(!await frame.evaluate(id=>!!document.querySelector(`.node[data-id="${CSS.escape(id)}"]`),created.last.id),'撤销后节点仍在画布');
            await frame.evaluate(()=>performRedo());
            await frame.waitForFunction(id=>!!document.querySelector(`.node[data-id="${CSS.escape(id)}"]`),created.last.id);
            let roundTrip=null;
            if(input.engine){
                const mediaId=await frame.evaluate(()=>[...document.querySelectorAll('.image-node[data-id]')].find(el=>el.querySelector('img')?.naturalWidth>0)?.dataset.id);
                assert(mediaId,'没有已解码的可见图片节点');
                await frame.evaluate(()=>{viewport.x=-4000;viewport.y=-3000;applyViewport()});
                await frame.waitForFunction(id=>!document.querySelector(`.node[data-id="${CSS.escape(id)}"]`),mediaId);
                await frame.evaluate(previous=>{viewport.x=previous.x;viewport.y=previous.y;viewport.scale=previous.scale;applyViewport()},afterPan);
                await frame.waitForFunction(id=>document.querySelector(`.node[data-id="${CSS.escape(id)}"] img`)?.naturalWidth>0,mediaId);
                roundTrip={mediaId,mounted:await frame.evaluate(()=>document.querySelectorAll('#nodes .node').length)};
            }
            await frame.evaluate(()=>saveCanvas());
            await frame.waitForFunction(async total=>{const response=await fetch('/api/canvases/'+canvas.id);return (await response.json()).canvas.nodes.length===total},input.nodes+1,{timeout:10000});
            const persisted=await frame.evaluate(async()=>{const response=await fetch('/api/canvases/'+canvas.id);return (await response.json()).canvas.nodes.length});
            assert.equal(persisted,input.nodes+1,'新建节点没有保存到工程');
            const interaction={before,afterWheel,afterPan,mounted,created,roundTrip,persisted};
            console.log(JSON.stringify({interaction,list_ms:''')
            script.write_text(browser, encoding='utf-8')
            input_file = work / 'input.json'
            input_file.write_text(json.dumps({'base':base,'id':canvas_id,'engine':engine,'nodes':node_count,'cookies':[{'name':c.name,'value':c.value} for c in session.cookies], 'screenshot':str(work/f'round-{turn}.png')}), encoding='utf-8')
            checked = subprocess.run(['node',str(script),str(input_file)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=160)
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
    parser.add_argument('--engine',action='store_true')
    parser.add_argument('--nodes',type=int,default=301)
    parser.add_argument('--direct',action='store_true')
    parser.add_argument('--interactions',action='store_true')
    args=parser.parse_args()
    run(args.rounds,args.port,args.engine,args.nodes,args.direct,args.interactions)
