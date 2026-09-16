const { chromium } = require('playwright');
const assert = require('node:assert/strict');

const base = process.argv[2] || 'http://127.0.0.1:13150';
const imageUrl = '/static/assets/camera-reference/angle-eye-front.png';

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'msedge' });
    try {
        const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/api/canvases/legacy-smart-migration', route => {
            if (route.request().method() !== 'GET') return route.continue();
            return route.fulfill({ json: { canvas: {
                id: 'legacy-smart-migration', title: '历史智能工程', kind: 'smart', project: 'default',
                updated_at: 1, viewport: { x: 40, y: 40, scale: 0.7 }, connections: [],
                nodes: [
                    { id: 'old-image', type: 'smart-image', x: 20, y: 20, images: [{ url: imageUrl, name: 'front.png', kind: 'image' }] },
                    { id: 'old-prompt', type: 'smart-prompt', x: 390, y: 20, text: '历史提示词' },
                    { id: 'old-loop', type: 'smart-loop', x: 780, y: 20, count: 4, showPrompt: true },
                ],
            } } });
        });
        await page.goto(`${base}/static/canvas.html?id=legacy-smart-migration`);
        await page.waitForFunction(() => canvas?.id && !window.canvasEntryOverlay);
        assert.equal(await page.evaluate(() => !!window.CanvasEngine?.active), true);
        const state = await page.evaluate(() => ({
            types: nodes.map(node => node.type),
            prompt: nodes.find(node => node.id === 'old-prompt')?.text,
            image: nodes.find(node => node.id === 'old-image')?.url,
            mounted: ['old-image', 'old-prompt', 'old-loop'].every(id => !!document.querySelector(`.node[data-id="${CSS.escape(id)}"]`)),
        }));
        assert.deepEqual(state.types, ['image', 'prompt', 'loop']);
        assert.equal(state.prompt, '历史提示词');
        assert.equal(state.image, imageUrl);
        assert.equal(state.mounted, true);
        assert.deepEqual(errors, []);
        console.log(JSON.stringify({ state, errors }));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
