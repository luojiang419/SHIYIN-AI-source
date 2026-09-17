// 配合 canvas_startup_fixture.py；所有操作限于隔离内存画布。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1440,height:960}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${process.argv[2] || 'http://127.0.0.1:3018'}/static/canvas.html?id=output-port-menu-check`);
        await page.waitForSelector('.node[data-id="generator"]');
        await page.evaluate(() => {
            nodes.push({id:'video-media',type:'image',mediaKind:'video',url:'/fixture-video.mp4',name:'a.mp4',x:1700,y:1200});
            render();
        });

        for(const id of ['generator','video','video-media']){
            const port = await page.locator(`.node[data-id="${id}"] .port.out`).boundingBox();
            assert.ok(port,`${id}: output port`);
            await page.mouse.move(port.x + port.width / 2,port.y + port.height / 2);
            await page.mouse.down();
            await page.mouse.move(1200,820,{steps:8});
            await page.mouse.up();
            await page.waitForSelector('#linkCreateMenu.open');
            assert.equal(await page.locator('#linkCreateMenu [data-link-create]').count(),id === 'generator' ? 19 : 5);
            await page.evaluate(() => closeLinkCreateMenu());
        }

        const imageTypes = ['generator','video','lookbook','depthMap','poseReplicate','storyboardMerge','batchGenerator','llm'];
        const videoTypes = ['video-clip','video-frames','depthVideo','video-screenshot','topazVideo'];
        assert.deepEqual(await page.evaluate(() => linkCreateOptions({originId:'generator',originKind:'out'}).map(item => item.type)), imageTypes);
        assert.deepEqual(await page.evaluate(() => linkCreateOptions({originId:'video',originKind:'out'}).map(item => item.type)), videoTypes);
        assert.deepEqual(await page.evaluate(() => linkCreateOptions({originId:'video-media',originKind:'out'}).map(item => item.type)), videoTypes);

        for(const type of imageTypes){
            const before = await page.evaluate(() => ({ids:nodes.map(node => node.id), edges:connections.length}));
            await page.evaluate(() => openLinkCreateMenu('generator','out',600,120));
            await page.locator(`#linkCreateMenu > [data-link-create="${type}"]`).click();
            const result = await page.evaluate(({type,before}) => {
                const created = nodes.find(node => !before.ids.includes(node.id) && node.type === type);
                const link = connections.find(edge => edge.from === 'generator' && edge.to === created?.id);
                return {created:!!created, connected:!!link, valid:link && canConnect(link.from,link.to,link.inputRole || '')};
            }, {type,before});
            assert.deepEqual(result,{created:true,connected:true,valid:true},type);
            await page.evaluate(() => performUndo());
        }

        await page.evaluate(() => openLinkCreateMenu('generator','out',600,120));
        const film = page.locator('#linkCreateMenu [data-link-ad-group]');
        assert.equal(await film.count(),1);
        assert.equal(await film.locator('.menu-submenu-trigger').innerText(),'影视制作');
        await film.locator('.menu-submenu-trigger').click();
        assert.equal(await film.locator('.create-submenu').isVisible(),true);
        await film.locator('[data-link-create="film-storyboard"]').click();
        assert.equal(await page.evaluate(() => connections.some(edge => edge.from === 'generator' && nodes.find(node => node.id === edge.to)?.type === 'film-storyboard' && canConnect(edge.from,edge.to,edge.inputRole || ''))),true);

        for(const source of ['video','video-media']){
            for(const type of ['depthVideo','topazVideo']){
                await page.evaluate(sourceId => openLinkCreateMenu(sourceId,'out',600,120),source);
                await page.locator(`#linkCreateMenu > [data-link-create="${type}"]`).click();
                assert.equal(await page.evaluate(({source,type}) => connections.some(edge => edge.from === source && nodes.find(node => node.id === edge.to)?.type === type && canConnect(edge.from,edge.to,edge.inputRole || '')),{source,type}),true,`${source} -> ${type}`);
                await page.evaluate(() => performUndo());
            }
        }

        const media = await page.evaluate(() => {
            const image = nodes.find(node => node.id === 'generator');
            const video = nodes.find(node => node.id === 'video');
            image.generatedOutputs = [{url:'/fixture.png',kind:'image'}];
            video.generatedOutputs = [{url:'/fixture-video.mp4',kind:'video'}];
            const merge = {id:'test-merge',type:'storyboardMerge'};
            nodes.push(merge);
            connections.push({id:'test-merge-link',from:image.id,to:merge.id});
            const entries = storyboardMergeEntries(merge);
            const source = videoToolSource(video);
            return {mergeUrl:entries[0]?.ref?.url, videoUrl:source?.url};
        });
        assert.deepEqual(media,{mergeUrl:'/fixture.png',videoUrl:'/fixture-video.mp4'});
        for(const source of ['video','video-media']){
            for(const [type,modal] of [['video-clip','videoClipModal'],['video-screenshot','videoClipModal'],['video-frames','videoFrameModal']]){
                await page.evaluate(sourceId => openLinkCreateMenu(sourceId,'out',600,120),source);
                await page.locator(`#linkCreateMenu > [data-link-create="${type}"]`).click();
                assert.equal(await page.locator(`#${modal}`).evaluate(el => el.classList.contains('open')),true,`${source} -> ${type}`);
                await page.evaluate(() => { closeVideoClipEditor(); closeVideoFrameExtractor(); });
            }
        }
        const derived = await page.evaluate(() => {
            const source = videoToolSource(nodes.find(node => node.id === 'video'));
            const clip = addVideoClipNodeFromResult({url:'/fixture-clip.mp4',start:0,end:2,duration:2},source);
            const frameGroup = createVideoFrameGroupFromResult({frames:[{url:'/fixture.png',timestamp:0}]},source);
            sanitizeConnections();
            return [clip,frameGroup].map(node => connections.some(edge => edge.from === source.id && edge.to === node.id && canConnect(edge.from,edge.to,edge.inputRole || '')));
        });
        assert.deepEqual(derived,[true,true]);
        assert.deepEqual(errors,[]);
        console.log(JSON.stringify({passed:true,imageItems:imageTypes.length,videoItems:videoTypes.length}));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
