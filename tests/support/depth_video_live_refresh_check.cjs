const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async()=>{
    const base = process.argv[2] || 'http://127.0.0.1:3012';
    const scripts = process.argv[3] || path.join(__dirname,'../../static/js');
    const browser = await chromium.launch({headless:true,channel:'chrome'});
    try{
        const page = await browser.newPage({viewport:{width:1440,height:900}});
        const errors=[];
        page.on('pageerror',error=>errors.push(error.message));
        for(const name of ['canvas.js','canvas-special-nodes.js']){
            await page.route(`**/static/js/${name}*`,route=>route.fulfill({status:200,contentType:'application/javascript',body:fs.readFileSync(path.join(scripts,name))}));
        }
        const canvasId=`depth-live-${Date.now()}`;
        await page.route('**/api/canvases/depth-live-*',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({canvas:{id:canvasId,name:'Depth live check',project:'default',nodes:[],connections:[],viewport:{x:0,y:0,scale:1}}})}));
        await page.route('**/api/runtime/config',route=>route.fulfill({status:200,contentType:'application/json',body:'{}'}));
        await page.goto(`${base}/static/canvas.html?id=${canvasId}`);
        await page.waitForSelector('#world',{state:'attached'});
        await page.waitForFunction(()=>typeof render==='function');
        await page.evaluate(()=>{
            const url='data:video/mp4;base64,AAAA';
            const signature=`${url}|input.mp4|x`;
            const depth={id:'depth-live',type:'depthVideo',x:80,y:80,w:620,h:390,
                depthVideoManualInput:{url,name:'input.mp4',kind:'video'},depthVideoInputSignature:signature,
                depthVideoGeneratedSignature:signature,depthVideoInputUrl:url,depthVideoInputName:'input.mp4',
                outputUrl:url,outputName:'depth.mp4',outputKind:'video',depthVideoStatus:'running',depthVideoProgress:10};
            const video={id:'video-live',type:'video',x:760,y:80,w:410,h:550,model:'veo3-fast'};
            canvas={id:'depth-live-check',title:'Depth live check',nodes:[],connections:[],viewport:{x:0,y:0,scale:1}};
            setCanvasMode(true);
            nodes.push(depth,video);
            connections.push({id:'depth-video-link',from:depth.id,to:video.id});
            viewport.x=0;viewport.y=0;viewport.scale=1;
            render();
            window.__depthLive={depth,video,input:document.querySelector('.depthVideo-node[data-id="depth-live"] [data-depth-video-media="input"]'),output:document.querySelector('.depthVideo-node[data-id="depth-live"] [data-depth-video-media="output"]')};
        });
        const initial=await page.evaluate(()=>document.querySelectorAll('.node[data-id="video-live"] .video-input-item').length);
        assert.equal(initial,1);
        const result=await page.evaluate(async()=>{
            const state=window.__depthLive;
            for(const progress of [25,50,75]){
                state.depth.depthVideoProgress=progress;
                state.depth.depthVideoMessage=`推理 ${progress}%`;
                refreshClassicDepthVideoNode(state.depth);
            }
            refreshGeneratorInputViews();
            const root=document.querySelector('.depthVideo-node[data-id="depth-live"]');
            const target=document.querySelector('.node[data-id="video-live"]');
            return {
                inputPreserved:state.input===root.querySelector('[data-depth-video-media="input"]'),
                outputPreserved:state.output===root.querySelector('[data-depth-video-media="output"]'),
                progress:root.querySelector('[data-depth-video-progress] b')?.textContent,
                status:root.querySelector('.pose-status span:last-child')?.textContent,
                modelProgress:state.depth.depthVideoProgress,
                inNodes:nodes.includes(state.depth),
                worldDisplay:getComputedStyle(document.querySelector('#world')).display,
                thumbs:target.querySelectorAll('.video-input-item').length,
                links:connections.filter(item=>item.id==='depth-video-link').length
            };
        });
        assert.deepEqual(result,{inputPreserved:true,outputPreserved:true,progress:'75%',status:'推理 75%',modelProgress:75,inNodes:true,worldDisplay:'block',thumbs:1,links:1});
        assert.deepEqual(errors,[]);
        console.log(JSON.stringify(result));
        await page.close();
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
