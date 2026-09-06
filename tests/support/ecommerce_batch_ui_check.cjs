const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3014';
    const screenshotPath = process.argv[3] || '';
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1440,height:980}});
        const errors = [];
        const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jEOsAAAAASUVORK5CYII=', 'base64');
        const submittedPayloads = [];
        let uploadIndex = 0;
        let depthRequests = 0;
        let taskIndex = 0;
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/api/person-depth/component/status', route => route.fulfill({json:{state:'ready',ready:true,install_available:true,progress:1}}));
        await page.route('**/api/person-depth/estimate', route => {
            depthRequests += 1;
            return route.fulfill({status:200,contentType:'image/png',body:png,headers:{'X-Person-Depth-Width':'1','X-Person-Depth-Height':'1'}});
        });
        await page.route('**/api/ai/upload', route => {
            uploadIndex += 1;
            return route.fulfill({json:{files:[{url:`/fixture.png?upload=${uploadIndex}`,name:`fixture-${uploadIndex}.png`,natural_w:600,natural_h:800,kind:'image'}]}});
        });
        await page.route('**/api/canvas/pose-replicate-tasks', async route => {
            submittedPayloads.push(route.request().postDataJSON());
            taskIndex += 1;
            return route.fulfill({json:{task_id:`batch-task-${taskIndex}`,status:'queued'}});
        });
        await page.route('**/api/canvas-image-tasks/*', route => {
            const id = route.request().url().split('/').pop();
            const index = Number(id.split('-').pop()) || 1;
            return route.fulfill({json:{task_id:id,status:'succeeded',result:{images:[`/fixture.png?result=${index}`],work_ids:[`work-generated-${index}`],batch_outfit_archive:[{source_url:`/fixture.png?result=${index}`,name:`result-${index}.png`,relative_path:`SS26-001/result-${index}.png`}]}}});
        });
        await page.goto(`${base}/static/ecommerce.html`);
        await page.waitForSelector('[data-operation="batch_outfit"]');
        assert.equal(await page.locator('#operationTabs [data-operation]').count(), 4);
        assert.deepEqual(await page.locator('#operationTabs [data-operation]').evaluateAll(items => items.map(item => item.dataset.operation)), ['universal','batch_outfit','try_on','pose_transfer']);
        assert.deepEqual(await page.locator('#operationTabs [data-operation] > span').allTextContents(), ['01','02','03','04']);
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

        await page.locator('[data-batch-group]').first().locator('[data-batch-upload="pose_reference"]').click();
        await page.locator('#batchOutfitFileInput').setInputFiles({name:'target.png',mimeType:'image/png',buffer:png});
        await page.locator('.ec-batch-depth-chip.is-ready').waitFor();
        assert.equal(depthRequests, 1);
        await page.locator('[data-batch-group]').first().locator('[data-batch-upload="target_image"]').click();
        await page.locator('#batchOutfitFileInput').setInputFiles([
            {name:'garment-1.png',mimeType:'image/png',buffer:png},
            {name:'garment-2.png',mimeType:'image/png',buffer:png},
        ]);
        await page.locator('[data-batch-group]').first().locator('.ec-batch-stack-controls b').waitFor();
        await page.evaluate(() => {
            EcommerceStudio.state.capabilities = {
                models:[{provider_id:'fixture',model:'fixture-image',max_reference_images:5}],
                routes:{standard:{provider_id:'fixture',model:'fixture-image'}},
            };
            EcommerceStudio.state.providerId = 'fixture';
            EcommerceStudio.state.model = 'fixture-image';
        });
        await page.locator('[data-batch-group]').first().locator('[data-batch-run]').click();
        await page.waitForFunction(() => EcommerceBatchOutfit.snapshot().groups[0].works.length === 2);
        assert.equal(submittedPayloads.length, 2);
        assert.ok(submittedPayloads.every(payload => payload.mode === 'depth'));
        assert.equal(new Set(submittedPayloads.map(payload => payload.inputs.target_image.url)).size, 2);
        assert.equal(new Set(submittedPayloads.map(payload => payload.inputs.control_map.url)).size, 1);

        await page.locator('#addBatchOutfit').click();
        await page.locator('#batchOutfitStyleName').fill('SS26-002');
        await page.locator('#confirmBatchOutfit').click();
        assert.equal(await page.locator('.ec-batch-group').count(), 2);
        assert.deepEqual(await page.locator('.ec-batch-group-number').allTextContents(), ['01','02']);
        assert.equal(await page.locator('.ec-batch-outfit-groups.is-single').count(), 0);

        const pixel = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="#c89468"/><circle cx="800" cy="420" r="210" fill="#f3eadf"/></svg>');
        await page.evaluate(pixelUrl => {
            const saved = EcommerceBatchOutfit.snapshot();
            saved.grid_ratio = '16:9';
            saved.groups[0].status = 'succeeded';
            saved.groups[0].inputs.target_image = [
                {url:pixelUrl,name:'服装参考-01.png'},
                {url:pixelUrl,name:'服装参考-02.png'},
            ];
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
        const workStage = page.locator('[data-batch-work-stage]');
        await workStage.hover();
        await page.waitForTimeout(200);
        assert.equal(await workStage.locator('[data-batch-work-step="-1"]').isDisabled(), true);
        assert.ok(Number(await workStage.locator('[data-batch-work-step="1"]').evaluate(element => getComputedStyle(element).opacity)) > .5);
        await page.keyboard.press('ArrowRight');
        assert.equal((await page.locator('.ec-batch-works-shell > header > strong').textContent()).trim(), '2 / 2');
        await page.keyboard.press('ArrowLeft');
        assert.equal((await page.locator('.ec-batch-works-shell > header > strong').textContent()).trim(), '1 / 2');
        await page.locator('[data-batch-work-preview]').click();
        await page.locator('#batchOutfitPreview[open]').waitFor();
        const previewBox = await page.locator('#batchOutfitPreview').boundingBox();
        assert.ok(previewBox.width >= 1439 && previewBox.height >= 979);
        const previewGeometry = await page.locator('#batchOutfitPreviewStage').evaluate(stage => {
            const image = stage.querySelector('img');
            const stageRect = stage.getBoundingClientRect();
            const imageRect = image.getBoundingClientRect();
            return {
                stage:{left:stageRect.left,top:stageRect.top,right:stageRect.right,bottom:stageRect.bottom},
                image:{left:imageRect.left,top:imageRect.top,right:imageRect.right,bottom:imageRect.bottom},
                objectFit:getComputedStyle(image).objectFit,
                boxSizing:getComputedStyle(stage).boxSizing,
            };
        });
        assert.equal(previewGeometry.objectFit, 'contain');
        assert.equal(previewGeometry.boxSizing, 'border-box');
        assert.ok(previewGeometry.image.left >= previewGeometry.stage.left && previewGeometry.image.right <= previewGeometry.stage.right);
        assert.ok(previewGeometry.image.top >= previewGeometry.stage.top && previewGeometry.image.bottom <= previewGeometry.stage.bottom);
        assert.equal(await page.locator('#batchOutfitPreviewZoomOut').isDisabled(), true);
        await page.locator('#batchOutfitPreviewZoomIn').click();
        assert.equal((await page.locator('#batchOutfitPreviewZoomReset').textContent()).trim(), '1.25×');
        const previewStageBox = await page.locator('#batchOutfitPreviewStage').boundingBox();
        const panBefore = await page.locator('#batchOutfitPreviewStage').evaluate(stage => getComputedStyle(stage).getPropertyValue('--ec-batch-preview-pan-x').trim());
        await page.mouse.move(previewStageBox.x + previewStageBox.width / 2, previewStageBox.y + previewStageBox.height / 2);
        await page.mouse.down();
        await page.mouse.move(previewStageBox.x + previewStageBox.width / 2 + 55, previewStageBox.y + previewStageBox.height / 2 + 35, {steps:4});
        await page.mouse.up();
        const panAfter = await page.locator('#batchOutfitPreviewStage').evaluate(stage => getComputedStyle(stage).getPropertyValue('--ec-batch-preview-pan-x').trim());
        assert.notEqual(panAfter, panBefore);
        assert.equal((await page.locator('#batchOutfitPreviewCount').textContent()).trim(), '1 / 2');
        assert.equal(await page.locator('[data-batch-preview-step="-1"]').isDisabled(), true);
        assert.equal(Number(await page.locator('[data-batch-preview-step="-1"]').evaluate(element => getComputedStyle(element).opacity)), 0);
        if(screenshotPath) await page.screenshot({path:screenshotPath.replace(/(\.[^.]+)$/, '-fullscreen$1')});
        await page.keyboard.press('ArrowRight');
        assert.equal((await page.locator('#batchOutfitPreviewCount').textContent()).trim(), '2 / 2');
        assert.equal((await page.locator('#batchOutfitPreviewZoomReset').textContent()).trim(), '1×');
        assert.equal(await page.locator('[data-batch-preview-step="1"]').isDisabled(), true);
        await page.locator('[data-batch-preview-step="-1"]').click();
        assert.equal((await page.locator('#batchOutfitPreviewCount').textContent()).trim(), '1 / 2');
        await page.locator('#closeBatchOutfitPreview').click();
        assert.equal(await page.locator('#batchOutfitPreview').getAttribute('open'), null);
        assert.equal((await page.locator('.ec-batch-works-shell > header > strong').textContent()).trim(), '1 / 2');
        const garmentCard = page.locator('[data-batch-group]').first().locator('[data-batch-upload="target_image"]');
        assert.equal(await garmentCard.locator('.ec-batch-card-shadow').count(), 2);
        assert.equal((await garmentCard.locator('.ec-batch-stack-controls b').textContent()).trim(), '1/2');
        assert.equal(await garmentCard.locator('.ec-batch-card-stack > img').evaluate(image => getComputedStyle(image).objectFit), 'contain');
        await page.locator('#batchOutfitGridRatio').selectOption('4:5');
        const cardRatio = await garmentCard.evaluate(element => element.getBoundingClientRect().width / element.getBoundingClientRect().height);
        assert.ok(Math.abs(cardRatio - .8) < .03, `expected 4:5 card ratio, received ${cardRatio}`);
        assert.equal((await page.evaluate(() => EcommerceBatchOutfit.snapshot().grid_ratio)), '4:5');
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
        await page.locator('[data-batch-work-preview]').click();
        const mobilePreviewBox = await page.locator('#batchOutfitPreview').boundingBox();
        assert.ok(mobilePreviewBox.width >= 639 && mobilePreviewBox.height >= 899);
        const [mobileTitleBox,mobileActionsBox] = await Promise.all([
            page.locator('#batchOutfitPreviewTitle').boundingBox(),
            page.locator('.ec-batch-preview-shell > header > div').boundingBox(),
        ]);
        assert.ok(mobileTitleBox.x + mobileTitleBox.width <= mobileActionsBox.x);
        if(screenshotPath) await page.screenshot({path:screenshotPath.replace(/(\.[^.]+)$/, '-mobile-fullscreen$1')});
        await page.locator('#closeBatchOutfitPreview').click();
        assert.deepEqual(errors, []);
        console.log('ecommerce batch outfit layout, grouping, works and responsive UI passed');
    } finally {
        await browser.close();
    }
})().catch(error=>{console.error(error);process.exitCode=1;});
