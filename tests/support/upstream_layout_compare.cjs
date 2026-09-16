const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');

const base = process.argv[2] || 'http://127.0.0.1:13150';
const targets = ['#board', '#quickToolbar', '.minimap', '#world', '.prompt-node[data-id="prompt"]'];

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'msedge' });
    const report = [];
    try {
        for (const viewport of [{ width: 1440, height: 1000 }, { width: 720, height: 920 }, { width: 390, height: 844 }]) {
            const modes = {};
            for (const mode of ['legacy', 'upstream']) {
                const page = await browser.newPage({ viewport });
                const errors = [];
                page.on('pageerror', error => errors.push(error.message));
                await page.goto(`${base}/static/canvas.html?id=layout-${viewport.width}${mode === 'legacy' ? '&canvasEngine=legacy' : ''}`);
                await page.waitForFunction(() => canvas?.id && !window.canvasEntryOverlay);
                const rects = await page.evaluate(selectors => {
                    const result = {};
                    selectors.forEach(selector => {
                        const element = document.querySelector(selector);
                        if (!element) return;
                        const rect = element.getBoundingClientRect();
                        result[selector] = { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
                    });
                    return result;
                }, targets);
                assert.deepEqual(errors, []);
                await page.screenshot({ path: path.join(os.tmpdir(), `canvas-layout-${viewport.width}-${mode}.png`) });
                modes[mode] = { rects, errors };
                await page.close();
            }
            for (const selector of targets) {
                const left = modes.legacy.rects[selector];
                const right = modes.upstream.rects[selector];
                assert(left && right, `${selector} missing on ${viewport.width}px viewport`);
                for (const key of ['x', 'y', 'width', 'height']) {
                    assert(Math.abs(left[key] - right[key]) <= 1, `${selector} ${key} shifted at ${viewport.width}px: ${left[key]} -> ${right[key]}`);
                }
            }
            report.push({ viewport, modes });
        }
        console.log(JSON.stringify(report));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
