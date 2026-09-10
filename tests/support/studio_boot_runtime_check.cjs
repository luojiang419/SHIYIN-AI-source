// 隔离浏览器使用后端 AccountIdentity.public() 的真实数据，不访问用户服务。
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const accounts=JSON.parse(process.env.STUDIO_TEST_ACCOUNTS);
const root=path.resolve(process.env.STUDIO_TEST_WEB_ROOT || 'static');
const origin='http://studio.test';

(async()=>{
    const browser=await chromium.launch({headless:true,channel:'msedge'});
    const results=[];
    async function scenario(name,account,mode='normal'){
        const context=await browser.newContext();
        const page=await context.newPage();
        let activeAccount=account,failAccount=mode==='retry';
        await page.route('**/*',async route=>{
            const url=new URL(route.request().url());
            if(url.origin!==origin)return route.abort();
            if(url.pathname==='/api/account/me')return route.fulfill({status:failAccount?503:200,json:failAccount?{detail:'fixture unavailable'}:{account:activeAccount}});
            if(url.pathname.startsWith('/api/'))return route.fulfill({json:{}});
            if(url.pathname==='/state-harness')return route.fulfill({contentType:'text/html',body:'<script src="/static/js/studio-page-state.js"></script>'});
            const file=path.resolve(root,url.pathname==='/'?'index.html':url.pathname.replace(/^\/static\//,''));
            if(!file.startsWith(root+path.sep))return route.abort();
            if(file.endsWith('.html') && file!==path.join(root,'index.html'))return route.fulfill({contentType:'text/html',body:'<p>Fixture workspace ready</p>'});
            if(!fs.existsSync(file))return route.fulfill({status:404,body:''});
            const mime=file.endsWith('.js')?'text/javascript':file.endsWith('.html')?'text/html':file.endsWith('.css')?'text/css':'application/octet-stream';
            return route.fulfill({contentType:mime,body:fs.readFileSync(file)});
        });
        await page.addInitScript(mode=>{
            window.WebSocket=class {addEventListener(){} close(){}};
            if(mode==='open-stalled')Object.defineProperty(window,'indexedDB',{value:{open:()=>({})}});
            if(mode==='storage-denied')Object.defineProperty(window,'indexedDB',{get(){throw new Error('storage denied');}});
            if(mode==='transaction-stalled')Object.defineProperty(window,'indexedDB',{value:{open(){
                const request={};setTimeout(()=>{
                    request.result={close(){},transaction(){return {objectStore(){return {get(){return {};},put(){return {};}};},abort(){this.onabort?.();}};}};
                    request.onsuccess();
                },0);return request;
            }}});
            if(mode==='restore-throws'){
                let state;
                Object.defineProperty(window,'StudioPageState',{get:()=>state,set(value){
                    state=value;const session=value.session;
                    value.session=name=>{const api=session(name);if(name==='shell')api.restore=async()=>{throw new Error('broken snapshot');};return api;};
                }});
            }
        },mode);
        try{
            await page.goto(origin+'/',{waitUntil:'domcontentloaded'});
            if(failAccount){
                await page.locator('#studio-boot-retry').waitFor({state:'visible'});
                assert.equal(await page.evaluate(()=>studioBootInFlight),false);
                failAccount=false;
                await page.locator('#studio-boot-retry').click();
            }
            await page.waitForFunction(()=>!document.documentElement.classList.contains('studio-route-booting') && !studioBootInFlight,null,{timeout:8000});
            assert.equal(await page.evaluate(()=>StudioPageState.accountId),account.account_id || '');
            assert.equal(await page.locator('iframe.active').count(),1);
            if(mode==='normal' && account.account_id){
                await page.evaluate(async()=>{const s=StudioPageState.session('contract');s.save({draft:'account draft'});await s.flush();});
                await page.reload({waitUntil:'domcontentloaded'});
                await page.waitForFunction(()=>!studioBootInFlight && StudioPageState.accountId);
                assert.equal(await page.evaluate(async()=>(await StudioPageState.session('contract').read()).draft),'account draft');
                activeAccount=accounts.find(item=>item.account_id!==account.account_id);
                await page.reload({waitUntil:'domcontentloaded'});
                await page.waitForFunction(()=>!studioBootInFlight && StudioPageState.accountId);
                assert.equal(await page.evaluate(()=>StudioPageState.session('contract').read()),null);
                // 独立页面自行验证账号也必须使用相同的真实账号字段。
                await page.goto(origin+'/state-harness');
                assert.equal(await page.evaluate(()=>StudioPageState.ready()),activeAccount.account_id);
            }
            results.push(name);
        }finally{await context.close();}
    }
    try{
        for(const account of accounts)await scenario(account.role+' contract, cold restore and isolation',account);
        for(const mode of ['open-stalled','transaction-stalled','storage-denied','restore-throws','retry'])await scenario(mode,accounts[0],mode);
        await scenario('missing account identifier safely disables cache',{account:'fixture',role:'user',is_admin:false});
        console.log(JSON.stringify({passed:results},null,2));
    }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
