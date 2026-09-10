const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage();const dialogs=[],errors=[],queries=[];
  page.on('dialog',async d=>{dialogs.push(d.message());await d.dismiss();});page.on('pageerror',e=>errors.push(e.message));
  const works=[1,2,3].map(i=>({id:String(i),name:`作品${i}`,url:'/fixture.png',preview_url:'/fixture.png',created_at:i,kind:'online',trashed:i===3}));
  await page.route('**/api/works?**',r=>{
   const p=new URL(r.request().url()).searchParams;queries.push(p.toString());
   const items=works.filter(w=>p.get('trashed_only')==='true'?w.trashed:p.get('include_trashed')==='true'||!w.trashed);
   return r.fulfill({json:{works:items,total:items.length,next_cursor:''}});
  });
  await page.route('**/api/works/*/metadata',r=>{const w=works.find(w=>r.request().url().includes(`/works/${w.id}/`));Object.assign(w,r.request().postDataJSON());return r.fulfill({json:{work:w}});});
  await page.route('**/api/works/batch',r=>{const p=r.request().postDataJSON();works.forEach(w=>{if(p.ids.includes(w.id))w.trashed=true;});return r.fulfill({json:{count:p.ids.length}});});
  await page.goto('http://127.0.0.1:3027/static/works.html');
  await page.waitForSelector('[data-work-id="1"]');
  assert.equal(await page.locator('[data-work-id="3"]').count(),0);
  await page.locator('[data-trash-work="1"]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-work-id="1"]'));
  await page.locator('[data-tab="trash"]').click();
  await page.waitForSelector('[data-work-id="1"]');
  assert.equal(await page.locator('[data-work-id="2"]').count(),0);
  await page.locator('[data-trash-work="1"]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-work-id="1"]'));
  await page.locator('[data-tab="all"]').click();await page.waitForSelector('[data-work-id="1"]');
  await page.locator('#worksSelectionModeToggle').click();
  await page.locator('[data-work-id="1"] .works-card-checkbox').check();
  await page.locator('#worksBatchTrash').click();
  await page.waitForFunction(()=>!document.querySelector('[data-work-id="1"]'));
  assert.equal(await page.locator('[data-work-id="2"]').count(),1);
  assert.deepEqual(dialogs,[]);assert.deepEqual(errors,[]);
  assert(queries.some(q=>q.includes('include_trashed=false')));assert(queries.some(q=>q.includes('trashed_only=true')));
  console.log('PASS: all excludes trash, single/batch no confirmation, trash-only view, restore removes card from trash');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
