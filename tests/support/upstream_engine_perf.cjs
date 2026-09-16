const { chromium } = require('playwright');
const assert = require('node:assert/strict');

const base = process.argv[2] || 'http://127.0.0.1:13150';

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'msedge' });
    const report = [];
    try {
        for (const mode of ['legacy', 'upstream']) {
            const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            await page.goto(`${base}/static/canvas.html?id=perf-${mode}&canvasPerf=1${mode === 'legacy' ? '&canvasEngine=legacy' : ''}`);
            await page.waitForFunction(() => canvas?.id && !window.canvasEntryOverlay);
            assert.equal(await page.evaluate(()=>!!window.CanvasEngine?.active),mode === 'upstream');
            const result = await page.evaluate(async () => {
                CanvasPerformance.clear();
                const started = performance.now();
                const cleanup = CanvasPerformance.installFixture('classic', { nodes: 1000, connections: 2000 });
                await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                const paintMs = performance.now() - started;
                const mounted = document.querySelectorAll('#nodes .node').length;
                const links = document.querySelectorAll('#links .link-hit').length;
                const stats = CanvasPerformance.snapshot();
                cleanup();
                return { paintMs, mounted, links, metrics: stats.metrics, longTasks: stats.longTasks.map(item => item.duration) };
            });
            assert.deepEqual(errors, []);
            assert.equal(result.links, 2000);
            if (mode === 'legacy') assert.equal(result.mounted, 1000);
            else assert(result.mounted < 250);
            report.push({ mode, ...result, errors });
            await page.close();
        }
        console.log(JSON.stringify(report));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
