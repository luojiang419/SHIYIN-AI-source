// Run against canvas_startup_fixture.py; no real Kling task is submitted.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');

(async () => {
    const base = process.argv[2] || 'http://127.0.0.1:3127';
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${base}/static/canvas.html?id=kling-routing-${Date.now()}`);
        await page.waitForSelector('.video-provider');
        const result = await page.evaluate(async () => {
            const node = nodes.find(item => item.id === 'video');
            apiProviders.push({id:'kling-cli', name:'可灵 CLI', enabled:true, video_models:['kling-video-v3_0-omni']});
            klingCliState = {...klingCliState, loaded:true, authenticated:true, generationEnabled:true,
                capabilities:{text_to_video:[{model:'kling-video-v3_0-omni',arguments:[]}], image_to_video:[{model:'kling-video-v3_0-omni',arguments:[]}]}};
            node.apiProvider = 'kling-cli';
            node.model = 'kling-video-v3_0-omni';
            render();
            const noVideo = {
                bridge:shouldUseKlingWebBridge(node),
                cliPanel:!!document.querySelector(`.node[data-id="video"] .kling-connection-panel`),
                webButton:!!document.querySelector(`.node[data-id="video"] [data-kling-web-fill]`)
            };
            const originalBridge = fillKlingWebDraft;
            const originalEnsure = ensureKlingGenerationAvailable;
            const calls = [];
            fillKlingWebDraft = async id => { calls.push(`bridge:${id}`); };
            ensureKlingGenerationAvailable = async () => { calls.push('cli'); return false; };
            await runVideoNode(node.id);
            const cliCalls = [...calls];
            const videoSource = {id:'routing-video',type:'image',url:'/fixture-video.mp4',name:'reference.mp4',x:0,y:0};
            nodes.push(videoSource);
            connections.push({id:'routing-link',from:videoSource.id,to:node.id});
            render();
            const withVideo = {
                bridge:shouldUseKlingWebBridge(node),
                webButton:!!document.querySelector(`.node[data-id="video"] [data-kling-web-fill]`),
                cliPanel:!!document.querySelector(`.node[data-id="video"] .kling-connection-panel`)
            };
            await runVideoNode(node.id);
            const bridgeCalls = [...calls];
            node.apiProvider = 'custom';
            const otherProviderBridge = shouldUseKlingWebBridge(node);
            node.apiProvider = 'kling-cli';
            node.type = 'film-video';
            const filmBridge = shouldUseKlingWebBridge(node);
            await runFilmNode(node.id);
            const filmCalls = [...calls];
            connections = connections.filter(item => item.id !== 'routing-link');
            const disconnectedBridge = shouldUseKlingWebBridge(node);
            fillKlingWebDraft = originalBridge;
            ensureKlingGenerationAvailable = originalEnsure;
            return {noVideo,cliCalls,withVideo,bridgeCalls,otherProviderBridge,filmBridge,filmCalls,disconnectedBridge};
        });
        assert.deepEqual(result.noVideo,{bridge:false,cliPanel:true,webButton:false});
        assert.deepEqual(result.cliCalls,['cli']);
        assert.deepEqual(result.withVideo,{bridge:true,webButton:true,cliPanel:false});
        assert.deepEqual(result.bridgeCalls,['cli','bridge:video']);
        assert.equal(result.otherProviderBridge,false);
        assert.equal(result.filmBridge,true);
        assert.deepEqual(result.filmCalls,['cli','bridge:video','bridge:video']);
        assert.equal(result.disconnectedBridge,false);
        assert.deepEqual(errors,[]);
        console.log('Kling CLI / browser bridge routing passed');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
