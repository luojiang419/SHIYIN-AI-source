// 使用 canvas_startup_fixture.py 隔离服务，不调用生成 API。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1280,height:900}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${process.argv[2] || 'http://127.0.0.1:3018'}/static/canvas.html?id=ad-menu-check`);
        await page.waitForSelector('.image-node[data-id="image"]');
        await page.evaluate(() => { selected.clear(); openCreateMenu(700,150); });
        await page.locator('#createMenu button[onclick="menuAdd(\'batchGenerator\')"]').click();
        assert.equal(await page.evaluate(() => nodes.filter(n => n.type === 'batchGenerator').length), 1);

        // 真实拖动图片输出端口到空白。
        const port = await page.locator('.image-node[data-id="image"] .port.out').boundingBox();
        await page.mouse.move(port.x+port.width/2,port.y+port.height/2);
        await page.mouse.down();
        await page.mouse.move(1100,780,{steps:8});
        await page.mouse.up();
        await page.waitForSelector('#linkCreateMenu.open');
        assert.equal(await page.locator('#linkCreateMenu [data-link-ad-group]').count(),1);
        const menu = await page.locator('#linkCreateMenu').boundingBox();
        assert.ok(menu.x>=0 && menu.y>=0 && menu.x+menu.width<=1280 && menu.y+menu.height<=900);
        const film = page.locator('#linkCreateMenu [data-link-ad-group]').filter({has:page.locator('button.menu-submenu-trigger', {hasText:'影视制作'})});
        await film.locator('.menu-submenu-trigger').hover();
        let sub = await film.locator('.create-submenu').boundingBox();
        assert.ok(sub.x>=0 && sub.y>=0 && sub.x+sub.width<=1280 && sub.y+sub.height<=900);
        assert.equal(await film.evaluate(el=>el.classList.contains('submenu-flip')),true);
        if(process.argv[3]) await page.screenshot({path:process.argv[3]});
        await page.locator('#linkCreateMenu > [data-link-create="lookbook"]').click();
        assert.equal(await page.locator('#linkCreateMenu').isVisible(),false);
        assert.equal(await page.evaluate(() => connections.some(c=>c.from==='image' && c.inputRole==='lookbook-person' && nodes.find(n=>n.id===c.to)?.type==='lookbook')),true);

        const items = await page.evaluate(() => imageLinkAdvertisingGroups({originId:'image',originKind:'out'})[0].items.map(item=>item.type));
        for(const type of items){
            const before = await page.evaluate(() => ({ids:nodes.map(n=>n.id),edges:connections.length,history:undoStack.length}));
            await page.evaluate(() => openLinkCreateMenu('image','out',640,100));
            const group = page.locator('#linkCreateMenu [data-link-ad-group]').last();
            await group.locator('.menu-submenu-trigger').click();
            await group.locator(`[data-link-create="${type}"]`).click();
            const result = await page.evaluate(({before,type}) => {
                const added = nodes.filter(n=>!before.ids.includes(n.id));
                const target = added.find(n=>n.type===(type==='film-workflow'?'film-storyboard':type));
                const edge = connections.find(c=>c.from==='image' && c.to===target?.id);
                return {count:added.length,connected:!!edge,valid:edge && canConnect(edge.from,edge.to,edge.inputRole||''),edges:connections.length-before.edges, types:added.map(n=>n.type), incoming:connections.filter(c=>c.to===target?.id)};
            },{before,type});
            assert.ok(result.connected && result.valid,`${type}: valid source image connection ${JSON.stringify(result)}`);
            assert.equal(result.count,type==='film-workflow'?4:1,`${type}: node count`);
            if(type==='film-workflow') assert.equal(result.edges,4);
            assert.equal(await page.evaluate(()=>undoStack.length),before.history+1,`${type}: one undo step`);
            await page.evaluate(()=>performUndo());
            assert.deepEqual(await page.evaluate(()=>({ids:nodes.map(n=>n.id),edges:connections.length})),{ids:before.ids,edges:before.edges});
            await page.evaluate(()=>performRedo());
            assert.equal(await page.evaluate(()=>nodes.length),before.ids.length+result.count);
        }
        // 影视选项只通过二级菜单提供，避免图片菜单重复。
        await page.evaluate(() => openLinkCreateMenu('image','out',640,100));
        for(const type of ['film-storyboard','film-line-art','film-video'])
            assert.equal(await page.locator(`#linkCreateMenu > [data-link-create="${type}"]`).count(),0);
        if(await page.evaluate(() => typeof applyCanvasWorkMode==='function')){
            await page.evaluate(() => { applyCanvasWorkMode('design'); openLinkCreateMenu('image','out',640,100); });
            assert.equal(await page.locator('#linkCreateMenu [data-link-ad-group]').count(),0);
            assert.equal(await page.locator('#linkCreateMenu [data-link-create="film-video"]').count(),0);
            await page.evaluate(() => { closeLinkCreateMenu(); applyCanvasWorkMode('all'); });
        }
        assert.equal(await page.evaluate(() => imageLinkAdvertisingGroups({originId:'prompt',originKind:'out'}).length),0);
        assert.equal(await page.evaluate(() => imageLinkAdvertisingGroups({originId:'image',originKind:'in'}).length),0);
        assert.deepEqual(errors,[]);
        console.log(JSON.stringify({passed:true,filmItems:items.length,checks:['batch context menu','real port drag','submenu flip/clamp','film submenu auto connections','no duplicate film shortcuts','design mode','no browser errors']}));
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode=1; });
