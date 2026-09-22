// 对已运行的安装版进行无生成费用验证；仅创建测试画布，结束后移入回收站。
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const base='http://127.0.0.1:3000';
 let canvasId, toolbarBefore, hiddenSelection;
 try{
  await context.request.get(base+'/api/auth/bootstrap');
  const account=await context.request.get(base+'/api/account/me');
  assert.equal(account.status(),200,'安装版必须已经登录');
  const config=await (await context.request.get(base+'/api/runtime/config')).json();
  const providers=config.api_providers||[];
  const imageProvider=providers.find(p=>p.enabled!==false&&p.image_generation_ready!==false&&p.image_models?.length);
  const videoProvider=providers.find(p=>p.id==='youyun-h3'&&p.enabled!==false)||providers.find(p=>p.id==='minimax-h3'&&p.enabled!==false)||providers.find(p=>p.enabled!==false&&p.video_models?.length);
  assert(imageProvider&&videoProvider,'需要已配置图片和视频平台');
  const page=await context.newPage();
  await page.goto(base+'/static/personal-preferences.html?installed-check=210');
  await page.waitForFunction(()=>!document.getElementById('preferencesFields').disabled,{},{timeout:20000});
  assert.equal(await page.evaluate(()=>PersonalPreferences.legacyBackend),true);
  await page.locator('#imageSettings [data-provider]').selectOption(imageProvider.id);
  await page.locator('#imageSettings [data-default]').selectOption(imageProvider.id);
  await page.locator('#imageSettings [data-field="ratio"]').selectOption('story');
  await page.locator('#imageSettings [data-field="resolution"]').selectOption('2k');
  await page.locator('#videoSettings [data-provider]').selectOption(videoProvider.id);
  await page.locator('#videoSettings [data-default]').selectOption(videoProvider.id);
  await page.locator('#videoSettings [data-field="duration"]').fill('9');
  await page.locator('#savePreferences').click();
  await page.getByText('已保存，新建节点将使用你的偏好').waitFor();
  await page.reload();await page.waitForFunction(()=>!document.getElementById('preferencesFields').disabled);
  assert.equal(await page.locator('#videoSettings [data-field="duration"]').inputValue(),'9');
  const output=path.join(process.cwd(),'.codex-tmp','personal-preferences-installed');fs.mkdirSync(output,{recursive:true});
  await page.screenshot({path:path.join(output,'preferences.png'),fullPage:true});
  const create=await context.request.post(base+'/api/canvases',{data:{title:'个人偏好安装版验证-210',kind:'classic',project:'default'}});
  assert(create.ok()); const created=await create.json();canvasId=created.id||created.canvas?.id;assert(canvasId);
  await page.goto(base+`/static/canvas.html?id=${encodeURIComponent(canvasId)}&installed-check=210`);
  await page.waitForFunction(()=>typeof addGeneratorNode==='function' && typeof canvas!=='undefined' && canvas && !document.getElementById('board')?.hidden,{},{timeout:30000});
  const nodes=await page.evaluate(()=>{
    const a=addGeneratorNode({x:0,y:0}), b=addVideoNode({x:600,y:0});
    return {image:{apiProvider:a.apiProvider,ratio:a.ratio,resolution:a.resolution},video:{apiProvider:b.apiProvider,duration:b.duration}};
  });
  assert.equal(nodes.image.apiProvider,imageProvider.id);assert.equal(nodes.image.ratio,'story');assert.equal(nodes.video.apiProvider,videoProvider.id);assert.equal(nodes.video.duration,9);
  toolbarBefore=(await (await context.request.get(base+'/api/preferences')).json()).values.canvas_quick_toolbar || await page.evaluate(()=>JSON.stringify(quickToolbarItemIds()));
  const button=page.locator('[data-toolbar-node]').first();const selected=await button.getAttribute('data-toolbar-node');
  await button.click({button:'right'});await page.waitForFunction(id=>!document.querySelector(`[data-toolbar-node="${id}"]`),selected);
  hiddenSelection=await page.evaluate(()=>localStorage.getItem('canvas_quick_toolbar_items_v1'));
  await page.waitForFunction(async expected=>{const r=await fetch('/api/preferences');return (await r.json()).values.canvas_quick_toolbar===expected;},hiddenSelection);
  await page.screenshot({path:path.join(output,'canvas.png'),fullPage:true});
  console.log(JSON.stringify({installedBackend:true,legacyPersistence:true,saveReload:true,newNodes:nodes,rightClickHide:true,screenshots:output}));
 } finally {
  if(hiddenSelection!==undefined){
   const data=await(await context.request.get(base+'/api/preferences')).json();
   if(data.values.canvas_quick_toolbar===hiddenSelection){
    const original=toolbarBefore;
    await context.request.put(base+'/api/preferences',{data:{values:{...data.values,canvas_quick_toolbar:original},base_revision:data.revision}});
   }
  }
  if(canvasId)await context.request.delete(base+`/api/canvases/${encodeURIComponent(canvasId)}`);
  await browser.close();
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
