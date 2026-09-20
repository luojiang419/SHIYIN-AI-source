const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
 const dir=path.resolve('案例/全能双风格/imgx-20260920');
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1050}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(dir,'实测论述报告.html')).href);
 const assets=await page.locator('img[src],video[src],a[href]').evaluateAll(ns=>ns.map(n=>n.getAttribute('src')||n.getAttribute('href')).filter(x=>x&&!x.startsWith('#')));
 for(const a of assets)assert.ok(fs.existsSync(path.resolve(dir,decodeURIComponent(a.split('#')[0]))),a);
 await page.locator('img[src]').evaluateAll(async ns=>Promise.all(ns.map(i=>i.decode())));
 assert.equal(await page.locator('[role=tab]').count(),6);
 await page.screenshot({path:path.join(dir,'sales-report-desktop.png')});
 for(const key of ['refs','pixels','depth','sales','animation']){await page.locator(`[data-tab=${key}]`).click();assert.ok(await page.locator(`#${key}`).isVisible())}
 await page.locator('[data-tab=pixels]').click();await page.locator('[data-kind=lookbook]').click();
 assert.ok(await page.locator('[data-comparison=lookbook]').isVisible());
 assert.ok(await page.locator('[data-comparison=lookbook] .pixelbox img').evaluateAll(ns=>ns.every(i=>Math.abs(i.getBoundingClientRect().width-i.naturalWidth)<1)));
 await page.screenshot({path:path.join(dir,'sales-report-texture.png')});
 await page.locator('#pixel-fit').click();assert.equal(await page.locator('#comparisons').getAttribute('class'),'fit');
 await page.locator('[data-tab=refs]').click();await page.locator('#refs .photo').first().click();await page.locator('#zoom').click();assert.equal(await page.locator('#large').getAttribute('class'),'full');await page.keyboard.press('Escape');assert.ok(!await page.locator('#viewer').isVisible());
 await page.locator('[data-tab=animation]').click();if(await page.locator('video').count()){await page.locator('video').evaluate(async v=>{if(!v.readyState)await new Promise((resolve,reject)=>{v.onloadedmetadata=resolve;v.onerror=reject});if(v.duration<45||v.videoWidth!==1280)throw new Error('Invalid demo video');v.currentTime=20;await new Promise(resolve=>v.onseeked=resolve)})}await page.locator('#duration').selectOption('4000');await page.locator('#play').click();await page.waitForTimeout(4200);assert.match(await page.locator('#demo-count').textContent(),/2 \/ 6/);await page.locator('#play').click();await page.locator('#next').click();assert.match(await page.locator('#demo-count').textContent(),/3 \/ 6/);await page.locator('#restart').click();assert.match(await page.locator('#demo-count').textContent(),/1 \/ 6/);
 await page.waitForTimeout(750);await page.screenshot({path:path.join(dir,'sales-report-animation.png')});
 await page.setViewportSize({width:390,height:844});
 for(const key of ['overview','refs','pixels','depth','sales','animation']){await page.locator(`[data-tab=${key}]`).click();assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),key)}
 await page.locator('[data-tab=overview]').click();await page.screenshot({path:path.join(dir,'sales-report-mobile.png')});assert.deepEqual(errors,[]);
 await page.goto(pathToFileURL(path.join(dir,'销售使用说明与功能汇报.html')).href);assert.ok(await page.locator('h1').isVisible());
 fs.writeFileSync(path.join(dir,'sales-report-verification.json'),JSON.stringify({status:'passed',tabs:6,checks:['all assets and images','tab switching','100% natural pixel width','fit toggle','image modal and Escape','animation play/pause/steps/restart','all tabs at 390px without overflow','sales handout','no page errors']},null,2));
 if(process.argv.includes('--video')){
 const ctx=await browser.newContext({viewport:{width:1280,height:900},recordVideo:{dir:path.join(dir,'demo-video'),size:{width:1280,height:900}}});const v=await ctx.newPage();await v.goto(pathToFileURL(path.join(dir,'实测论述报告.html')).href+'#animation');await v.addStyleTag({content:'header,nav,footer,main>.links,#step-buttons{display:none!important}main{padding:18px 28px}#animation>h2{margin:0;font-size:25px}#animation>p{margin:5px 0 12px;font-size:14px}.demo-images{height:430px}.toolbar{margin:12px 0}'});await v.evaluate(()=>scrollTo(0,0));await v.locator('#duration').selectOption('8000');await v.locator('#play').click();await v.waitForTimeout(49000);const video=v.video();await ctx.close();await video.saveAs(path.join(dir,'操作演示.webm'));
 }
 console.log('Sales report checks passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
