const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3014';
    const screenshotPath = process.argv[3] || '';
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1440,height:980}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(`${base}/static/ecommerce.html`);
        await page.waitForSelector('[data-operation="batch_outfit"]');
        assert.equal(await page.locator('#operationTabs [data-operation]').count(), 4);
        for(const operation of ['prop_replace','angle_change','background_change']) {
            assert.equal(await page.locator(`[data-operation="${operation}"]`).count(), 0);
        }

        await page.locator('[data-operation="batch_outfit"]').click();
        await page.waitForSelector('#batchOutfitControl:not(.hidden)');
        assert.equal((await page.locator('.ec-result-head h2').textContent()).trim(), '查看作品');
        assert.equal(await page.locator('#advancedSettings.collapsed').count(), 1);
        assert.equal(await page.locator('#modelPanelToggle').getAttribute('aria-expanded'), 'false');
        assert.equal(await page.locator('#modelPanelBody').isVisible(), false);
        await page.locator('#modelPanelToggle').click();
        assert.equal(await page.locator('#advancedSettings.collapsed').count(), 0);
        assert.equal(await page.locator('#modelPanelToggle').getAttribute('aria-expanded'), 'true');
        assert.equal(await page.locator('#modelPanelBody').isVisible(), true);
        assert.equal(await page.locator('.ec-batch-empty').count(), 1);

        await page.locator('#addBatchOutfit').click();
        await page.locator('#batchOutfitStyleName').fill('SS26-001');
        await page.locator('#confirmBatchOutfit').click();
        assert.equal(await page.locator('.ec-batch-group').count(), 1);
        assert.equal(await page.locator('.ec-batch-group-slots > button').count(), 5);
        assert.equal(await page.locator('.ec-batch-outfit-groups.is-single').count(), 1);

        await page.locator('#addBatchOutfit').click();
        await page.locator('#batchOutfitStyleName').fill('SS26-002');
        await page.locator('#confirmBatchOutfit').click();
        assert.equal(await page.locator('.ec-batch-group').count(), 2);
        assert.deepEqual(await page.locator('.ec-batch-group-number').allTextContents(), ['01','02']);
        assert.equal(await page.locator('.ec-batch-outfit-groups.is-single').count(), 0);

        const pixel = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800"><rect width="600" height="800" fill="#c89468"/><circle cx="300" cy="290" r="130" fill="#f3eadf"/></svg>');
        await page.evaluate(pixelUrl => {
            const saved = EcommerceBatchOutfit.snapshot();
            saved.groups[0].status = 'succeeded';
            saved.groups[0].works = [
                {url:pixelUrl,name:'SS26-001-01.png',workId:'work-1',archivePath:'SS26-001/a.png'},
                {url:pixelUrl,name:'SS26-001-02.png',workId:'work-2',archivePath:'SS26-001/b.png'},
            ];
            saved.selected_group_id = saved.groups[0].id;
            EcommerceBatchOutfit.hydrate(saved);
        }, pixel);
        assert.equal((await page.locator('.ec-batch-works-shell h2').textContent()).trim(), 'SS26-001');
        assert.equal(await page.locator('.ec-batch-work-thumbs button').count(), 2);
        assert.equal(await page.locator('[data-batch-download-selected]').count(), 1);
        assert.equal(await page.locator('[data-batch-delete-all]').count(), 1);
        await page.evaluate(() => {
            localStorage.setItem('pose_replicate_prompt_templates_v1', JSON.stringify({schema_version:1,overrides:{'skeleton:base-wardrobe':'共享提示词'}}));
            window.dispatchEvent(new StorageEvent('storage', {key:'pose_replicate_prompt_templates_v1'}));
        });
        assert.match((await page.locator('#batchOutfitPromptStatus').textContent()).trim(), /已同步 1 个自定义组合/);
        if(screenshotPath) await page.screenshot({path:screenshotPath, fullPage:true});

        await page.setViewportSize({width:640,height:900});
        const columns = await page.locator('.ec-batch-group-slots').first().evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length);
        assert.equal(columns, 2);
        await page.evaluate(() => {
            document.documentElement.classList.add('studio-theme-dark');
            document.documentElement.classList.remove('studio-theme-pure-white','theme-pure-white');
        });
        assert.notEqual(await page.locator('.ec-batch-group').first().evaluate(element => getComputedStyle(element).backgroundImage), 'none');
        assert.deepEqual(errors, []);
        console.log('ecommerce batch outfit layout, grouping, works and responsive UI passed');
    } finally {
        await browser.close();
    }
})().catch(error=>{console.error(error);process.exitCode=1;});
