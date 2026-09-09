// 使用 canvas_startup_fixture.py；所有生成/深度请求均由本文件拦截，不访问外部 API。
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=process.argv[2] || 'http://127.0.0.1:3017';
const artifacts=process.argv[3] || '测试/分镜合成-127';
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jEOsAAAAASUVORK5CYII=','base64');
(async()=>{
    fs.mkdirSync(artifacts,{recursive:true});
    const browser=await chromium.launch({headless:true,channel:'chrome'});
    const reports=[];
    try {
        for(const smart of [false,true]){
            const page=await browser.newPage({viewport:{width:1440,height:1100}});
            const errors=[],requests=[],tasks=new Map(),sceneRequests=[]; let depths=0,failSecond=true,failGeneration=false,holdResults=false,seed=true,badMatches=false,matchingPending=0;
            page.on('pageerror',error=>errors.push(error.message));
            if(process.env.STORYBOARD_CANDIDATE_DIR) await page.route('**/static/**',route=>{
                const relative=decodeURIComponent(new URL(route.request().url()).pathname).replace(/^\//,'');
                const file=path.join(process.env.STORYBOARD_CANDIDATE_DIR,relative);
                if(!fs.existsSync(file)) return route.continue();
                const contentType=file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html';
                return route.fulfill({body:fs.readFileSync(file),contentType});
            });
            await page.route(/\/api\/canvas-image-tasks(?:\/[^/?]+)?(?:\?.*)?$/,async route=>{
                if(route.request().method()==='POST'){
                    assert.equal(matchingPending,0,'生成必须等待场景匹配完成');
                    const body=route.request().postDataJSON(); requests.push(body);
                    const shot=(body.reference_images.find(ref=>ref.input_role==='reference') || body.reference_images.find(ref=>['sketch','depth'].includes(ref.input_role)))?.url || '';
                    if(failSecond && shot.includes('shot=2')) return route.fulfill({status:503,json:{detail:'fixture 镜头2提交失败'}});
                    const id=`task-${requests.length}`; tasks.set(id,{body,shot});
                    return route.fulfill({status:202,json:{task_id:id,provider_id:'custom',model:'private-image'}});
                }
                const id=new URL(route.request().url()).pathname.split('/').pop();
                const task=tasks.get(id); assert.ok(task,`unknown task ${id}`);
                if(holdResults) return route.fulfill({json:{status:'running'}});
                if(failGeneration && task.shot.includes('shot=2')) return route.fulfill({json:{status:'failed',error:'fixture 服务端生成失败'}});
                await new Promise(resolve=>setTimeout(resolve,task.shot.includes('shot=1') ? 350 : 20));
                return route.fulfill({json:{status:'succeeded',result:{images:[{url:`/fixture.png?result=${id}`,kind:'image'}]}}});
            });
            await page.route('**/api/canvas-llm',async route=>{
                const body=route.request().postDataJSON();sceneRequests.push(body);
                const manifest=JSON.parse(body.message.match(/SCENE_MATCH_INPUT\n([^\n]+)/)[1]);
                matchingPending++;
                await new Promise(resolve=>setTimeout(resolve,40));
                matchingPending--;
                return route.fulfill({json:{text:JSON.stringify({matches:manifest.shots.map((shot,index)=>({shot_id:shot.shot_id,scene_id:badMatches ? 'S999' : manifest.scenes[index%manifest.scenes.length].scene_id,location:`${index ? '花园拱门' : '室内门窗'}旁的人物落点`,framing:'保留线稿对应的机位与背景柱体遮挡',lighting:'迁移原始参考图的暖色侧光、冷阴影与曝光',reason:'门窗轮廓、纵深与人物位置对应'}))})}});
            });
            await page.route('**/api/person-depth/estimate',async route=>{ depths++; await new Promise(resolve=>setTimeout(resolve,250)); return route.fulfill({contentType:'image/png',headers:{'X-Person-Depth-Width':'1024','X-Person-Depth-Height':'1024'},body:png}); });
            await page.route('**/api/ai/upload',route=>route.fulfill({json:{files:[{url:`/fixture.png?depth=${depths}`,name:'depth.png',kind:'image',natural_w:1024,natural_h:1024}]}}));
            const id=`storyboard-${smart ? 'smart' : 'classic'}-${Date.now()}`;
            if(smart){
                await page.route('**/static/smart-canvas.html*',async route=>{
                    const response=await route.fetch();
                    const body=process.env.STORYBOARD_CANDIDATE_DIR ? fs.readFileSync(path.join(process.env.STORYBOARD_CANDIDATE_DIR,'static/smart-canvas.html'),'utf8') : await response.text();
                    return route.fulfill({response,body:body.replace(/\s*<!-- 兼容历史书签：智能画布已下线，统一进入画布编辑器。 -->\s*<script>[\s\S]*?location\.replace\(target\);[\s\S]*?<\/script>/,'')});
                });
                await page.route(`**/api/canvases/${id}`,route=>{
                    if(route.request().method()!=='GET' || !seed) return route.continue();
                    seed=false; return route.fulfill({json:{canvas:{id,title:'分镜测试',kind:'smart',project:'default',viewport:{x:40,y:40,scale:.7},connections:[],nodes:[{id:'seed',type:'smart-image',x:0,y:0,images:[]}]}}});
                });
            }
            await page.goto(`${base}/static/${smart ? 'smart-canvas' : 'canvas'}.html?id=${id}`);
            await page.waitForFunction(()=>window.CanvasFilmStoryboard && document.querySelector('.node,.image-node'));
            await page.evaluate(smart=>{
                const img=(id,shot)=>smart ? {id,type:'smart-image',x:1000,y:0,images:[{url:`/fixture.png?shot=${shot}`,name:id,kind:'image',natural_w:1024,natural_h:1024}]} : {id,type:'image',x:1000,y:0,url:`/fixture.png?shot=${shot}`,name:id,width:1024,height:1024};
                const film=window.CanvasFilmNodes.createNode('film-storyboard',{x:0,y:0},{id:'film',apiProvider:'custom',model:'private-image',count:2,...(smart ? {specialType:'film-storyboard',w:520,scale:1} : {})});
                nodes.splice(0,nodes.length,film,img('actor','actor'),img('outfit','outfit'),img('s1',1),img('s2',2),img('s3',3),{id:'shots',type:smart ? 'smart-group' : 'group',x:1400,y:0,w:300,h:200,items:['s1','s2']});
                const edges=[{id:'a',from:'actor',to:'film',inputRole:'actor-0'},{id:'o',from:'outfit',to:'film',inputRole:'outfit-0'},{id:'g',from:'shots',to:'film',inputRole:'sketch'},{id:'s',from:'s3',to:'film',inputRole:'sketch'}];
                if(smart) canvas.connections=edges; else connections.splice(0,connections.length,...edges);
                viewport.x=40; viewport.y=40; viewport.scale=.85; render(); applyViewport();
            },smart);
            const panel=page.locator('[data-id="film"]').filter({has:page.locator('.film-node-panel')});
            assert.equal(await panel.locator('[data-film-mode="single"]').getAttribute('aria-pressed'),'true');
            await panel.locator('[data-film-mode="batch"]').click();
            await page.waitForFunction(()=>document.querySelector('[data-film-mode="batch"]')?.getAttribute('aria-pressed')==='true');
            assert.match(await panel.locator('.film-storyboard-summary').textContent(),/3 个镜头/);
            assert.equal(await panel.locator('[data-film-field="count"]').isDisabled(),true);
            assert.equal(await panel.locator('[data-film-field="storyboardBatchAspectRatio"]').inputValue(),'source');
            assert.match(await panel.locator('.film-input-row[data-input-role="sketch"]').textContent(),/3 张/);
            const layout=await panel.evaluate(el=>{
                const frame=el.getBoundingClientRect();
                const alignment=[...el.querySelectorAll('.film-role-port')].map(port=>{
                    const row=el.querySelector(`.film-input-row[data-input-role="${port.dataset.inputRole}"]`);
                    const p=port.getBoundingClientRect(),r=row.getBoundingClientRect();
                    return Math.abs(p.top+p.height/2-r.top-r.height/2);
                });
                return {alignment,overflow:[...el.querySelectorAll('button,select,.film-input-row')].filter(control=>{const r=control.getBoundingClientRect();return r.width && (r.left<frame.left-3 || r.right>frame.right+3);}).map(el=>el.outerHTML.slice(0,150))};
            });
            const grain=panel.locator('[data-film-field="storyboardGrain"]');
            assert.equal(await grain.inputValue(),'0');
            const grainLayout=await panel.evaluate(el=>{
                const a=el.querySelector('[data-film-field="count"]').closest('label').getBoundingClientRect();
                const b=el.querySelector('.film-grain-control').getBoundingClientRect();
                return {right:b.left>=a.right,aligned:Math.abs(a.top-b.top)<4};
            });
            assert.deepEqual(grainLayout,{right:true,aligned:true});
            await grain.fill('7');
            assert.equal(await panel.locator('[data-film-grain-value]').textContent(),'7');
            assert.deepEqual(layout.overflow,[]);
            assert.ok(layout.alignment.every(value=>value<4),JSON.stringify(layout));
            await page.evaluate(smart=>smart ? runSmartFilmNode(nodes.find(n=>n.id==='film')) : runFilmNode('film'),smart);
            assert.equal(requests.length,3);
            assert.ok(requests.every(r=>r.prompt.includes('额外强度 7/10') && r.prompt.includes('画框与可见范围锁定')));
            assert.equal(depths,0);
            assert.ok(requests.every(r=>r.reference_images.length===3 && r.auto_optimize_prompt===false));
            const result=await page.evaluate(smart=>{
                const film=nodes.find(n=>n.id==='film');
                const out=smart ? nodes.find(n=>n.id===film.filmOutputNodeId) : nodes.find(n=>n.type==='output');
                return {urls:(out.images || []).map(r=>r.url || r),failed:smart ? smartGenerationSlots(out).filter(s=>s.status==='error').length : (out._pending || []).filter(p=>p.failed).length,error:film.runError,running:film.running};
            },smart);
            assert.deepEqual(result.urls,['/fixture.png?result=task-1','/fixture.png?result=task-3']);
            assert.equal(result.failed,1); assert.equal(result.running,false); assert.match(result.error,/1\/3/);
            await panel.screenshot({path:`${artifacts}/${smart ? 'smart' : 'classic'}-batch.png`});
            failSecond=false; failGeneration=true; const before=requests.length;
            await page.evaluate(smart=>{
                const edges=smart ? canvas.connections : connections;
                for(let i=edges.length-1;i>=0;i--) if(edges[i].to==='film' && edges[i].inputRole==='sketch') edges.splice(i,1);
                edges.push({id:'photos',from:'shots',to:'film',inputRole:'reference'});
                render();
            },smart);
            await page.evaluate(smart=>{ if(smart) void runSmartFilmNode(nodes.find(n=>n.id==='film')); else void runFilmNode('film'); },smart);
            await page.waitForFunction(()=>nodes.find(n=>n.id==='film')?.storyboardDepthPreviews?.some(item=>item.status==='running'));
            assert.match(await panel.locator('.film-storyboard-summary').textContent(),/正在提取参考图深度 1\/2 · 已完成 0\/2/);
            await panel.screenshot({path:`${artifacts}/${smart ? 'smart' : 'classic'}-depth-progress.png`});
            await page.waitForFunction(()=>nodes.find(n=>n.id==='film')?.running===false);
            assert.equal(depths,2); assert.equal(requests.length-before,2);
            for(const request of requests.slice(before)){
                assert.equal(request.reference_images.length,4);
                assert.equal(request.reference_images.filter(r=>r.role==='control_map').length,1);
                assert.match(request.prompt,/背景必须依据这些证据从零重新生成/);
                assert.match(request.prompt,/禁止以原图为底板扩图/);
            }
            assert.equal(await panel.locator('.film-depth-preview.is-ready').count(),2);
            assert.ok((await panel.locator('.film-depth-preview.is-ready img').all()).length===2);
            await panel.screenshot({path:`${artifacts}/${smart ? 'smart' : 'classic'}-depth-ready.png`});
            const failedGeneration=await page.evaluate(smart=>{
                const film=nodes.find(n=>n.id==='film');
                const out=smart ? nodes.find(n=>n.id===film.filmOutputNodeId) : nodes.find(n=>n.type==='output');
                return {error:film.runError,failures:smart ? smartGenerationSlots(out).filter(s=>s.status==='error').length : (out._pending || []).filter(p=>p.failed).length};
            },smart);
            assert.match(failedGeneration.error,/1\/2/); assert.ok(failedGeneration.failures>=1);
            failGeneration=false;
            if(smart){
                const countBeforeRetry=requests.length;
                await page.evaluate(async()=>{
                    const film=nodes.find(n=>n.id==='film'),out=nodes.find(n=>n.id===film.filmOutputNodeId);
                    const slot=smartGenerationSlots(out).find(s=>s.status==='error');
                    await retrySmartGenerationSlot(out.id,slot.id);
                });
                assert.equal(requests.length,countBeforeRetry+1);
                assert.equal(requests.at(-1).auto_optimize_prompt,false);
                assert.match(requests.at(-1).prompt,/额外强度 7\/10/);
                assert.equal(requests.at(-1).reference_images.filter(r=>r.input_role==='reference').length,1);
                assert.equal(requests.at(-1).reference_images.filter(r=>r.role==='control_map').length,1);
            }
            const depthBefore=depths,requestBefore=requests.length;
            await page.evaluate(smart=>{
                const film=nodes.find(n=>n.id==='film'); film.storyboardMode='single'; film.count=2;
                const edges=smart ? canvas.connections : connections;
                for(let i=edges.length-1;i>=0;i--) if(edges[i].to==='film' && edges[i].inputRole==='reference') edges.splice(i,1);
                edges.push({id:'manual-depth',from:'s3',to:'film',inputRole:'depth'}); render();
            },smart);
            await page.evaluate(smart=>smart ? runSmartFilmNode(nodes.find(n=>n.id==='film')) : runFilmNode('film'),smart);
            assert.equal(depths,depthBefore,'已有深度不再次提取'); assert.equal(requests.length,requestBefore+2,'单图数量保留');
            assert.ok(requests.slice(requestBefore).every(r=>r.reference_images.some(ref=>ref.role==='control_map')));
            const beforeSceneSingle=requests.length;
            await page.evaluate(smart=>{
                const img=(id)=>smart ? {id,type:'smart-image',x:1400,y:0,images:[{url:`/fixture.png?scene=${id}`,name:id,kind:'image',natural_w:1024,natural_h:1024}]} : {id,type:'image',x:1400,y:0,url:`/fixture.png?scene=${id}`,name:id,width:1024,height:1024};
                nodes.push(img('room'),img('garden'),{id:'backgrounds',type:smart ? 'smart-group' : 'group',x:1700,y:0,w:300,h:200,items:['room','garden']});
                const edges=smart ? canvas.connections : connections;
                edges.push({id:'background',from:'backgrounds',to:'film',inputRole:'scene'},{id:'color',from:'s1',to:'film',inputRole:'reference'});
                render();
            },smart);
            await page.evaluate(smart=>smart ? runSmartFilmNode(nodes.find(n=>n.id==='film')) : runFilmNode('film'),smart);
            assert.equal(sceneRequests.length,1,'单图的多个输出共用一次 AI 场景匹配');
            assert.equal(requests.length,beforeSceneSingle+2);
            for(const request of requests.slice(beforeSceneSingle)){
                assert.equal(request.reference_images.filter(ref=>ref.input_role==='scene').length,1);
                assert.ok(request.reference_images.find(ref=>ref.input_role==='scene').url.includes('scene=room'));
                assert.match(request.prompt,/用户场景图是唯一的背景身份/);
                assert.match(request.prompt,/室内门窗旁的人物落点/);
                assert.match(request.prompt,/不能换回原始参考照片的背景/);
            }
            await panel.locator('[data-film-mode="batch"]').click();
            await page.evaluate(smart=>{
                const edges=smart ? canvas.connections : connections;
                for(let i=edges.length-1;i>=0;i--) if(edges[i].to==='film' && ['depth','reference'].includes(edges[i].inputRole)) edges.splice(i,1);
                edges.push({id:'scene-shots',from:'shots',to:'film',inputRole:'reference'});render();
            },smart);
            const beforeSceneBatch=requests.length;
            await page.evaluate(smart=>smart ? runSmartFilmNode(nodes.find(n=>n.id==='film')) : runFilmNode('film'),smart);
            assert.equal(sceneRequests.length,2,'批量一次快速分析两个镜头和两个背景');
            assert.equal(requests.length,beforeSceneBatch+2);
            assert.deepEqual(requests.slice(beforeSceneBatch).map(request=>request.reference_images.find(ref=>ref.input_role==='scene').url),['/fixture.png?scene=room','/fixture.png?scene=garden']);
            assert.match(await panel.locator('.film-scene-matches summary').textContent(),/2 个任务组/);
            await panel.locator('.film-scene-matches summary').click();
            assert.equal(await panel.locator('.film-scene-matches').evaluate(el=>el.open),true);
            assert.match(await panel.locator('.film-scene-matches').textContent(),/garden → 镜头 2/);
            await panel.screenshot({path:`${artifacts}/${smart ? 'smart' : 'classic'}-scene-match.png`});
            badMatches=true; const beforeBad=requests.length;
            await page.evaluate(smart=>smart ? runSmartFilmNode(nodes.find(n=>n.id==='film')) : runFilmNode('film'),smart);
            assert.equal(requests.length,beforeBad,'错误的场景编号不能派发图片任务');
            badMatches=false;
            // 恢复之前的单深度输入，复查新匹配阶段不会改变既有后台图片任务恢复。
            await page.evaluate(smart=>{
                const edges=smart ? canvas.connections : connections;
                for(let i=edges.length-1;i>=0;i--) if(edges[i].to==='film' && ['scene','reference'].includes(edges[i].inputRole)) edges.splice(i,1);
                edges.push({id:'resume-depth',from:'s3',to:'film',inputRole:'depth'});render();
            },smart);
            holdResults=true; const beforeResume=requests.length;
            await page.evaluate(smart=>{ if(smart) void runSmartFilmNode(nodes.find(n=>n.id==='film')); else void runFilmNode('film'); },smart);
            await page.waitForFunction(smart=>{
                const film=nodes.find(n=>n.id==='film');
                return smart ? (nodes.find(n=>n.id===film.filmOutputNodeId)?.pendingTasks || []).some(t=>t.taskId.startsWith('task-'))
                    : nodes.some(n=>(n._pending || []).some(p=>p.canvasTaskId && !p.failed));
            },smart);
            assert.equal(requests.length,beforeResume+1);
            const recoveredUrl=`/fixture.png?result=task-${requests.length}`;
            await page.evaluate(()=>saveCanvas());
            holdResults=false;
            await page.reload();
            await page.waitForSelector('[data-id="film"] [data-film-mode="batch"][aria-pressed="true"]');
            await page.waitForFunction(({smart,url})=>{
                const film=nodes.find(n=>n.id==='film');
                const out=smart ? nodes.find(n=>n.id===film.filmOutputNodeId) : nodes.find(n=>n.type==='output');
                return (out?.images || []).some(r=>(r.url || r)===url);
            },{smart,url:recoveredUrl});
            assert.equal(requests.length,beforeResume+1,'刷新恢复只查询已提交任务，不重复生成');
            assert.equal(await page.locator('[data-id="film"] [data-film-field="storyboardGrain"]').inputValue(),'7');
            assert.deepEqual(errors,[]);
            reports.push({smart,requests:requests.length,sceneRequests:sceneRequests.length,depths,result,layout,errors});
            await page.close();
        }
        fs.writeFileSync(`${artifacts}/report.json`,JSON.stringify(reports,null,2));
        console.log(JSON.stringify(reports,null,2));
    } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
