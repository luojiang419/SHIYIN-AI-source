const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require('playwright');
(async()=>{
  const dir=path.resolve('案例/全能双风格/imgx-20260920');
  const browser=await chromium.launch({headless:true,channel:'chrome'});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1050}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.join(dir,fs.existsSync(path.join(dir,'技术验证归档.html'))?'技术验证归档.html':'实测论述报告.html')).href);
    const assets=await page.locator('img[src],a[href]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('src')||n.getAttribute('href')).filter(v=>!v.startsWith('#')));
    for(const asset of assets)assert.ok(fs.existsSync(path.resolve(dir,decodeURIComponent(asset))),asset);
    await page.locator('img[src]').evaluateAll(async nodes=>{await Promise.all(nodes.map(async img=>{img.loading='eager';await img.decode()}))});
    assert.equal(await page.locator('.gallery article').count(),8);
    await page.screenshot({path:path.join(dir,'report-desktop.png')});
    await page.locator('[data-filter="standard"]').click();
    assert.equal(await page.locator('.gallery article:visible').count(),3);
    await page.locator('.gallery article:visible .photo').first().click();
    assert.ok(await page.locator('#viewer').isVisible());
    await page.locator('#zoom').click();
    assert.equal(await page.locator('#large').getAttribute('class'),'full');
    await page.keyboard.press('Escape');
    await page.locator('#viewer').waitFor({state:'hidden'});
    await page.locator('[data-filter="all"]').click();
    await page.locator('#gallery').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(dir,'report-gallery.png')});
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>scrollTo(0,0));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.screenshot({path:path.join(dir,'report-mobile.png')});
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(dir,'report-verification.json'),JSON.stringify({status:'passed',images:8,checks:['all assets exist and images decoded','style filters','lightbox and original-size toggle','Escape closes','390px without horizontal overflow','no page errors']},null,2));
    console.log('HTML report: 8 images, assets, filters, zoom, desktop/mobile and console checks passed');
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
