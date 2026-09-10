// 隔离真实浏览器重绘回归；不访问用户工程或生成 API。
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const base=process.argv[2] || 'http://127.0.0.1:3027';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try {
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  if(process.env.CANVAS_TEST_SCRIPT) await page.route('**/static/js/canvas.js?*',r=>r.fulfill({contentType:'application/javascript',body:require('node:fs').readFileSync(process.env.CANVAS_TEST_SCRIPT)}));
  const png=await (await page.request.get(base+'/fixture.png')).body();
  let requests=0;
  await page.route('**/api/account/me',r=>r.fulfill({json:{account:{id:'redraw-test',is_admin:true}}}));
  await page.route('**/api/canvases/redraw',r=>r.fulfill({json:{canvas:{id:'redraw',updated_at:1,connections:[],viewport:{x:20,y:20,scale:1},nodes:[
   {id:'i',type:'image',url:'/assets/input/a.png',x:0,y:0,w:260,h:300},
   {id:'o',type:'output',images:[{url:'/assets/input/b.png'}],x:300,y:0,w:350,h:300}
  ]}}}));
  await page.route('**/api/media-preview**',r=>{requests++;return r.fulfill({body:png,contentType:'image/png'});});
  await page.goto(base+'/static/canvas.html?id=redraw');
  await page.waitForFunction(()=>!window.canvasEntryOverlay && document.querySelector('#nodes img')?.naturalWidth>0);
  await page.evaluate(()=>{stopCanvasRemotePolling();window.originalImages=[...document.querySelectorAll('#nodes img')];});
  const before=requests;
  for(const kind of ['full','partial','mutation']){
   const result=await page.evaluate(async kind=>{
    if(kind==='full') render();
    else if(kind==='partial') refreshNodes(['i','o']);
    else {const n=nodes.find(n=>n.id==='i');n.name='changed';renderClassicMutation({replaceIds:new Set(['i','o'])});}
    await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
    return originalImages.map(img=>({connected:img.isConnected,ready:img.complete&&img.naturalWidth>0}));
   },kind);
   assert(result.every(r=>r.connected&&r.ready),`${kind} 重绘丢失已加载图片: ${JSON.stringify(result)}`);
  }
  await page.waitForTimeout(400);
  assert.equal(requests,before,'未变化资源不应重新请求');
  await page.evaluate(()=>{nodes=nodes.map(n=>({...n}));render();window.previewCalls=[];openImageEditor=(...args)=>previewCalls.push(args);});
  await page.locator('.image-node img').dispatchEvent('dblclick');
  assert.equal(await page.evaluate(()=>previewCalls.length),1,'多次重绘不能积累图片事件');
  await page.evaluate(()=>{window.outputUsesCurrent=false;openOutputLightbox=(_url,node)=>{outputUsesCurrent=node===nodes.find(n=>n.id==='o');};});
  await page.locator('.output-node img').dispatchEvent('dblclick');
  assert(await page.evaluate(()=>outputUsesCurrent),'输出图交互必须绑定当前模型');
  let release;
  const gate=new Promise(resolve=>release=resolve);
  let replacementRequests=0;
  await page.route('**/api/media-preview**',async r=>{
   if(new URL(r.request().url()).searchParams.get('url')==='/assets/input/replaced.png'){
    replacementRequests++;await gate;
   }
   await r.fulfill({body:png,contentType:'image/png'});
  });
  await page.evaluate(()=>{nodes.find(n=>n.id==='i').url='/assets/input/replaced.png';refreshNodes(['i']);});
  assert.equal(await page.evaluate(()=>originalImages[0].isConnected),false,'不同资源不能复用旧图片');
  await page.waitForFunction(()=>document.querySelector('.image-node img')?.dataset.previewState==='loading');
  await page.evaluate(()=>{window.pendingImage=document.querySelector('.image-node img');render();});
  assert(await page.evaluate(()=>pendingImage.isConnected),'重绘不能丢弃加载中的队列任务');
  release();
  await page.waitForFunction(()=>document.querySelector('.image-node img')?.naturalWidth>0);
  assert.equal(replacementRequests,1,'加载中重绘不能重复排队');
  assert.deepEqual(errors,[]);
  console.log('PASS: full/partial redraw keeps pixels and requests, handlers rebind once, replacement loads new resource');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
