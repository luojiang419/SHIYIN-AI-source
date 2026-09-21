// 隔离真实浏览器验证：请求时序、旧快照隔离、慢服务和单节点资源恢复。
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.argv[2] || 'http://127.0.0.1:3038';
const config={api_providers:[{id:'custom',image_models:['fixture'],video_models:['fixture']}],image_models:['fixture'],video_models:['fixture']};
const project={id:'cold',title:'冷启动验证',updated_at:1,connections:[],viewport:{x:0,y:0,scale:1},nodes:[
 {id:'img',type:'image',url:'/assets/input/cold.png',x:0,y:0,w:300,h:300},
 {id:'text',type:'prompt',prompt:'server text',x:400,y:0}
]};
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const report=[];
 try{
   for(const scenario of (process.env.CANVAS_TEST_SCENARIOS?.split(',') || ['shell-cache','list-cache','list-timeout','stale-canvas-snapshot','slow-assets','slow-capability','slow-media','failed-media','account-retry'])){
   const context=await browser.newContext({viewport:{width:1440,height:900}});
    const page=await context.newPage();const errors=[],requests=[],saves=[];let release,fail=true;
   if(process.env.CANVAS_TEST_SCRIPT) await page.route('**/static/js/canvas.js?*',r=>r.fulfill({contentType:'application/javascript',body:require('node:fs').readFileSync(process.env.CANVAS_TEST_SCRIPT)}));
   const gate=new Promise(resolve=>release=resolve);const started=Date.now();
   page.on('pageerror',e=>errors.push(e.message));
   page.on('request',r=>requests.push({url:r.url(),at:Date.now()-started}));
   let accountReads=0;
   await page.route('**/api/account/me',r=>{
    accountReads++;
    if(scenario==='account-retry' && accountReads===1)return r.fulfill({status:503,json:{detail:'busy'}});
    return r.fulfill({json:{account:{id:'cold-test',is_admin:true}}});
   });
   await page.route('**/api/runtime/config',r=>r.fulfill({json:config}));
   await page.route('**/api/projects',r=>r.fulfill({json:{projects:[{id:'default',name:'远程项目'}]}}));
   await page.route('**/api/canvases',r=>r.fulfill({json:{canvases:[{id:'remote',title:'远程工程',project:'default'}]}}));
   const data=structuredClone(project);
   if(scenario==='slow-capability') data.nodes.push({id:'h3',type:'video',apiProvider:'minimax-h3',model:'MiniMax H3',x:850,y:0});
   await page.route('**/api/canvases/cold',r=>{
    if(r.request().method()==='PUT'){saves.push(r.request().postDataJSON());Object.assign(data,saves.at(-1),{updated_at:2});return r.fulfill({json:{canvas:data}});}
    return r.fulfill({json:{canvas:data}});
   });
   const png=await(await page.request.get(base+'/fixture.png')).body();
   const serveMedia=async r=>{
    if(scenario==='slow-media') await gate;
    if(scenario==='failed-media' && fail)return r.fulfill({status:404,body:''});
    await r.fulfill({body:png,contentType:'image/png'}).catch(()=>{});
   };
   await page.route('**/api/media-preview**',serveMedia);
   await page.route('**/assets/input/cold.png',serveMedia);
   await page.route('**/api/canvas-assets/check',async r=>{if(scenario==='slow-assets')await gate;await r.fulfill({json:{exists:{'/assets/input/cold.png':true}}}).catch(()=>{});});
   await page.route('**/api/minimax-h3/status',async r=>{if(scenario==='slow-capability')await gate;await r.fulfill({json:{generation_enabled:true,resolutions:[],defaults:{}}}).catch(()=>{});});
    if(['shell-cache','list-cache'].includes(scenario)){
      const record=scenario==='shell-cache' ? {schema:1,value:{page:'ecommerce'}}
       :{schema:1,value:{projects:[{id:'stale',name:'旧缓存'}],canvases:[{id:'stale'}],currentProjectId:'stale',viewport:{x:0,y:0,scale:1}}};
    await page.addInitScript(()=>{window.__cacheGate=new Promise(resolve=>window.__releaseCache=resolve);});
    if(scenario==='shell-cache'){
     await page.addInitScript(()=>localStorage.setItem('studio_active_page','canvas'));
     await page.route('**/static/index.html',async r=>{const response=await r.fetch();await r.fulfill({response,body:(await response.text()).replace('preloadStudioFrames(id);','/* 隔离其他产品页面预热 */')});});
    }
    await page.route('**/static/js/studio-page-state.js*',async r=>{
     const response=await r.fetch();let body=await response.text();
      body=body.replace('let initial=readInitial();',`let initial=readInitial();if(${scenario==='shell-cache' ? "name==='shell'" : 'true'}) initial.promise=window.__cacheGate.then(()=>(${JSON.stringify(record)}));`);
      await r.fulfill({response,body});
     });
    }
    if(scenario==='stale-canvas-snapshot'){
     const stale={schema:1,value:{canvas:{...structuredClone(data),nodes:[{id:'text',type:'prompt',prompt:'stale cached text',x:400,y:0}]},config,dirty:true,selected:[]}};
     await page.goto(base+'/fixture.png');
     await page.evaluate(record=>new Promise((resolve,reject)=>{
      const req=indexedDB.open('shiyin-page-state-v1',1);
      req.onupgradeneeded=()=>req.result.createObjectStore('pages');
      req.onerror=()=>reject(req.error);
      req.onsuccess=()=>{const db=req.result,tx=db.transaction('pages','readwrite');tx.objectStore('pages').put(record,'cold-test:canvas:cold');tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};
     }),stale);
    }
   if(scenario==='list-timeout')await page.addInitScript(()=>{
    const originalFetch=window.fetch,originalTimer=window.setTimeout;
    window.__listCalls=0;
    window.setTimeout=(callback,delay,...args)=>originalTimer(callback,delay===15000?150:delay,...args);
    window.fetch=(url,options)=>['/api/projects','/api/canvases'].includes(url)
     ? new Promise((resolve,reject)=>{window.__listCalls++;options.signal.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')),{once:true});})
     : originalFetch(url,options);
   });
   await page.goto(base+(scenario==='shell-cache'?'/static/index.html':scenario.startsWith('list-')?'/static/canvas-list.html':'/static/canvas.html?id=cold'),{waitUntil:'domcontentloaded'});
   if(scenario==='list-timeout'){
    await page.waitForFunction(()=>window.__listCalls>=4,null,{timeout:2500});
    assert.equal(await page.getByText('画布列表加载失败，请重试。',{exact:true}).count(),0,'暂时超时不应显示错误');
    assert(await page.getByText('本地服务正在启动，画布列表将自动恢复',{exact:true}).count());
   }else if(scenario==='shell-cache'){
    await page.waitForFunction(()=>document.getElementById('frame-canvas')?.contentWindow?.canvasListEntryOverlay===null);
    assert(requests.some(r=>r.url.endsWith('/api/canvases')),'工作台快照不能阻塞目标页请求');
    await page.evaluate(()=>window.__releaseCache());await page.waitForTimeout(200);
    assert(await page.locator('#frame-canvas').evaluate(el=>el.classList.contains('active')),'晚到工作台偏好不能切走当前页面');
   }else if(scenario==='list-cache'){
    await page.waitForFunction(()=>!window.canvasListEntryOverlay);
    assert(requests.some(r=>r.url.endsWith('/api/canvases')),'缓存等待期间必须已请求服务器列表');
    await page.evaluate(()=>window.__releaseCache());await page.waitForTimeout(200);
    assert(await page.getByText('远程工程',{exact:true}).count());
    assert.equal(await page.getByText('旧缓存',{exact:true}).count(),0);
    }else if(scenario==='stale-canvas-snapshot'){
     await page.waitForFunction(()=>!document.getElementById('shell').inert);
     assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='text').prompt),'server text','旧 IndexedDB 快照不得覆盖服务端工程');
     await page.waitForFunction(async()=>new Promise(resolve=>{
      const req=indexedDB.open('shiyin-page-state-v1');
      req.onsuccess=()=>{const db=req.result,read=db.transaction('pages').objectStore('pages').get('cold-test:canvas:cold');read.onsuccess=()=>{db.close();resolve(!read.result);};};
     }));
   }else if(scenario==='account-retry'){
    await page.waitForFunction(()=>!document.getElementById('shell').inert || window.canvasEntryOverlay?.el.querySelector('button'));
    if(await page.locator('.canvas-entry-progress').count()) await page.getByRole('button',{name:'重试',exact:true}).click();
    await page.waitForFunction(()=>!document.getElementById('shell').inert);
    assert(accountReads>=2,'账号预检暂时失败后可以重试');
    }else{
    await page.waitForFunction(()=>!document.getElementById('shell').inert,{},{timeout:3500});
    assert.equal(await page.locator('#shell').evaluate(el=>el.inert),false);
    if(scenario==='slow-media'){
     await page.getByText('1 项资源加载中…',{exact:true}).waitFor();
     await page.screenshot({path:'.codex-tmp/canvas-cold-pending.png'});
    }
    if(scenario==='failed-media'){
     const retry=page.getByRole('button',{name:'1 项资源加载失败 · 重试',exact:true});
     await retry.waitFor();assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='img').url),'/assets/input/cold.png');
     fail=false;await retry.click();
     await page.waitForFunction(()=>document.querySelector('#nodes img')?.naturalWidth>0 && !document.querySelector('.canvas-resource-notice'));
    }
    release();
    if(scenario==='slow-media')await page.waitForFunction(()=>!document.querySelector('.canvas-resource-notice'));
   }
   report.push({scenario,elapsedMs:Date.now()-started,firstMediaMs:requests.find(r=>r.url.includes('/api/media-preview'))?.at,pageErrors:errors});
   assert.deepEqual(errors,[]);release();await context.close();
  }
 }finally{await browser.close();}
 console.log(JSON.stringify(report,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
