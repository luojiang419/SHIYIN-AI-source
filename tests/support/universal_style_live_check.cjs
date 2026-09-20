const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

(async () => {
  const base = process.env.UNIVERSAL_TEST_URL || 'http://127.0.0.1:8900';
  const output = path.resolve(process.env.UNIVERSAL_CASE_DIR || '案例/全能双风格/20260920');
  const browser = await chromium.launch({headless:true, channel:'chrome'});
  const checks = [];
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    await context.request.get(base + '/api/auth/bootstrap?token=universal-style-local-check');
    const page = await context.newPage();
    await page.goto(base + '/static/ecommerce.html');
    const trigger = page.locator('[data-open-generation-style]');
    await trigger.waitFor();
    for (const theme of ['light','dark']) {
      await page.evaluate(t => document.documentElement.classList.toggle('studio-theme-dark',t === 'dark'),theme);
      await trigger.click();
      const dialog = page.locator('.ec-generation-style-dialog');
      assert.equal(await dialog.locator('[data-generation-style]').count(),2);
      await dialog.screenshot({path:path.join(output,`style-dialog-${theme}.png`)});
      await page.keyboard.press('Escape');
      await dialog.waitFor({state:'detached'});
      assert.equal(await dialog.count(),0);
      checks.push(`${theme}: 双选项弹窗、Escape 关闭`);
    }
    for(const style of ['lookbook','standard_product']) {
      await trigger.click();
      await page.locator(`[data-generation-style="${style}"]`).click();
      await page.reload();
      await trigger.waitFor();
      await trigger.click();
      assert.equal(await page.locator(`[data-generation-style="${style}"]`).getAttribute('aria-pressed'),'true');
      await page.keyboard.press('Escape');
      await page.locator('.ec-generation-style-dialog').waitFor({state:'detached'});
      checks.push(`${style}: 选择并刷新持久化`);
    }
    await page.setViewportSize({width:390,height:844});
    await trigger.click();
    const box=await page.locator('.ec-generation-style-dialog').boundingBox();
    assert.ok(box.x>=0 && box.x+box.width<=391 && box.height<=844);
    await page.locator('.ec-generation-style-dialog').screenshot({path:path.join(output,'style-dialog-mobile.png')});
    checks.push('390px: 弹窗无横向溢出');
    fs.writeFileSync(path.join(output,'ui-verification.json'),JSON.stringify({status:'passed',checks},null,2));
    console.log(JSON.stringify({status:'passed',checks}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
