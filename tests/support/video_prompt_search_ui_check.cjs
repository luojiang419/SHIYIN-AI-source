// 配合 canvas_startup_fixture.py 使用；所有提示词 API 均由浏览器内 stub 接管。
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

(async()=>{
    const base=process.argv[2] || 'http://127.0.0.1:3023';
    const output=process.argv[3] || '.codex-artifacts/video-prompt-ui';
    fs.mkdirSync(output,{recursive:true});
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    const requests=[], errors=[];
    try {
        const page=await browser.newPage({viewport:{width:1440,height:1000}});
        page.on('pageerror',error=>errors.push(error.message));
        await page.route('**/api/canvas-*tasks',async route=>{
            requests.push(route.request().postDataJSON());
            await route.fulfill({json:{task_id:'fixture-prompt'}});
        });
        await page.route('**/api/canvas-prompt-tasks/*',route=>route.fulfill({json:{status:'succeeded',result:{text:'The subject walks left.'}}}));
        await page.goto(`${base}/static/canvas.html?id=prompt-search-classic-${Date.now()}`);
        await page.waitForSelector('.video-node');
        await page.evaluate(()=>{const n=nodes.find(n=>n.id==='video');viewport.x=40-n.x*.5;viewport.y=40;applyViewport();});
        const classic=page.locator('.node[data-id="video"]');
        const toggle=classic.locator('[data-video-prompt-search]');
        assert.equal(await toggle.isChecked(),false);
        await classic.locator('.generator-prompt-input').fill('The subject walks left.');
        await classic.locator('[data-video-prompt-polish]').click();
        await page.waitForFunction(()=>!document.querySelector('[data-id="video"] [data-video-prompt-polish]').disabled);
        assert.equal(requests.at(-1).web_search,false);
        await toggle.check();
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='video').promptWebSearch),true);
        await classic.locator('[data-video-prompt-polish]').click();
        await page.waitForFunction(()=>!document.querySelector('[data-id="video"] [data-video-prompt-polish]').disabled);
        assert.equal(requests.at(-1).web_search,true);
        await page.screenshot({path:path.join(output,'classic.png')});
        await page.waitForTimeout(1300);
        await page.reload();await page.waitForSelector('.video-node');
        assert.equal(await toggle.isChecked(),true,'saved checkbox survives reload');
        await page.evaluate(()=>{const n=nodes.find(n=>n.id==='video');n.prompt='';n.promptWebSearch=false;connections.push({id:'fixture-input',from:'image',to:n.id});refreshNodes([n.id]);});
        await page.evaluate(async()=>{
            const n=nodes.find(n=>n.id==='video');
            await autoParseCanvasVideoPrompt(n,[{url:'/fixture.png',kind:'image'}]);
        });
        assert.equal(requests.at(-1).web_search,false);
        assert.equal(requests.at(-1).images.length,1);

        // 当前产品已将旧智能画布入口重定向到普通画布；验收实际在用的影视节点。
        const id=await page.evaluate(()=>{
            const n=window.CanvasFilmNodes.createNode('film-video',{x:400,y:100},{apiProvider:'custom',model:'private-video'});
            nodes.push(n);render();viewport.x=40-n.x*.5;viewport.y=40;applyViewport();return n.id;
        });
        const smart=page.locator(`[data-id="${id}"]`);
        const smartToggle=smart.locator('[data-video-prompt-search]');
        await smartToggle.waitFor();
        assert.equal(await smartToggle.isChecked(),false);
        await smartToggle.check();
        assert.equal(await page.evaluate(id=>nodes.find(n=>n.id===id).promptWebSearch,id),true);
        await smart.locator('[data-film-field="prompt"]').fill('The subject walks left.');
        await smart.locator('[data-film-action="polish"]').click();
        await page.waitForFunction(id=>!document.querySelector(`[data-id="${id}"] [data-film-action="polish"]`).disabled,id);
        assert.equal(requests.at(-1).web_search,true);
        await smartToggle.uncheck();
        await page.evaluate(async id=>{
            const n=nodes.find(n=>n.id===id);
            await window.CanvasFilmNodes.autoParseVideoPrompt(n,[{url:'/fixture.png',kind:'image',role:'storyboard'}],{visionProvider:()=> 'custom',visionModel:()=> 'private-chat'});
        },id);
        assert.equal(requests.at(-1).web_search,false);
        await page.screenshot({path:path.join(output,'film.png')});
        const legacy=fs.readFileSync(path.join(__dirname,'../../static/js/smart-canvas.js'),'utf8');
        const functionSource=legacy.slice(legacy.indexOf('async function polishSmartVideoPrompt('),legacy.indexOf('async function submitSmartCanvasPromptTask(')).trim();
        await page.evaluate(async source=>{
            window.submitSmartCanvasPromptTask=submitCanvasPromptTask;
            const run=eval(`(${source})`);
            await run({promptWebSearch:false},'The subject walks left.');
            await run({promptWebSearch:true},'The subject walks left.');
        },functionSource);
        assert.deepEqual(requests.slice(-2).map(r=>r.web_search),[false,true]);
        assert.deepEqual(errors,[]);
        const result={requests:requests.map(r=>({search:r.web_search,images:r.images.length})),persisted:true,legacySmartRequestCompatibility:true,errors};
        fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(result,null,2));
        console.log(JSON.stringify(result));
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
