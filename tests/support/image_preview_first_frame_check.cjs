// 配合 canvas_startup_fixture.py；仅使用隔离内存图片，不读写用户工程。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const baseline = process.argv.includes('--baseline');
const output = '.codex-artifacts/preview-first-frame';

(async () => {
    fs.mkdirSync(output, {recursive:true});
    const browser = await chromium.launch({headless:true, channel:'msedge'});
    try {
        const page = await browser.newPage({viewport:{width:1440,height:1000}});
        const errors = [], requests = [], cases = [];
        let failOriginal = true;
        page.on('pageerror', error => errors.push(error.message));
        const images = await page.evaluate(() => {
            const make = (width, height, color) => {
                const canvas = document.createElement('canvas');
                canvas.width = width; canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = color; ctx.fillRect(0,0,width,height);
                ctx.fillStyle = '#fff'; ctx.fillRect(width/4,height/4,width/2,height/2);
                return canvas.toDataURL('image/png').split(',')[1];
            };
            return {quick:make(512,768,'#b43220'), full:make(2048,3072,'#b43220'), blue:make(2048,1024,'#2052b4')};
        });
        await page.route('**/api/media-preview?**', async route => {
            const url = new URL(route.request().url());
            if(!url.searchParams.get('url')?.includes('preview-check')) return route.continue();
            requests.push(url.pathname + url.search);
            if(Number(url.searchParams.get('w')) > 512) await new Promise(resolve => setTimeout(resolve, 1800));
            const key = url.searchParams.get('url').includes('blue') ? 'blue' : 'quick';
            await route.fulfill({contentType:'image/png', body:Buffer.from(images[key],'base64')});
        });
        await page.route('**/assets/preview-check-*.png', async route => {
            const url = route.request().url(); requests.push(url);
            await new Promise(resolve => setTimeout(resolve, /blue|fail/.test(url) ? 300 : 3000));
            if(url.includes('fail') && failOriginal) return route.fulfill({status:503,body:'unavailable'});
            await route.fulfill({contentType:'image/png', body:Buffer.from(url.includes('blue') ? images.blue : images.full,'base64')});
        });
        await page.goto(`http://127.0.0.1:3063/static/canvas.html?id=preview-first-frame-${Date.now()}`);
        await page.waitForSelector('.node[data-id="image"]');
        await page.evaluate(() => {
            nodes.splice(0, nodes.length,
                {id:'preview-red',type:'image',x:80,y:80,w:300,url:'/assets/preview-check-red.png',name:'red.png'},
                {id:'preview-blue',type:'image',x:480,y:80,w:300,url:'/assets/preview-check-blue.png',name:'blue.png'});
            connections.splice(0); selected.clear(); viewport.x=0; viewport.y=0; viewport.scale=1;
            render(); applyViewport();
        });
        await page.waitForFunction(() => document.querySelector('[data-id="preview-red"] img')?.naturalWidth > 0);
        const metrics = await page.evaluate(async () => {
            const start = performance.now();
            document.querySelector('[data-id="preview-red"] img').dispatchEvent(new MouseEvent('dblclick',{bubbles:true,detail:2}));
            const opened = performance.now()-start;
            return await new Promise((resolve,reject) => {
                const check = () => {
                    if(performance.now()-start > 10000) return reject(new Error('Preview first pixels timed out'));
                    const img = document.getElementById('cropImage');
                    const canvas = document.querySelector('[data-editor-preview-pixels]');
                    if((canvas && canvas.width > 0) || (img.complete && img.naturalWidth > 0)) {
                        resolve({openedMs:opened,firstPixelsMs:performance.now()-start,via:canvas?'existing-pixels':'image-load'});
                    } else requestAnimationFrame(check);
                };
                requestAnimationFrame(check);
            });
        });
        console.log(JSON.stringify({baseline,...metrics}));
        if(!baseline) {
            assert.equal(metrics.via,'existing-pixels');
            assert.ok(metrics.firstPixelsMs < 250, JSON.stringify(metrics));
            await page.waitForTimeout(400);
            assert.equal(await page.locator('[data-editor-preview-pixels]').count(),1);
            assert.deepEqual(await page.evaluate(() => Array.from(document.querySelector('[data-editor-preview-pixels]').getContext('2d').getImageData(0,0,1,1).data)), [180,50,32,255]);
            await page.screenshot({path:`${output}/pending.png`});
            await page.waitForFunction(() => document.getElementById('cropImage').dataset.editorLoadState === 'ready');
            assert.equal(await page.locator('[data-editor-preview-pixels]').count(),0);
            assert.deepEqual(await page.evaluate(() => [cropImage.naturalWidth,cropImage.naturalHeight]),[2048,3072]);
            assert.ok(await page.evaluate(() => editDrawCanvas().width < 2048), 'preview must not allocate full-size editing canvas');
            await page.evaluate(() => setImageEditMode('brush',true));
            assert.deepEqual(await page.evaluate(() => [editDrawCanvas().width,editDrawCanvas().height]),[2048,3072]);
            assert.equal(requests.filter(url => /[?&]w=(1536|2048)(?:&|$)/.test(url)).length,0);
            cases.push('慢原图下一帧可见、连续保留像素、高清交接、编辑画布延迟分配');

            // 验证编辑像素和缩放，而不只检查 DOM 类名。
            await page.evaluate(() => {
                const ctx = editDrawCanvas().getContext('2d');
                ctx.fillStyle = '#00ff00'; ctx.fillRect(0,0,20,20);
                imageEditZoom = 1.5; applyImageEditZoom();
            });
            assert.deepEqual(await page.evaluate(() => Array.from(editDrawCanvas().getContext('2d').getImageData(1,1,1,1).data)),[0,255,0,255]);
            await page.waitForTimeout(100);
            assert.deepEqual(await page.evaluate(() => Array.from(editDrawCanvas().getContext('2d').getImageData(1,1,1,1).data)),[0,255,0,255]);
            cases.push('高清编辑、缩放后绘图不被异步回调清空');
            await page.evaluate(() => closeImageEditor());
            assert.equal(await page.evaluate(() => editDrawCanvas().width),1);

            // 真正鼠标双击（mousedown + dblclick），同一窗口只启动一轮加载。
            const beforeOriginal = requests.filter(url => url.endsWith('preview-check-blue.png')).length;
            await page.locator('[data-id="preview-blue"] .image-preview-wrap img').dblclick();
            await page.waitForFunction(() => cropImage.dataset.editorLoadState === 'ready');
            assert.equal(requests.filter(url => url.endsWith('preview-check-blue.png')).length-beforeOriginal,1);
            cases.push('真实鼠标双击不重复初始化');
            await page.evaluate(() => closeImageEditor());

            const addAndOpen = async (id, mode='preview') => page.evaluate(({id,mode}) => {
                closeImageEditor();
                nodes.push({id,type:'image',x:800,y:80,url:`/assets/preview-check-${id}.png`,name:`${id}.png`});
                openImageEditor(id,mode);
            },{id,mode});
            // 没有挂载节点像素时允许并行获取已有 512px 缩略图。
            await addAndOpen('no-node-pixels');
            await page.waitForSelector('[data-editor-preview-pixels]');
            assert.equal(await page.evaluate(() => cropImage.dataset.editorLoadState),'loading');
            await page.evaluate(() => { setImageEditMode('crop',true); applyImageEdit(); });
            assert.equal(await page.evaluate(() => imageEditMode),'preview');
            await page.waitForFunction(() => cropImage.dataset.editorLoadState === 'ready');
            assert.equal(await page.evaluate(() => imageEditMode),'crop');
            cases.push('无节点缩略图兜底、加载中不导出低清图、原图就绪后进入请求的编辑模式');

            // 真实裁剪导出必须使用 2048x3072 原图。
            let exported = null;
            await page.route('**/api/ai/upload', async route => {
                const body = route.request().postDataBuffer();
                const offset = body.indexOf(Buffer.from([137,80,78,71,13,10,26,10]));
                assert.ok(offset >= 0);
                exported = [body.readUInt32BE(offset+16),body.readUInt32BE(offset+20)];
                await route.fulfill({contentType:'application/json',body:JSON.stringify({files:[{url:'/assets/preview-check-export.png',name:'crop.png'}]})});
            });
            await page.evaluate(async () => {
                const img = document.getElementById('cropImage');
                cropState.x=0; cropState.y=0; cropState.w=img.clientWidth/2; cropState.h=img.clientHeight/2;
                await applyImageEdit();
            });
            assert.deepEqual(exported,[1024,1536]);
            cases.push('真实裁剪上传尺寸为原图的一半（1024×1536），不是缩略图的一半');

            await addAndOpen('switch-red');
            await page.waitForSelector('[data-editor-preview-pixels]');
            await page.evaluate(() => openImageEditor('preview-blue','preview'));
            await page.waitForFunction(() => cropImage.dataset.editorLoadState === 'ready');
            await page.waitForTimeout(3100);
            assert.ok(await page.evaluate(() => cropImage.getAttribute('src').endsWith('preview-check-blue.png')));
            assert.deepEqual(await page.evaluate(() => [cropImage.naturalWidth,cropImage.naturalHeight]),[2048,1024]);
            cases.push('快速切换后旧原图不会覆盖新图片');

            await addAndOpen('close-red');
            await page.waitForSelector('[data-editor-preview-pixels]');
            await page.evaluate(() => closeImageEditor());
            await page.waitForTimeout(3100);
            assert.equal(await page.locator('[data-editor-preview-pixels]').count(),0);
            assert.equal(await page.evaluate(() => cropImage.getAttribute('src')),null);
            assert.equal(await page.evaluate(() => cropState),null);
            cases.push('加载中关闭释放图片和回调');

            await addAndOpen('fail-red');
            await page.waitForFunction(() => cropImage.dataset.editorLoadState === 'error');
            assert.equal(await page.locator('[data-editor-preview-pixels]').count(),1);
            await page.evaluate(() => { setImageEditMode('brush',true); applyImageEdit(); });
            assert.equal(await page.evaluate(() => imageEditMode),'preview');
            failOriginal = false;
            await page.getByRole('button',{name:'重试',exact:true}).click();
            await page.waitForFunction(() => cropImage.dataset.editorLoadState === 'ready');
            assert.equal(await page.evaluate(() => imageEditMode),'brush');
            assert.deepEqual(await page.evaluate(() => [editDrawCanvas().width,editDrawCanvas().height]),[2048,3072]);
            cases.push('原图失败保留预览、重试恢复高清编辑');
            await page.evaluate(() => closeImageEditor());
        }
        fs.writeFileSync(`${output}/${baseline?'baseline':'current'}.json`,JSON.stringify({metrics,cases,requests,errors},null,2));
        assert.deepEqual(errors,[]);
        if(!baseline) console.log(`${cases.length} browser scenarios passed`);
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
