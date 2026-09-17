const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<div id="batchOutfitControl"><div id="batchOutfitGroups"></div></div><input id="batchOutfitFileInput" type="file"><div id="batchOutfitWorks"></div>');
  await page.addStyleTag({content:fs.readFileSync('static/css/ecommerce.css','utf8')});
  await page.evaluate(()=>{
   window.EcommerceStudio={state:{operation:'batch_outfit',batchOutfit:{}},persist(){},showToast(){}};
   window.fetch=async()=>new Response(JSON.stringify({files:[{url:'/fabric-new.png',name:'detail.png'}]}),{status:200});
  });
  await page.addScriptTag({content:fs.readFileSync('static/js/ecommerce-batch-outfit.js','utf8')});
  await page.evaluate(()=>{
   EcommerceBatchOutfit.init();
   EcommerceBatchOutfit.hydrate({groups:[{id:'fabric_test',style_name:'面料实测',inputs:{target_image:[{url:'/garment-a.png'},{url:'/garment-b.png'}]},fabric_details:{'/garment-a.png':{url:'/detail-a.png'},'/garment-b.png':{url:'/detail-b.png'}}}]});
   EcommerceBatchOutfit.render();
  });
  assert.equal(await page.locator('[data-batch-upload="fabric_detail"] img').getAttribute('src'),'/detail-a.png');
  await page.locator('[data-batch-input-step="1"]').click();
  assert.equal(await page.locator('[data-batch-upload="fabric_detail"] img').getAttribute('src'),'/detail-b.png');
  await page.locator('[data-batch-upload="fabric_detail"]').click();
  await page.locator('#batchOutfitFileInput').setInputFiles({name:'detail.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aTioAAAAASUVORK5CYII=','base64')});
  await page.waitForFunction(()=>EcommerceBatchOutfit.snapshot().groups[0].fabric_details['/garment-b.png']?.url==='/fabric-new.png');
  await page.evaluate(()=>{const saved=EcommerceBatchOutfit.snapshot();EcommerceBatchOutfit.hydrate(saved);EcommerceBatchOutfit.render();});
  assert.equal(await page.locator('[data-batch-upload="fabric_detail"] img').getAttribute('src'),'/fabric-new.png');
  await page.locator('[data-batch-remove-input="target_image"]').click();
  const data=await page.evaluate(()=>EcommerceBatchOutfit.snapshot().groups[0]);
  assert.equal(data.fabric_details['/garment-b.png'],undefined);
  assert.equal(data.fabric_details['/garment-a.png'].url,'/detail-a.png');
  assert.deepEqual(errors,[]);
  fs.mkdirSync('.codex-artifacts/fabric-ui',{recursive:true});
  await page.screenshot({path:'.codex-artifacts/fabric-ui/batch.png'});
  console.log('逐款细节绑定、上传、切换、保存恢复与删除通过；页面错误 0');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
