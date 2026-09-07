const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
function fixture(){
    const requests=[];
    const sandbox={window:{},queueMicrotask:()=>{},setTimeout,crypto:require('node:crypto').webcrypto,
        fetch:async(_,opts)=>{requests.push(JSON.parse(opts.body));return {ok:true,json:async()=>({ok:true,project_id:'p',snapshot:{scriptId:'s',shots:[{id:'shot-1',number:1}],parameters:{},tasks:[]}})};}};
    vm.runInNewContext(fs.readFileSync('static/js/canvas-film-workflow.js','utf8'),sandbox);
    const api=sandbox.window.CanvasFilmWorkflow;
    const nodes=[{id:'g',type:'group',items:['i']},{id:'i',type:'image',url:'/input/a.png'},
        {id:'p',type:api.PREPARE},{id:'c',type:api.CONFIRM},{id:'v',type:'film-video',w:520}];
    const connections=[{from:'g',to:'p'},{from:'p',to:'c'},{from:'c',to:'v'}];
    const ctx={nodes,connections,canvasId:'canvas',changed:()=>{},invalidate:()=>{}};
    api.sync(ctx);return {api,nodes,connections,ctx,requests,sandbox};
}
test('only a direct confirmation link enables list; detach restores ordinary width',()=>{
    const f=fixture(),v=f.nodes[4];assert.equal(f.api.isList(v),true);assert.equal(v.w,960);
    f.connections.pop();f.api.sync(f.ctx);assert.equal(f.api.isList(v),false);assert.equal(v.w,520);
    assert.equal(f.api.handles(v),false);
    f.connections.push({from:'g',to:'v'});f.api.sync(f.ctx);assert.equal(f.api.isList(v),false);
});
test('sync is data-only, shares snapshot down chain and preserves ordinary params',async()=>{
    const f=fixture();f.nodes[4].model='unchanged';await f.api.request(f.nodes[2],'sync');
    assert.equal(f.requests.length,1);assert.equal(f.requests[0].action,'sync');
    assert.equal(f.nodes[4].workflowSnapshot.scriptId,'s');assert.equal(f.nodes[4].model,'unchanged');
    assert.equal(f.nodes[2].workflowSnapshot,f.nodes[3].workflowSnapshot);
});
test('disconnect prepare clears downstream active snapshot without deleting source snapshot',async()=>{
    const f=fixture();await f.api.request(f.nodes[2],'sync');f.connections.splice(1,1);f.api.sync(f.ctx);
    assert.equal(f.nodes[4].workflowScriptId,'');assert.equal(f.nodes[2].workflowScriptId,'s');
});
test('group order and topology are deterministic and reject unrelated stage sources',()=>{
    const f=fixture();assert.equal(f.api.sourceFor(f.nodes[4],f.nodes,f.connections).frames[0].id,'i');
    assert.equal(f.api.canConnect(f.nodes[1],f.nodes[3],'workflow',f.nodes,f.connections),false);
    assert.equal(f.api.canConnect(f.nodes[0],f.nodes[2],'workflow',f.nodes,f.connections),true);
});
test('ordinary film video preserves existing outputs, size and settings even beside a workflow',()=>{
    const f=fixture(), ordinary={id:'ordinary',type:'film-video',w:780,model:'my-model',generatedOutputs:[{url:'/output/existing.mp4'}]};
    f.nodes.push(ordinary);f.api.sync(f.ctx);
    assert.equal(ordinary.w,780);assert.equal(ordinary.generatedOutputs[0].url,'/output/existing.mp4');assert.equal(ordinary.model,'my-model');
    assert.equal(ordinary.workflowList,undefined);
});
test('late response from a replaced input cannot overwrite the new group script',async()=>{
    const f=fixture();let resolve;
    f.sandbox.fetch=()=>new Promise(done=>{resolve=done;});
    const pending=f.api.request(f.nodes[2],'sync');
    f.nodes.push({id:'other-group',type:'group',items:['i']});
    f.connections[0].from='other-group';f.api.sync(f.ctx);
    resolve({ok:true,json:async()=>({ok:true,snapshot:{scriptId:'stale-script',shots:[]}})});
    await pending;
    assert.notEqual(f.nodes[2].workflowScriptId,'stale-script');assert.equal(f.nodes[2].workflowBusy,false);
    assert.equal(f.nodes[2].workflowGroupId,'other-group');
});
