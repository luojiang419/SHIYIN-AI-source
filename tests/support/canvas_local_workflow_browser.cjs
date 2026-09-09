// 使用 canvas_startup_fixture.py；仅访问隔离内存工程，模型响应全部拦截。
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
    const base=process.argv[2] || 'http://127.0.0.1:3027',dir=process.argv[3];
    fs.mkdirSync(dir,{recursive:true});
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    try {
        const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[],film=[],model=[];
        if(process.env.WORKFLOW_CANDIDATE_DIR) await page.route('**/static/**',route=>{
            const relative=decodeURIComponent(new URL(route.request().url()).pathname).replace(/^\//,'');
            const file=path.join(process.env.WORKFLOW_CANDIDATE_DIR,relative);
            return fs.existsSync(file)?route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.js')?'text/javascript':'text/html'}):route.continue();
        });
        page.on('pageerror',error=>errors.push(error.message));
        await page.route('**/api/canvas-film-workflow',route=>{film.push(route.request().url());return route.fulfill({status:503,json:{detail:'film 未启动'}});});
        await page.route('**/api/canvas-llm',route=>{model.push('analyze');return route.fulfill({json:{text:'人物站在窗前，侧面近景，自然光。'}});});
        await page.route(/\/api\/(?:person-depth|depth)\/estimate$/,route=>route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jEOsAAAAASUVORK5CYII=','base64')}));
        await page.route('**/api/canvas-image-tasks**',route=>{
            if(route.request().method()==='POST'){model.push('image');return route.fulfill({json:{task_id:'local-image-task'}});}
            return route.fulfill({json:{status:'succeeded',result:{images:[{url:'/fixture.png?generated=1',kind:'image'}]}}});
        });
        await page.route('**/api/canvas-video',route=>{model.push('video');return route.fulfill({json:{videos:[{url:'/fixture.mp4',kind:'video'}]}});});
        const nodes=[...['a','b','c'].map((id,index)=>({id,type:'image',url:`/fixture.png?${id}`,name:id,x:0,y:index*370,w:300})),
            {id:'g',type:'group',items:['b','a'],x:0,y:0,w:350,h:800},
            {id:'p',type:'film-prepare-assets',x:700,y:0,w:960},{id:'c1',type:'film-confirm-shots',x:1800,y:0,w:960},
            {id:'v',type:'film-video',x:2900,y:0,w:520}];
        const connections=[['a','p'],['g','p'],['c','p'],['p','c1'],['c1','v']].map(([from,to],i)=>({id:`edge${i}`,from,to,inputRole:'workflow'}));
        await page.request.put(`${base}/api/canvases/local-workflow`,{data:{nodes,connections,viewport:{x:-600,y:80,scale:1},title:'独立资产工作流'}});
        await page.goto(`${base}/static/canvas.html?id=local-workflow`);
        await page.waitForFunction(()=>document.querySelectorAll('[data-id="p"] .wf-shot').length===3);
        assert.equal(film.length,0);assert.equal(model.length,0);
        assert.deepEqual(await page.evaluate(()=>window.CanvasFilmWorkflow.sourceFor(nodes.find(n=>n.id==='p'),nodes,connections).frames.map(n=>n.id)),['a','b','c']);
        assert.equal(await page.evaluate(()=>classicFilmInputAllowsMultiple('p','workflow')),true);
        const focus=async id=>page.evaluate(id=>{const n=nodes.find(n=>n.id===id);viewport={x:90-n.x,y:100-n.y,scale:1};applyViewport();},id);
        await focus('p');
        await page.locator('[data-id="p"] [data-wf-fullscreen]').click();
        await page.locator('.wf-fullscreen [data-wf-action="analyze"][data-shot]').first().click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='p').workflowSnapshot.shots[0].content.includes('窗前'));
        await page.locator('.wf-fullscreen [data-wf-param="replicationInstructions"]').fill('保持人物朝向');
        await page.locator('.wf-fullscreen [data-wf-close]').click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='p').workflowSnapshot.parameters.replicationInstructions==='保持人物朝向');
        await page.waitForFunction(()=>!nodes.find(n=>n.id==='p').workflowBusy);
        await page.screenshot({path:`${dir}/prepare.png`});
        await focus('c1');
        const field=page.locator('[data-id="c1"] [data-wf-shot-field="content"]').first();
        await field.fill('手动镜头描述');await field.press('Tab');
        await page.waitForFunction(()=>nodes.find(n=>n.id==='p').workflowSnapshot.shots[0].content==='手动镜头描述');
        await page.locator('[data-id="c1"] [data-wf-action="confirm"]').click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='p').workflowSnapshot.shots.every(s=>s.confirmed));
        await page.waitForFunction(()=>!nodes.find(n=>n.id==='c1').workflowBusy);
        await page.screenshot({path:`${dir}/confirm.png`});
        await page.evaluate(()=>saveCanvas());await page.reload();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='p')?.workflowSnapshot?.shots[0]?.content==='手动镜头描述');
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='p').workflowSnapshot.shots.every(s=>s.confirmed)),true);
        await focus('p');
        await page.locator('[data-id="p"] [data-wf-action="replicate"][data-shot]').first().click();
        await page.waitForFunction(()=>nodes.find(n=>n.id==='p').workflowSnapshot.shots[0].replica || nodes.find(n=>n.id==='p').workflowError,{},{timeout:30000});
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='p').workflowError),'',JSON.stringify(await page.evaluate(()=>nodes.filter(n=>n.runError || n.workflowError || n._pending).map(n=>({id:n.id,error:n.runError || n.workflowError,pending:n._pending})))));
        assert.ok(model.includes('image'),'真实分镜生成路径已提交到隔离图片任务接口');
        await page.evaluate(()=>window.CanvasFilmWorkflow.request(nodes.find(n=>n.id==='c1'),'confirm',{shot_id:'shot:a'}));
        await page.evaluate(()=>window.CanvasFilmWorkflow.request(nodes.find(n=>n.id==='v'),'generate',{shot_id:'shot:a'}));
        assert.ok(model.includes('video'));
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='p').workflowSnapshot.tasks[0].status),'completed');
        assert.equal(film.length,0);assert.deepEqual(errors,[]);
        fs.writeFileSync(`${dir}/result.json`,JSON.stringify({filmRequests:film.length,modelCalls:model,errors,passed:true},null,2));
        console.log('PASS: 混合连接、去重、自动同步无模型调用、全屏编辑、确认、保存重开、真实图片/视频生成调用链；film 请求为零。');
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
