// 对隔离的真实后端验证上传、保存、重新登录恢复；不发起付费生成。
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');

(async()=>{
    const base=process.argv[2]||'http://127.0.0.1:3042';
    const output=process.argv[3]||'.codex-artifacts/lookbook-styles-ui';
    fs.mkdirSync(output,{recursive:true});
    let browser;
    const open=async()=>{
        browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'msedge'});
        const page=await browser.newPage({viewport:{width:1280,height:1000}});
        await page.goto(`${base}/api/auth/bootstrap?token=lookbook-style-ui-120`);
        const created=await page.request.post(`${base}/api/canvases`,{data:{title:'Lookbook 风格回归',kind:'classic'}});
        assert.equal(created.ok(),true);
        const canvas=(await created.json()).canvas;
        await page.goto(`${base}/static/canvas.html?id=${canvas.id}`);
        await page.waitForFunction(()=>window.CanvasLookbookNode&&typeof render==='function');
        await page.evaluate(()=>{
            nodes.splice(0,nodes.length);connections.splice(0,connections.length);
            nodes.push({...CanvasLookbookNode.createNode({x:0,y:0}),id:'lookbook-style-ui-node'});
            viewport.x=60;viewport.y=60;viewport.scale=1;render();
        });
        await page.locator('[data-lookbook-choose]').click();
        await page.waitForFunction(()=>document.querySelector('[data-lookbook-status]')?.textContent.includes('封面自动保存'));
        return page;
    };
    try{
        let page=await open();
        assert.equal(await page.locator('.lookbook-style-card').count(),6);
        await page.waitForFunction(()=>[...document.querySelectorAll('.lookbook-card-cover img')].every(img=>img.complete&&img.naturalWidth>0));
        await page.screenshot({path:path.join(output,'six-style-covers.png'),fullPage:true});
        const input=page.locator('[data-lookbook-cover="fw-cream-cyan-film"]');
        await input.setInputFiles(path.resolve('static/img/lookbook-covers/fashion-advertising.webp'));
        await page.waitForFunction(()=>document.querySelector('[data-lookbook-status]')?.textContent==='封面已自动保存');
        const card=page.locator('.lookbook-style-card').filter({has:page.locator('[data-lookbook-cover="fw-cream-cyan-film"]')});
        const savedCover=await card.locator('img').getAttribute('src');
        assert.match(savedCover,/^\/assets\//);
        await page.locator('[data-lookbook-select="fw-cream-cyan-film"]').click();
        assert.equal(await page.locator('.lookbook-style-cover img').getAttribute('src'),savedCover);
        // 完整关闭 Chromium，新进程重新登录，localStorage 为空。
        await browser.close();
        page=await open();
        const restored=page.locator('.lookbook-style-card').filter({has:page.locator('[data-lookbook-cover="fw-cream-cyan-film"]')});
        assert.equal(await restored.locator('img').getAttribute('src'),savedCover);
        // 服务端拒绝保存时，页面必须保留旧封面并显示错误。
        await page.route('**/api/lookbook/styles',async route=>{
            if(route.request().method()==='PUT')await route.fulfill({status:500,json:{detail:'测试：磁盘空间不足'}});
            else await route.continue();
        });
        await page.locator('[data-lookbook-cover="fw-cream-cyan-film"]').setInputFiles(path.resolve('static/img/lookbook-covers/standard-advertising.webp'));
        await page.waitForFunction(()=>document.querySelector('[data-lookbook-status]')?.textContent.includes('磁盘空间不足'));
        assert.equal(await restored.locator('img').getAttribute('src'),savedCover);
        await page.unroute('**/api/lookbook/styles');
        await page.locator('[data-lookbook-select="fashion-advertising"]').click();
        const selected=await page.evaluate(()=>nodes.find(n=>n.id==='lookbook-style-ui-node'));
        assert.equal(selected.lookbookStyleName,'时尚广告');
        assert.match(selected.lookbookStylePrompt,/REFERENCE ROUTER/);
        assert.equal(selected.count,4);
        assert.equal(selected.aspectRatio,'16:9');
        await page.screenshot({path:path.join(output,'fashion-selected.png'),fullPage:true});
        fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({passed:true,styles:6,uploadSaved:true,emptyBrowserCacheRestored:true,failedSavePreservedCover:true,fashionSkillSelected:true,savedCover},null,2));
        console.log('PASS: six covers, upload persistence, fresh browser restore, failure preservation, fashion skill selection');
    }finally{await browser?.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
