const { chromium } = require('playwright');
const assert = require('node:assert/strict');

const base = process.argv[2] || 'http://127.0.0.1:13150';

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'msedge' });
    const report = [];
    try {
        for (const mode of ['legacy', 'upstream']) {
            const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            await page.goto(`${base}/static/canvas.html?id=marquee-${mode}${mode === 'legacy' ? '&canvasEngine=legacy' : ''}`);
            await page.waitForFunction(() => canvas?.id && !window.canvasEntryOverlay);
            await page.evaluate(() => {
                nodes = [
                    { id: 'marquee-a', type: 'prompt', x: 300, y: 300, w: 260, h: 160, text: 'A' },
                    { id: 'marquee-b', type: 'prompt', x: 700, y: 300, w: 260, h: 160, text: 'B' },
                ];
                connections = [];
                viewport = { x: 40, y: 40, scale: 0.5 };
                selected.clear();
                render();
            });
            await page.waitForSelector('.node[data-id="marquee-b"]');
            await page.mouse.move(100, 140);
            await page.mouse.down();
            await page.mouse.move(620, 450, { steps: 12 });
            await page.mouse.up();
            const state = await page.evaluate(() => ({ selected: [...selected].sort(), selectionBox: document.getElementById('selectionBox')?.className }));
            assert.deepEqual(state.selected, ['marquee-a', 'marquee-b']);
            const before = await page.evaluate(() => nodes.map(node => ({ id: node.id, x: node.x, y: node.y })));
            const header = await page.locator('.node[data-id="marquee-a"] .node-head').boundingBox();
            assert(header);
            await page.mouse.move(header.x + 35, header.y + header.height / 2);
            await page.mouse.down();
            await page.mouse.move(header.x + 85, header.y + header.height / 2 + 35, { steps: 8 });
            await page.mouse.up();
            const after = await page.evaluate(() => nodes.map(node => ({ id: node.id, x: node.x, y: node.y })));
            assert(after[0].x > before[0].x + 80 && after[0].y > before[0].y + 50, 'selected node did not move');
            assert.deepEqual(errors, []);
            report.push({ mode, state, before, after, errors });
            await page.close();
        }
        console.log(JSON.stringify(report));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
