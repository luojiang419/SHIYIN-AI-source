const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {test}=require('node:test');
function harness(){
    const ctx={window:{},console}; vm.createContext(ctx);
    for(const file of ['canvas-film-nodes','canvas-film-storyboard']) vm.runInContext(fs.readFileSync(`static/js/${file}.js`,'utf8'),ctx);
    return {film:ctx.window.CanvasFilmNodes,api:ctx.window.CanvasFilmStoryboard,ctx};
}
const node=(extra={})=>({type:'film-storyboard',apiProvider:'custom',model:'image-model',...extra});
const ref=(role,url)=>({role,ref:{url,name:url,kind:'image'}});
const plain=value=>JSON.parse(JSON.stringify(value));
test('旧画布默认单图、多演员资产与原有数量保留',()=>{
    const {film,api}=harness(), n=node({count:3,actorCount:2});
    film.normalize(n); assert.equal(n.storyboardMode,'single');
    const plans=api.plans(n,[ref('actor-0','A'),ref('actor-1','B'),ref('sketch','s1'),ref('sketch','s2')]);
    assert.equal(plans.length,3); assert.equal(plans[0].assets.length,4);
    assert.deepEqual(plain(film.inputPorts(n).slice(-3).map(p=>p.role)),['sketch','depth','reference']);
});
test('批量每镜一张，所有共享资产绑定且不混入相邻镜头',()=>{
    const {api}=harness();
    const plans=api.plans(node({storyboardMode:'batch',count:4}),[ref('actor-0','actor'),ref('outfit-0','shirt'),ref('prop-0','bag'),ref('reference','photo1'),ref('reference','photo2')]);
    assert.equal(plans.length,2);
    assert.deepEqual(plain(plans.map(p=>p.assets.map(r=>r.url))),[['actor','shirt','bag','photo1'],['actor','shirt','bag','photo2']]);
});
test('显式线稿或深度与色光图按数量配对，不允许静默错配',()=>{
    const {api}=harness(),n=node({storyboardMode:'batch'});
    const controls=[ref('sketch','s1'),ref('depth','d2')];
    assert.deepEqual(plain(api.plans(n,[...controls,ref('reference','r')]).map(p=>p.assets.map(r=>r.url))),[['s1','r'],['d2','r']]);
    assert.deepEqual(plain(api.plans(n,[...controls,ref('reference','r1'),ref('reference','r2')]).map(p=>p.assets.map(r=>r.url))),[['s1','r1'],['d2','r2']]);
    assert.throws(()=>api.plans(n,[...controls,...[1,2,3].map(i=>ref('reference','r'+i))]),/等量/);
    assert.throws(()=>api.plans(n,[ref('actor-0','a')]),/批量模式请连接/);
});
test('超过20张镜头输入不会在分批前截断，视频不算图片',()=>{
    const {api}=harness();
    const plans=api.plans(node({storyboardMode:'batch'}),[...Array.from({length:42},(_,i)=>ref('sketch','s'+i)),{role:'sketch',ref:{url:'video',kind:'video'}}]);
    assert.equal(plans.length,42);
    assert.equal(plans[41].source.url,'s41');
});
test('参考图自动提深度并保留独立色光角色、重建背景约束',async()=>{
    const {api}=harness(),n=node({storyboardMode:'batch'});
    const plan=api.plans(n,[ref('actor-0','a'),ref('reference','photo')])[0];
    const built=await api.createPreparer(n,{depth:async r=>({url:r.url+'-depth'})})(plan);
    assert.equal(built.refs.length,3);
    assert.equal(built.refs.find(r=>r.url==='photo-depth').role,'control_map');
    assert.match(built.refs.find(r=>r.url==='photo').role_label,/背景从零重建/);
    for(const text of ['色温','光源方向','背景必须','禁止以原图为底板扩图','服装、道具按演员编号绑定']) assert.ok(built.prompt.includes(text));
    assert.equal(plan.assets.length,2,'预处理不能污染输入快照');
});
test('已有控制图跳过深度推理，相同参考单次点击仅处理一次',async()=>{
    const {api}=harness(); let calls=0;
    const depth=async()=>{ calls++; return {url:'depth'}; };
    let n=node({storyboardMode:'batch'});
    await api.createPreparer(n,{depth})(api.plans(n,[ref('depth','d'),ref('reference','r')])[0]);
    assert.equal(calls,0);
    n=node({count:3}); const prepare=api.createPreparer(n,{depth});
    await Promise.all(api.plans(n,[ref('reference','r')]).map(prepare));
    assert.equal(calls,1);
});
test('深度失败隔离，后续镜头仍可完成；不截断超限共享资产',async()=>{
    const {api}=harness(),n=node({storyboardMode:'batch'});
    const prepare=api.createPreparer(n,{depth:async r=>{if(r.url==='bad') throw Error('坏图'); return {url:'depth'};}});
    const results=await Promise.allSettled(api.plans(n,[ref('reference','bad'),ref('reference','ok')]).map(prepare));
    assert.deepEqual(results.map(r=>r.status),['rejected','fulfilled']);
    const tooMany=api.plans(n,[...Array.from({length:20},(_,i)=>ref('actor-0','a'+i)),ref('sketch','s')])[0];
    await assert.rejects(()=>prepare(tooMany),/最多 20 张/);
});
test('经典编组递归展开图片及输出、循环不死锁，视频链路仍保留视频',()=>{
    const {ctx}=harness();
    const source=fs.readFileSync('static/js/canvas.js','utf8');
    const start=source.indexOf('function classicFilmSourceRefs('),end=source.indexOf('\n}',start)+2;
    ctx.nodes=[{id:'g',type:'group',items:['a','nested','g']},{id:'a',type:'image'},{id:'nested',type:'group',items:['out']},{id:'out',type:'output'}];
    ctx.mediaRefsFromNode=n=>n.id==='out' ? [{url:'b'},{url:'c'}] : [{url:'a'}];
    vm.runInContext(source.slice(start,end),ctx);
    assert.deepEqual(plain(ctx.classicFilmSourceRefs(ctx.nodes[0]).map(r=>r.url)),['a','b','c']);
    ctx.mediaRefsFromNode=()=>[{url:'v',kind:'video'}];
    assert.equal(ctx.classicFilmSourceRefs({id:'v',type:'image'})[0].kind,'video');
});
test('普通智能生图继续默认优化，分镜重试保留完整控制提示词',async()=>{
    const {ctx}=harness(),requests=[];
    const source=fs.readFileSync('static/js/smart-canvas.js','utf8');
    const start=source.indexOf('async function runApiGeneration('),end=source.indexOf('\n}',start)+2;
    Object.assign(ctx,{settings:{},imageRefsOnly:refs=>refs,sizeForRun:()=> '1024x1024',fetch:async(_url,options)=>{requests.push(JSON.parse(options.body));return {ok:true,json:async()=>({task_id:'t'})};}});
    vm.runInContext('const SMART_REFERENCE_IMAGE_MAX=20;\n'+source.slice(start,end),ctx);
    await ctx.runApiGeneration('prompt',[{url:'a'}],{provider_id:'p',model:'m'});
    await ctx.runApiGeneration('prompt',[{url:'a'}],{provider_id:'p',model:'m',autoOptimizePrompt:false,promptNodeType:'film-storyboard'});
    assert.equal(requests[0].auto_optimize_prompt,true);
    assert.equal(requests[0].prompt_context.node_type,'smart-image');
    assert.equal(requests[1].auto_optimize_prompt,false);
    assert.equal(requests[1].prompt_context.node_type,'film-storyboard');
});
