const {chromium}=require('playwright');
const assert=require('node:assert/strict');

(async()=>{
    const base=process.argv[2] || 'http://127.0.0.1:3024';
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    const requests=[];
    try {
        const page=await browser.newPage();
        const errors=[];
        page.on('pageerror',error=>errors.push(error.message));
        for(const kind of ['canvas-prompt-polish-tasks','canvas-video-auto-parse-tasks']){
            await page.route(`**/api/${kind}`,async route=>{
                const editorValues=await page.evaluate(()=>({
                    classic:document.querySelector('[data-id="video"] .generator-prompt-input')?.value,
                    film:document.querySelector('[data-film-field="prompt"]')?.value,
                    ecom:document.querySelector('[data-id="ecom-repeat"] .generator-prompt-input')?.value,
                }));
                requests.push({kind,payload:route.request().postDataJSON(),editorValues});
                await route.fulfill({json:{task_id:`repeat-${requests.length}`}});
            });
        }
        await page.route('**/api/canvas-prompt-tasks/*',route=>route.fulfill({json:{status:'succeeded',result:{text:`新结果 ${requests.length}`}}}));
        await page.goto(`${base}/static/canvas.html?id=video-prompt-repeat-${Date.now()}`);
        const classic=page.locator('.node[data-id="video"]');
        await classic.locator('[data-video-prompt-polish]').waitFor();
        await classic.locator('.generator-prompt-input').fill('原始创意');
        await classic.locator('[data-video-prompt-polish]').click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='video').prompt==='新结果 1');
        await page.evaluate(()=>{nodes.find(n=>n.id==='video').videoPromptLastResult={prompt:'旧生成结果'};});
        await classic.locator('[data-video-prompt-polish]').click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='video').prompt==='新结果 2');
        assert.deepEqual(requests.slice(0,2).map(item=>item.payload.prompt),['原始创意','原始创意']);
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='video').videoPromptLastResult),undefined);

        const filmId=await page.evaluate(()=>{
            const node=window.CanvasFilmNodes.createNode('film-video',{x:400,y:100},{apiProvider:'custom',model:'private-video'});
            node.id=uid('n');
            nodes.push(node);render();return node.id;
        });
        const film=page.locator(`[data-id="${filmId}"]`);
        await film.locator('[data-film-field="prompt"]').fill('影视原始创意');
        await film.locator('[data-film-action="polish"]').click();
        await page.waitForFunction(id=>nodes.find(n=>n.id===id).prompt==='新结果 3',filmId);
        await page.evaluate(id=>{nodes.find(n=>n.id===id).videoPromptLastResult={prompt:'旧生成结果'};},filmId);
        await film.locator('[data-film-action="polish"]').click();
        await page.waitForFunction(id=>nodes.find(n=>n.id===id).prompt==='新结果 4',filmId);
        assert.deepEqual(requests.slice(2,4).map(item=>item.payload.prompt),['影视原始创意','影视原始创意']);
        assert.equal(await page.evaluate(id=>nodes.find(n=>n.id===id).videoPromptLastResult,filmId),undefined);

        await page.evaluate(()=>{
            const node=nodes.find(n=>n.id==='video');node.prompt='';delete node.videoPromptTaskResult;
            connections.push({id:'repeat-reference',from:'image',to:node.id});refreshNodes([node.id]);
        });
        await classic.locator('[data-video-prompt-polish]').click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='video').prompt==='新结果 5');
        await classic.locator('[data-video-prompt-polish]').click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='video').prompt==='新结果 6');
        assert.deepEqual(requests.slice(4,6).map(item=>[item.kind,item.payload.prompt]),[
            ['canvas-video-auto-parse-tasks',''],['canvas-video-auto-parse-tasks','']
        ]);
        await page.evaluate(id=>{
            const node=nodes.find(n=>n.id===id);node.prompt='';delete node.videoPromptTaskResult;
            connections.push({id:'repeat-film-reference',from:'image',to:id,inputRole:'storyboard'});
            refreshNodes([id]);
        },filmId);
        await film.locator('[data-film-action="polish"]').click();
        await page.waitForFunction(id=>nodes.find(n=>n.id===id).prompt==='新结果 7',filmId);
        await film.locator('[data-film-action="polish"]').click();
        await page.waitForFunction(id=>nodes.find(n=>n.id===id).prompt==='新结果 8',filmId);
        assert.deepEqual(requests.slice(6,8).map(item=>[item.kind,item.payload.prompt]),[
            ['canvas-video-auto-parse-tasks',''],['canvas-video-auto-parse-tasks','']
        ]);
        await film.locator('[data-film-action="parse"]').click();
        await page.waitForFunction(id=>nodes.find(n=>n.id===id).prompt==='新结果 9',filmId);
        await film.locator('[data-film-action="parse"]').click();
        await page.waitForFunction(id=>nodes.find(n=>n.id===id).prompt==='新结果 10',filmId);
        assert.deepEqual(requests.slice(8,10).map(item=>[item.kind,item.payload.prompt]),[
            ['canvas-video-auto-parse-tasks',''],['canvas-video-auto-parse-tasks','']
        ]);
        await classic.locator('.generator-prompt-input').fill('用户修改后的创意');
        await classic.locator('[data-video-prompt-polish]').click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='video').prompt==='新结果 11');
        assert.equal(requests.at(-1).payload.prompt,'用户修改后的创意');
        await page.evaluate(()=>{
            nodes.push({id:'ecom-repeat',type:'ecom-video',x:900,y:300,apiProvider:'custom',model:'private-video',prompt:''});
            render();
        });
        const ecom=page.locator('[data-id="ecom-repeat"]');
        await ecom.locator('[data-video-prompt-polish]').waitFor();
        await ecom.locator('.generator-prompt-input').fill('商品原始创意');
        await ecom.locator('[data-video-prompt-polish]').click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='ecom-repeat').prompt==='新结果 12');
        await ecom.locator('[data-video-prompt-polish]').click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='ecom-repeat').prompt==='新结果 13');
        assert.deepEqual(requests.slice(11,13).map(item=>item.payload.prompt),['商品原始创意','商品原始创意']);
        assert(requests.every((item,index)=>{
            const editor=index===2 || index===3 || (index>=6 && index<=9) ? 'film' : index>=11 ? 'ecom' : 'classic';
            return item.editorValues[editor]==='';
        }),'新请求发出前必须清空对应编辑框');
        assert.deepEqual(errors,[]);
        console.log(JSON.stringify({requests:requests.length,classicPolish:true,filmPolish:true,classicAutoParse:true,filmAutoParse:true,filmParseButton:true,ecomPolish:true,manualEdit:true}));
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
