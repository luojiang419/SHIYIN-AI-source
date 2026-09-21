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
