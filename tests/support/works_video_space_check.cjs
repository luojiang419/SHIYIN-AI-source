// 用浏览器录制的本地视频验证真实播放状态，不调用外部媒体或生成 API。
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  if(process.argv.includes('--baseline')){
   const source=require('node:child_process').execFileSync('git',['show','HEAD:static/js/works.js']);
   await page.route('**/static/js/works.js*',r=>r.fulfill({body:source,contentType:'text/javascript'}));
  }
  await page.route('**/api/works?**',r=>r.fulfill({json:{works:[{id:'v',name:'video.webm',url:'/fixture.webm',media_type:'video',created_at:1}],total:1,next_cursor:''}}));
  await page.goto('http://127.0.0.1:3027/static/works.html');
  const bytes=await page.evaluate(async()=>{
   const canvas=document.createElement('canvas');canvas.width=96;canvas.height=96;
   canvas.getContext('2d').fillRect(0,0,96,96);
   const stream=canvas.captureStream(20), recorder=new MediaRecorder(stream,{mimeType:'video/webm'}),chunks=[];
   let frame=0;
   const draw=setInterval(()=>{canvas.getContext('2d').fillStyle=`rgb(${frame++%255},80,90)`;canvas.getContext('2d').fillRect(0,0,96,96);},50);
   recorder.ondataavailable=e=>chunks.push(e.data);
   await new Promise(resolve=>{recorder.onstop=resolve;recorder.start();setTimeout(()=>recorder.stop(),1800);});
   clearInterval(draw);
   stream.getTracks().forEach(t=>t.stop());
   return [...new Uint8Array(await new Blob(chunks).arrayBuffer())];
  });
  await page.route('**/fixture.webm',r=>r.fulfill({body:Buffer.from(bytes),contentType:'video/webm'}));
  await page.locator('[data-work-id="v"] .works-card-media').click();
  await page.waitForFunction(()=>document.querySelector('#worksPreviewVideo').readyState>=2);
  const video=page.locator('#worksPreviewVideo');
  await video.evaluate(v=>{v.loop=true;v.muted=true;});
  async function toggleCheck(){
   await page.keyboard.press('Space');await page.waitForTimeout(300);
   assert.equal(await video.evaluate(v=>v.paused),false,'一次空格应持续播放');
   const time=await video.evaluate(v=>v.currentTime);await page.waitForTimeout(250);
   assert.notEqual(await video.evaluate(v=>v.currentTime),time,'播放时间应持续推进');
   await page.keyboard.press('Space');assert.equal(await video.evaluate(v=>v.paused),true,'第二次空格应暂停');
  }
  await video.focus();await toggleCheck();
  await page.locator('#worksPreviewFullscreen').click();
  await page.waitForFunction(()=>Boolean(document.fullscreenElement));
  await page.locator('#worksPreviewFrame').evaluate(el=>{el.tabIndex=-1;el.focus();});
  await page.mouse.move(5,5);await toggleCheck();
  await video.focus();await page.keyboard.down('Space');
  await page.keyboard.down('Space');await page.keyboard.down('Space');
  await page.keyboard.up('Space');await page.waitForTimeout(200);
  assert.equal(await video.evaluate(v=>v.paused),false,'长按重复事件不能反复切换');
  await page.keyboard.press('Space');assert.equal(await video.evaluate(v=>v.paused),true);
  await page.evaluate(()=>document.exitFullscreen());
  await page.locator('#closeWorksPreview').focus();await toggleCheck();
  assert.equal(await page.locator('#worksPreviewDialog').evaluate(el=>el.open),true,'空格释放不能点击关闭按钮');
  assert.deepEqual(errors,[]);
  console.log('PASS: focused native video, fullscreen margin, hold repeat, keyup button suppression, actual playback clock');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
