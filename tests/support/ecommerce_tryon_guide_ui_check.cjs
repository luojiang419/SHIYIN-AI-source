const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1500,height:900}});
        await page.addInitScript(() => localStorage.setItem('studio_theme','dark'));
        const calls = [];
        await page.route('**/api/**', async route => {
            const url = new URL(route.request().url());
            const path = url.pathname;
            const request = route.request();
            if(path === '/api/ecommerce/capabilities') return route.fulfill({json:{models:[{provider_id:'demo',model:'demo-image'}],providers:[{id:'demo',name:'Demo'}],routes:{standard:{provider_id:'demo',model:'demo-image'}},vision_analysis:{enabled:true},reference_slot_types:[]}});
            if(path === '/api/ai/upload') return route.fulfill({json:{files:[{url:'/static/images/logo.png',kind:'image',width:512,height:512,name:'reference.png'}]}});
            if(path === '/api/ecommerce/analyze') { calls.push({path, body:request.postDataJSON()}); return route.fulfill({json:{status:'succeeded',message:'视觉分析完成',prompt_preview:'人物身份锁定；保留上装材质和颜色；完成真实试穿。',analysis:{status:'succeeded',category:'upper'},reference_plan:{ordered_reference_ids:['source','upper_garment']}}}); }
            if(path === '/api/ecommerce/tasks' && request.method() === 'POST') { calls.push({path, body:request.postDataJSON()}); return route.fulfill({json:{id:'guide-demo',task_id:'guide-demo',operation:'universal',status:'queued',result:null}}); }
            if(path === '/api/ecommerce/tasks/guide-demo') return route.fulfill({json:{id:'guide-demo',task_id:'guide-demo',operation:'universal',status:'succeeded',result:{images:['/static/images/logo.png']}}});
            if(path === '/api/ecommerce/tasks') return route.fulfill({json:{tasks:[]}});
            return route.fulfill({json:{}});
        });
        await page.goto('http://127.0.0.1:8765/static/ecommerce.html');
        await page.locator('[data-operation="try_on"]').click();
        await page.locator('.ec-tryon-stepbar [data-tryon-step="0"]').waitFor();
        assert.equal(await page.locator('.ec-tryon-slot-card.is-model').count(),1);
        assert.equal(await page.locator('.ec-tryon-slot-card.is-outfit').count(),0);
        await page.locator('[data-tryon-step-next]').click();
        assert.equal(await page.locator('.ec-tryon-stepbar [data-tryon-step="0"].active').count(),1);
        const image = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lXcAAAAASUVORK5CYII=','base64');
        await page.locator('.ec-tryon-slot-card.is-model .ec-upload-slot').click();
        await page.locator('#fileInput').setInputFiles({name:'model.png',mimeType:'image/png',buffer:image});
        await page.locator('.ec-tryon-slot-card.is-model img').waitFor();
        await page.locator('[data-tryon-step-next]').click();
        assert.equal(await page.locator('.ec-tryon-slot-card.is-model').count(),0);
        await page.locator('.ec-tryon-slot-card.is-outfit .ec-upload-slot').first().click();
        await page.locator('#fileInput').setInputFiles({name:'top.png',mimeType:'image/png',buffer:image});
        await page.locator('.ec-tryon-slot-card.is-outfit img').first().waitFor();
        await page.locator('[data-tryon-step-next]').click();
        assert.equal(await page.locator('.ec-tryon-slot-card.is-fabric-detail').count(),1);
        await page.locator('[data-tryon-step-next]').click();
        await page.locator('[data-tryon-plan-prompt]').click();
        await page.locator('[data-tryon-plan-result]').getByText('人物身份锁定；保留上装材质和颜色；完成真实试穿。').waitFor();
        await page.locator('[data-generate-tryon-guide]').click();
        await page.locator('[data-export-tryon-guide]').waitFor({timeout:10000});
        const guideCall = calls.find(item => item.path === '/api/ecommerce/tasks');
        assert.equal(guideCall.body.operation,'universal');
        assert.equal(guideCall.body.options.prompt_policy,'free');
        assert.equal(guideCall.body.inputs[0].role,'model_identity');
        assert.ok(calls.some(item => item.path === '/api/ecommerce/analyze'));
        await page.locator('[data-tryon-guide-format]').selectOption('jpeg');
        const downloadPromise = page.waitForEvent('download');
        await page.locator('[data-export-tryon-guide]').click();
        assert.match((await downloadPromise).suggestedFilename(),/\.jpg$/);
        await page.waitForTimeout(3500);
        await page.screenshot({path:'.codex-tmp/ecommerce-tryon-guide-demo.png',fullPage:true});
        await page.setViewportSize({width:520,height:900});
        await page.locator('.ec-tryon-stepbar [data-tryon-step="1"]').click();
        const columns = await page.locator('.ec-tryon-closet-grid').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length);
        assert.equal(columns,1,'窄屏服饰步骤应为单列');
        console.log('ecommerce guided try-on and outfit guide passed');
    } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
