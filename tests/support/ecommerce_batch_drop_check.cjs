// 隔离真实浏览器事件回归；上传和深度接口均为内存响应。
const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
    const browser = await chromium.launch({headless:true, channel:'chrome'});
    try {
        const page = await browser.newPage();
        const errors = [];
        let uploads = 0;
        let depth = 0;
        page.on('pageerror', error => errors.push(error.message));
        await page.route('http://fixture/**', route => {
            const url = route.request().url();
            if(url.endsWith('/api/ai/upload')) return route.fulfill({json:{files:[{url:`/image.png?${++uploads}`,name:'image.png'}]}});
            if(url.endsWith('/api/person-depth/component/status')) return route.fulfill({json:{state:'ready',ready:true}});
            if(url.endsWith('/api/person-depth/estimate')) depth++;
            if(url.includes('/image.png') || url.endsWith('/estimate')) return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jEOsAAAAASUVORK5CYII=','base64')});
            return route.fulfill({contentType:'text/html',body:'<div id="batchOutfitGroups"></div><input id="batchOutfitFileInput" type="file" multiple>'});
        });
        await page.goto('http://fixture/');
        await page.evaluate(() => {
            window.toasts = [];
            window.EcommerceStudio = {state:{operation:'batch_outfit',batchOutfit:{groups:[{id:'one',style_name:'款一'},{id:'two',style_name:'款二'}]}},persistSettings(){},showToast(message){toasts.push(message);}};
        });
        await page.addScriptTag({path:path.resolve(__dirname,'../../static/js/ecommerce-batch-outfit.js')});
        await page.evaluate(() => EcommerceBatchOutfit.init());
        const snapshot = () => page.evaluate(() => EcommerceBatchOutfit.snapshot());
        const drop = async (role, count=1, type='image/png', group='one') => {
            await page.locator(`[data-batch-group="${group}"] [data-batch-upload="${role}"]`).evaluate((card, {count,type}) => {
                const dataTransfer = new DataTransfer();
                for(let i=0;i<count;i++) dataTransfer.items.add(new File(['fixture'], `file-${i}.png`, {type}));
                card.dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer}));
                const event = new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer});
                card.querySelector('span').dispatchEvent(event);
                if(!event.defaultPrevented) throw new Error('未阻止文件默认打开');
            }, {count,type});
            await page.waitForFunction(() => EcommerceBatchOutfit.snapshot().groups.every(g => !['uploading','preparing'].includes(g.status)));
        };
        await drop('target_image',2);
        assert.equal((await snapshot()).groups[0].inputs.target_image.length,2);
        await drop('target_image',1);
        assert.equal((await snapshot()).groups[0].inputs.target_image.length,3);
        for(const role of ['model_subject','scene','pose_reference']) {
            await drop(role,2);
            assert.ok((await snapshot()).groups[0].inputs[role].url);
        }
        assert.equal(depth,1);
        assert.ok((await snapshot()).groups[0].control_map.url);
        await drop('scene',1,'image/png','two');
        assert.ok((await snapshot()).groups[1].inputs.scene.url);
        const beforeInvalid = uploads;
        await drop('scene',1,'text/plain');
        assert.equal(uploads,beforeInvalid);
        await drop('target_image',25);
        assert.equal((await snapshot()).groups[0].inputs.target_image.length,20);
        const beforeFull = uploads;
        await drop('target_image');
        assert.equal(uploads,beforeFull);
        await page.evaluate(() => {
            const data = EcommerceBatchOutfit.snapshot();
            data.groups[0].status = 'running';
            EcommerceBatchOutfit.hydrate(data);
            EcommerceBatchOutfit.render();
        });
        await drop('scene');
        assert.equal(uploads,beforeFull);
        // 点击选择文件继续走同一个上传链路。
        await page.locator('[data-batch-group="two"] [data-batch-upload="model_subject"]').click();
        await page.locator('#batchOutfitFileInput').setInputFiles({name:'click.png',mimeType:'image/png',buffer:Buffer.from('fixture')});
        await page.waitForFunction(() => !!EcommerceBatchOutfit.snapshot().groups[1].inputs.model_subject);
        assert.equal(await page.locator('.is-file-dragover').count(),0);
        assert.deepEqual(errors,[]);
        console.log('PASS: 四类格子拖放、多图追加/上限、分组定位、深度提取、非法文件、忙碌保护、点击上传');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
