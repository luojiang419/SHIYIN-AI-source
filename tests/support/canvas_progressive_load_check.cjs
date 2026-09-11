const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.argv[2] || 'http://127.0.0.1:3027';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 let release;const gate=new Promise(r=>release=r);
 try{
  const page=await browser.newPage({viewport:{width:1200,height:850}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  if(process.env.CANVAS_TEST_SCRIPT) await page.route('**/static/js/canvas.js?*',r=>r.fulfill({contentType:'application/javascript',body:require('node:fs').readFileSync(process.env.CANVAS_TEST_SCRIPT)}));
  const png=await (await page.request.get(base+'/fixture.png')).body(),requested=[];
  await page.route('**/api/account/me',r=>r.fulfill({json:{account:{id:'progressive',is_admin:true}}}));
  await page.route('**/api/canvases/progressive',r=>r.fulfill({json:{canvas:{id:'progressive',updated_at:1,viewport:{x:20,y:20,scale:1},connections:[],nodes:[
   {id:'front',type:'image',url:'/assets/input/front.png',x:0,y:0,w:250,h:300},
   ...Array.from({length:24},(_,i)=>({id:`far-${i}`,type:'image',url:`/assets/input/far-${i}.png`,x:8000+i*1500,y:0,w:250,h:300}))
  ]}}}));
  await page.route('**/api/media-preview**',async r=>{
   const params=new URL(r.request().url()).searchParams,url=params.get('url');
   if(url.includes('far-') && params.get('w')!=='96'){requested.push(url);await gate;}
   await r.fulfill({body:png,contentType:'image/png'}).catch(()=>{});
  });
  await page.goto(base+'/static/canvas.html?id=progressive');
  await page.waitForFunction(()=>!window.canvasEntryOverlay,null,{timeout:5000});
  await page.waitForFunction(()=>ensureClassicMediaQueue().snapshot().activeTotal===2,null,{timeout:3000});
  assert.equal(requested.length,2,'不移动视口也应自动加载远处图片，且背景最多两路');
  const priorityRequest=page.waitForRequest(r=>new URL(r.url()).searchParams.get('url')==='/assets/input/far-23.png',{timeout:3000});
  await page.evaluate(()=>{viewport={x:-(8000+23*1500)+20,y:20,scale:1};applyViewport();scheduleClassicMediaQueue();});
  await page.waitForFunction(()=>document.querySelector('[data-id="far-23"] img')?.dataset.previewState==='loading',null,{timeout:3000});
  await priorityRequest;
  release();
  await page.waitForFunction(()=>[...document.querySelectorAll('#nodes img[data-preview-src]')].every(img=>['loaded','evicted'].includes(img.dataset.previewState)),null,{timeout:15000});
  assert.equal(new Set(requested).size,24,'未访问区域也必须自动完成加载');
  assert.equal(requested.length,24,'首次预载不重复请求');
  assert.deepEqual(errors,[]);
  console.log('PASS: nonblocking entry, automatic two-slot background preload, viewport priority, all 24 offscreen images loaded without visits');
 }finally{release();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
