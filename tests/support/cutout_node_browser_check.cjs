const {chromium}=require('playwright');
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE});
const page=await browser.newPage({viewport:{width:1600,height:1000}});
page.on('pageerror',e=>console.log('PAGE ERROR',e.message));
await require('./account_test_login.cjs').loginForTest(page.request,'http://127.0.0.1:8792');
const created=await (await page.request.post('http://127.0.0.1:8792/api/canvases',{data:{title:'抠像集成测试'}})).json();
await page.goto('http://127.0.0.1:8792/static/canvas.html?id='+created.canvas.id);
await page.waitForTimeout(2500);
console.log(await page.evaluate(()=>({title:document.title,body:document.body.innerText.slice(-1500),has:typeof addAutoCutoutNode})));
const fs=require('fs');
const uploaded=await (await page.request.post('http://127.0.0.1:8792/api/ai/upload',{multipart:{files:{name:'test.png',mimeType:'image/png',buffer:fs.readFileSync('generated-images/20260830-open-mannequin-refs/ref-01.png')}}})).json();
console.log(await page.evaluate(url=>{
 const source=addImageNode({x:50,y:60});source.url=url;source.w=300;source.h=300;
 runClassicMediaToolbarAction(source.id,'autoCutout');
 const cutout=nodes.find(n=>n.type==='autoCutout');
 const downstream=addOutputNode({x:1000,y:60});
 connections.push({id:uid('c'),from:cutout.id,to:downstream.id});
 render();
 window.cutoutTest={source:source.id,cutout:cutout.id,out:downstream.id};
 return {cutout,allowed:canConnect(source.id,cutout.id),menu:mediaToolbarItemsForNode(source).map(i=>i.id)};
},uploaded.files[0].url));
const id=await page.evaluate(()=>cutoutTest.cutout);
await page.locator('.node[data-id="'+id+'"] [data-cutout-open]').click();
const editor=page.frameLocator('iframe[src="/static/cutout-editor/index.html"]');
await editor.locator('#maskCanvas').waitFor({state:'visible'});
await editor.locator('#busy').waitFor({state:'hidden'});
await editor.locator('#maskCanvas').click();
await editor.locator('#busy').waitFor({state:'hidden',timeout:180000});
await page.locator('#imageEditApplyBtn').click();
await page.waitForFunction(()=>nodes.find(n=>n.id===cutoutTest.cutout).outputUrl,{},{timeout:180000});
console.log('SAVED',await page.evaluate(()=>{
 const n=nodes.find(n=>n.id===cutoutTest.cutout),out=nodes.find(n=>n.id===cutoutTest.out);
 if(out.images?.[0]?.url!==n.outputUrl)throw Error('下游未更新');
 if(n.cutoutSourceUrl===n.outputUrl||!n.cutoutSettings.points.length)throw Error('原图或参数丢失');
 return {output:n.outputUrl,points:n.cutoutSettings.points.length};
}));
const firstUrl=await page.evaluate(()=>nodes.find(n=>n.id===cutoutTest.cutout).outputUrl);
await page.locator('.node[data-id="'+id+'"] [data-cutout-fullscreen]').click();
const again=page.frameLocator('iframe[src="/static/cutout-editor/index.html"]');
await again.locator('#maskCanvas').waitFor({state:'visible'});
await again.locator('#busy').waitFor({state:'hidden',timeout:180000});
for(const theme of ['dark','light']){
 await page.evaluate(theme=>applyTheme(theme),theme);
 await again.locator('body').evaluate(async ()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const colors=await page.evaluate(()=>({text:getComputedStyle(document.body).getPropertyValue('--text').trim()}));
 const frame=page.frames().find(f=>f.url().includes('/static/cutout-editor/index.html'));
 await frame.waitForFunction(expected=>document.documentElement.style.getPropertyValue('--text')===expected,colors.text);
 for(const id of ['threshold','feather','edgeShift','zoomSlider']){
   const control=again.locator('#'+id);
   await control.scrollIntoViewIfNeeded();
   if(!await control.isVisible())throw Error('全屏控件不可见: '+id);
   const bounds=await control.boundingBox();
   if(!bounds||bounds.y<0||bounds.y+bounds.height>1000)throw Error('全屏控件越界: '+id);
 }
}
console.log('PASS full-screen controls and live light/dark theme');
await again.locator('#edgeShift').fill('2');
await again.locator('#busy').waitFor({state:'hidden',timeout:180000});
await page.locator('#imageEditApplyBtn').click();
await page.waitForFunction(old=>nodes.find(n=>n.id===cutoutTest.cutout).outputUrl!==old,firstUrl,{timeout:180000});
console.log('RESAVED',await page.evaluate(()=>{
const node=nodes.find(n=>n.id===cutoutTest.cutout),out=nodes.find(n=>n.id===cutoutTest.out);
if(out.images.length!==1||out.images[0].url!==node.outputUrl)throw Error('再次保存下游未替换');
if(node.cutoutSettings.edge_shift!==2)throw Error('修改参数未保存');
return {url:node.outputUrl,edge:node.cutoutSettings.edge_shift};
}));
await page.locator('.node[data-id="'+id+'"] [data-cutout-preview]').evaluate(async img=>{await img.decode();if(!img.naturalWidth)throw Error('节点缩略图未加载')});
await page.waitForTimeout(500);
await page.screenshot({path:'.codex-tmp/cutout-canvas.png'});
await page.waitForTimeout(1800);
const savedNode=await page.evaluate(()=>JSON.parse(JSON.stringify(nodes.find(n=>n.id===cutoutTest.cutout))));
await page.reload();await page.waitForFunction(()=>typeof nodes!=='undefined'&&nodes.some(n=>n.type==='autoCutout'));
console.log('RESTORED',await page.evaluate(expected=>{
 const n=nodes.find(n=>n.id===expected.id);
 if(n.outputUrl!==expected.outputUrl||n.cutoutSourceUrl!==expected.cutoutSourceUrl||n.cutoutSettings.edge_shift!==2)throw Error('画布恢复丢失抠像状态');
 return n.id;
},savedNode));
await browser.close();
})()
