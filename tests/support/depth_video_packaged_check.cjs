const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
    const input = JSON.parse(fs.readFileSync(0, 'utf8'));
    const browser = await chromium.launch({headless:true, channel:'msedge'});
    try {
        const context = await browser.newContext({viewport:{width:1400,height:900}});
        await context.addCookies(input.cookies.map(c => ({...c,url:input.base})));
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.goto(`${input.base}/static/canvas.html?id=${input.id}`);
        await page.waitForFunction(() => typeof nodes !== 'undefined' && nodes.find(n => n.id === 'recovery-node')?.outputUrl);
        const video = page.locator('[data-id="recovery-node"] [data-depth-video-media="output"]');
        await video.waitFor();
        await page.waitForFunction(() => document.querySelector('[data-id="recovery-node"] [data-depth-video-media="output"]')?.videoWidth > 0);
        const playback = await video.evaluate(async el => { el.muted=true; await el.play(); return {width:el.videoWidth,height:el.videoHeight,paused:el.paused}; });
        assert.equal(playback.width,160);
        assert.equal(playback.paused,false);
        // Wait for the real canvas autosave, then verify a full reload.
        await page.waitForFunction(async ({base,id}) => {
            const r = await fetch(`${base}/api/canvases/${id}`);
            const body = await r.json();
            return body.canvas.nodes.find(n => n.id === 'recovery-node')?.outputUrl;
        }, input);
        await page.reload();
        await page.waitForFunction(() => document.querySelector('[data-id="recovery-node"] [data-depth-video-media="output"]')?.videoWidth > 0);
        await page.screenshot({path:input.screenshot});
        assert.deepEqual(errors,[]);
        console.log(JSON.stringify({playback,autosave:true,reload:true,pageErrors:errors}));
    } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode=1; });
