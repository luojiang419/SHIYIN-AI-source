// 用同一隔离项目和 512px PNG 对照指定基线 JS；不读取用户画布或调用生成 API。
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
(async()=>{
    const base=process.argv[2] || 'http://127.0.0.1:3013';
    const dir=process.argv[3] || '测试/画布资源与节点回归-20260905';
    fs.mkdirSync(dir,{recursive:true});
    const png=execFileSync('python',['-c',"from PIL import Image; import sys; Image.effect_noise((512,512),64).convert('RGB').save(sys.stdout.buffer,format='PNG')"],{maxBuffer:4*1024*1024});
    const baselineRef=process.argv[4] || 'b6e762c';
    const baseline=execFileSync('git',['show',`${baselineRef}:static/js/canvas.js`],{encoding:'utf8',maxBuffer:8*1024*1024});
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    const report=[];
    try {
        for(const variant of ['baseline','current']) for(let sample=0;sample<3;sample++){
            const page=await browser.newPage({viewport:{width:1440,height:1000}});
            let renders=0,previewRequests=0;
            page.on('console',m=>{if(m.text().startsWith('[fixture-render]'))renders++;});
            await page.addInitScript(()=>{
                document.addEventListener('load',event=>{
                    if(!window.fixtureFirstLoaded && event.target?.matches?.('img[data-preview-src]') && event.target.naturalWidth===512) window.fixtureFirstLoaded=performance.now();
                },true);
            });
            if(variant==='baseline') await page.route('**/static/js/canvas.js?*',route=>route.fulfill({contentType:'text/javascript',body:baseline.replace('function render(){','function render(){ console.log("[fixture-render]");')}));
            await page.route('**/api/canvases/resource-benchmark',async route=>{
                const response=await route.fetch();const data=await response.json();
                data.canvas.nodes=data.canvas.nodes.filter(n=>['depth','pose'].includes(n.id)).map((n,i)=>({...n,x:6000+i*800,y:0}));
                for(let i=0;i<300;i++) data.canvas.nodes.push({id:`media-${i}`,type:'image',x:(i%20)*300,y:Math.floor(i/20)*230,w:260,h:180,url:`/assets/input/fixture-${i}.png`,natural_w:512,natural_h:512});
                await route.fulfill({json:data});
            });
            await page.route('**/api/media-preview?*',async route=>{
                previewRequests++;
                await new Promise(resolve=>setTimeout(resolve,80));
                await route.fulfill({contentType:'image/png',body:png}).catch(()=>{});
            });
            await page.goto(`${base}/static/canvas.html?id=resource-benchmark&canvasPerf=1`);
            await page.waitForFunction(()=>window.fixtureFirstLoaded>0);
            await page.waitForTimeout(1100);
            const loaded=await page.evaluate(()=>({firstLoadedMs:Math.round(window.fixtureFirstLoaded),nodes:document.querySelectorAll('.node').length,loadedImages:[...document.querySelectorAll('img[data-preview-src]')].filter(img=>img.complete&&img.naturalWidth===512).length}));
            assert.equal(loaded.nodes,302);assert.ok(loaded.loadedImages>0);
            if(variant==='current') assert.equal(renders,1);
            report.push({variant,sample,renders,previewRequests,...loaded});
            await page.close();
        }
        fs.writeFileSync(path.join(dir,'resource-benchmark.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
    }finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
