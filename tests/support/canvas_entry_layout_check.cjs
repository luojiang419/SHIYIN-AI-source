// 使用隔离 fixture，阻塞屏幕外媒体与低清缓存，验证入口不被它们拖住。
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.argv[2] || 'http://127.0.0.1:3027';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 let releaseVisible,releaseBackground;
 const visibleGate=new Promise(r=>releaseVisible=r),backgroundGate=new Promise(r=>releaseBackground=r);
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  if(process.env.CANVAS_TEST_SCRIPT) await page.route('**/static/js/canvas.js?*',r=>r.fulfill({contentType:'application/javascript',body:fs.readFileSync(process.env.CANVAS_TEST_SCRIPT)}));
  const png=await (await page.request.get(base+'/fixture.png')).body();
  let backgroundRequests=0;
  await page.route('**/api/account/me',r=>r.fulfill({json:{account:{id:'entry-layout',is_admin:true}}}));
  await page.route('**/api/canvases/entry-layout',r=>r.fulfill({json:{canvas:{id:'entry-layout',updated_at:1,viewport:{x:20,y:20,scale:1},connections:[],nodes:[
   {id:'visible',type:'image',url:'/assets/input/visible.png',x:0,y:0,w:260,h:300},
   ...Array.from({length:300},(_,i)=>({id:`off-${i}`,type:'image',url:`/assets/input/off-${i}.png`,x:8000+(i%20)*320,y:Math.floor(i/20)*350,w:260,h:300}))
  ]}}}));
  await page.route('**/api/minimax-h3/status',async r=>{await backgroundGate;await r.fulfill({json:{generation_enabled:true}}).catch(()=>{});});
  await page.route('**/api/media-preview**',async r=>{
   const q=new URL(r.request().url()).searchParams;
   if(q.get('url')==='/assets/input/visible.png' && q.get('w')!=='96') await visibleGate;
   else {backgroundRequests++;await backgroundGate;}
   await r.fulfill({body:png,contentType:'image/png'}).catch(()=>{});
  });
  await page.goto(base+'/static/canvas.html?id=entry-layout');
  await page.waitForSelector('[data-id="visible"] img');
  assert(await page.locator('#shell').evaluate(e=>e.inert),'可见图片未加载前必须保留门禁');
  const start=Date.now();releaseVisible();
  await page.waitForFunction(()=>!window.canvasEntryOverlay,null,{timeout:4500});
  const entryMs=Date.now()-start;
  assert(await page.locator('[data-id="visible"] img').evaluate(e=>e.complete&&e.naturalWidth>0));
  await page.evaluate(()=>{stopCanvasRemotePolling();});
  await page.locator('[data-id="visible"] img').hover();
  assert.equal(await page.locator('[data-id="visible"] [data-image-node-prompt-panel]').count(),0,'hover 不应创建面板');
  await page.locator('[data-id="visible"] img').click();
  await page.locator('[data-id="visible"] [data-image-node-prompt-panel]').waitFor({state:'visible'});
  await page.mouse.click(1100,800);
  await page.waitForFunction(()=>!document.querySelector('[data-id="visible"] [data-image-node-prompt-panel]'));
  releaseBackground();
  const layout=await page.evaluate(()=>{
   nodes.push({id:'out',type:'output',x:6000,y:5000,images:Array.from({length:13},(_,i)=>({url:`/assets/input/batch-${i}.png`,kind:'image'}))});
   nodes.push({id:'batch',type:'batchGenerator',x:350,y:0,w:480,h:100,apiProvider:'custom',model:'private-image'});
   connections.push({id:'batch-link',from:'out',to:'batch'});render();
   const el=document.querySelector('[data-id="batch"]'),list=el.querySelector('.input-list');
   const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,bottom:r.bottom,width:r.width};};
   return {refs:batchGeneratorImageRefs(nodes.find(n=>n.id==='batch')).length,items:[...list.children].map(rect),list:rect(list),bottom:rect(el.querySelector('.node-bottom-controls')),frame:rect(el),run:rect(el.querySelector('.gen-btn')),overflow:list.scrollWidth-list.clientWidth,sized:el.classList.contains('sized')};
  });
  assert.equal(layout.refs,13);assert.equal(layout.items.length,13);
  assert.equal(layout.items[0].y,layout.items[5].y);assert(layout.items[6].y>layout.items[0].y);
  assert.equal(layout.items[0].x,layout.items[6].x);assert(layout.items[12].y>layout.items[6].y);
  assert(layout.overflow<=1,'缩略图不能横向溢出');
  assert(layout.bottom.y>=layout.list.bottom-1,'参数区不得被图片挤压覆盖');
  assert(layout.run.bottom<=layout.frame.bottom+1,'运行按钮必须在框架内');
  assert.equal(layout.sized,false,'旧固定小高度不能裁切批量功能区');
  await page.waitForFunction(()=>[...document.querySelectorAll('[data-id="batch"] img')].every(img=>img.complete&&img.naturalWidth>0));
  if(process.env.CANVAS_TEST_SCREENSHOT) await page.screenshot({path:process.env.CANVAS_TEST_SCREENSHOT});
  await page.evaluate(()=>{viewport={x:-7980,y:20,scale:1};applyViewport();scheduleClassicMediaQueue();});
  await page.waitForFunction(()=>document.querySelector('[data-id="off-0"] img')?.naturalWidth>0);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({entryMs,backgroundRequests,refs:layout.refs,rows:3,hover:false,clickPanel:true,errors},null,2));
 }finally{releaseVisible();releaseBackground();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
