const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'chrome' });
    try {
        const page = await browser.newPage();
        await page.setContent(`
            <style>${fs.readFileSync('static/css/ecommerce.css', 'utf8')}</style>
            <main class="ec-page is-universal">
                <section class="ec-universal-dock">
                    <div class="ec-universal-dock-inputs"></div>
                    <div class="ec-universal-dock-actions"><section class="ec-generate-actions">
                        <button class="ec-add-reference ec-add-reference-action" type="button"></button>
                        <div class="ec-inline-error">功能参数过大</div>
                        <button class="ec-primary-button" type="button">开始生成</button>
                    </section></div>
                </section>
            </main>
        `);

        for (const viewport of [{ width: 1689, height: 700 }, { width: 1000, height: 700 }, { width: 800, height: 700 }]) {
            await page.setViewportSize(viewport);
            const geometry = await page.evaluate(() => {
                const box = element => {
                    const rect = element.getBoundingClientRect();
                    return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom };
                };
                return {
                    dock: box(document.querySelector('.ec-universal-dock')),
                    error: box(document.querySelector('.ec-inline-error')),
                    generate: box(document.querySelector('.ec-primary-button')),
                };
            });
            for (const name of ['error', 'generate']) {
                const rect = geometry[name];
                const dock = geometry.dock;
                assert.ok(rect.left >= dock.left && rect.right <= dock.right, `${viewport.width}px: ${name} 横向越出素材坞`);
                assert.ok(rect.top >= dock.top && rect.bottom <= dock.bottom, `${viewport.width}px: ${name} 纵向越出素材坞`);
            }
        }
        await page.evaluate(() => document.querySelector('.ec-inline-error').classList.add('hidden'));
        const centered = await page.evaluate(() => {
            const rect = selector => document.querySelector(selector).getBoundingClientRect();
            const add = rect('.ec-add-reference-action');
            const generate = rect('.ec-primary-button');
            return { add, generate };
        });
        assert.ok(Math.abs((centered.add.top + centered.add.bottom) / 2 - (centered.generate.top + centered.generate.bottom) / 2) <= 1, '无错误时生成按钮应与添加按钮垂直居中对齐');
        console.log('ecommerce universal action layout passed');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
