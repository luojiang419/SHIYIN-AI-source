const {chromium}=require('playwright');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const output='.codex-artifacts/media-architecture';
fs.mkdirSync(output,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  const report=[];
  try{
    for(const [variant,port] of [['baseline',3051],['current',3052]]){
      const context=await browser.newContext({viewport:{width:1440,height:1000}});
      const base=`http://127.0.0.1:${port}`;
      const login=await context.request.post(base+'/api/account/login',{data:{account:'jiang',password:'jiang'}});
      assert.equal(login.status(),200);
      const api=[];
      for(const surface of ['works','canvas']){
        const page=await context.newPage();
        await page.addInitScript(()=>{
          window.mediaMetrics={longTasks:[],first:0};
          new PerformanceObserver(list=>window.mediaMetrics.longTasks.push(...list.getEntries().map(e=>e.duration))).observe({type:'longtask',buffered:true});
          document.addEventListener('load',event=>{
            if(!window.mediaMetrics.first && event.target.matches?.('img[data-preview-src], .works-card-media img') && event.target.naturalWidth>0)window.mediaMetrics.first=performance.now();
          },true);
        });
        for(const cycle of ['cold','warm']){
          const errors=[];const listener=e=>errors.push(e.message);page.on('pageerror',listener);
          await page.goto(base+(surface==='canvas'?'/static/canvas.html?id=media-benchmark&canvasPerf=1':'/static/works.html'),{waitUntil:'domcontentloaded'});
          await page.waitForFunction(()=>window.mediaMetrics?.first>0,{timeout:30000});
          await page.waitForTimeout(800);
          if(surface==='canvas'){
            await page.evaluate(()=>{
              window.panFrames=[];window.panActive=true;let last=performance.now();
              function tick(now){window.panFrames.push(now-last);last=now;if(window.panActive)requestAnimationFrame(tick)}requestAnimationFrame(tick);
            });
            await page.mouse.move(1250,880);await page.mouse.down({button:'middle'});
            await page.mouse.move(900,650,{steps:30});await page.mouse.up({button:'middle'});
            await page.evaluate(()=>{window.panActive=false});
          }
          const metrics=await page.evaluate(async()=>{
            const frames=[];let last=performance.now();
            for(let i=0;i<45;i++)await new Promise(resolve=>requestAnimationFrame(now=>{frames.push(now-last);last=now;resolve()}));
            frames.sort((a,b)=>a-b);
            const pan=[...(window.panFrames||[])].sort((a,b)=>a-b);
            const media=performance.getEntriesByType('resource').filter(e=>e.name.includes('/api/media-preview') || e.name.includes('/api/download-output') || e.name.includes('/assets/output/'));
            return {...window.mediaMetrics,panFrameP95:pan[Math.floor(pan.length*.95)]||null,frameP95:frames[Math.floor(frames.length*.95)],nodes:document.querySelectorAll('.node').length,
              images:[...document.querySelectorAll('img[data-preview-src], .works-card-media img')].filter(img=>img.naturalWidth>0).length,
              mediaRequests:media.length,mediaBytes:media.reduce((n,e)=>n+e.encodedBodySize,0),
              decodedWidths:[...new Set([...document.querySelectorAll('img[data-preview-src], .works-card-media img')].filter(i=>i.naturalWidth>0).map(i=>i.naturalWidth))]};
          });
          report.push({variant,surface,cycle,api,...metrics,errors});
          console.log(JSON.stringify(report.at(-1)));
          if(variant==='current')await page.screenshot({path:`${output}/${surface}-${cycle}.png`});
          page.off('pageerror',listener);
        }
        await page.close();
      }
      for(let i=0;i<4;i++){
        const start=performance.now();const response=await context.request.get(base+'/api/works?limit=120');
        const data=await response.json();assert.ok(data.works.length===120);assert.equal(data.total,1250);
        api.push(Math.round(performance.now()-start));
      }
      await context.close();
    }
  }finally{
    fs.writeFileSync(output+'/benchmark.json',JSON.stringify(report,null,2));await browser.close();
  }
})().catch(e=>{console.error(e.message.split('Call log:')[0]);process.exitCode=1});
