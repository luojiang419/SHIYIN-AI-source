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
            nodes.push({id:`function-${id}`,type:'group',title,workflowFunctionGroup:true,workflowOwnerId:id,items:[id],x:n.x-24,y:n.y-64,w:1008,h:790});
        }
        const snapshot={scriptId:'fixture-script',name:'画板拍摄脚本',parameters:{generationMode:'quick',model:'fixture',aspectRatio:'16:9',imageSize:'2K',quality:'high',sourceFrameMode:'colorReference',videoSteps:12},
            options:{models:[{id:'fixture',label:'测试模型'}],aspectRatios:['16:9','9:16'],imageSizes:['2K','4K'],qualities:['high'],videoBackend:'fixture'},
            shots:Array.from({length:41},(_,i)=>i+1).map(n=>({id:`shot-${n}`,number:n,frame:'/static/assets/camera-reference/angle-eye-front.png',content:`镜头 ${n} 描述`,prompt:`镜头 ${n} 提示词`,confirmed:true,durationSeconds:5})),assets:[{id:'asset-1',name:'测试资产',url:'/static/assets/camera-reference/angle-eye-front.png'}],tasks:[]};
        let offlineOnce=true;
        await page.route('**/api/canvas-film-workflow',async route=>{
            const body=route.request().postDataJSON();calls.push(body);
            if(offlineOnce){offlineOnce=false;return route.fulfill({status:503,json:{ok:false,detail:'film 测试服务尚未启动',retryable:true}});}
            if(body.action==='parameters') Object.assign(snapshot.parameters,body.parameters);
            if(body.action==='edit-shot') Object.assign(snapshot.shots.find(s=>s.id===body.shot_id),body.parameters);
            if(body.action==='depth')return route.fulfill({json:{ok:true,project_id:'fixture-project',snapshot,job:{id:'depth-job',status:'running'}}});
            if(body.action==='job')return route.fulfill({json:{ok:true,project_id:'fixture-project',snapshot,job:{id:'depth-job',status:'completed'}}});
            await route.fulfill({json:{ok:true,project_id:'fixture-project',snapshot}});
        });
        await page.request.put(`${base}/api/canvases/film-workflow-ui`,{data:{id:'film-workflow-ui',title:'影视联动 UI 回归',nodes,connections,viewport:{x:80,y:130,scale:.28}}});
        await page.goto(`${base}/static/canvas.html?id=film-workflow-ui`);
        await page.waitForFunction(()=>document.querySelectorAll('.film-workflow-panel').length===3);
        await page.waitForFunction(()=>document.querySelector('[data-id="confirm"] .wf-shot'));
        assert.equal(calls.filter(c=>c.action==='sync').length,2,'failed discovery retries once when film becomes available');
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
        const wheelScroll=async(selector)=>{
            const scroll=page.locator(selector), before=await page.evaluate(()=>({...viewport}));
            const box=await scroll.boundingBox();
            await page.mouse.move(box.x+box.width-15,box.y+Math.min(80,box.height/2));
            await page.mouse.wheel(0,520);
            await page.waitForFunction(selector=>document.querySelector(selector).scrollTop>50,selector);
            assert.deepEqual(await page.evaluate(()=>({...viewport})),before,'panel wheel must not zoom or pan canvas');
        };
        for(const id of ['prepare','confirm']){
            await focus(id);
            await wheelScroll(`[data-id="${id}"] .wf-shot-scroll`);
            await wheelScroll(`[data-id="${id}"] .wf-parameters`);
            await page.locator(`[data-id="${id}"] [data-wf-fullscreen]`).click();
            const dialog=page.locator('dialog.wf-fullscreen');
            assert.equal(await dialog.evaluate(el=>el.open),true);
            const bounds=await dialog.boundingBox();
            assert.equal(bounds.width,1500);assert.equal(bounds.height,1050);
            await wheelScroll('dialog.wf-fullscreen .wf-shot-scroll');
            if(await page.locator('dialog .wf-parameters').evaluate(el=>el.scrollHeight>el.clientHeight+80)) await wheelScroll('dialog.wf-fullscreen .wf-parameters');
            await page.locator('dialog .wf-shot-scroll').evaluate(el=>el.scrollTop=0);
            if(id==='prepare'){
                await page.locator('dialog [data-wf-param="imageSize"]').selectOption('2K');
                await page.waitForFunction(()=>nodes.find(n=>n.id==='prepare').workflowSnapshot.parameters.imageSize==='2K');
                await page.locator('dialog [data-wf-action="depth"][data-shot="shot-1"]').click();
                await page.waitForFunction(()=>!nodes.find(n=>n.id==='prepare').workflowBusy);
                assert.ok(calls.some(c=>c.action==='depth' && c.shot_id==='shot-1'));
                assert.ok(calls.some(c=>c.action==='job' && c.job_id==='depth-job'),'fullscreen polls the original task');
                await page.locator('dialog [data-wf-binding="shot-1"]').selectOption('asset-1');
                await page.waitForFunction(()=>!nodes.find(n=>n.id==='prepare').workflowBusy);
                await page.locator('dialog [data-wf-asset="asset-1"]').dragTo(page.locator('dialog [data-wf-shot="shot-1"]'));
                await page.waitForFunction(()=>!nodes.find(n=>n.id==='prepare').workflowBusy);
                assert.equal(calls.filter(c=>c.action==='bind-asset' && c.shot_id==='shot-1' && c.asset_id==='asset-1').length,2,'select and drag use the same asset binding path');
            } else {
                const edit=page.locator('dialog [data-wf-shot-field="content"]').first();
                await edit.fill('全屏编辑保存到 film');await edit.press('Tab');
                await page.waitForFunction(()=>nodes.find(n=>n.id==='confirm').workflowSnapshot.shots[0].content==='全屏编辑保存到 film');
                await page.locator('dialog [data-wf-action="group-start"][data-shot="shot-1"]').click();
                await page.waitForFunction(()=>!nodes.find(n=>n.id==='confirm').workflowBusy);
                assert.ok(calls.some(c=>c.action==='group-start' && c.shot_id==='shot-1'));
            }
            await page.locator('dialog .wf-shot-scroll').evaluate(el=>el.scrollTop=0);
            await page.locator('dialog [data-wf-action="next"]').click();
            await page.waitForFunction(()=>document.querySelector('dialog [data-wf-shot]')?.dataset.wfShot==='shot-13');
            await dialog.screenshot({path:`${dir}/${id}-fullscreen.png`});
            await page.keyboard.press('Escape');
            assert.equal(await page.locator('dialog.wf-fullscreen').count(),0);
            await page.waitForFunction(id=>document.querySelector(`[data-id="${id}"] [data-wf-shot]`)?.dataset.wfShot==='shot-13',id);
            await page.locator(`[data-id="${id}"] [data-wf-fullscreen]`).click();
            assert.equal(await page.locator('dialog [data-wf-shot]').first().getAttribute('data-wf-shot'),'shot-13');
            await page.locator('dialog .wf-shot-scroll').evaluate(el=>el.scrollTop=0);
            await page.locator('dialog [data-wf-action="previous"]').click();
            await page.waitForFunction(()=>document.querySelector('dialog [data-wf-shot]')?.dataset.wfShot==='shot-1');
            // 聚焦输入后直接退出，也应提交编辑，且不会触发画布快捷键。
            if(id==='confirm') await page.locator('dialog [data-wf-shot-field="visual"]').first().fill('退出前未失焦的编辑');
            await page.locator('dialog [data-wf-close]').click();
            if(id==='confirm') await page.waitForFunction(()=>nodes.find(n=>n.id==='confirm').workflowSnapshot.shots[0].visual==='退出前未失焦的编辑');
        }
        await page.evaluate(()=>saveCanvas());
        await page.reload();
        await page.waitForFunction(()=>document.querySelectorAll('.film-workflow-panel').length===3);
        assert.equal(await page.locator('[data-id="confirm"] .wf-shot').count(),12);
        assert.equal(await page.locator('[data-id="group"]').count(),1,'initial render keeps source group');
        assert.equal(await page.locator('.workflow-function-group').count(),1);
        assert.ok(await page.evaluate(()=>linkCreateOptions({originId:'group',originKind:'out'}).some(o=>o.type==='film-prepare-assets')));
        await focus('confirm');
        await page.locator('[data-id="confirm"] [data-wf-fullscreen]').click();
        await page.setViewportSize({width:720,height:800});
        await page.evaluate(()=>{document.documentElement.classList.add('theme-dark');document.body.classList.add('theme-dark');});
        assert.equal(await page.locator('dialog').evaluate(el=>el.scrollWidth<=el.clientWidth),true,'small fullscreen has no horizontal overflow');
        await wheelScroll('dialog.wf-fullscreen .wf-shot-scroll');
        await page.locator('dialog').screenshot({path:`${dir}/confirm-fullscreen-small-dark.png`});
        await page.keyboard.press('Escape');
        await page.setViewportSize({width:1500,height:1050});
        // 复现旧 41 帧、三列、250px 行距；混合横竖图，打开即整理并落盘。
        const layoutNodes=Array.from({length:41},(_,i)=>({id:`layout-${i}`,type:'image',url:`/film-layout-${i%2}.svg`,natural_w:i%2?32:64,natural_h:i%2?64:32,w:260,h:220,x:148+(i%3)*290,y:186+Math.floor(i/3)*250}));
        const importedGroup={id:'imported',type:'group',x:120,y:120,w:898,h:3600,items:layoutNodes.map(n=>n.id),bridgeSource:'filmstoryboard',bridgeDirection:'film-to-shiyin',bridgeId:'fixture:layout',workflowNodeIds:['layout-prepare']};
        await page.route('**/film-layout-*.svg',route=>{const portrait=route.request().url().endsWith('1.svg');return route.fulfill({contentType:'image/svg+xml',body:`<svg xmlns="http://www.w3.org/2000/svg" width="${portrait?32:64}" height="${portrait?64:32}"><rect width="100%" height="100%" fill="#6a8c80"/></svg>`});});
        await page.request.put(`${base}/api/canvases/film-layout-ui`,{data:{id:'film-layout-ui',title:'41 帧导入布局',nodes:[importedGroup,...layoutNodes,{id:'layout-prepare',type:'film-prepare-assets',x:120+898+184,y:184,w:960}],connections:[],viewport:{x:40,y:40,scale:.23}}});
        await page.goto(`${base}/static/canvas.html?id=film-layout-ui`);
        await page.waitForFunction(()=>nodes.find(n=>n.id==='imported')?.bridgeLayoutVersion===1);
        await page.waitForTimeout(400);
        const layout=await page.evaluate(()=>{const group=nodes.find(n=>n.id==='imported');return {group:nodeRect(group),images:group.items.map(id=>nodeRect(nodes.find(n=>n.id===id)))};});
        assert.equal(new Set(layout.images.map(n=>n.x)).size,7);
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='layout-prepare').x),layout.group.x+layout.group.w+184,'default workflow follows expanded source group');
        for(let i=0;i<layout.images.length;i++){
            const a=layout.images[i],g=layout.group;
            assert.ok(a.x>=g.x && a.y>=g.y+58 && a.x+a.w<=g.x+g.w+1 && a.y+a.h<=g.y+g.h+1,'all image cards contained');
            for(const b of layout.images.slice(i+1))assert.ok(a.x+a.w<=b.x || b.x+b.w<=a.x || a.y+a.h<=b.y || b.y+b.h<=a.y,'no overlapping image cards');
        }
        await page.screenshot({path:`${dir}/import-layout-41.png`});
        await page.evaluate(()=>{nodes.find(n=>n.id==='layout-0').x=9999;return saveCanvas();});
        await page.reload();await page.waitForFunction(()=>nodes.some(n=>n.id==='layout-0'));
        assert.equal(await page.evaluate(()=>nodes.find(n=>n.id==='layout-0').x),9999,'reopening never overrides subsequent manual layout');
        assert.deepEqual(errors,[]);
        fs.writeFileSync(`${dir}/result.json`,JSON.stringify({passed:true,checks:['film 延迟启动后自动建脚本','普通节点不变','参数保存','镜头编辑','单个/全部生成范围','断线恢复','重连列表','保存重开','无脚本异常','旧包装组迁移','左右栏滚轮且画布视口不变','两节点全屏与退出','全屏分页与重新打开','全屏未失焦编辑保存','全屏异步任务轮询','全屏资产选择与拖拽绑定','41帧横竖混排无重叠且全部包含','工作流随图片组扩宽避让','重开保留手工排布'],calls:calls.map(c=>({action:c.action,shot_id:c.shot_id}))},null,2));
        console.log('film workflow browser: legacy checks + scrolling/fullscreen/41-frame layout passed');
    } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
