// 本地报告显示验证；不连接生产应用、不调用 API。
const { chromium } = require('playwright');
const { pathToFileURL } = require('node:url');
const path = require('node:path');
const fs = require('node:fs');
const assert = require('node:assert/strict');

(async () => {
  const report = path.resolve('输出/Lookbook两阶段方案-20260910/Lookbook两阶段故事设计与实测报告.html');
  const output = path.resolve('.codex-artifacts/lookbook-two-stage-report');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, channel: 'msedge' });
  const failures = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.on('pageerror', error => failures.push(error.message));
    await page.goto(pathToFileURL(report).href);
    await page.waitForFunction(() => [...document.images].filter(img => img.getAttribute('src')).every(img => img.complete && img.naturalWidth > 0));
    assert.equal(await page.locator('section').count(), 8);
    assert.equal(await page.locator('.figure img').count(), 2);
    assert.equal(await page.locator('.crop').count(), 4);
    assert.equal(await page.locator('details').count(), 6);
    assert.equal(await page.locator('#case').innerText().then(t => t.includes('未通过；原文冻结不能放大事实错误')), true);
    await page.screenshot({ path: path.join(output, 'desktop-top.png') });
    await page.locator('#demo-replay').click();
    await page.waitForFunction(() => document.getElementById('demo-status').textContent.startsWith('回放完成'));
    assert.match(await page.locator('#demo-brief').inputValue(), /光落在快门之前/);
    await page.locator('#experience').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'desktop-experience.png') });
    await page.locator('.sheet img').click();
    assert.equal(await page.locator('#lightbox').evaluate(el => el.open), true);
    await page.getByRole('button', { name: '关闭图片预览' }).click();
    await page.locator('.sheet').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'desktop-case.png') });
    await page.locator('details').first().locator('summary').click();
    assert.equal(await page.locator('details').first().evaluate(el => el.open), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => scrollTo(0, 0));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: path.join(output, 'mobile-top.png') });
    await page.locator('.sheet').scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'mobile-case.png') });
    assert.deepEqual(failures, []);
    const result = { status: 'passed', desktop: '1440x1000', mobile: '390x844', loadedImages: 2, previewCrops: 4, evidenceDetails: 6, replay: 'passed', lightbox: 'passed', horizontalOverflow: false, pageErrors: failures };
    fs.writeFileSync(path.join(output, 'verification.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
