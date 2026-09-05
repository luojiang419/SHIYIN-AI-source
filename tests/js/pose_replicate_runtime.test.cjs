const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/canvas.js','utf8');
function fn(name){
    const start = source.search(new RegExp('(?:async )?function '+name+'\\('));
    return source.slice(start, source.indexOf('\n}', start)+2);
}
function harness(){
    let serial = 0;
    const requests = [], frames = [];
    const ctx = {window:{}, nodes:[], connections:[], selected:new Set(), console,
        uid:prefix=>prefix+(++serial), imageApiProviders:()=>[{id:'provider'}], allImageModels:()=>['model'],
        apiImageSize:()=> '1536x2048', runSnapshot:()=>({}), pushUndo(){},
        positionCanvasNodeRelative(){}, indexClassicConnectionModel(){},
        makePendingForRun:(id,run,node,params,meta)=>({id,run,...meta}),
        pendingById:(output,id)=>output._pending.find(item=>item.id===id),
        outputNodesForSource:()=>[], render(){}, refreshRunNodes(){}, refreshNodes:ids=>ctx.refreshed.push(ids),refreshed:[],
        scheduleSave(){},saveCanvas:async()=>{},
        cascadeFetch:(_,options)=>new Promise(resolve=>requests.push({payload:JSON.parse(options.body),resolve})),
        responseErrorMessage:async()=> 'submission failed', nowMs:()=>100, addGenerationLog(){},
        requestAnimationFrame:cb=>{frames.push(cb); return frames.length;},
        pollCanvasImageTask:async id=>{
            for(const output of ctx.nodes){
                const p=output._pending?.find(item=>item.canvasTaskId===id);
                if(p){output.images.push({url:id+'.png'});output._pending=output._pending.filter(item=>item!==p);}
            }
            return 'completed';
        }};
    vm.createContext(ctx);
    vm.runInContext(fs.readFileSync('static/js/pose-replicate-settings.js','utf8'),ctx);
    vm.runInContext(fn('classicPoseReplicateOutputPosition')+'\n'+fn('generateClassicPoseReplicate'),ctx);
    vm.runInContext('const classicSpecialRefreshes = new Set(); let classicSpecialRefreshFrame = 0;\n'+fn('queueClassicSpecialRefresh'),ctx);
    const node={id:'source',type:'poseReplicate',poseReplicateProvider:'provider',poseReplicateModel:'model',poseReplicateMode:'skeleton'};
    ctx.nodes.push(node);
    const inputs={action:{url:'action'},control:{url:'control'},target:{url:'target'},mode:'skeleton'};
    return {ctx,node,inputs,requests,frames};
}
async function run(){
    const batchHarness=harness();
    batchHarness.inputs.targets=[
        {url:'red',name:'red.png'},
        {url:'blue',name:'blue.png'},
        {url:'green',name:'green.png'}
    ];
    const batchPromise=batchHarness.ctx.generateClassicPoseReplicate(batchHarness.node,batchHarness.inputs,'batch');
    const batchOutput=batchHarness.ctx.nodes.find(node=>node.type==='output');
    assert.equal(batchHarness.requests.length,3);
    assert.equal(batchOutput._pending.length,3);
    assert.deepEqual(batchHarness.requests.map(item=>item.payload.inputs.target_image.url),['red','blue','green']);
    assert.deepEqual(batchHarness.requests.map(item=>item.payload.prompt_policy.template_id),['pose-replicate.v3.0','pose-replicate.v3.0','pose-replicate.v3.0']);
    batchHarness.requests[2].resolve({ok:true,json:async()=>({task_id:'green-result'})});
    batchHarness.requests[0].resolve({ok:true,json:async()=>({task_id:'red-result'})});
    batchHarness.requests[1].resolve({ok:true,json:async()=>({task_id:'blue-result'})});
    await batchPromise;
    assert.equal(batchOutput.images.length,3);
    assert.equal(batchOutput._pending.length,0);

    const partialHarness=harness();
    partialHarness.inputs.targets=[{url:'one'},{url:'two'},{url:'three'}];
    const partialPromise=partialHarness.ctx.generateClassicPoseReplicate(partialHarness.node,partialHarness.inputs,'partial');
    const partialOutput=partialHarness.ctx.nodes.find(node=>node.type==='output');
    partialHarness.requests[0].resolve({ok:true,json:async()=>({task_id:'one-result'})});
    partialHarness.requests[1].resolve({ok:false});
    partialHarness.requests[2].resolve({ok:true,json:async()=>({task_id:'three-result'})});
    await assert.rejects(partialPromise,/1\/3 款服装复刻失败/);
    assert.equal(partialOutput.images.length,2);
    assert.equal(partialOutput._pending.length,1);
    assert.equal(partialOutput._pending[0].failed,true);

    const h=harness();
    h.node.poseReplicatePromptTemplates={'skeleton:base-wardrobe':'custom rules'};
    const a=h.ctx.generateClassicPoseReplicate(h.node,h.inputs,'first');
    const b=h.ctx.generateClassicPoseReplicate(h.node,h.inputs,'second');
    const output=h.ctx.nodes.find(node=>node.type==='output');
    assert.equal(h.ctx.nodes.length,2);assert.equal(h.ctx.connections.length,1);
    assert.equal(output._pending.length,2);assert.notEqual(output._pending[0].id,output._pending[1].id);
    assert.equal(h.requests[0].payload.prompt_policy.custom_template,'custom rules');
    // 第二次先返回，结果仍合并到同一节点，各自清理自己的 pending。
    h.requests[1].resolve({ok:true,json:async()=>({task_id:'second'})}); await b;
    assert.equal(output.images.length,1);assert.equal(output._pending.length,1);
    h.requests[0].resolve({ok:true,json:async()=>({task_id:'first'})});await a;
    assert.equal(output.images.length,2);assert.equal(output._pending.length,0);
    // 模拟保存后恢复的源和输出对象，第三次继续复用。
    h.ctx.nodes=JSON.parse(JSON.stringify(h.ctx.nodes));
    const c=h.ctx.generateClassicPoseReplicate(h.ctx.nodes[0],h.inputs,'third');
    assert.equal(h.ctx.nodes.length,2);
    h.requests[2].resolve({ok:false});await assert.rejects(c,/submission failed/);
    assert.equal(h.ctx.nodes[1].images.length,2);assert.equal(h.ctx.nodes[1]._pending[0].failed,true);
    // 克隆源不能通过保存的 Output ID 写入原源的结果。
    const clone={...h.ctx.nodes[0],id:'clone'};h.ctx.nodes.push(clone);
    const d=h.ctx.generateClassicPoseReplicate(clone,h.inputs,'clone');
    assert.equal(h.ctx.nodes.filter(n=>n.type==='output').length,2);
    h.requests[3].resolve({ok:true,json:async()=>({task_id:'clone-result'})});await d;
    assert.equal(h.ctx.nodes[1].images.length,2);
    // 状态风暴按帧合并，切换画布后的旧对象不刷新新节点。
    const current=h.ctx.nodes[0];
    h.ctx.queueClassicSpecialRefresh(current);h.ctx.queueClassicSpecialRefresh(current);
    assert.equal(h.frames.length,1);h.frames.shift()();
    assert.equal(h.ctx.refreshed.length,1);assert.deepEqual([...h.ctx.refreshed[0]],['source']);
    h.ctx.queueClassicSpecialRefresh(current);h.ctx.nodes=[];h.frames.shift()();
    assert.equal(h.ctx.refreshed.length,1);
    console.log('pose replicate concurrency, persistence, failures, cloning and refresh batching passed');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
