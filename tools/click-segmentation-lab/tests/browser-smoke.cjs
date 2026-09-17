const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
  await page.goto('http://127.0.0.1:8791', { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(__dirname, 'desktop-smoke.png'), fullPage: true });
  const metrics = await page.evaluate(() => ({
    title: document.title,
    bodyWidth: document.body.scrollWidth,
    viewportWidth: innerWidth,
    bodyHeight: document.body.scrollHeight,
    viewportHeight: innerHeight,
    heading: document.querySelector('h1')?.textContent,
  }));
  if (metrics.bodyWidth > metrics.viewportWidth || metrics.bodyHeight > metrics.viewportHeight) {
    throw new Error(`页面溢出: ${JSON.stringify(metrics)}`);
  }
  if (process.env.SEGMENT_TEST_IMAGE) {
    await page.locator('#fileInput').setInputFiles(process.env.SEGMENT_TEST_IMAGE);
    await page.locator('#maskCanvas').waitFor({ state: 'visible' });
    await page.locator('#busy').waitFor({ state: 'hidden', timeout: 60_000 });
    const canvas = await page.locator('#maskCanvas').boundingBox();
    await page.mouse.click(canvas.x + canvas.width / 2, canvas.y + canvas.height / 2);
    await page.locator('#busy').waitFor({ state: 'visible', timeout: 10_000 });
    await page.locator('#busy').waitFor({ state: 'hidden', timeout: 900_000 });
    await page.screenshot({ path: path.join(__dirname, 'segmented-smoke.png'), fullPage: true });
    const selected = await page.evaluate(() => ({
      points: document.querySelectorAll('#maskCanvas').length,
      exportEnabled: !document.querySelector('#cutoutExportButton').disabled,
      outputSize: document.querySelector('#outputSize').textContent,
    }));
    if (!selected.exportEnabled) throw new Error(`分割后导出未启用: ${JSON.stringify(selected)}`);
    console.log(JSON.stringify(selected));
  }
  console.log(JSON.stringify(metrics));
  await browser.close();
})();
