const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3022';
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1280,height:900}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${base}/static/canvas.html?id=connection-double-click-check`);
        await page.waitForSelector('.image-node[data-id="image"]');
        await page.evaluate(() => {
            connections.splice(0, connections.length,
                {id:'disconnect-me',from:'prompt',to:'generator'},
                {id:'keep-me',from:'image',to:'generator'}
            );
            markClassicConnectionStructureDirty();
            render();
        });
        await page.waitForSelector('.link-hit[data-connection-id="disconnect-me"]');
        assert.equal(await page.locator('.link-hit[data-connection-id]').count(), 2);

        await page.locator('#board').dispatchEvent('dblclick', {button:0,detail:2,bubbles:true});
        assert.equal(await page.evaluate(() => connections.length), 2, 'double-clicking canvas background must not remove connections');

        await page.locator('.link-hit[data-connection-id="disconnect-me"]').dispatchEvent('dblclick', {button:0,detail:2,bubbles:true});
        await page.waitForFunction(() => connections.length === 1);
        assert.deepEqual(await page.evaluate(() => connections.map(connection => connection.id)), ['keep-me']);

        await page.evaluate(() => performUndo());
        await page.waitForFunction(() => connections.length === 2);
        assert.deepEqual((await page.evaluate(() => connections.map(connection => connection.id))).sort(), ['disconnect-me','keep-me']);
        assert.deepEqual(errors, []);
        console.log('classic canvas connection double-click disconnect and undo passed');
    } finally {
        await browser.close();
    }
})().catch(error=>{console.error(error);process.exitCode=1;});
