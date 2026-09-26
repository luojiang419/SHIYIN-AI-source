const assert = require('node:assert/strict');
const fs = require('node:fs');
const nodePath = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try {
        const page = await browser.newPage({viewport:{width:1500,height:900}});
        let uploads = 0;
        const tasks = [];
        await page.route('**/api/**', route => {
            const {pathname} = new URL(route.request().url());
            if(pathname === '/api/ecommerce/capabilities') return route.fulfill({json:{models:[{provider_id:'demo',model:'demo-image'}],providers:[{id:'demo',name:'Demo'}],routes:{standard:{provider_id:'demo',model:'demo-image'}},vision_analysis:{enabled:true},reference_slot_types:[]}});
            if(pathname === '/api/ai/upload') { const name=['model.png','blazer.png','trousers.png','blazer-detail.png','loafers.png','model.png','blazer.png'][uploads++] || 'blazer.png'; const localAsset=nodePath.join('.codex-tmp/tryon-steps-demo/assets',name); const url=fs.existsSync(localAsset) ? `/${localAsset.replaceAll('\\','/')}?drop=${uploads}` : `/static/images/logo.png?drop=${uploads}`; return route.fulfill({json:{files:[{url,kind:'image',width:512,height:512,name}]}}); }
            if(pathname === '/api/ecommerce/analyze') return route.fulfill({json:{status:'skipped',message:'规则分析',prompt_preview:'试穿',analysis:{status:'skipped'}}});
            if(pathname === '/api/ecommerce/tasks' && route.request().method() === 'POST') {
                const body = route.request().postDataJSON();
                tasks.push(body);
                const id = `drop-task-${tasks.length}`;
                return route.fulfill({json:{id,task_id:id,operation:body.operation,status:'queued',result:null}});
            }
            if(pathname === '/api/ecommerce/tasks') return route.fulfill({json:{tasks:[]}});
            if(pathname.startsWith('/api/ecommerce/tasks/')) return route.fulfill({json:{id:pathname.split('/').at(-1),status:'queued',result:null}});
            return route.fulfill({json:{}});
        });
        const dropImage = async (selector,count=1) => {
            const response = page.waitForResponse(item => new URL(item.url()).pathname === '/api/ai/upload' && item.request().method() === 'POST');
            await page.locator(selector).evaluate((element,count) => {
                const transfer = new DataTransfer();
                for(let index=0;index<count;index++) transfer.items.add(new File([new Uint8Array([137,80,78,71])],`external-${Date.now()}-${index}.png`,{type:'image/png'}));
                element.dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer:transfer}));
                element.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
            },count);
            assert.equal((await response).status(),200);
        };
        await page.goto('http://127.0.0.1:8765/static/ecommerce.html');
        await page.locator('[data-operation="try_on"]').click();
        await dropImage('.ec-tryon-materials');
        await page.locator('.ec-tryon-slot-card.is-model img[src*="drop="]').waitFor();
        assert.equal(await page.locator('.ec-tryon-slot-card.is-model').count(),1);
        await page.locator('[data-tryon-model-description="0"]').fill('保持面部身份');

        await page.locator('[data-tryon-step-next]').click();
        await dropImage('.ec-tryon-materials',2);
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_1"] img[src*="drop="]').waitFor();
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_2"] img[src*="drop="]').waitFor();
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_1"] [data-tryon-reference-type]').selectOption('upper_garment');
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_1"] [data-tryon-description-role]').fill('米白色西装');
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_2"] [data-tryon-reference-type]').selectOption('lower_garment');
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_2"] [data-tryon-description-role]').fill('棕色长裤');

        await page.locator('[data-tryon-step-next]').click();
        await dropImage('.ec-tryon-stepbar');
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_3"] img[src*="drop="]').waitFor();
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_3"] [data-tryon-reference-type]').selectOption('detail');
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_3"] [data-tryon-detail-target]').selectOption('tryon_extra_1');
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_3"] [data-tryon-description-role]').fill('领口织纹');

        await page.locator('[data-tryon-step-next]').click();
        await dropImage('.ec-tryon-generation-outfit');
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_4"] img[src*="drop="]').waitFor();
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_4"] [data-tryon-reference-type]').selectOption('shoes');
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_4"] [data-tryon-description-role]').fill('深棕色皮鞋');
        await dropImage('.ec-tryon-generation-models');
        await page.locator('[data-tryon-model-description="1"]').fill('第二位模特');
        assert.equal(await page.locator('.ec-tryon-generation-models .ec-tryon-generation-card').count(),1);
        assert.equal(await page.locator('.ec-tryon-generation-model-strip button').count(),2);
        assert.equal(await page.locator('.ec-tryon-generation-outfit .ec-tryon-generation-card').count(),4);
        await page.waitForFunction(() => [...document.querySelectorAll('.ec-tryon-generation-card img')].every(image => image.complete && image.naturalWidth > 0));
        const layout = await page.locator('.ec-tryon-generation-references').evaluate(element => ({heroBottom:element.querySelector('.is-model-hero').getBoundingClientRect().bottom,referenceBottom:Math.max(...[...element.querySelectorAll('.ec-tryon-generation-outfit .ec-tryon-generation-card')].map(card => card.getBoundingClientRect().bottom)),actionTop:document.querySelector('.ec-operation-controls').getBoundingClientRect().top}));
        assert.ok(layout.heroBottom < layout.actionTop && layout.referenceBottom < layout.actionTop,'模特大图和两排小卡应完整显示在底部生成需求上方');
        await page.screenshot({path:'.codex-tmp/ecommerce-tryon-drop-generation.png'});
        await page.setViewportSize({width:520,height:900});
        const narrow = await page.locator('.ec-tryon-generation-references').evaluate(element => ({modelBottom:element.querySelector('.ec-tryon-generation-models').getBoundingClientRect().bottom,referenceTop:element.querySelector('.ec-tryon-generation-outfit').getBoundingClientRect().top,right:element.getBoundingClientRect().right}));
        assert.ok(narrow.modelBottom <= narrow.referenceTop && narrow.right <= 521,'窄屏应将模特大图排在参考卡上方，且不超出视口');
        await page.setViewportSize({width:1500,height:900});
        await page.locator('#generateButton').click();
        await page.waitForFunction(() => document.querySelector('[data-export-tryon-guide]') || document.querySelector('#tryOnGuidePanel .ec-tryon-guide-state')?.textContent.includes('正在生成'));
        assert.equal(tasks.length,2);
        const tryOn = tasks.find(task => task.operation === 'try_on');
        assert.equal(tryOn.inputs.find(item => item.role === 'source').instruction,'第二位模特');
        assert.equal(tryOn.inputs.find(item => item.reference_id === 'tryon_extra_1').role,'upper_garment');
        assert.equal(tryOn.inputs.find(item => item.reference_id === 'tryon_extra_1').instruction,'米白色西装');
        assert.equal(tryOn.inputs.find(item => item.reference_id === 'tryon_extra_3').detail_target_id,'tryon_extra_1');
        assert.equal(tryOn.inputs.find(item => item.reference_id === 'tryon_extra_4').role,'shoes');
        assert.equal(tryOn.inputs.find(item => item.reference_id === 'tryon_extra_4').instruction,'深棕色皮鞋');
        await page.locator('.ec-tryon-stepbar [data-tryon-step="1"]').click();
        await dropImage('[data-tryon-wardrobe-role="tryon_extra_1"] .ec-upload-slot');
        await page.locator('[data-tryon-wardrobe-role="tryon_extra_5"] img[src*="drop="]').waitFor();
        assert.equal(await page.locator('[data-tryon-wardrobe-role="tryon_extra_1"]').count(),1,'拖到已有图片卡上应新增卡片而非覆盖');
        console.log('try-on external image drops passed across all four steps');
    } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
