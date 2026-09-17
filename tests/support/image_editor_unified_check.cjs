const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  page.on('pageerror',error=>console.log('PAGE ERROR',error.message));
  const base=process.env.CUTOUT_TEST_URL||'http://127.0.0.1:8792';
  // 仅屏蔽与本地编辑无关的首次 API Key 引导，不写入账号配置或伪造实际密钥。
  await page.route('**/api/providers',async route=>{const response=await route.fetch();const data=await response.json();data.providers=(data.providers||[]).map(p=>p.id==='shiying'?{...p,has_key:true}:p);await route.fulfill({response,json:data})});
  await page.request.post(base+'/api/account/login',{data:{account:'jiang',password:'jiang'}});
  const created=await (await page.request.post(base+'/api/canvases',{data:{title:'统一编辑器真实主壳测试'}})).json();
  const uploaded=await (await page.request.post(base+'/api/ai/upload',{multipart:{files:{name:'test.png',mimeType:'image/png',buffer:fs.readFileSync('generated-images/20260830-open-mannequin-refs/ref-01.png')}}})).json();
  await page.goto(base+'/static/index.html');
  await page.waitForFunction(()=>typeof switchUI==='function'&&window.CanvasSessionHost);
  await page.locator('#shiying-api-key-modal').waitFor({state:'visible',timeout:5000}).then(()=>page.getByRole('button',{name:'稍后设置',exact:true}).click()).catch(()=>{});
  await page.evaluate(id=>{switchUI(null,'canvas');CanvasSessionHost.open('/static/canvas.html?id='+id);},created.canvas.id);
  await page.waitForFunction(id=>document.getElementById('frame-canvas')?.contentWindow?.CanvasSessionLifecycle?.state().id===id,created.canvas.id);
  const canvas=page.frameLocator('#frame-canvas');
  await canvas.locator('#imageEditModal').waitFor({state:'attached'});
  await canvas.locator('body').evaluate((_,url)=>{
   const source=addImageNode({x:50,y:60});source.url=url;source.w=300;source.h=300;
   runClassicMediaToolbarAction(source.id,'autoCutout');
   const cutout=nodes.find(n=>n.type==='autoCutout');const out=addOutputNode({x:1000,y:60});
   connections.push({id:uid('c'),from:cutout.id,to:out.id});render();
   window.unifiedTest={source:source.id,cutout:cutout.id,out:out.id,original:url};
  },uploaded.files[0].url);
  const cutoutId=await canvas.locator('body').evaluate(()=>unifiedTest.cutout);
  const modal=canvas.locator('#imageEditModal');const apply=canvas.locator('#imageEditApplyBtn');
  const tool=canvas.frameLocator('#imageCutoutFrame');
  await canvas.locator(`[data-id="${cutoutId}"] [data-cutout-open]`).click();
  await tool.locator('#maskCanvas').waitFor({state:'visible'});
  await tool.locator('#busy').waitFor({state:'hidden',timeout:180000});
  assert.deepEqual(await page.locator('#frame-canvas').boundingBox(),{x:0,y:0,width:1600,height:1000});
  await page.evaluate(()=>broadcastRouteState());
  assert(await apply.isDisabled());
  for(const mode of ['crop','grid','cutout']){
   await canvas.locator(`[data-image-edit-mode="${mode}"]`).click();
   assert.equal(await canvas.locator('body').evaluate(()=>imageEditMode),mode);
   assert(await modal.isVisible());
  }
  await tool.locator('#maskCanvas').click();
  await tool.locator('#busy').waitFor({state:'hidden',timeout:180000});
  assert(await apply.isEnabled());
  await page.screenshot({path:'.codex-tmp/unified-image-editor.png'});
  await apply.click();await modal.waitFor({state:'hidden'});
  const first=await canvas.locator('body').evaluate(()=>{
   const n=nodes.find(n=>n.id===unifiedTest.cutout),out=nodes.find(n=>n.id===unifiedTest.out);
   if(!n.outputUrl||out.images[0].url!==n.outputUrl)throw Error('抠像输出未同步');return n.outputUrl;
  });
  assert((await page.locator('#frame-canvas').boundingBox()).width<1600);
  await canvas.locator('body').evaluate(()=>openImageEditor(unifiedTest.cutout,'crop'));
  await canvas.locator('#cropImage').evaluate(img=>img.decode());
  await canvas.locator('[data-crop-ratio="1:1"]').click();
  await apply.click();await modal.waitFor({state:'hidden'});
  await canvas.locator('body').evaluate((_,old)=>{
   const n=nodes.find(n=>n.id===unifiedTest.cutout),out=nodes.find(n=>n.id===unifiedTest.out);
   if(n.outputUrl===old||out.images[0].url!==n.outputUrl||n.outputWidth!==n.outputHeight)throw Error('抠像节点裁切未同步');
  },first);
  await canvas.locator('body').evaluate(()=>openImageEditor(unifiedTest.source,'grid'));
  await canvas.locator('#imageGridTools.active').waitFor();
  await canvas.locator('body').evaluate(async()=>{while(gridAutoDetecting)await new Promise(r=>setTimeout(r,50));applyGridPreset(2,2)});
  await apply.click();await modal.waitFor({state:'hidden'});
  await canvas.locator('body').evaluate(()=>{
   if(!nodes.some(n=>n.type==='output'&&n.images?.length===4))throw Error('多宫格输出不是4张');
   if(nodes.find(n=>n.id===unifiedTest.source).url!==unifiedTest.original)throw Error('原图被修改');
  });
  await canvas.locator('body').evaluate(()=>openImageEditor(unifiedTest.source,'cutout'));
  await tool.locator('#busy').waitFor({state:'hidden'});
  await tool.locator('#maskCanvas').click();await tool.locator('#busy').waitFor({state:'hidden',timeout:180000});
  await apply.click();await modal.waitFor({state:'hidden'});
  assert.equal(await canvas.locator('body').evaluate(()=>nodes.filter(n=>n.type==='autoCutout').length),2);
  await page.route('**/static/cutout-editor/index.html',route=>route.fulfill({status:500,contentType:'text/html',body:'工具加载失败'}));
  await canvas.locator('body').evaluate(()=>openImageEditor(unifiedTest.source,'cutout'));
  await modal.waitFor({state:'visible'});
  await canvas.locator('[data-image-editor-close]').click();
  await modal.waitFor({state:'hidden'});
  await canvas.locator('body').evaluate(()=>openImageEditor(unifiedTest.source,'crop'));
  await canvas.locator('[data-image-edit-mode="crop"]').press('Escape');await modal.waitFor({state:'hidden'});
  assert((await page.locator('#frame-canvas').boundingBox()).width<1600);
  await canvas.locator('body').evaluate(()=>openImageEditor(unifiedTest.source,'crop'));
  await page.evaluate(()=>switchUI(null,'works'));
  assert.notEqual(await page.locator('#frame-canvas').evaluate(frame=>frame.style.position),'fixed');
  console.log('PASS real studio shell: fullscreen, tool switching, cutout save/downstream, cutout crop, 2x2 grid, source cutout, failed-load close, Escape, viewport restore and route cleanup');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
