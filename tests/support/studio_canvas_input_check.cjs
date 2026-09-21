// 冷启动完整工作台：真实鼠标交互与按需加载；所有工程/API 均为隔离 fixture。
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.argv[2] || 'http://127.0.0.1:13382';
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const background=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('studio_active_page','canvas'));
  if(process.env.STUDIO_TEST_INDEX) await page.route('**/static/index.html',r=>r.fulfill({contentType:'text/html',body:fs.readFileSync(process.env.STUDIO_TEST_INDEX)}));
  await page.route(/\/static\/(ecommerce|gpt-chat|asset-manager|works|api-settings|app-settings|depth-map-tuner)\.html/,r=>{
   background.push(new URL(r.request().url()).pathname);
   return r.fulfill({contentType:'text/html',body:'<p>按需加载测试页面</p>'});
  });
  await page.route('**/api/projects',r=>r.fulfill({json:{projects:[{id:'default',name:'默认'}]}}));
  await page.route('**/api/providers',r=>r.fulfill({json:{providers:[{id:'shiying',has_key:true}]}}));
  await page.route('**/api/canvases',r=>r.fulfill({json:{canvases:[{id:'input-test',title:'交互测试',project:'default',node_count:10}]}}));
  await page.route('**/api/canvases/input-test',async r=>{
   if(r.request().method()!=='GET')return r.continue();
   const response=await r.fetch(),data=await response.json();
   data.canvas.viewport={x:180,y:200,scale:0.65};
   return r.fulfill({json:data});
  });
  await page.goto(base+'/static/index.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!document.documentElement.classList.contains('studio-route-booting'));
  await page.frameLocator('#frame-canvas').locator('.ws-card[data-canvas-id="input-test"]').click();
  await page.waitForFunction(()=>document.getElementById('frame-canvas')?.contentWindow?.CanvasSessionLifecycle?.state().id==='input-test');
  const editor=await page.locator('#frame-canvas').elementHandle().then(e=>e.contentFrame());
  await editor.waitForFunction(()=>!document.getElementById('shell').inert);
  const prompt=editor.locator('.node[data-id="prompt"] .node-title');
  await prompt.waitFor();
  const before=await editor.evaluate(()=>({x:nodes.find(n=>n.id==='prompt').x,y:nodes.find(n=>n.id==='prompt').y}));
  const box=await prompt.boundingBox();
  const hit=await page.evaluate(p=>{const e=document.elementFromPoint(p.x+p.width/2,p.y+p.height/2);return {tag:e?.tagName,id:e?.id};},box);
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
  await page.mouse.move(box.x+box.width/2+100,box.y+box.height/2+60,{steps:8});await page.mouse.up();
  const after=await editor.evaluate(()=>({x:nodes.find(n=>n.id==='prompt').x,y:nodes.find(n=>n.id==='prompt').y}));
  assert(after.x>before.x+50 && after.y>before.y+30,`首开节点必须可以实际拖动 ${JSON.stringify({before,after,box,hit})}`);
  await editor.locator('#canvasPanTool').click();
  const panBefore=await editor.evaluate(()=>({...viewport}));
  await page.mouse.move(1370,160);await page.mouse.down();await page.mouse.move(1210,260,{steps:8});await page.mouse.up();
  assert(await editor.evaluate(v=>Math.abs(viewport.x-v.x)>50,panBefore),'首开必须可以平移');
  await page.mouse.wheel(0,-150);
  await editor.waitForFunction(v=>viewport.scale>v.scale,panBefore);
  assert.deepEqual(background,[],'冷启动不应启动未访问业务页面');
  await editor.evaluate(()=>window.__residentDocument=document);
  await page.evaluate(()=>switchUI(null,'ecommerce'));
  await page.frameLocator('#frame-ecommerce').getByText('按需加载测试页面').waitFor();
  assert.deepEqual(background,['/static/ecommerce.html']);
  await page.evaluate(()=>switchUI(null,'canvas'));
  assert(await editor.evaluate(()=>window.__residentDocument===document),'往返保留已打开工程');
  assert.equal(await page.locator('#frame-canvas').evaluate(e=>e.inert),false);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,drag:{before,after},background,pageErrors:errors}));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
