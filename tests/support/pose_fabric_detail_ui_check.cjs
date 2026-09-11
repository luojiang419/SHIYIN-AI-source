const {chromium}=require('playwright');
const fs=require('node:fs'); const path=require('node:path'); const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const page=await browser.newPage({viewport:{width:1000,height:1050}});
 await page.route('**/api/**',route=>route.fulfill({json:{ready:false}}));
 await page.setContent('<html><body style="background:#eee;font-family:Arial"><main style="width:720px;margin:40px auto;padding:20px;background:white"></main></body></html>');
 for(const file of ['canvas-special-nodes.css','pose-replicate-node.css']) await page.addStyleTag({content:fs.readFileSync('static/css/'+file,'utf8')});
 await page.addScriptTag({content:fs.readFileSync('static/js/canvas-special-nodes.js','utf8')});
 const assets={};for(const [role,name] of [['pose-reference','target.png'],['target-image','garment.png'],['fabric-detail','fabric.png']]) assets[role]={url:'data:image/png;base64,'+fs.readFileSync('输出/一键复刻面料细节-20260911/'+name).toString('base64'),name};
 await page.evaluate(assets=>{
  window.testNode={id:'fabric',poseReplicateSchemaVersion:2,poseReplicateMode:'skeleton',poseReplicateManualInputs:{...assets,'target-image':[assets['target-image']]}};
  window.draw=()=>document.querySelector('main').innerHTML=window.CanvasSpecialNodes.poseReplicateBodyHtml(testNode);
  draw();
 },assets);
 assert.equal(await page.locator('[data-pose-replicate-slot="fabric-detail"]').count(),1);
 assert.equal(await page.locator('.pose-replicate-input-row').count(),5);
 await page.screenshot({path:'输出/一键复刻面料细节-20260911/node-single.png'});
 await page.evaluate(()=>{testNode.poseReplicateManualInputs['target-image'].push({url:'second.png'});draw();});
 assert.ok((await page.locator('main').innerText()).includes('批量不生效'));
 // 连接输入解析及同步、移除手动输入后回退到连接输入。
 await page.evaluate(()=>{
  const root=document.querySelector('main');
  testNode.poseReplicateManualInputs={};testNode.poseStatus='failed';
  window.CanvasSpecialNodes.bindPoseReplicate(root,testNode,{getInputImage:(_,role)=>role==='fabric-detail'?{url:'connected.png'}:null});
 });
 assert.equal(await page.evaluate(()=>testNode.fabricDetailUrl),'connected.png');
 await page.evaluate(()=>{
  window.fetch=async url=>new Response(JSON.stringify(url==='/api/ai/upload'?{files:[{url:'uploaded.png',name:'fabric.png'}]}:{ready:false}),{status:200});
 });
 await page.locator('[data-pose-replicate-file="fabric-detail"]').setInputFiles('D:/data/图片/纹理细节.jpg');
 await page.waitForFunction(()=>testNode.fabricDetailUrl==='uploaded.png');
 assert.equal(await page.evaluate(()=>testNode.poseReplicateManualInputs['fabric-detail'].url),'uploaded.png');
 await page.evaluate(()=>{draw();CanvasSpecialNodes.bindPoseReplicate(document.querySelector('main'),testNode,{getInputImage:(_,role)=>role==='fabric-detail'?{url:'connected.png'}:null});});
 await page.locator('[data-pose-replicate-remove-role="fabric-detail"]').click();
 assert.equal(await page.evaluate(()=>testNode.fabricDetailUrl),'connected.png');
 assert.equal(await page.evaluate(()=>Boolean(testNode.poseReplicateManualInputs['fabric-detail'])),false);

 await browser.close(); console.log('fabric component render, batch notice and connected input passed');
})().catch(e=>{console.error(e);process.exitCode=1});
