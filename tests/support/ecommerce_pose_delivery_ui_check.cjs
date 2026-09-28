const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1500,height:900}});
        let uploads = 0;
        let statusCalls = 0;
        let worksCalls = 0;
        const resultUrl = '/static/images/logo.png?result=pose';
        const oldTryOn = {id:'tryon-old',task_id:'tryon-old',operation:'try_on',status:'succeeded',created_at:Date.now()/1000-60,inputs:[],options:{guide_style:'none'},result:{images:['/static/images/logo.png?result=tryon']}};
        await page.route('**/api/**', route => {
            const {pathname} = new URL(route.request().url());
            if(pathname === '/api/ecommerce/capabilities') return route.fulfill({json:{models:[{provider_id:'demo',model:'demo-image',max_reference_images:8}],providers:[{id:'demo',name:'Demo'}],routes:{standard:{provider_id:'demo',model:'demo-image'}},vision_analysis:{enabled:false},reference_slot_types:[]}});
            if(pathname === '/api/ai/upload') return route.fulfill({json:{files:[{url:`/static/images/logo.png?upload=${++uploads}`,kind:'image',width:512,height:512,name:`external-${uploads}.png`}]}});
            if(pathname === '/api/ecommerce/tasks' && route.request().method() === 'POST') return route.fulfill({json:{id:'pose-ui',task_id:'pose-ui',operation:'pose_transfer',status:'queued',created_at:Date.now()/1000}});
            if(pathname === '/api/ecommerce/tasks') return route.fulfill({json:{tasks:[oldTryOn]}});
            if(pathname === '/api/ecommerce/tasks/status') {
                statusCalls += 1;
                return route.fulfill({json:{tasks:[{id:'pose-ui',task_id:'pose-ui',status:'succeeded'}],missing:[]}});
            }
            if(pathname === '/api/ecommerce/tasks/tryon-old') return route.fulfill({json:oldTryOn});
            if(pathname === '/api/ecommerce/tasks/pose-ui') return route.fulfill({json:{id:'pose-ui',task_id:'pose-ui',operation:'pose_transfer',status:'succeeded',created_at:Date.now()/1000,result:{images:[resultUrl],image_items:[{url:resultUrl}],generation_elapsed_seconds:51}}});
            if(pathname === '/api/works') { worksCalls += 1; return route.fulfill({json:{works:[],total:0,next_cursor:''}}); }
            return route.fulfill({json:{}});
        });
        await page.goto(`${process.env.POSE_TEST_BASE_URL || 'http://127.0.0.1:8877'}/static/ecommerce.html`);
        await page.locator('#historyToggle').click();
        await page.locator('[data-open-task="tryon-old"]').click();
        await page.locator('#tryOnFinalPanel img[src*="result=tryon"]').waitFor();
        await page.locator('[data-operation="batch_outfit"]').click();
        assert.equal(await page.locator('#tryOnFinalPanel, #tryOnGuidePanel, #tryOnResultGallery, #tryOnGuideStatus').count(),0,'批量复刻页不得保留自由换衣模块');
        assert.equal(await page.locator('.ec-result-panel.is-showing-final, .ec-result-panel.is-showing-guide').count(),0,'批量复刻页不得保留自由换衣布局状态');
        await page.locator('[data-operation="try_on"]').click();
        await page.locator('#tryOnFinalPanel img[src*="result=tryon"]').waitFor();
        await page.locator('[data-operation="pose_transfer"]').click();
        assert.equal(await page.locator('#tryOnFinalPanel').count(),0,'切换动作迁移后必须清除自由换衣成品面板');
        assert.equal(await page.locator('#tryOnResultGallery').count(),0,'自由换衣作品导航不得串页');
        const drop = async (role, name) => {
            const response = page.waitForResponse(item => new URL(item.url()).pathname === '/api/ai/upload');
            await page.locator(`.ec-upload-slot[data-role="${role}"]`).evaluate((slot, filename) => {
                const transfer = new DataTransfer();
                transfer.items.add(new File([new Uint8Array([137,80,78,71])], filename, {type:'image/png'}));
                slot.dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer:transfer}));
                slot.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
            }, name);
            assert.equal((await response).status(),200);
        };
        await drop('source','first.png');
        await page.locator('.ec-upload-slot[data-role="source"] img[src*="upload=1"]').waitFor();
        await drop('source','replacement.png');
        await page.locator('.ec-upload-slot[data-role="source"] img[src*="upload=2"]').waitFor();
        assert.equal(uploads,2,'已有素材格应被外部文件直接替换');
        await page.locator('#generateButton').click();
        await page.waitForFunction(() => document.querySelector('#afterImage')?.getAttribute('src')?.includes('result=pose'));
        assert.ok(statusCalls > 0);
        assert.equal(await page.locator('#generationOverlay').isVisible(),false,'生成完成后不应继续显示计时');
        assert.ok((await page.locator('#afterImage').getAttribute('src') || '').includes('result=pose'));
        await page.locator('#historyToggle').click();
        await page.locator('[data-retry-task="pose-ui"]').waitFor();

        const works = await browser.newPage();
        await works.route('**/api/**', route => {
            if(new URL(route.request().url()).pathname === '/api/works') { worksCalls += 1; return route.fulfill({json:{works:[],total:0,next_cursor:''}}); }
            return route.fulfill({json:{}});
        });
        await works.goto(`${process.env.POSE_TEST_BASE_URL || 'http://127.0.0.1:8877'}/static/works.html`);
        await works.waitForFunction(() => document.querySelector('#worksRefresh:not(:disabled)'));
        const initial = worksCalls;
        const refresh = works.waitForResponse(response => new URL(response.url()).pathname === '/api/works');
        await works.evaluate(() => window.postMessage({type:'studio-route-active',active:true},location.origin));
        await refresh;
        assert.ok(worksCalls > initial,'返回作品页时应立即刷新');
        console.log('pose transfer drag replacement, completed state, cross-tab cleanup and works route refresh passed');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
