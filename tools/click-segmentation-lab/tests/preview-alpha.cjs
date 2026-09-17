const {chromium}=require('playwright');
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
const page=await browser.newPage({viewport:{width:1440,height:900}});
await page.goto('http://127.0.0.1:8791');
const fixtures=await page.evaluate(()=>{
 const c=document.createElement('canvas');c.width=c.height=100;const x=c.getContext('2d');
 x.fillStyle='#ef8040';x.fillRect(0,0,100,100);const preview=c.toDataURL();
 x.fillStyle='black';x.fillRect(0,0,100,100);x.fillStyle='white';x.fillRect(25,25,50,50);
 return {preview,mask:c.toDataURL()};
});
let exports=0;
await page.route('**/api/images',r=>r.fulfill({json:{session_id:'fixture',width:100,height:100,preview:fixtures.preview}}));
await page.route('**/api/segment',r=>r.fulfill({json:{mask:fixtures.mask}}));
page.on('request',r=>{if(r.url().includes('/api/export/'))exports++});
await page.locator('#fileInput').setInputFiles({name:'fixture.png',mimeType:'image/png',buffer:Buffer.from(fixtures.preview.split(',')[1],'base64')});
await page.waitForFunction(()=>document.querySelector('#imageCanvas').width>100);
const before=await page.locator('#imageCanvas').evaluate(c=>c.getContext('2d').getImageData(5,5,1,1).data[3]);
if(before!==255)throw Error('导入后原图不可见');
await page.locator('#maskCanvas').click();
await page.waitForFunction(()=>!document.querySelector('#cutoutExportButton').disabled);
const pixels=await page.evaluate(()=>{
const c=document.querySelector('#maskCanvas'),x=c.getContext('2d');
const composite=document.createElement('canvas');composite.width=c.width;composite.height=c.height;
const ctx=composite.getContext('2d');ctx.drawImage(document.querySelector('#imageCanvas'),0,0);ctx.drawImage(c,0,0);
const dark=ctx.getImageData(5,5,1,1).data[0],bright=ctx.getImageData(c.width*.4,c.height*.4,1,1).data[0];
if(dark<75||dark>90||bright!==239)throw Error('背景未压暗或前景被变暗: '+dark+','+bright);
return {dark,bright,background:x.getImageData(5,5,1,1).data[3],foreground:x.getImageData(c.width*.4,c.height*.4,1,1).data[3],base:document.querySelector('#imageCanvas').getContext('2d').getImageData(5,5,1,1).data[3]};
});
if(pixels.background!==0||pixels.foreground!==255||pixels.base!==255||exports)throw Error(JSON.stringify({pixels,exports}));
console.log(JSON.stringify({before,pixels,exports,result:'PASS'}));
await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
