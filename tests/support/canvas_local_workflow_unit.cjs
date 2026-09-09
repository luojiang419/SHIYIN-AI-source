const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'), vm=require('node:vm');
function fixture(){
    const calls=[];
    const sandbox={window:{},queueMicrotask:()=>{},setTimeout,clearTimeout,crypto:require('node:crypto').webcrypto,
        fetch:async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>({text:'原帧视觉描述'})};}};
    for(const file of ['canvas-local-workflow.js','canvas-film-workflow.js']) vm.runInNewContext(fs.readFileSync(`static/js/${file}`,'utf8'),sandbox);
    const api=sandbox.window.CanvasFilmWorkflow;
    const nodes=[{id:'a',type:'image',url:'/a.png'},{id:'b',type:'image',url:'/b.png'},
        {id:'g',type:'group',items:['b','a']},{id:'p',type:api.PREPARE},{id:'c',type:api.CONFIRM},{id:'v',type:'film-video'}];
    const connections=[{from:'a',to:'p'},{from:'g',to:'p'},{from:'p',to:'c'},{from:'c',to:'v'}];
    const ctx={canvasId:'test',nodes,connections,changed:()=>{},invalidate:()=>{},vision:()=>({provider:'vision',model:'vlm'}),
        depth:async()=>({url:'/depth.png'}),generate:async()=>({url:'/generated.png'})};
    api.sync(ctx);
    return {sandbox,api,nodes,ctx,calls,p:nodes[3],c:nodes[4],v:nodes[5],request:(node,action,extra)=>api.request(node,action,extra)};
}
test('multiple images and overlapping nested groups deduplicate by node and preserve input order',()=>{
    const f=fixture(); f.nodes[2].items.push('g');
    assert.deepEqual(Array.from(f.api.sourceFor(f.p,f.nodes,f.ctx.connections).frames,n=>n.id),['a','b']);
    assert.equal(f.api.canConnect(f.nodes[0],f.p,'workflow',f.nodes,f.ctx.connections),true);
    assert.equal(f.api.canConnect({type:'image',mediaKind:'video'},f.p,'workflow',f.nodes,f.ctx.connections),false);
});
test('sync and confirmation work with zero film or model requests and share downstream snapshot',async()=>{
    const f=fixture();await f.request(f.p,'sync');await f.request(f.c,'confirm');
    assert.equal(f.calls.length,0);assert.equal(f.p.workflowSnapshot.shots.length,2);
    assert.ok(f.p.workflowSnapshot.shots.every(s=>s.confirmed));assert.equal(f.v.workflowSnapshot,f.p.workflowSnapshot);
    assert.equal(f.p.workflowProjectId,'');
});
test('legacy snapshots with equal image URLs never assign the same shot ID twice',async()=>{
    const f=fixture();f.nodes[1].url='/a.png';
    f.p.workflowSnapshot={shots:[{id:'legacy-shot',frame:'/a.png',content:'旧描述'}]};
    await f.request(f.p,'sync');
    const shots=f.p.workflowSnapshot.shots;
    assert.equal(new Set(shots.map(shot=>shot.id)).size,2);
    assert.equal(shots[0].content,'旧描述');
});
test('asset import, bind, rename and removal persist without deleting source files',async()=>{
    const f=fixture();await f.request(f.p,'sync');
    await f.request(f.p,'import-asset',{asset_url:'/actor.png',name:'演员',asset_type:'character'});
    const id=f.p.workflowSnapshot.assets[0].id;
    await f.request(f.p,'bind-asset',{asset_id:id,shot_id:'shot:a'});
    await f.request(f.p,'edit-asset',{asset_id:id,parameters:{name:'主角'}});
    assert.equal(f.c.workflowSnapshot.bindings.length,1);assert.equal(f.c.workflowSnapshot.boundAssets[0].name,'主角');
    await f.request(f.p,'delete-asset',{asset_id:id});assert.equal(f.p.workflowSnapshot.bindings.length,0);assert.equal(f.calls.length,0);
});
test('editing then refreshing retains fields, confirmation and generation through JSON persistence',async()=>{
    const f=fixture();await f.request(f.p,'sync');await f.request(f.c,'edit-shot',{shot_id:'shot:a',parameters:{content:'手改',durationSeconds:7}});
    await f.request(f.c,'confirm',{shot_id:'shot:a'});await f.request(f.p,'snapshot');
    const stored=JSON.parse(JSON.stringify(f.p));Object.assign(f.p,stored);await f.request(f.p,'snapshot');
    assert.equal(f.p.workflowSnapshot.shots[0].content,'手改');assert.equal(f.p.workflowSnapshot.shots[0].confirmed,true);
    await assert.rejects(f.request(f.c,'edit-shot',{shot_id:'shot:a',parameters:{durationSeconds:0}}),/1–120/);
});
test('analysis, depth and generation use native callbacks only on explicit action',async()=>{
    const f=fixture();await f.request(f.p,'sync');await f.request(f.p,'analyze',{shot_id:'shot:a'});
    assert.equal(f.calls.length,1);assert.equal(f.calls[0].url,'/api/canvas-llm');assert.equal(f.calls[0].body.provider,'vision');
    await f.request(f.p,'depth',{shot_id:'shot:a'});assert.equal(f.p.workflowSnapshot.guides[0].depth,'/depth.png');
    await f.request(f.p,'replicate',{shot_id:'shot:a'});assert.equal(f.p.workflowSnapshot.shots[0].replica,'/generated.png');
    assert.equal(f.p.workflowSnapshot.shots[0].confirmed,false);
});
test('disconnect hides stale shots; changing input URL invalidates confirmation and generated image',async()=>{
    const f=fixture();await f.request(f.p,'sync');await f.request(f.c,'confirm');await f.request(f.p,'replicate',{shot_id:'shot:a'});
    f.nodes[0].url='/new.png';await f.request(f.p,'sync');
    assert.equal(f.p.workflowSnapshot.shots[0].replica,undefined);assert.equal(f.p.workflowSnapshot.shots[0].confirmed,false);
    f.ctx.connections.splice(0,2);f.api.sync(f.ctx);
    assert.ok(!f.api.bodyHtml(f.p).includes('/new.png'));assert.ok(f.api.bodyHtml(f.p).includes('将多张图片'));
});
test('adding another group keeps existing edits and does not restore a stale group session',async()=>{
    const f=fixture();f.ctx.connections.shift();await f.request(f.p,'sync');
    await f.request(f.c,'edit-shot',{shot_id:'shot:b',parameters:{content:'保留'}});
    f.ctx.connections.push({from:'a',to:'p'});f.api.sync(f.ctx);await f.request(f.p,'sync');
    assert.equal(f.p.workflowSnapshot.shots.find(s=>s.id==='shot:b').content,'保留');
});
test('late analysis result after input changes cannot overwrite current snapshot',async()=>{
    const f=fixture();await f.request(f.p,'sync');let resolve;
    f.sandbox.fetch=()=>new Promise(done=>resolve=done);
    const pending=f.request(f.p,'analyze',{shot_id:'shot:a'});f.nodes[0].url='/replacement.png';
    resolve({ok:true,json:async()=>({text:'过期描述'})});await assert.rejects(pending,/输入已变更/);
    assert.notEqual(f.p.workflowSnapshot.shots[0].content,'过期描述');
});
test('one workflow serializes operations across prepare and confirm nodes',async()=>{
    const f=fixture();await f.request(f.p,'sync');let resolve;
    f.sandbox.fetch=()=>new Promise(done=>resolve=done);
    const pending=f.request(f.p,'analyze');await assert.rejects(f.request(f.c,'confirm'),/另一项操作/);
    resolve({ok:true,json:async()=>({text:'描述'})});
    // Analyze only one shot to avoid a second deferred request.
    f.sandbox.fetch=async()=>({ok:true,json:async()=>({text:'描述'})});await pending;
});
test('only confirmed shots generate video; errors are retained and never replayed by sync',async()=>{
    const f=fixture();await f.request(f.p,'sync');let count=0;
    f.ctx.generate=async()=>{count++;throw new Error('生成服务错误');};
    await assert.rejects(f.request(f.v,'generate'),/先确认/);assert.equal(count,0);
    await f.request(f.c,'confirm',{shot_id:'shot:a'});
    await assert.rejects(f.request(f.v,'generate'),/生成服务错误/);await f.request(f.p,'snapshot');
    assert.equal(count,1);assert.equal(f.p.workflowSnapshot.tasks[0].status,'failed');
});
