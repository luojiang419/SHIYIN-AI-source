import { test } from 'node:test';
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
import { pathToFileURL, fileURLToPath } from 'node:url';

test('批量界面串行调用真实命令、保留参数并隔离失败任务', async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1520,height:940}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.addInitScript(() => {
      window.calls = []; window.active = 0; window.peak = 0;
      window.__TAURI__ = {event:{listen:async () => () => {}},core:{convertFileSrc:p => p,invoke:async (name,args) => {
        window.calls.push({name,args});
        if(name === 'get_runtime_status') return {runtimeReady:true,device:'cpu',models:[]};
        if(name === 'choose_input_videos') return ['one.mp4','two.mp4'].map(name => ({name,path:'C:/input/'+name}));
        if(name === 'choose_output_directory') return 'C:/output';
        if(name === 'run_inference') {
          window.peak = Math.max(window.peak, ++window.active);
          await new Promise(r => setTimeout(r,100)); window.active--;
          if(args.request.inputPath.endsWith('one.mp4')) throw '模拟首项失败';
          return {outputDirectory:'C:/output/two',rawDepthPath:'C:/output/two/raw.npz'};
        }
        if(name === 'apply_parameters') return {outputVideoPath:args.request.outputPath};
      }}};
    });
    await page.goto(pathToFileURL(fileURLToPath(new URL('../batch-prototype/index.html',import.meta.url))).href);
    await page.locator('[data-action=add]').click();
    await page.locator('[data-action=start]').click();
    await page.waitForFunction(() => document.querySelectorAll('.job.done').length === 1);
    assert.equal(await page.locator('.job.failed').count(),1);
    assert.equal(await page.evaluate(() => window.peak),1);
    await page.locator('[data-select="1"]').click();
    await page.locator('[data-parameter=gamma]').fill('12');
    await page.locator('[data-action=export-adjusted]').click();
    const calls = await page.evaluate(() => window.calls);
    const requests = calls.filter(c => c.name === 'run_inference');
    assert.equal(requests.length,2);
    assert.equal(requests[0].args.request.maxFrames,-1);
    assert.equal(requests[0].args.request.extractionMode,'professional');
    assert.equal(calls.find(c => c.name === 'apply_parameters').args.request.parameters.midtone,12);
    assert.equal(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight),true);
    assert.equal(await page.locator('.summary').count(),0);
    assert.equal(await page.locator('.compact-model-status [data-action=start]').count(),1);
    assert.equal(await page.locator('body > .actions, main > .actions').count(),0);
    await page.reload();
    assert.equal(await page.locator('.job.done').count(),1);
    assert.deepEqual(errors,[]);
  } finally { await browser.close(); }
});

test('拖拽视频到任务区域会自动导入并清除拖拽提示', async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage();
    await page.addInitScript(() => {
      window.calls = []; window.listeners = {};
      window.__TAURI__ = {event:{listen:async (name, callback) => { window.listeners[name] = callback; }},core:{convertFileSrc:p => p,invoke:async (name,args) => {
        window.calls.push({name,args});
        if(name === 'get_runtime_status') return {runtimeReady:true,device:'cpu',models:[]};
        if(name === 'load_input_video') return {name:args.path.split('/').pop(),path:args.path,width:1920,height:1080,fps:30};
      }}};
    });
    await page.goto(pathToFileURL(fileURLToPath(new URL('../batch-prototype/index.html',import.meta.url))).href);
    await page.waitForFunction(() => Boolean(window.listeners['tauri://drag-drop']));
    await page.evaluate(() => window.listeners['tauri://drag-enter']({payload:{}}));
    assert.equal(await page.locator('.queue-panel.drag-active').count(),1);
    await page.evaluate(() => window.listeners['tauri://drag-drop']({payload:{paths:['C:/video/a.mp4','C:/video/b.mov']}}));
    await page.waitForFunction(() => document.querySelectorAll('.job').length === 2);
    assert.equal(await page.locator('.queue-panel.drag-active').count(),0);
    assert.deepEqual(await page.evaluate(() => window.calls.filter(c => c.name === 'load_input_video').map(c => c.args.path)),['C:/video/a.mp4','C:/video/b.mov']);
  } finally { await browser.close(); }
});

test('人物模式传递到组件准备与推理请求', async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage();
    await page.addInitScript(() => {
      window.calls = [];
      window.__TAURI__ = {event:{listen:async () => () => {}},core:{convertFileSrc:p => p,invoke:async (name,args) => {
        window.calls.push({name,args});
        if(name === 'get_runtime_status') return {runtimeReady:true,device:'cpu',models:[]};
        if(name === 'choose_input_videos') return [{name:'person.mp4',path:'C:/person.mp4'}];
        if(name === 'choose_output_directory') return 'C:/output';
        if(name === 'run_inference') return {outputDirectory:'C:/output/person',rawDepthPath:'C:/output/person/raw.npz'};
      }}};
    });
    await page.goto(pathToFileURL(fileURLToPath(new URL('../batch-prototype/index.html',import.meta.url))).href);
    await page.locator('[data-action=add]').click();
    await page.locator('[data-field=mode]').selectOption('person');
    await page.locator('[data-action=start]').click();
    await page.waitForFunction(() => document.querySelectorAll('.job.done').length === 1);
    const calls = await page.evaluate(() => window.calls);
    assert.equal(calls.find(c => c.name === 'ensure_components').args.extractionMode,'person');
    assert.equal(calls.find(c => c.name === 'run_inference').args.request.extractionMode,'person');
    assert.match(await page.locator('[data-note] b').textContent(), /全部提取完成 · 显存已释放/);
    assert.match(await page.locator('[data-toast]').textContent(), /推理进程已退出，显存已释放/);
  } finally { await browser.close(); }
});

