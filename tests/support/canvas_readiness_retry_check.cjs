const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base='http://127.0.0.1:3027';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/account/me',r=>r.fulfill({json:{account:{id:'retry-test',is_admin:true}}}));
  let calls=0;
  await page.route('**/api/projects',r=>{calls++;return calls===1?r.fulfill({status:503,json:{code:'account_database_busy'}}):r.fulfill({json:{projects:[]}});});
  await page.goto(base+'/static/canvas-list.html');
  await page.waitForFunction(()=>!window.canvasListEntryOverlay);
  assert(calls>=2,'暂时失败必须自动重试');
  let releaseOld,releaseNew;
  const oldGate=new Promise(r=>releaseOld=r),newGate=new Promise(r=>releaseNew=r);
  const png=await (await page.request.get(base+'/fixture.png')).body();
  await page.route('**/api/canvases/dynamic',r=>r.fulfill({json:{canvas:{id:'dynamic',nodes:[{id:'i',type:'image',url:'/assets/input/slow.png',x:0,y:0}],connections:[],updated_at:1}}}));
  await page.route('**/api/media-preview**',async r=>{await oldGate;await r.fulfill({body:png,contentType:'image/png'}).catch(()=>{});});
  await page.route('**/new-image.png',async r=>{await newGate;await r.fulfill({body:png,contentType:'image/png'});});
  await page.goto(base+'/static/canvas.html?id=dynamic');
  await page.waitForSelector('#nodes img');
  await page.evaluate(()=>{
   const old=document.querySelector('#nodes img'),img=new Image();img.src='/new-image.png';old.replaceWith(img);
  });
  releaseOld();await page.waitForTimeout(700);
  assert(await page.locator('#shell').evaluate(el=>el.inert),'重绘后的普通图片未完成时必须保持遮罩');
  releaseNew();await page.waitForFunction(()=>!window.canvasEntryOverlay);
  assert(await page.locator('#nodes img').evaluate(el=>el.complete&&el.naturalWidth>0));
  // 资源失败不能自动跳过；重试后成功才释放门禁。
  let fail=true;
  await page.route('**/api/media-preview**',r=>fail?r.fulfill({status:404,body:''}):r.fulfill({body:png,contentType:'image/png'}));
  await page.route('**/assets/input/slow.png',r=>r.fulfill({status:404,body:''}));
  await page.goto(base+'/static/canvas.html?id=dynamic');
  await page.getByRole('button',{name:'重试',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'继续进入',exact:true}).count(),0);
  assert(await page.locator('#shell').evaluate(el=>el.inert));
  fail=false;await page.getByRole('button',{name:'重试',exact:true}).click();
  await page.waitForFunction(()=>!window.canvasEntryOverlay);
  assert.deepEqual(errors,[]);
  console.log('PASS: automatic list retry, replaced DOM/plain image gate, failed media stays blocked, retry succeeds');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
