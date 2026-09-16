const { chromium } = require('playwright');
const assert = require('node:assert/strict');

const base = process.argv[2] || 'http://127.0.0.1:13158';

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'msedge' });
    try {
        const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.addInitScript(() => {
            window.__canvasEntryOverlays = [];
            new MutationObserver(records => {
                for (const record of records) {
                    for (const node of record.addedNodes) {
                        if (!(node instanceof Element)) continue;
                        if (node.matches('.canvas-entry-progress') || node.querySelector('.canvas-entry-progress')) {
                            window.__canvasEntryOverlays.push(performance.now());
                        }
                    }
                }
            }).observe(document, { childList: true, subtree: true });
        });

        await page.route('**/api/projects', async route => {
            const path = new URL(route.request().url()).pathname;
            if (path !== '/api/projects') return route.continue();
            return route.fulfill({ json: { projects: [{ id: 'default', name: '默认项目', order: 0, canvas_count: 1 }] } });
        });
        await page.route('**/api/canvases', async route => {
            const path = new URL(route.request().url()).pathname;
            if (path !== '/api/canvases') return route.continue();
            return route.fulfill({ json: { canvases: [{ id: 'instant-entry', title: '极速进入测试', project: 'default', node_count: 10, updated_at: 1 }] } });
        });
        await page.goto(`${base}/static/canvas-list.html`);
        await page.waitForSelector('.ws-card[data-canvas-id="instant-entry"]');
        await page.waitForFunction(() => !window.canvasListEntryOverlay);
        await page.evaluate(() => { window.__canvasEntryOverlays = []; });
        const clickedAt = Date.now();
        await page.locator('.ws-card[data-canvas-id="instant-entry"]').click();
        const editor = await page.waitForSelector('iframe.active');
        const frame = await editor.contentFrame();
        await frame.waitForFunction(() => typeof canvas !== 'undefined' && canvas?.id === 'instant-entry' && !document.getElementById('shell').inert);
        await frame.waitForSelector('#nodes .node');
        const result = await frame.evaluate(() => {
            const snapshot = CanvasPerformance.snapshot();
            return {
                engine: Boolean(window.CanvasEngine?.active),
                overlayInsertions: window.__canvasEntryOverlays.length,
                mountedNodes: document.querySelectorAll('#nodes .node').length,
                metrics: Object.keys(snapshot.metrics),
            };
        });
        result.hostOverlayInsertions = await page.evaluate(() => window.__canvasEntryOverlays.length);
        result.clickToInteractiveMs = Date.now() - clickedAt;

        assert.equal(result.engine, true);
        assert.equal(result.overlayInsertions, 0);
        assert.equal(result.hostOverlayInsertions, 0);
        assert.ok(result.mountedNodes > 0);
        assert.ok(result.metrics.includes('classic.entry-structure-ready'), JSON.stringify(result));
        assert.equal(result.metrics.includes('classic.entry-media-wait'), false);
        assert.deepEqual(errors, []);
        console.log(JSON.stringify(result));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
