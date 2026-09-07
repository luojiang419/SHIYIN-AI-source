const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('static/js/canvas-linkfox-video.js','utf8');
function environment(responder){
    const calls=[],ctx={window:{},document:{querySelectorAll:()=>[]},AbortController,
        setTimeout:(fn,ms)=>{if(ms===2500)queueMicrotask(fn);return 1;},clearTimeout:()=>{},
        fetch:async(url,opts)=>{calls.push([url,opts]);return responder(url,opts);}};
    vm.createContext(ctx);vm.runInContext(source,ctx);
    return {api:ctx.window.CanvasLinkfoxVideo,calls};
}
const response=(body,status=200)=>({ok:status<400,status,json:async()=>body});
const payload={provider_id:'linkfox',model:'seedance2.0',duration:5};
(async()=>{
    let queries=0;
    const env=environment((url,opts)=>response(opts?.method==='POST'
        ? {status:'running',upstream_task_id:'up-1',message:'生成中'}
        : ++queries===1?{status:'finalizing',upstream_task_id:'up-1',message:'正在保存'}
        : {status:'succeeded',result:{videos:['/result.mp4']}}));
    const node={id:'one'},messages=[];
    const result=await env.api.generate(node,payload,{onChange:()=>messages.push(node.linkfoxTaskStatus)});
    assert.equal(result.videos[0],'/result.mp4');assert.equal(node.linkfoxTaskId,'');
    assert(messages.some(text=>text.includes('up-1')));assert(messages.some(text=>text.includes('正在保存')));
    assert.equal(env.calls.filter(c=>c[1]?.method==='POST').length,1);
    const resumed=environment(()=>response({status:'succeeded',result:{videos:['/saved.mp4']}}));
    await resumed.api.generate({id:'resume',linkfoxTaskId:'canvas_video_saved'},payload);
    assert.equal(resumed.calls.filter(c=>c[1]?.method==='POST').length,0);
    const failed=environment(()=>response({status:'failed',error:'图片审核不通过',upstream_task_id:'bad-task'}));
    await assert.rejects(failed.api.generate({id:'failure'},payload),/图片审核不通过/);
    const uncertain=environment((url,opts)=>{if(opts?.method==='POST') throw new Error('connection lost');return response({status:'succeeded',result:{videos:['/recovered.mp4']}});});
    await uncertain.api.generate({id:'lost'},payload);
    assert.equal(uncertain.calls.filter(c=>c[1]?.method==='POST').length,1);
    const mapped=env.api.taskPayload({entry:'img2video',mode:'first_last_frame',imageUrl:'first',lastFrameImageUrl:'last',videoType:'seedance2.0',videoTime:5,promptOptimizer:true});
    assert.equal(mapped.images[1].role,'last_frame');assert.equal(mapped.linkfox_prompt_optimizer,false);
    assert.equal(mapped.auto_adapt_prompt,true);assert(mapped.prompt_origin_key);
    console.log('LinkFox async UI: success, progress, resume, failure, lost response, first/last frame passed');
})().catch(error=>{console.error(error);process.exit(1);});
