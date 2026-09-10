// 浏览器真实 IndexedDB + 业务页面；只使用内存接口，不访问用户数据或生成服务。
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const base=process.argv[2] || 'http://127.0.0.1:3027';
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const png=fs.readFileSync('static/assets/camera-reference/angle-eye-front.png');

async function fixture(page){
    let account='account-a',blocked=false,releases=[];
    const provider={id:'custom',name:'Fixture API',base_url:'https://fixture.invalid',protocol:'openai',enabled:true,
        chat_models:['private-chat'],image_models:['private-image'],video_models:['private-video'],has_key:true};
    const records={
        '/api/providers':{providers:[provider]},
        '/api/runtime/providers':{providers:[provider]},
        '/api/conversations':{conversations:[]},
        '/api/asset-library':{library:{libraries:[{id:'default',name:'Fixture Library',categories:[{id:'photos',name:'Fixture Photos',type:'image',items:[{id:'image-a',name:'asset.png',url:'/fixture.png'}]}]}]}},
        '/api/works':{works:Array.from({length:40},(_,i)=>({id:`w${i}`,name:`work-${i}.png`,url:'/fixture.png',media_type:'image',kind:'image',created_at:i+1})),total:40,next_cursor:''},
        '/api/ecommerce/capabilities':{providers:[provider],models:[],routes:{},reference_slot_types:[]},
    };
    await page.route('**/api/**',async route=>{
        const request=route.request(), path=new URL(request.url()).pathname;
        if(path==='/api/account/me')return route.fulfill({json:{account:{id:account,account,is_admin:true}}});
        if(path==='/api/media-preview')return route.fulfill({contentType:'image/png',body:png});
        if(path==='/api/person-depth/estimate')return route.fulfill({contentType:'image/png',body:png});
        let response;
        if(records[path]){
            if(request.method()==='PUT' && path==='/api/providers')records[path]={providers:request.postDataJSON()};
            response={json:structuredClone(records[path])};
        } else {
            const fetched=await route.fetch();
            response={response:fetched};
        }
        if(blocked)await new Promise(resolve=>releases.push(resolve));
        await route.fulfill(response).catch(()=>{});
    });
    return {block(){blocked=true;},release(){blocked=false;releases.splice(0).forEach(resolve=>resolve());},account(id){account=id;}};
}
async function checkpoint(page,name){
    await page.evaluate(name=>{window.StudioPageState.session(name).checkpoint();},name);
    await page.waitForFunction(async name=>{
        const db=await new Promise(resolve=>{const r=indexedDB.open('shiyin-page-state-v1');r.onsuccess=()=>resolve(r.result);});
        return new Promise(resolve=>{const r=db.transaction('pages').objectStore('pages').get(`account-a:${name}`);r.onsuccess=()=>resolve(Boolean(r.result));});
    },name);
    await sleep(100);
}

