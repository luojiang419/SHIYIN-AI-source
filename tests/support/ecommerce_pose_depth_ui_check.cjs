const assert = require('node:assert/strict');
const {chromium} = require('playwright');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage();
        let uploads = 0;
        let estimates = 0;
        let releaseFirstDepth;
        const firstDepthReady = new Promise(resolve => { releaseFirstDepth = resolve; });
        let depthHeadRequests = 0;
        page.on('request', request => {
            if(request.url().includes('depth=') && request.method() === 'HEAD') depthHeadRequests += 1;
        });
        await page.route('**/api/**', route => {
            const path = new URL(route.request().url()).pathname;
            if(path === '/api/ecommerce/capabilities') return route.fulfill({json:{models:[{provider_id:'demo',model:'demo-image',max_reference_images:8}],providers:[{id:'demo',name:'Demo'}],routes:{standard:{provider_id:'demo',model:'demo-image'}},vision_analysis:{enabled:false},pose_presets:[{id:'standing_front',name:'正面站立'}],reference_slot_types:[]}});
            if(path === '/api/ai/upload') return route.fulfill({json:{files:[{url:`/static/images/logo.png?upload=${++uploads}`,kind:'image',width:512,height:512,name:'input.png'}]}});
            if(path === '/api/person-depth/component/status') return route.fulfill({json:{ready:true,model_tier:'quality'}});
            if(path === '/api/ecommerce/pose-depth') {
                const source = route.request().postDataJSON().source_url;
                estimates += 1;
                const estimate = estimates;
                return (estimate === 1 ? firstDepthReady : Promise.resolve()).then(() =>
                    route.fulfill({json:{url:`/static/images/logo.png?depth=${estimate}`,source_url:source,tier:'quality'}}));
            }
            if(path === '/api/ecommerce/tasks' && route.request().method() === 'POST') {
                return route.fulfill({json:{id:'pose-depth-check',task_id:'pose-depth-check',operation:'pose_transfer',status:'queued',created_at:Date.now()/1000}});
            }
            if(path === '/api/ecommerce/tasks') return route.fulfill({json:{tasks:[]}});
            return route.fulfill({json:{}});
        });
        await page.goto(`${process.env.POSE_TEST_BASE_URL || 'http://127.0.0.1:3042'}/static/ecommerce.html`);
        await page.locator('[data-operation="pose_transfer"]').click();
        for(const role of ['source','pose']) {
            await page.locator(`.ec-upload-slot[data-role="${role}"]`).evaluate((slot, name) => {
                const transfer = new DataTransfer();
                transfer.items.add(new File([new Uint8Array([137,80,78,71])], name, {type:'image/png'}));
                slot.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
            }, `${role}.png`);
            await page.locator(`.ec-upload-slot[data-role="${role}"] img[src*="upload="]`).waitFor();
        }
        await page.getByRole('button', {name:'深度图提取中...'}).waitFor();
        assert.equal(await page.locator('#generateButton').isDisabled(), true, '提取完成前不能提交生成');
        releaseFirstDepth();
        await page.locator('.ec-upload-slot[data-role="pose"] .ec-pose-depth-status img').waitFor();
        await page.getByRole('button', {name:'开始生成'}).waitFor();
        assert.equal(await page.locator('#generateButton').isEnabled(), true, '提取完成后按钮应恢复可用');
        assert.equal(estimates, 1, '添加姿势图后应立即提取一次深度图');
        await page.locator('.ec-upload-slot[data-role="pose"]').evaluate(slot => {
            const transfer = new DataTransfer();
            transfer.items.add(new File([new Uint8Array([137,80,78,71])], 'new-pose.png', {type:'image/png'}));
            slot.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
        });
        await page.locator('.ec-upload-slot[data-role="pose"] .ec-pose-depth-status img[src*="depth=2"]').waitFor();
        assert.equal(estimates, 2, '更换姿势图后应重新提取深度图');
        const storedDepth = await page.evaluate(() => JSON.parse(localStorage.getItem('studio_ecommerce_settings_v2')).workspaces.pose_transfer.pose_depth);
        assert.match(storedDepth.url, /depth=2/, '已提取的深度图应写入工作区偏好');
        const submittedRequest = page.waitForRequest(request => new URL(request.url()).pathname === '/api/ecommerce/tasks' && request.method() === 'POST');
        await page.locator('#generateButton').click();
        const request = await submittedRequest;
        const submitted = request.postDataJSON();
        assert.equal(submitted.options.pose_depth.source_url, submitted.inputs.find(item => item.role === 'pose').url);
        assert.match(submitted.options.pose_depth.url, /depth=2/);
        assert.equal(estimates, 2, '提交时应复用当前姿势图已提取的深度图');
        assert.equal(depthHeadRequests, 0, '提交时不应通过不支持的 HEAD 请求误判深度图失效');
        console.log('pose depth immediate extraction and submission passed');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
