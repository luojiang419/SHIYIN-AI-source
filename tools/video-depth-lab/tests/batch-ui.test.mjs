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
    assert.equal(calls.find(c => c.name === 'apply_parameters').args.request.parameters.midtone,12);
    assert.equal(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight),true);
    await page.reload();
    assert.equal(await page.locator('.job.done').count(),1);
    assert.deepEqual(errors,[]);
  } finally { await browser.close(); }
});
