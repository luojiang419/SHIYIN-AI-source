const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'msedge'});
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(e.message));
        await page.route('http://depth.test/**', route => route.fulfill({contentType:'text/html', body:'<main id="node"></main>'}));
        await page.goto('http://depth.test/');
        await page.evaluate(() => {
            window.requests = [];
            window.mode = 'recover';
            window.fetch = async url => {
                if(!url.includes('/video-depth/tasks/')) return new Response('{}', {headers:{'Content-Type':'application/json'}});
                window.requests.push(url);
                if(window.mode === 'retry' && window.requests.length === 1) throw new TypeError('network disconnected');
                if(window.mode === 'stale') await new Promise(resolve => window.finishStale = resolve);
                if(window.mode === 'missing') return new Response('{"detail":"任务不存在"}', {status:404});
                return new Response(JSON.stringify({status:'done', outputUrl:'/assets/output/depth.mp4', width:320, height:180}));
            };
        });
        await page.addScriptTag({path:path.resolve(__dirname, '../../static/js/canvas-special-nodes.js')});
        const setup = async (mode, status) => page.evaluate(({mode,status}) => {
            window.mode = mode; window.requests = [];
            const input = {url:'/assets/input/input.mp4',name:'input.mp4',kind:'video'};
            window.node = {type:'depthVideo', depthVideoManualInput:input,
                depthVideoInputSignature:CanvasSpecialNodes.sourceSignature(input),
                depthVideoTaskId:mode, depthVideoStatus:status, depthVideoError:'旧错误'};
            window.options = {onChange(){ document.getElementById('node').innerHTML = CanvasSpecialNodes.depthVideoBodyHtml(node, options); }};
            CanvasSpecialNodes.bindDepthVideo(document.getElementById('node'),node,options);
        }, {mode,status});

        await setup('recover','failed');
        await page.waitForFunction(() => node.outputUrl);
        assert.equal(await page.evaluate(() => node.depthVideoError), '');
        assert.equal(await page.locator('[data-depth-video-media="output"]').getAttribute('src'), '/assets/output/depth.mp4');
        // Saved nodes still render their result after reopening.
        await page.evaluate(() => {
            window.node = JSON.parse(JSON.stringify(node));
            CanvasSpecialNodes.bindDepthVideo(document.getElementById('node'),node,options);
        });
        assert.equal(await page.evaluate(() => requests.length), 1);

        await setup('retry','running');
        await page.waitForFunction(() => node.outputUrl);
        assert.equal(await page.evaluate(() => requests.length), 2);

        await setup('stale','running');
        await page.waitForFunction(() => typeof finishStale === 'function');
        await page.evaluate(() => { node.depthVideoTaskId = 'replacement'; finishStale(); });
        await page.waitForTimeout(100);
        assert.equal(await page.evaluate(() => node.outputUrl), undefined);

        await setup('missing','failed');
        await page.waitForFunction(() => node.depthVideoError === '任务不存在');
        await page.evaluate(() => {
            for(let i=0;i<5;i++) CanvasSpecialNodes.bindDepthVideo(document.getElementById('node'),node,options);
        });
        assert.equal(await page.evaluate(() => requests.length), 1);
        assert.deepEqual(errors, []);
        console.log(JSON.stringify({recovery:true,savedResult:true,networkRetry:true,staleResponseIgnored:true,noRecoveryLoop:true,pageErrors:errors}));
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
