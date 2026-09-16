const {chromium} = require('playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');

(async () => {
    const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    const browser = await chromium.launch({headless:true, channel:'msedge'});
    try {
        const context = await browser.newContext({viewport:{width:1440,height:1000}});
        await context.addCookies(input.cookies.map(c=>({...c,url:input.base})));
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error=>errors.push(error.message));
        await page.goto(`${input.base}/static/canvas.html?id=${input.id}&canvasPerf=1`);
        await page.waitForFunction(()=>canvas?.id && document.querySelector('#nodes img')?.naturalWidth>0);
        await page.waitForTimeout(800);
        const report = await page.evaluate(async () => {
            const frame = () => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
            const check = (condition, message) => { if(!condition) throw Error(message); };
            const root = document.querySelector('#nodes .image-node');
            const img = root.querySelector('img');
            const id = root.dataset.id;
            const origin = {...viewport};
            render(); await frame();
            check(canvasNodeDomIndex.get(id) === root, '无变更 render 重建了节点');
            check(root.querySelector('img') === img, '无变更 render 重建了图片');
            viewport.x -= 3500; applyViewport(); await frame();
            check(!root.isConnected, '离屏普通节点没有卸载');
            Object.assign(viewport, origin); applyViewport(); await frame();
            check(canvasNodeDomIndex.get(id) === root && root.querySelector('img') === img && img.naturalWidth>0, '往返未保留 DOM 与像素');
            const sibling = [...canvasNodeDomIndex.values()].find(el=>el!==root);
            const siblingId = sibling.dataset.id;
            const node = nodes.find(n=>n.id===id);
            img.dataset.previewState = 'failed';
            img.dataset.previewState = 'queued';
            activateEngineMedia(root);
            await new Promise((resolve,reject)=>{
                if(img.complete && img.naturalWidth>0 && img.dataset.previewState==='loaded') return resolve();
                img.addEventListener('load',resolve,{once:true});
                setTimeout(()=>reject(Error('原生图片重试未完成')),5000);
            });
            node.w += 10; refreshNodes([id]); await frame();
            check(canvasNodeDomIndex.get(siblingId) === sibling, '单节点变更重建了其他节点');
            check(canvasNodeDomIndex.get(id).style.width === `${node.w}px`, '节点尺寸修改未生效');
            viewport.x -= 3500; applyViewport(); await frame();
            node.w += 10; refreshNodes([id]); await frame();
            Object.assign(viewport, origin); applyViewport(); await frame();
            check(canvasNodeDomIndex.get(id).style.width === `${node.w}px`, '离屏修改返回后仍为旧内容');
            nodes = nodes.filter(n=>n.id!==id); render(); await frame();
            check(!canvasNodeDomIndex.has(id), '删除后仍挂载节点');
            const samples=[];
            for(let i=0;i<45;i++){
                const start=performance.now(); viewport.x-=20; applyViewport();
                await new Promise(resolve=>requestAnimationFrame(resolve)); samples.push(performance.now()-start);
            }
            const stats=CanvasEngine.stats();
            check(stats.cached<=stats.mounted+192, '离屏缓存超过上限');
            check(!document.querySelector('img[data-preview-state="evicted"]'), '仍触发旧媒体淘汰');
            const timings=samples.sort((a,b)=>a-b);
            for(let row=0;row<15;row++){
                viewport.y=-row*700; applyViewport(); await frame();
                const step=CanvasEngine.stats();
                check(step.cached<=step.mounted+192, '连续跨区浏览缓存超过上限');
            }
            const swept=CanvasEngine.stats();
            Object.assign(viewport,origin); applyViewport(); await frame();
            check(canvasNodeDomIndex.get(siblingId)?.querySelector('img')?.getAttribute('src'), '淘汰后的节点返回没有直接媒体源');
            return {nodes:nodes.length,stats,swept,panMedianMs:timings[22],panP95Ms:timings[42],reuse:true,offscreenUpdate:true,delete:true};
        });
        const types = ['image','prompt','loop','group','promptGroup','llm','generator','batchGenerator','video','linkfox-video','rh','lookbook','ecom-model','ecom-product','ecom-scene','ecom-compose','ecom-video','film-storyboard','film-line-art','film-video','dwpose','depthMap','depthVideo','director3d','poseReplicate','multiView','resultCompare','output','storyboardMerge','panorama','topazVideo'];
        for(const type of types){
            await page.evaluate(type=>{
                CanvasEngine.clear();
                nodes=[{id:'type-'+type,type,x:0,y:0,w:500,h:500}]; connections=[];
                viewport={x:40,y:40,scale:1}; render();
            },type);
            await page.waitForFunction(()=>document.querySelector('#nodes .node .node-body'));
        }
        await page.evaluate(()=>{
            CanvasEngine.clear();
            nodes=[{id:'prompt-source',type:'prompt',text:'before',x:0,y:0}, {id:'target',type:'generator',x:500,y:0}];
            connections=[{id:'edge',from:'prompt-source',to:'target'}]; render();
            const target=canvasNodeDomIndex.get('target');
            nodes[0].text='after'; render();
            if(target===canvasNodeDomIndex.get('target')) throw Error('上游内容变化未刷新关联节点');
            if(document.querySelectorAll('#links .link-hit').length!==1) throw Error('连线未保留');
        });
        await page.screenshot({path:input.screenshot.replace('.png','-render-chain.png')});
        await page.evaluate(()=>{ CanvasEngine.clear(); if(CanvasEngine.stats().cached!==0) throw Error('清空后缓存未释放'); });
        assert.deepEqual(errors,[]);
        console.log(JSON.stringify({...report,nodeTypes:types.length,errors}));
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