(async()=>{
    const browser=await chromium.launch({headless:true,channel:'msedge'});
    const results=[];
    try {
        // 公共层：最新写入、对象隔离、删除、账号切换与旧恢复失效。
        {
            const page=await browser.newPage();await fixture(page);
            await page.route('**/state-harness',route=>route.fulfill({contentType:'text/html',body:'<meta charset="utf-8"><script src="/static/js/studio-page-state.js"></script><input id="draft">'}));
            await page.goto(`${base}/state-harness`);
            const checks=await page.evaluate(async()=>{
                await StudioPageState.ready();
                const session=StudioPageState.session('core-test');
                const object={draft:'first'};session.save(object);object.draft='mutated outside';
                const isolated=(await session.read()).draft==='first';
                for(let i=0;i<20;i++)session.save({draft:`latest-${i}`});
                const latest=(await session.read()).draft==='latest-19';
                const valid=session.guard();session.mark();const staleIgnored=!valid();
                await session.flush();
                StudioPageState.configure({id:'account-b'});
                const separated=await StudioPageState.session('core-test').read()===null;
                StudioPageState.configure({id:'account-a'});
                const resumed=StudioPageState.session('core-test');
                const persisted=(await resumed.read())?.draft==='latest-19';
                await resumed.remove();resumed.save({draft:'cannot resurrect'});
                const deleted=await StudioPageState.session('core-test').read()===null;
                return {isolated,latest,staleIgnored,separated,persisted,deleted};
            });
            assert.ok(Object.values(checks).every(Boolean),JSON.stringify(checks));
            results.push({page:'state-core',...checks});await page.close();
        }
        const cases=[
            ['works','#worksSearch','第一次作品筛选','最新作品筛选'],
            ['gpt-chat','#messageInput','退出前草稿','冷启动立即输入的新草稿'],
            ['asset-manager','#assetSearch','原始素材筛选','最新素材筛选'],
            ['api-settings','#nameInput','离开前平台名','立即编辑的新平台名'],
            ['api-settings','#linkfoxGatewayInput','https://old-fixture.invalid','https://latest-fixture.invalid'],
            ['app-settings','#shortcutSearch','复制','粘贴'],
        ];
        for(const [name,selector,oldValue,newValue] of cases.filter(item=>!process.env.WORKSPACE_CASES || process.env.WORKSPACE_CASES.split(',').includes(item[0]))){
            const page=await browser.newPage({viewport:{width:1440,height:980}}), errors=[];
            page.on('pageerror',error=>errors.push(error.message));
            const api=await fixture(page);
            await page.goto(`${base}/static/${name}.html`);
            if(name==='api-settings'){
                await page.waitForFunction(()=>typeof providers!=='undefined' && providers.some(p=>p.id==='custom'));
                await page.evaluate(id=>selectProvider(id),selector==='#nameInput'?'custom':'linkfox');
                if(selector==='#nameInput')await page.locator('#keyInput').fill('fixture-secret-never-persist');
            }
            await page.locator(selector).fill(oldValue);
            await sleep(850);
            await checkpoint(page,name);
            if(name==='api-settings'){
                assert.equal(await page.evaluate(async()=>JSON.stringify(await StudioPageState.session('api-settings').read()).includes('fixture-secret-never-persist')),false);
            }
            api.block();
            await page.reload({waitUntil:'domcontentloaded'});
            const start=Date.now();
            await page.waitForFunction(({selector,value})=>document.querySelector(selector)?.value===value,{selector,value:oldValue},{timeout:3000});
            const restoreMs=Date.now()-start;
            const navigationToInteractiveMs=await page.evaluate(()=>Math.round(performance.now()));
            if(process.env.WORKSPACE_DEBUG && name==='api-settings')console.log(await page.evaluate(()=>({selectedId,provider:provider()?.id,ids:providers.map(p=>({id:p.id,virtual:p.is_virtual})),recommendInlineOpen,body:document.body.className,dirty:apiPageDirty})));
            await page.locator(selector).fill(newValue); // 所有业务读取仍未返回，页面已可编辑。
            api.release();
            await sleep(1100);
            assert.equal(await page.locator(selector).inputValue(),newValue,`${name}: 旧返回值覆盖新输入`);
            await checkpoint(page,name);
            if(name==='gpt-chat'){
                api.account('account-b');
                await page.reload();await sleep(300);
                assert.equal(await page.locator(selector).inputValue(),'','B 不得恢复 A 的草稿');
                api.account('account-a');api.block();await page.reload({waitUntil:'domcontentloaded'});
                await page.waitForFunction(value=>document.querySelector('#messageInput').value===value,newValue);
                api.release();
            }
            assert.deepEqual(errors,[],name);
            results.push({page:name,coldRestoreMs:restoreMs,navigationToInteractiveMs,editableBeforeNetwork:true,staleResponseProtected:true});
            console.log('cold restore passed:',name);
            await page.close();
        }
        if(process.env.WORKSPACE_CASES){console.log(JSON.stringify(results));return;}
        // 存储不可用不阻塞原始页面，内存中仍保持最新操作。
        {
            const page=await browser.newPage();await fixture(page);const errors=[];
            page.on('pageerror',error=>errors.push(error.message));
            await page.addInitScript(()=>Object.defineProperty(window,'indexedDB',{value:null}));
            await page.goto(`${base}/static/gpt-chat.html`);
            await page.locator('#messageInput').fill('存储不可用时仍可操作');
            await sleep(200);
            assert.equal(await page.locator('#messageInput').inputValue(),'存储不可用时仍可操作');
            assert.deepEqual(errors,[]);results.push({page:'storage-fallback',usable:true});await page.close();
        }
        // 真正退出浏览器进程，再以相同独立 profile 启动；验证磁盘持久化而非文档内存。
        {
            const profile=fs.mkdtempSync(path.join(os.tmpdir(),'shiyin-state-cold-'));
            let context;
            try {
                context=await chromium.launchPersistentContext(profile,{headless:true,channel:'msedge'});
                let page=await context.newPage();await fixture(page);
                await page.goto(`${base}/static/gpt-chat.html`);
                await page.locator('#messageInput').fill('浏览器进程退出后保留的草稿');
                await page.evaluate(()=>StudioPageState.flushAll());await context.close();context=null;
                const started=Date.now();
                context=await chromium.launchPersistentContext(profile,{headless:true,channel:'msedge'});
                page=await context.newPage();const api=await fixture(page);api.block();
                await page.goto(`${base}/static/gpt-chat.html`,{waitUntil:'domcontentloaded'});
                await page.waitForFunction(()=>document.querySelector('#messageInput').value==='浏览器进程退出后保留的草稿');
                await page.locator('#messageInput').fill('进程冷启动后立即编辑');
                results.push({page:'process-cold-start',restoredFromDisk:true,processToEditableMs:Date.now()-started});
                api.release();
            } finally {
                if(context)await context.close();
                const resolved=fs.realpathSync(profile),root=fs.realpathSync(os.tmpdir());
                if(path.dirname(resolved)===root && path.basename(resolved).startsWith('shiyin-state-cold-'))fs.rmSync(resolved,{recursive:true,force:true});
            }
        }
        // 电商参数通过原有业务快照保存，后台恢复旧任务不得重置最新参数。
        {
            const page=await browser.newPage(), api=await fixture(page), errors=[];
            page.on('pageerror',error=>errors.push(error.message));
            await page.goto(`${base}/static/ecommerce.html`);
            await page.waitForFunction(()=>window.EcommerceStudio && !EcommerceStudio.state.initializing);
            await page.evaluate(()=>{EcommerceStudio.state.zoom=1.6;EcommerceStudio.state.compareValue=37;EcommerceStudio.persistSettings();});
            await checkpoint(page,'ecommerce');api.block();await page.reload({waitUntil:'domcontentloaded'});
            await page.waitForFunction(()=>window.EcommerceStudio?.state.zoom===1.6 && !EcommerceStudio.state.initializing);
            await page.evaluate(()=>{EcommerceStudio.state.zoom=2.1;EcommerceStudio.persistSettings();});
            api.release();await sleep(1000);
            assert.equal(await page.evaluate(()=>EcommerceStudio.state.zoom),2.1);
            await checkpoint(page,'ecommerce');api.account('account-b');await page.reload();
            await page.waitForFunction(()=>window.EcommerceStudio && !EcommerceStudio.state.initializing);
            assert.equal(await page.evaluate(()=>EcommerceStudio.state.zoom),1,'B 不得导入 A 的旧全局电商设置');
            assert.deepEqual(errors,[]);results.push({page:'ecommerce',restored:true});await page.close();
        }
        // 深度工具冷启动恢复源文件和已计算结果，不重复运行模型。
        {
            const page=await browser.newPage(),api=await fixture(page);
            await page.goto(`${base}/static/depth-map-tuner.html`);
            await page.locator('#depthInputFile').setInputFiles({name:'fixture.png',mimeType:'image/png',buffer:png});
            await page.waitForFunction(()=>!document.getElementById('depthOutputCanvas').hidden);
            await page.locator('[data-depth-field="brightness"]').first().evaluate(input=>{input.value='31';input.dispatchEvent(new Event('input',{bubbles:true}));});
            await checkpoint(page,'depth-map-tuner');api.block();await page.reload({waitUntil:'domcontentloaded'});
            await page.waitForFunction(()=>!document.getElementById('depthOutputCanvas').hidden && document.querySelector('[data-depth-field="brightness"]').value==='31');
            api.release();results.push({page:'depth-map-tuner',restoredFileAndResult:true});await page.close();
        }
        // 画布冷启动使用最近数据和配置，在启动 GET 被阻塞时仍能修改节点。
        {
            const page=await browser.newPage(),api=await fixture(page);
            await page.goto(`${base}/static/canvas.html?id=workspace-cold`);
            const input=page.locator('[data-id="prompt"] [contenteditable="true"]');
            await input.fill('冷启动前的节点');await page.waitForFunction(()=>!localCanvasDirty && !savingCanvasNow);
            await checkpoint(page,'canvas:workspace-cold');api.block();await page.reload({waitUntil:'domcontentloaded'});
            await page.waitForFunction(()=>typeof nodes!=='undefined' && nodes.find(n=>n.id==='prompt')?.text==='冷启动前的节点');
            await input.fill('网络返回前的新节点输入');api.release();await sleep(800);
            assert.equal(await input.innerText(),'网络返回前的新节点输入');
            results.push({page:'canvas',editableBeforeNetwork:true});await page.close();
        }
        // 主框架全部页面热驻留，超过旧 15 分钟回收阈值也不销毁文档。
        {
            const page=await browser.newPage(),api=await fixture(page);
            await page.goto(`${base}/static/index.html`);
            await page.waitForFunction(()=>typeof currentStudioAccount!=='undefined' && currentStudioAccount?.id);
            await page.evaluate(()=>pauseStudioFramePreload('test'));
            for(const id of ['ecommerce','gpt-chat','canvas','asset-manager','works','api-settings','app-settings','depth-map-tuner']){
                await page.evaluate(id=>switchUI(null,id),id);
                const frame=await (await page.locator(`#frame-${id}`).elementHandle()).contentFrame();
                await frame.waitForURL(url=>url.pathname.startsWith('/static/'));
                await frame.waitForLoadState('domcontentloaded');
                await frame.evaluate(()=>{window.retainedDocument=document;});
            }
            await page.evaluate(()=>{
                document.querySelectorAll('iframe').forEach(frame=>{frame.dataset.lastActiveAt='1';});
                maybeUnloadIdleFrames();
            });
            for(const id of ['ecommerce','gpt-chat','canvas','asset-manager','works','api-settings','app-settings','depth-map-tuner']){
                await page.evaluate(id=>switchUI(null,id),id);
                const frame=await (await page.locator(`#frame-${id}`).elementHandle()).contentFrame();
                assert.equal(await frame.evaluate(()=>document===window.retainedDocument),true,id);
            }
            await page.evaluate(()=>switchUI(null,'canvas'));
            const manager=await (await page.locator('#frame-canvas').elementHandle()).contentFrame();
            await manager.waitForFunction(()=>typeof openCanvas==='function');
            await manager.evaluate(()=>openCanvas({id:'workspace-shell',project:'default'}));
            await page.waitForFunction(()=>document.getElementById('frame-canvas')?.contentWindow?.CanvasSessionLifecycle?.state().id==='workspace-shell');
            const editor=await (await page.locator('#frame-canvas').elementHandle()).contentFrame();
            await editor.locator('[data-id="prompt"] [contenteditable="true"]').fill('最后离开的实际画布');
            await editor.waitForFunction(()=>!localCanvasDirty && !savingCanvasNow);
            await checkpoint(page,'shell');api.block();await page.reload({waitUntil:'domcontentloaded'});
            await page.waitForFunction(()=>document.getElementById('frame-canvas')?.contentWindow?.CanvasSessionLifecycle?.state().id==='workspace-shell');
            const coldEditor=await (await page.locator('#frame-canvas').elementHandle()).contentFrame();
            assert.equal(await coldEditor.locator('[data-id="prompt"] [contenteditable="true"]').innerText(),'最后离开的实际画布');
            results.push({page:'shell',retainedPages:8,coldRestoresLastCanvas:true});api.release();await page.close();
        }
        console.log(JSON.stringify(results,null,2));
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
