const assert = require('node:assert/strict');
const {chromium} = require('playwright');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage();
        let uploads = 0;
        let submitted = null;
        await page.route('**/api/**', route => {
            const pathname = new URL(route.request().url()).pathname;
            if(pathname === '/api/ecommerce/capabilities') {
                return route.fulfill({json:{models:[{provider_id:'demo',model:'demo-image',max_reference_images:8}],providers:[{id:'demo',name:'Demo'}],routes:{standard:{provider_id:'demo',model:'demo-image'}},vision_analysis:{enabled:false},pose_presets:[{id:'standing_front',name:'正面站立'},{id:'walking',name:'自然行走'}],reference_slot_types:[]}});
            }
            if(pathname === '/api/ai/upload') return route.fulfill({json:{files:[{url:`/static/images/logo.png?background=${++uploads}`,kind:'image',width:512,height:512,name:'background.png'}]}});
            if(pathname === '/api/ecommerce/tasks' && route.request().method() === 'POST') {
                submitted = route.request().postDataJSON();
                return route.fulfill({json:{id:'pose-background-check',task_id:'pose-background-check',operation:'pose_transfer',status:'queued',created_at:Date.now()/1000}});
            }
            if(pathname === '/api/ecommerce/tasks') return route.fulfill({json:{tasks:[]}});
            return route.fulfill({json:{}});
        });
        await page.goto(`${process.env.POSE_TEST_BASE_URL || 'http://127.0.0.1:8877'}/static/ecommerce.html`);
        await page.locator('[data-operation="pose_transfer"]').click();
        await page.locator('[data-option-button="pose_source"][data-value="preset"]').click();
        assert.equal(await page.locator('#posePresetGrid').count(), 1);
        await page.locator('[data-option-button="pose_source"][data-value="reference"]').click();
        assert.equal(await page.locator('#posePresetGrid').count(), 0);
        await page.locator('[data-option-button="pose_source"][data-value="preset"]').click();
        assert.equal(await page.locator('#posePresetGrid').count(), 1);
        assert.equal(await page.locator('.ec-upload-slot[data-role="background"]').count(), 1);
        await page.locator('[data-open-studio-dialog]').click();
        await page.locator('[data-studio-reference="studio_white"]').click();
        assert.equal(await page.locator('[data-studio-reference-card].is-selected').count(), 1);
        const response = page.waitForResponse(item => new URL(item.url()).pathname === '/api/ai/upload');
        await page.locator('.ec-upload-slot[data-role="background"]').evaluate(slot => {
            const transfer = new DataTransfer();
            transfer.items.add(new File([new Uint8Array([137,80,78,71])], 'background.png', {type:'image/png'}));
            slot.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
        });
        assert.equal((await response).status(), 200);
        await page.locator('.ec-upload-slot[data-role="background"] img[src*="background=1"]').waitFor();
        assert.equal(await page.locator('[data-studio-reference-card].is-selected').count(), 0);
        await page.locator('[data-open-studio-dialog]').click();
        await page.locator('[data-studio-reference="studio_white"]').click();
        assert.equal(await page.locator('[data-studio-reference-card].is-selected').count(), 0);
        await page.evaluate(() => document.querySelector('#studioDialog')?.close());
        for(const role of ['source','pose']) {
            const uploaded = page.waitForResponse(item => new URL(item.url()).pathname === '/api/ai/upload');
            await page.locator(`.ec-upload-slot[data-role="${role}"]`).evaluate((slot, name) => {
                const transfer = new DataTransfer();
                transfer.items.add(new File([new Uint8Array([137,80,78,71])], name, {type:'image/png'}));
                slot.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
            }, `${role}.png`);
            assert.equal((await uploaded).status(), 200);
            await page.locator(`.ec-upload-slot[data-role="${role}"] img[src*="background="]`).waitFor();
        }
        await page.locator('[data-option-button="pose_source"][data-value="reference"]').click();
        const submittedRequest = page.waitForRequest(request => new URL(request.url()).pathname === '/api/ecommerce/tasks' && request.method() === 'POST');
        await page.locator('#generateButton').click();
        await submittedRequest;
        assert.ok(submitted, '生成请求应已提交');
        assert.deepEqual(submitted.inputs.map(item => item.role).sort(), ['background','pose','source']);
        assert.equal(submitted.options.studio_reference, '');
        console.log('pose source and background controls passed');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
