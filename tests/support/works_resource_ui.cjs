const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base='http://127.0.0.1:3052';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.request.post(base+'/api/account/login',{data:{account:'jiang',password:'jiang'}});
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const work={id:'test',name:'SHIYIN-000001-20260910.jpg',original_name:'fixture-0.jpg',url:'/assets/output/fixture-0.jpg',preview_url:'/api/media-preview?w=512&url=%2Fassets%2Foutput%2Ffixture-0.jpg',resource_status:'local',media_type:'image',created_at:1700000000};
  await page.route('**/api/works?*',async route=>{
    const kind=new URL(route.request().url()).searchParams.get('media_type');
    await new Promise(resolve=>setTimeout(resolve,kind==='video'?20:300));
    await route.fulfill({json:{works:kind==='video'?[]:[work],total:kind==='video'?0:1,next_cursor:''}}).catch(()=>{});
  });
  await page.goto(base+'/static/works.html',{waitUntil:'domcontentloaded'});
  await page.locator('#worksMediaFilter [data-media-type="video"]').click();
  await page.waitForTimeout(500);
  assert.equal(await page.locator('.works-card').count(),0,'stale all response must not overwrite video filter');
  await page.locator('#worksMediaFilter [data-media-type="image"]').click();
  await page.waitForFunction(()=>document.querySelector('.works-card-media img')?.naturalWidth===512);
  await page.locator('.works-card-media').click();
  await page.waitForFunction(()=>document.querySelector('#worksPreviewImage')?.naturalWidth===2048);
  const preview='/api/media-preview?w=512&url=%2Fassets%2Foutput%2Ffixture-0.jpg';
  await page.evaluate(async()=>{await navigator.serviceWorker.ready});
  assert.equal(await page.evaluate(async url=>(await fetch(url)).status,preview),200);
  await page.evaluate(async()=>fetch('/api/account/logout',{method:'POST'}));
  assert.equal(await page.evaluate(async url=>(await fetch(url)).status,preview),401,'logout must deny cached media');
  assert.deepEqual(errors,[]);
  console.log('works UI: racing filters, 512px thumbnails, 2048px original, authenticated SW logout passed');
 }finally{await browser.close()}
})().catch(error=>{console.error(error.message.split('Call log:')[0]);process.exitCode=1});
