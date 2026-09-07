// 真实画布 UI + 隔离 HTTP fixture；不访问用户工程或付费生成 API。
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict'), fs=require('node:fs');
(async()=>{
    const base=process.argv[2] || 'http://127.0.0.1:3018', dir=process.argv[3] || 'tests/artifacts/film-workflow';
    fs.mkdirSync(dir,{recursive:true});
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    try {
        const page=await browser.newPage({viewport:{width:1500,height:1050}}), errors=[],calls=[];
        if(process.env.WORKFLOW_STAGED_ROOT){
            for(const [url,file,contentType] of [['**/static/canvas.html?*','static_canvas.html.staged','text/html'],['**/static/js/canvas.js?*','static_js_canvas.js.staged','application/javascript']]){
                await page.route(url,route=>route.fulfill({body:fs.readFileSync(`${process.env.WORKFLOW_STAGED_ROOT}/${file}`),contentType}));
            }
        }
        page.on('pageerror',e=>errors.push(e.message));
        const nodes=[{id:'group',type:'group',title:'导出画板',items:['frame-a','frame-b'],x:0,y:0,w:650,h:500},
            ...['a','b'].map((id,i)=>({id:`frame-${id}`,type:'image',name:id,url:'/static/assets/camera-reference/angle-eye-front.png',x:30+i*290,y:60,w:260,h:230})),
            {id:'prepare',type:'film-prepare-assets',x:800,y:0,w:960},{id:'confirm',type:'film-confirm-shots',x:1900,y:0,w:960},
            {id:'video-list',type:'film-video',x:3000,y:0,w:520,apiProvider:'custom',model:'private-video'},
            {id:'ordinary',type:'film-video',x:4100,y:0,w:520,apiProvider:'custom',model:'private-video'}];
        const connections=[{id:'a',from:'group',to:'prepare',inputRole:'workflow'},{id:'b',from:'prepare',to:'confirm',inputRole:'workflow'},{id:'c',from:'confirm',to:'video-list',inputRole:'workflow'}];
        for(const [id,title] of [['prepare','准备资产'],['confirm','确认镜头'],['video-list','视频生成']]){
            const n=nodes.find(n=>n.id===id);
            nodes.push({id:`function-${id}`,type:'group',title,workflowFunctionGroup:true,items:[id],x:n.x-24,y:n.y-64,w:1008,h:790});
        }
        const snapshot={scriptId:'fixture-script',name:'画板拍摄脚本',parameters:{generationMode:'quick',model:'fixture',aspectRatio:'16:9',imageSize:'2K',quality:'high',sourceFrameMode:'colorReference',videoSteps:12},
            options:{models:[{id:'fixture',label:'测试模型'}],aspectRatios:['16:9','9:16'],imageSizes:['2K','4K'],qualities:['high'],videoBackend:'fixture'},
            shots:[1,2].map(n=>({id:`shot-${n}`,number:n,frame:'/static/assets/camera-reference/angle-eye-front.png',content:`镜头 ${n} 描述`,prompt:`镜头 ${n} 提示词`,confirmed:true,durationSeconds:5})),assets:[],tasks:[]};
        await page.route('**/api/canvas-film-workflow',async route=>{
            const body=route.request().postDataJSON();calls.push(body);
            if(body.action==='parameters') Object.assign(snapshot.parameters,body.parameters);
            if(body.action==='edit-shot') Object.assign(snapshot.shots.find(s=>s.id===body.shot_id),body.parameters);
            await route.fulfill({json:{ok:true,project_id:'fixture-project',snapshot}});
        });
        await page.request.put(`${base}/api/canvases/film-workflow-ui`,{data:{id:'film-workflow-ui',title:'影视联动 UI 回归',nodes,connections,viewport:{x:80,y:130,scale:.28}}});
        await page.goto(`${base}/static/canvas.html?id=film-workflow-ui`);
        await page.waitForFunction(()=>document.querySelectorAll('.film-workflow-panel').length===3);
        await page.waitForFunction(()=>document.querySelector('[data-id="confirm"] .wf-shot'));
        assert.equal(calls.filter(c=>c.action==='sync').length,1,'connection creates only one script');
        assert.equal(calls.filter(c=>c.action==='generate').length,0,'connection never generates');
        assert.equal(await page.locator('[data-id="ordinary"] .film-node-panel').count(),1);
        const focus=async id=>{await page.evaluate(id=>{const n=nodes.find(n=>n.id===id);viewport={x:120-n.x,y:120-n.y,scale:1};applyViewport();},id);};
        await focus('prepare');
        await page.locator('[data-id="prepare"] [data-wf-param="imageSize"]').selectOption('4K');
        await page.waitForFunction(()=>nodes.find(n=>n.id==='prepare').workflowSnapshot?.parameters?.imageSize==='4K');
        await page.locator('[data-id="prepare"]').screenshot({path:`${dir}/prepare.png`});
        await focus('confirm');
        const field=page.locator('[data-id="confirm"] [data-wf-shot-field="content"]').first();
        await field.fill('手动修改镜头描述');await field.press('Tab');
        await page.waitForFunction(()=>nodes.find(n=>n.id==='confirm').workflowSnapshot?.shots?.[0]?.content==='手动修改镜头描述');
        await page.locator('[data-id="confirm"]').screenshot({path:`${dir}/confirm.png`});
        await focus('video-list');
        await page.locator('[data-id="video-list"] [data-wf-action="generate"][data-shot="shot-1"]').click();
        await page.waitForTimeout(150);
        await page.locator('[data-id="video-list"] .wf-primary').click();
        await page.waitForTimeout(150);
        assert.deepEqual(calls.filter(c=>c.action==='generate').map(c=>c.shot_id),['shot-1','']);
        await page.locator('[data-id="video-list"]').screenshot({path:`${dir}/video-list.png`});
        await page.evaluate(()=>deleteConnection('c'));
        await page.waitForFunction(()=>!document.querySelector('[data-id="video-list"] .film-workflow-panel'));
        assert.equal(await page.locator('[data-id="video-list"] .film-node-panel').count(),1);
        await page.evaluate(()=>{connections.push({id:'c2',from:'confirm',to:'video-list',inputRole:'storyboard'});syncGeneratorInputs();render();scheduleSave();});
        await page.waitForFunction(()=>!!document.querySelector('[data-id="video-list"] .film-workflow-panel'));
        await page.evaluate(()=>saveCanvas());
        await page.reload();
        await page.waitForFunction(()=>document.querySelectorAll('.film-workflow-panel').length===3);
        assert.equal(await page.locator('[data-id="confirm"] .wf-shot').count(),2);
        assert.equal(await page.locator('[data-id="group"]').count(),1,'initial render keeps source group');
        assert.equal(await page.locator('.workflow-function-group').count(),3);
        assert.ok(await page.evaluate(()=>linkCreateOptions({originId:'group',originKind:'out'}).some(o=>o.type==='film-prepare-assets')));
        assert.deepEqual(errors,[]);
        fs.writeFileSync(`${dir}/result.json`,JSON.stringify({passed:true,checks:['自动建脚本','普通节点不变','参数保存','镜头编辑','单个/全部生成范围','断线恢复','重连列表','保存重开','无脚本异常'],calls:calls.map(c=>({action:c.action,shot_id:c.shot_id}))},null,2));
        console.log('film workflow browser: 9 checks passed');
    } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
