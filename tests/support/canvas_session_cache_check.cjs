// 仅使用内存工程和本地 fixture，不读写用户画布，不调用生成 API。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const base = process.argv[2] || 'http://127.0.0.1:3027';
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function waitUntil(predicate){
    const deadline=Date.now()+10000;
    while(!predicate()){
        if(Date.now()>deadline) throw new Error('等待测试请求超时');
        await sleep(10);
    }
}

(async () => {
    const browser = await chromium.launch({headless:true, channel:'msedge'});
    const results = [];
    try {
        for(const mode of ['standalone', 'studio']){
            const page = await browser.newPage({viewport:{width:1440,height:1000}});
            const errors = [];
            page.on('pageerror', error => errors.push(error.message));
            const docs = new Map();
            let reads = 0, mediaReads = 0, saves = 0;
            const mediaUrls = [];
            let holdNextRead = false, releaseRead = null;
            let holdNextSave = false, releaseSave = null;
            for(const id of ['a','b','c','d']) docs.set(id, {
                id, title:`缓存测试 ${id}`, project:'default', kind:'classic', updated_at:1, revision:1,
                viewport:{x:40,y:40,scale:0.65}, connections:[], logs:[],
                nodes:[{id:'prompt',type:'prompt',text:'原始内容',x:0,y:0,w:300,h:200},
                    ...Array.from({length:300}, (_,i) => ({id:`image-${i}`,type:'image',x:(i%20)*330,y:300+Math.floor(i/20)*330,
                        w:280,h:260,url:`/assets/input/session-${i}.png`,natural_w:512,natural_h:512}))]
            });
            await page.route('**/api/canvases*', route => route.fulfill({json:{canvases:[...docs.values()]}}));
            await page.route('**/api/canvases/**', async route => {
                const req=route.request(), parts=new URL(req.url()).pathname.split('/'), id=parts[3];
                if(!docs.has(id)) return route.fulfill({json:{canvases:[]}});
                if(parts[4]==='meta') return route.fulfill({json:{id,updated_at:docs.get(id).updated_at}});
                if(parts[4]) return route.fulfill({json:{canvas:docs.get(id)}});
                if(req.method()==='PUT'){
                    saves++;
                    const data=req.postDataJSON();
                    if(holdNextSave){
                        holdNextSave=false;
                        await new Promise(resolve=>{releaseSave=resolve;});
                    }
                    // 模拟离开时保存仍在进行，不能被缓存淘汰。
                    await sleep(120);
                    docs.set(id,{...docs.get(id),...data,updated_at:docs.get(id).updated_at+1,revision:docs.get(id).revision+1});
                } else {
                    reads++;
                    if(holdNextRead){
                        holdNextRead=false;
                        const stale=structuredClone(docs.get(id));
                        // 即使旧响应声称时间戳更新，也不能覆盖请求发出后的本地编辑。
                        stale.updated_at+=100;
                        await new Promise(resolve=>{releaseRead=resolve;});
                        return route.fulfill({json:{canvas:stale}});
                    }
                }
                return route.fulfill({json:{canvas:docs.get(id)}});
            });
            await page.route('**/api/media-preview?*', async route => {
                mediaReads++;
                mediaUrls.push(route.request().url());
                await route.fulfill({contentType:'image/png',body:fs.readFileSync('static/assets/camera-reference/angle-eye-front.png')});
            });
            await page.route('**/api/account/me', route => route.fulfill({json:{account:{id:'fixture',account:'fixture',is_admin:false}}}));
            await page.addInitScript(() => localStorage.setItem('studio_active_page','canvas'));
            await page.goto(`${base}/static/${mode==='studio'?'index':'canvas-list'}.html`);
            if(mode==='studio') await page.evaluate(() => switchUI(null,'canvas'));
            const list = mode==='studio'
                ? await (await page.locator('#frame-canvas').elementHandle()).contentFrame() : page.mainFrame();
            await list.waitForFunction(() => typeof openCanvas === 'function');
            const open = async id => {
                await list.evaluate(id => openCanvas({id,project:'default'}),id);
                const frame = page.frames().find(f => f.url().includes(`/static/canvas.html?id=${id}&`));
                if(frame){ await frame.waitForFunction(() => window.CanvasSessionLifecycle?.state().id && !window.canvasEntryOverlay); return frame; }
                await page.waitForFunction(() => [...document.querySelectorAll('iframe')].some(f => f.src.includes('/static/canvas.html')));
                await sleep(50);
                const loaded=page.frames().find(f => f.url().includes(`canvas.html?id=${id}&`));
                await loaded.waitForFunction(() => window.CanvasSessionLifecycle?.state().id && !window.canvasEntryOverlay);
                return loaded;
            };
            const a = await open('a');
            await a.waitForFunction(() => document.querySelector('[data-id="image-0"] img')?.naturalWidth>0);
            await a.waitForFunction(() => !window.canvasEntryOverlay);
            // 首开只准备视口，低清预热后台执行；恢复不能重复下载已加载资源。
            await sleep(5000);
            await a.evaluate(() => {
                window.cacheDocument=document;
                window.cacheImage=document.querySelector('[data-id="image-0"] img');
                viewport={x:45,y:42,scale:0.65}; applyViewport(); scheduleViewportSave();
                selected.add('image-0');
                nodes.find(n=>n.id==='prompt').text='离开前修改'; scheduleSave();
                // 浏览器实际解码并播放 canvas 录制的视频，验证 DOM 和播放位置保留。
            });
            const videoBytes = await a.evaluate(async () => {
                const c=document.createElement('canvas'); c.width=64;c.height=64;
                const ctx=c.getContext('2d');ctx.fillStyle='#4387c9';ctx.fillRect(0,0,64,64);
                const stream=c.captureStream(10), recorder=new MediaRecorder(stream,{mimeType:'video/webm'}), chunks=[];
                let color=0;
                const draw=setInterval(()=>{ctx.fillStyle=`rgb(${color++%255},80,100)`;ctx.fillRect(0,0,64,64);},80);
                recorder.ondataavailable=e=>chunks.push(e.data);
                await new Promise(resolve=>{recorder.onstop=resolve;recorder.start();setTimeout(()=>recorder.stop(),600);});
                clearInterval(draw);
                stream.getTracks().forEach(t=>t.stop());
                return [...new Uint8Array(await new Blob(chunks,{type:'video/webm'}).arrayBuffer())];
            });
            await a.evaluate(async bytes => {
                const url=URL.createObjectURL(new Blob([new Uint8Array(bytes)],{type:'video/webm'}));
                const video=document.createElement('video'); video.src=url;video.muted=true;video.loop=true;
                document.querySelector('[data-id="image-0"]').appendChild(video);
                await video.play();window.cacheVideo=video;
            },videoBytes);
            await sleep(500);
            const before = {reads,mediaReads};
            const assertWarmMedia = () => {
                const known = new Set(mediaUrls.slice(0,before.mediaReads));
                const extra = mediaUrls.slice(before.mediaReads);
                assert.equal(new Set(extra).size,extra.length,'恢复期间不得重复请求同一媒体');
                assert(extra.every(url=>!known.has(url)),
                    '恢复允许首次后台预载和低清预热，不得重载已有图片');
            };
            await a.locator('#backToManagerBtn').click();
            await a.waitForFunction(() => canvasSessionSuspended && cacheVideo.paused);
            const pausedTime=await a.evaluate(()=>cacheVideo.currentTime);
            await sleep(3500); // 超过媒体驻留淘汰宽限期。
            assert.equal(await a.evaluate(()=>cacheVideo.currentTime),pausedTime);
            const start=Date.now();
            assert.equal(await open('a'),a);
            await a.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
            const warmMs=Date.now()-start;
            assert.deepEqual(await a.evaluate(()=>({
                document:document===cacheDocument,image:document.querySelector('[data-id="image-0"] img')===cacheImage,
                video:cacheVideo.isConnected,selected:selected.has('image-0'),viewport, text:nodes.find(n=>n.id==='prompt').text
            })),{document:true,image:true,video:true,selected:true,viewport:{x:45,y:42,scale:0.65},text:'离开前修改'});
            await sleep(500);
            assert.equal(reads,before.reads,'重复进入不请求整份工程');
            assertWarmMedia();
            assert.ok(saves>0); assert.equal(docs.get('a').nodes[0].text,'离开前修改');
            if(mode==='studio'){
                await page.evaluate(()=>{switchUI(null,'app-settings');switchUI(null,'canvas');});
                await sleep(500);
                assert.equal(await a.evaluate(()=>document.querySelector('[data-id="image-0"] img')===cacheImage),true);
                assertWarmMedia();
            }
            // 其他窗口的变更在返回时后台更新；无需阻塞第一帧。
            await a.locator('#backToManagerBtn').click();
            docs.get('a').nodes[0].text='外部已修改'; docs.get('a').updated_at++;
            await open('a');
            await a.waitForFunction(()=>nodes.find(n=>n.id==='prompt').text==='外部已修改');
            await a.evaluate(()=>{stopCanvasRemotePolling();document.activeElement.blur();});
            holdNextRead=true;
            await a.evaluate(()=>{window.delayedSync=syncRemoteCanvasNow();});
            await waitUntil(()=>releaseRead);
            await a.locator('[data-id="prompt"] [contenteditable="true"]').fill('刚刚输入的最新内容');
            await a.waitForFunction(()=>!localCanvasDirty && !savingCanvasNow);
            releaseRead();
            await a.evaluate(()=>window.delayedSync);
            assert.equal(await a.evaluate(()=>nodes.find(n=>n.id==='prompt').text),'刚刚输入的最新内容','旧 GET 不能覆盖已保存的新编辑');
            // PUT 进行中继续输入、离开、重进，旧保存响应也不能倒退当前状态。
            holdNextSave=true;
            await a.locator('[data-id="prompt"] [contenteditable="true"]').fill('第一步输入');
            await waitUntil(()=>releaseSave);
            await a.locator('[data-id="prompt"] [contenteditable="true"]').fill('第二步立即输入');
            await a.locator('#backToManagerBtn').click();
            await open('a');
            releaseSave();
            await a.waitForFunction(()=>!localCanvasDirty && !savingCanvasNow && !saveCanvasAgain);
            assert.equal(await a.evaluate(()=>nodes.find(n=>n.id==='prompt').text),'第二步立即输入');
            assert.equal(docs.get('a').nodes[0].text,'第二步立即输入');
            // 最近三个干净画布驻留，第四个淘汰最早实例。
            for(const id of ['b','c','d']){
                await page.evaluate(()=>{const f=document.querySelector('iframe[data-canvas-session-resident].active');if(f)CanvasSessionHost.back(f.contentWindow,'default');});
                await open(id);
            }
            await page.evaluate(()=>CanvasSessionHost.prune());
            assert.equal(page.frames().filter(f=>f.url().includes('/static/canvas.html')).length,3);
            assert.ok(a.isDetached(),'LRU 淘汰最早画布');
            // 所有旧实例都在保存/生成时，允许临时超出上限，不能丢弃操作。
            const b=await open('b');
            holdNextSave=true; releaseSave=null;
            await b.locator('[data-id="prompt"] [contenteditable="true"]').fill('仍在保存的最新内容');
            await waitUntil(()=>releaseSave);
            for(const id of ['c','d']){
                const frame=page.frames().find(f=>f.url().includes(`canvas.html?id=${id}&`));
                await frame.evaluate(()=>{nodes[0].running=true;});
            }
            await page.evaluate(()=>{const f=document.querySelector('iframe[data-canvas-session-resident].active');CanvasSessionHost.back(f.contentWindow,'default');});
            await open('a');
            assert.equal(page.frames().filter(f=>f.url().includes('/static/canvas.html')).length,4);
            assert.ok(!b.isDetached(),'保存中的实例不得淘汰');
            releaseSave();
            await b.waitForFunction(()=>!localCanvasDirty && !savingCanvasNow);
            await page.evaluate(()=>CanvasSessionHost.prune());
            assert.equal(page.frames().filter(f=>f.url().includes('/static/canvas.html')).length,3);
            assert.ok(b.isDetached(),'保存完成后收敛到驻留上限');
            await page.evaluate(()=>CanvasSessionHost.invalidate('a'));
            assert.equal(page.frames().filter(f=>f.url().includes('/static/canvas.html')).length,2);
            await page.evaluate(()=>CanvasSessionHost.clear());
            assert.equal(page.frames().filter(f=>f.url().includes('/static/canvas.html')).length,0);
            assert.deepEqual(errors,[]);
            results.push({mode,nodes:301,warmMs,reentryCanvasReads:0,reentryRepeatedMediaReads:0,saves});
            await page.close();
        }
        console.log(JSON.stringify(results,null,2));
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
