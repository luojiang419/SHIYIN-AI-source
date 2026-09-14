// 配合 canvas_startup_fixture.py；仅验证本地内存画布，不调用生成 API。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3040';
    const screenshotPath = process.argv[3] || '';
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1440,height:1000}});
        const errors=[];
        page.on('pageerror',error=>errors.push(error.message));
        await page.goto(`${base}/static/canvas.html?id=depth-export-${Date.now()}`);
        await page.waitForSelector('.depthMap-node');
        await page.evaluate(()=>{
            const depth=nodes.find(node=>node.id==='depth');
            depth.outputUrl='/fixture.png?depth=current';
            depth.outputName='depth-current.png';
            depth.outputWidth=1024;
            depth.outputHeight=1024;
            depth.depthMapStatus='done';
            refreshNodes(['depth']);
            viewport.x=80-depth.x*viewport.scale;
            viewport.y=80-depth.y*viewport.scale;
            applyViewport();
        });
        const button=page.locator('.depthMap-node [data-special-action="export-depth-map"]');
        assert.equal(await button.isDisabled(),false);
        await button.click();
        const result=await page.evaluate(()=>{
            const source=nodes.find(node=>node.id==='depth');
            const output=nodes.find(node=>node.id===source.depthMapExportNodeId);
            return {title:output?.title,url:output?.images?.[0]?.url,connected:connections.some(connection=>connection.from===source.id&&connection.to===output?.id)};
        });
        assert.deepEqual(result,{title:'深度图输出',url:'/fixture.png?depth=current',connected:true});
        assert.deepEqual(errors,[]);
        if(screenshotPath) await page.screenshot({path:screenshotPath,fullPage:true});
        console.log('depth map export output node passed');
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
