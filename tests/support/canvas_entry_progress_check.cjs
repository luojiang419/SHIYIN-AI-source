// 隔离工程与偏好；不读写用户数据、不调用生成 API。
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.argv[2] || 'http://127.0.0.1:3027';
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 let preferences={},revision=1;
 const errors=[];
 async function setup(){
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/account/me',r=>r.fulfill({json:{account:{id:'entry-test',is_admin:true}}}));
  await page.route('**/api/preferences',async r=>{
   if(r.request().method()==='PUT'){preferences=r.request().postDataJSON().values;revision++;}
   await r.fulfill({json:{values:preferences,revision,allowed_keys:['canvas_media_toolbar','canvas_quick_toolbar','theme']}});
  });
  await page.route('**/api/canvases/empty',r=>r.fulfill({json:{canvas:{id:'empty',title:'空画布',project:'default',nodes:[],connections:[],updated_at:1}}}));
  return {page,context};
 }
 try{
  let {page,context}=await setup();
  let release;const gate=new Promise(resolve=>release=resolve);
  await page.route('**/api/canvases/entry',async r=>{await sleep(450);await r.fulfill({json:{canvas:{id:'entry',title:'加载测试',project:'default',updated_at:1,viewport:{x:0,y:0,scale:1},connections:[],nodes:Array.from({length:12},(_,i)=>({id:`image-${i}`,type:'image',x:i*450,y:0,url:`/assets/input/entry-${i}.png`,w:300,h:300}))}}});});
  await page.route('**/api/media-preview**',async r=>{if(r.request().url().includes('entry-11'))await gate;else await sleep(100);const response=await page.request.get(base+'/fixture.png');await r.fulfill({body:await response.body(),contentType:'image/png'});});
  await page.goto(base+'/static/canvas.html?id=entry',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('.canvas-entry-progress [role=progressbar]')?.getAttribute('aria-valuenow')>35);
  assert.equal(await page.locator('#shell').evaluate(el=>el.inert),true);
  assert.equal(await page.locator('[data-entry-message]').textContent(),'正在进入画布中...');
  await page.screenshot({path:'.codex-tmp/canvas-entry-loading.png'});
  release();await page.waitForFunction(()=>!window.canvasEntryOverlay);
  assert.equal(await page.locator('#shell').evaluate(el=>el.inert),false);
  assert.equal(await page.locator('#nodes img[data-preview-state="loaded"]').count(),12);
  await page.evaluate(()=>{openCanvasSettings('media');saveCanvasPreferenceList(MEDIA_TOOLBAR_ITEMS_KEY,['download','edit']);});
  await page.waitForFunction(()=>window.RuntimeSync.state.values.canvas_media_toolbar==='["download","edit"]');
  assert.equal(preferences.canvas_media_toolbar,'["download","edit"]');
  await context.close();
  ({page,context}=await setup());
  await page.goto(base+'/static/canvas.html?id=empty',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>typeof openCanvasSettings==='function' && window.RuntimeSync?.state.ready);
  await page.evaluate(()=>openCanvasSettings('media'));
  assert.deepEqual(await page.locator('[data-canvas-setting-id]:checked').evaluateAll(els=>els.map(el=>el.dataset.canvasSettingId).sort()),['download','edit']);
  await page.evaluate(()=>saveCanvasPreferenceList(MEDIA_TOOLBAR_ITEMS_KEY,[]));
  await page.waitForFunction(()=>window.RuntimeSync.state.values.canvas_media_toolbar==='[]');
  await context.close();
  ({page,context}=await setup());
  await page.goto(base+'/static/canvas.html?id=empty',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>typeof openCanvasSettings==='function' && window.RuntimeSync?.state.ready);
  await page.evaluate(()=>openCanvasSettings('media'));
  assert.equal(await page.locator('[data-canvas-setting-id]:checked').count(),0);
  assert.deepEqual(errors,[]);
  console.log('PASS: slow progress, offscreen thumbnails, interaction gate, fresh-context preferences, empty selection, zero page errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
