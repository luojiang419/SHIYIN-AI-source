const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1500,height:900}});
        await page.addInitScript(() => localStorage.setItem('studio_theme','dark'));
        const calls = [];
        let uploadCount = 0;
        await page.route('**/api/**', async route => {
            const url = new URL(route.request().url());
            const path = url.pathname;
            const request = route.request();
            if(path === '/api/ecommerce/capabilities') return route.fulfill({json:{models:[{provider_id:'demo',model:'demo-image'}],providers:[{id:'demo',name:'Demo'}],routes:{standard:{provider_id:'demo',model:'demo-image'}},vision_analysis:{enabled:true},reference_slot_types:[]}});
            if(path === '/api/ai/upload') return route.fulfill({json:{files:[{url:`/static/images/logo.png?reference=${++uploadCount}`,kind:'image',width:512,height:512,name:'reference.png'}]}});
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
        await page.locator('[data-add-tryon-model]').click();
        await page.locator('#fileInput').setInputFiles([
            {name:'model-two.png',mimeType:'image/png',buffer:image},
            {name:'model-three.png',mimeType:'image/png',buffer:image},
        ]);
        await page.locator('[data-tryon-model-index]').nth(2).waitFor();
        assert.equal(await page.locator('[data-tryon-model-index]').count(),3);
        await page.locator('[data-tryon-model-index="1"]').click();
        assert.equal(await page.locator('[data-tryon-model-index="1"]').getAttribute('aria-pressed'),'true');
        const selectedModelUrl = await page.locator('.ec-tryon-model-select[aria-pressed="true"] img').getAttribute('src');
        const modelLayout = await page.locator('.ec-tryon-closet-grid').evaluate(element => {
            const cards = [...element.querySelectorAll(':scope > .ec-tryon-slot-card.is-model')];
            return {count:cards.length, maxRight:Math.max(...cards.map(card => card.getBoundingClientRect().right)), maxBottom:Math.max(...cards.map(card => card.getBoundingClientRect().bottom)), viewport:innerWidth, height:innerHeight};
        });
        assert.equal(modelLayout.count,4,'三位模特和添加卡片应直接平铺在操作区');
        assert.ok(modelLayout.maxRight <= modelLayout.viewport, '模特卡片应完整显示在工作台内');
        assert.ok(modelLayout.maxBottom <= modelLayout.height, '添加模特卡片应和其他模特在首屏完整显示');
        assert.equal(await page.locator('[data-tryon-step-back]').count(),0);
        const firstArrow = await page.locator('.ec-tryon-materials').evaluate(element => {
            const card = element.querySelector('.ec-tryon-slot-card.is-model:last-child').getBoundingClientRect();
            const arrow = element.querySelector('[data-tryon-step-next]').getBoundingClientRect();
            return {clear:arrow.left >= card.right - 1,round:getComputedStyle(element.querySelector('[data-tryon-step-next]')).borderRadius};
        });
        assert.ok(firstArrow.clear,'右侧箭头不应遮挡添加模特卡');
        assert.equal(firstArrow.round,'50%');
        await page.screenshot({path:'.codex-tmp/ecommerce-tryon-multiple-models.png'});
        await page.locator('[data-tryon-model-remove="2"]').click();
        assert.equal(await page.locator('[data-tryon-model-index]').count(),2);
        assert.equal(await page.locator('[data-tryon-model-index="1"]').getAttribute('aria-pressed'),'true','删除其他模特时应保留当前选择');
        const remainingModelUrl = await page.locator('.ec-tryon-model-select[aria-pressed="true"] img').getAttribute('src');
        await page.locator('[data-tryon-step-next]').click();
        assert.equal(await page.locator('.ec-tryon-slot-card.is-model').count(),0);
        assert.equal(await page.locator('[data-tryon-step-back]').count(),1);
        assert.equal(await page.locator('[data-tryon-step-next]').count(),1);
        await page.locator('[data-tryon-step-back]').click();
        assert.equal(await page.locator('[data-tryon-model-index]').count(),2);
        assert.equal(await page.locator('.ec-tryon-model-select[aria-pressed="true"] img').getAttribute('src'),remainingModelUrl);
        await page.locator('[data-tryon-step-next]').click();
        await page.locator('.ec-tryon-slot-card.is-outfit .ec-upload-slot').first().click();
        await page.locator('#fileInput').setInputFiles({name:'top.png',mimeType:'image/png',buffer:image});
        await page.locator('.ec-tryon-slot-card.is-outfit img').first().waitFor();
        await page.locator('[data-tryon-step-next]').click();
        assert.equal(await page.locator('.ec-tryon-slot-card.is-fabric-detail').count(),1);
        await page.locator('[data-tryon-step-next]').click();
        await page.locator('[data-tryon-plan-prompt]').click();
        assert.equal(await page.locator('[data-tryon-step-next]').count(),0);
        assert.equal(await page.locator('[data-tryon-step-back]').count(),1);
        await page.locator('[data-tryon-plan-result]').getByText('人物身份锁定；保留上装材质和颜色；完成真实试穿。').waitFor();
        const analyzeCall = calls.find(item => item.path === '/api/ecommerce/analyze');
        assert.equal(analyzeCall.body.inputs.filter(item => item.role === 'source').length,1);
        assert.equal(analyzeCall.body.inputs.find(item => item.role === 'source').url,selectedModelUrl);
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
        await page.locator('.ec-tryon-stepbar [data-tryon-step="0"]').click();
        await page.locator('[data-tryon-model-remove="1"]').click();
        assert.equal(await page.locator('[data-tryon-model-index]').count(),1);
        assert.equal(await page.locator('[data-tryon-model-index="0"]').getAttribute('aria-pressed'),'true','删除当前模特后应选中剩余模特');
        await page.setViewportSize({width:520,height:900});
        const narrowCards = await page.locator('.ec-tryon-closet-grid').evaluate(element => [...element.querySelectorAll(':scope > .ec-tryon-slot-card')].every(card => card.getBoundingClientRect().right <= innerWidth));
        assert.ok(narrowCards,'窄屏模特卡片不应超出视口');
        const narrowArrow = await page.locator('.ec-tryon-materials').evaluate(element => ({
            cardBottom:element.querySelector('.ec-tryon-slot-card.is-add-model').getBoundingClientRect().bottom,
            arrowTop:element.querySelector('[data-tryon-step-next]').getBoundingClientRect().top,
        }));
        assert.ok(narrowArrow.arrowTop >= narrowArrow.cardBottom,'窄屏箭头应在卡片下方，避免遮挡上传');
        await page.locator('[data-tryon-step-next]').scrollIntoViewIfNeeded();
        await page.screenshot({path:'.codex-tmp/ecommerce-tryon-model-cards-narrow.png',fullPage:true});
        await page.locator('.ec-tryon-stepbar [data-tryon-step="1"]').click();
        const columns = await page.locator('.ec-tryon-closet-grid').evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length);
        assert.equal(columns,1,'窄屏服饰步骤应为单列');
        console.log('ecommerce guided try-on and outfit guide passed');
    } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
