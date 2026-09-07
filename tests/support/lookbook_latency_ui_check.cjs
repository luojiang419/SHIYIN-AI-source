// 与 canvas_startup_fixture.py 配合使用，真实点击控件；所有生成请求均在浏览器内模拟。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async()=>{
    const base=process.argv[2] || 'http://127.0.0.1:3026';
    const out=process.argv[3] || '.codex-artifacts/lookbook-latency-ui';
    fs.mkdirSync(out,{recursive:true});
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    const errors=[], requests=[];
    try{
        const page=await browser.newPage({viewport:{width:1440,height:1080}});
        page.on('pageerror',e=>errors.push(e.message));
        let task={};
        await page.route('**/api/ecommerce/tasks**',async route=>{
            if(route.request().method()==='POST'){
                const payload=route.request().postDataJSON(); requests.push(payload.options);
                const quality=payload.options.lookbook_quality_gate ? {final:{status:'succeeded',passed:false,score:47,summary:'需人工复核',issues:['人物动作需检查']}} : null;
                task={id:'fixture-lookbook',status:'succeeded',options:payload.options,request:payload,lookbook_research:payload.options.lookbook_search?{status:'skipped',reason:'联网研究超过30秒，已继续生成'}:{status:'disabled'},
                    progress_status:quality?'Lookbook 图片已生成；质检未达标，请查看检查结果。':'Lookbook 图片已生成（未启用质检）。',
                    result:{images:[`${base}/fixture.png`],lookbook_quality:quality}};
            }
            await route.fulfill({json:task});
        });
        await page.goto(`${base}/static/canvas.html?id=lookbook-latency-ui-${Date.now()}`);
        await page.waitForSelector('.poseReplicate-node');
        await page.evaluate(()=>{
            nodes.splice(0,nodes.length); connections.splice(0,connections.length);
            nodes.push({...CanvasLookbookNode.createNode({x:0,y:0}),id:'lookbook-latency',apiProvider:'custom',model:'private-image',count:1,lookbookPrompt:'一张时装广告',lookbookGenerationExpanded:true});
            viewport.x=60;viewport.y=60;viewport.scale=1;render();
        });
        const quality=page.locator('[data-lookbook-field="lookbookQualityGate"]');
        const repair=page.locator('[data-lookbook-field="lookbookAutoRepair"]');
        const search=page.locator('[data-lookbook-field="lookbookSearch"]');
        const run=async()=>{
            const before=requests.length;
            await page.locator('[data-lookbook-run]').click();
            await page.waitForFunction(()=>!nodes.find(n=>n.id==='lookbook-latency').running);
            assert.equal(requests.length,before+1);
        };
        assert.equal(await quality.isChecked(),false);
        assert.equal(await repair.isEnabled(),false);
        assert.equal(await search.isChecked(),false);
        await run();
        assert.equal(requests[0].lookbook_quality_gate,false);
        assert.equal(requests[0].lookbook_auto_repair,false);
        assert.equal(requests[0].lookbook_search,false);
        await quality.check(); await repair.check();
        await run();
        assert.equal(requests[1].lookbook_quality_gate,true);
        assert.equal(requests[1].lookbook_auto_repair,true);
        await page.locator('.lookbook-quality-result summary').click();
        assert.match(await page.locator('.lookbook-quality-result').innerText(),/需人工复核/);
        await page.screenshot({path:path.join(out,'quality-result.png')});
        await quality.uncheck();
        assert.equal(await repair.isEnabled(),false);
        await run();
        assert.equal(requests[2].lookbook_auto_repair,false);
        await search.check(); await run();
        assert.equal(requests[3].lookbook_search,true);
        assert.match(await page.locator('.lookbook-node-panel').innerText(),/联网研究超过30秒/);
        await page.evaluate(()=>saveCanvas());
        await page.reload();
        await page.waitForSelector('[data-lookbook-field="lookbookSearch"]');
        assert.equal(await search.isChecked(),true);
        assert.equal(await quality.isChecked(),false);
        assert.equal(await repair.isEnabled(),false);
        await page.screenshot({path:path.join(out,'settings.png')});
        assert.deepEqual(errors,[]);
        fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({requests,errors,persistence:true},null,2));
        console.log(JSON.stringify({requests:requests.length,errors,persistence:true}));
    }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
