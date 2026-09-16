const { chromium } = require('playwright');
const assert = require('node:assert/strict');

const base = process.argv[2] || 'http://127.0.0.1:13150';
const types = [
    'image', 'prompt', 'loop', 'group', 'promptGroup', 'llm',
    'generator', 'batchGenerator', 'video', 'linkfox-video', 'rh', 'lookbook',
    'ecom-model', 'ecom-product', 'ecom-scene', 'ecom-compose', 'ecom-video',
    'film-storyboard', 'film-line-art', 'film-video', 'dwpose', 'depthMap',
    'depthVideo', 'director3d', 'poseReplicate', 'multiView', 'resultCompare',
    'output', 'storyboardMerge', 'panorama', 'topazVideo',
];

(async () => {
    const browser = await chromium.launch({ headless: true, channel: 'msedge' });
    try {
        const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${base}/static/canvas.html?id=all-node-upstream`);
        await page.waitForFunction(() => canvas?.id && !window.canvasEntryOverlay);
        assert.equal(await page.evaluate(()=>!!window.CanvasEngine?.active),true);
        await page.evaluate(nodeTypes => {
            nodes = nodeTypes.map((type, index) => ({
                id: `migration-${index}`, type,
                x: (index % 5) * 620,
                y: Math.floor(index / 5) * 850,
                w: 500,
                h: 500,
            }));
            connections = [];
            render();
        }, types);

        const results = [];
        for (let row = 0; row < Math.ceil(types.length / 5); row++) {
            await page.evaluate(index => {
                viewport.x = 40;
                viewport.y = 40 - index * 850 * viewport.scale;
                applyViewport();
            }, row);
            for (let index = row * 5; index < Math.min(types.length, (row + 1) * 5); index++) {
                const id = `migration-${index}`;
                await page.waitForFunction(nodeId => !!document.querySelector(`.node[data-id="${CSS.escape(nodeId)}"]`), id);
                const item = await page.locator(`.node[data-id="${id}"]`).evaluate(element => ({
                    title: element.querySelector('.node-title')?.textContent?.trim() || '',
                    body: !!element.querySelector('.node-body'),
                    ports: element.querySelectorAll('.port').length,
                    width: element.getBoundingClientRect().width,
                    height: element.getBoundingClientRect().height,
                }));
                assert(item.title && item.body && item.width > 0 && item.height > 0, `${types[index]} rendered incompletely`);
                results.push({ type: types[index], ...item });
            }
        }
        assert.deepEqual(errors, []);
        assert.equal(results.length, types.length);
        console.log(JSON.stringify({ count: results.length, errors, results }));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