test('组件准备期间显示进度并可取消，不进入推理', async () => {
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage();
    await page.addInitScript(() => {
      window.calls = []; window.listeners = {};
      window.__TAURI__ = {event:{listen:async (name, callback) => { window.listeners[name] = callback; }},core:{convertFileSrc:p => p,invoke:async name => {
        window.calls.push(name);
        if(name === 'get_runtime_status') return {runtimeReady:false,models:[]};
        if(name === 'choose_input_videos') return [{name:'one.mp4',path:'C:/one.mp4'}];
        if(name === 'choose_output_directory') return 'C:/output';
        if(name === 'ensure_components') return new Promise((resolve,reject) => { window.cancelPreparation = () => reject('cancelled'); setTimeout(() => window.listeners['depth-progress']({payload:{percent:0,message:'Downloading: 12 / 500 MB'}}),20); });
        if(name === 'cancel_inference') { window.cancelPreparation(); return true; }
      }}};
    });
    await page.goto(pathToFileURL(fileURLToPath(new URL('../batch-prototype/index.html',import.meta.url))).href);
    await page.locator('[data-action=add]').click();
    await page.locator('[data-action=start]').click();
    await page.waitForFunction(() => document.querySelector('[data-note]').textContent.includes('12 / 500'));
    assert.equal(await page.locator('[data-action=pause]').textContent(),'取消准备');
    await page.locator('[data-action=pause]').click();
    await page.waitForFunction(() => !document.querySelector('[data-action=start]').disabled);
    assert.equal(await page.evaluate(() => window.calls.includes('run_inference')),false);
    assert.match(await page.locator('[data-toast]').textContent(),/已取消/);
  } finally { await browser.close(); }
});

test('真实视频可播放定位、独立全屏及划像同步，并可打开输出目录', async t => {
  const { readFile, mkdir } = await import('node:fs/promises');
  const sample = new URL('../runtime/inputs/full-1080p-8f.mp4', import.meta.url);
  let bytes;
  try { bytes = await readFile(sample); } catch (e) { if (e.code === 'ENOENT') return t.skip('需要本地 runtime/inputs/full-1080p-8f.mp4 媒体样本'); throw e; }
  const media = 'data:video/mp4;base64,' + bytes.toString('base64');
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1520,height:940}});
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.addInitScript(media => {
      localStorage.setItem('shiyin-depth-batch-v1', JSON.stringify({outputRoot:'C:/output',queue:[{name:'人物.sample.mov',path:'source',state:'done',result:{outputVideoPath:'depth',outputDirectory:'C:/output/run',rawDepthPath:'raw'}}]}));
      window.calls = [];
      window.__TAURI__ = {event:{listen:async () => {}},core:{convertFileSrc:() => media,invoke:async (name,args) => {
        window.calls.push({name,args});
        if (name === 'get_runtime_status') return {runtimeReady:true,models:[]};
        if (name === 'apply_parameters') return {outputVideoPath:args.request.outputPath};
      }}};
    },media);
    await page.goto(pathToFileURL(fileURLToPath(new URL('../batch-prototype/index.html',import.meta.url))).href);
    await page.waitForFunction(() => document.querySelector('.preview-stage video').readyState >= 2);
    await page.locator('[data-action=play-preview]').click();
    await page.waitForFunction(() => !document.querySelector('.preview-stage video').paused);
    await page.locator('[data-play-icon]').waitFor({state:'hidden'});
    await page.locator('[data-preview-controls] [data-player-toggle]').click();
    await page.locator('[data-play-icon]').waitFor({state:'visible'});
    await page.locator('[data-preview-controls] [data-player-seek]').fill('500');
    assert.equal(await page.evaluate(() => { const v = document.querySelector('.preview-stage video'); return Math.abs(v.currentTime/v.duration-.5)<.02; }),true);
    await page.locator('[data-preview-controls] [data-player-fullscreen]').click();
    await page.waitForFunction(() => document.fullscreenElement?.hasAttribute('data-preview-player'));
    assert.equal(await page.locator('[data-compare-dialog]').isVisible(),false);
    await page.evaluate(() => document.exitFullscreen());
    await page.locator('[data-action=play-preview]').dblclick();
    await page.waitForFunction(() => document.querySelector('[data-compare-source] video').readyState >= 2);
    await page.locator('[data-compare-controls] [data-player-toggle]').click();
    await page.locator('[data-compare-controls] [data-player-seek]').fill('600');
    assert.equal(await page.evaluate(() => Math.abs(document.querySelector('[data-compare-source] video').currentTime-document.querySelector('.compare-depth video').currentTime)<.03),true);
    await mkdir('.codex-tmp/depth-batch-player', {recursive:true});
    await page.screenshot({path:'.codex-tmp/depth-batch-player/compare.png'});
    await page.locator('[data-action=close-compare]').click();
    await page.locator('[data-action=open-output]').click();
    await page.locator('[data-action=export-adjusted]').click();
    const calls = await page.evaluate(() => window.calls);
    assert.equal(calls.find(c => c.name === 'open_output_directory').args.path,'C:/output');
    assert.equal(calls.find(c => c.name === 'apply_parameters').args.request.outputPath,'C:/output/run/adjusted/人物.sample_depth.mp4');
    await page.screenshot({path:'.codex-tmp/depth-batch-player/player.png'});
    assert.deepEqual(errors,[]);
  } finally { await browser.close(); }
});
