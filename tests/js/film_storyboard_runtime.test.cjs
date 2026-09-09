const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {test}=require('node:test');
function harness(){
    const ctx={window:{},console}; vm.createContext(ctx);
    for(const file of ['canvas-film-nodes','canvas-film-scene-matcher','canvas-film-storyboard']) vm.runInContext(fs.readFileSync(`static/js/${file}.js`,'utf8'),ctx);
    return {film:ctx.window.CanvasFilmNodes,api:ctx.window.CanvasFilmStoryboard,ctx};
}
const node=(extra={})=>({type:'film-storyboard',apiProvider:'custom',model:'image-model',...extra});
const ref=(role,url)=>({role,ref:{url,name:url,kind:'image'}});
const plain=value=>JSON.parse(JSON.stringify(value));

test('质感规则按实际控制图分支，并保留多演员映射与用户换装范围',async()=>{
    for(const mode of ['single','batch']){
        for(const control of ['sketch','depth','reference']){
            const {api}=harness(),n=node({actorCount:2,storyboardMode:mode,prompt:'只换上装，保留眼镜'});
            const plan=api.plans(n,[ref('actor-0','A'),ref('outfit-0','shirt-A'),ref('actor-1','B'),ref('outfit-1','shirt-B'),ref(control,'shot')])[0];
            const built=await api.createPreparer(n,{depth:async()=>({url:'generated-depth'})})(plan);
            assert.deepEqual(plain(built.refs.filter(r=>/^(actor|outfit)-/.test(r.inputRole)).map(r=>[r.inputRole,r.url])),[['actor-0','A'],['outfit-0','shirt-A'],['actor-1','B'],['outfit-1','shirt-B']]);
            for(const text of ['只换上装，保留眼镜','不混脸、不串衣','自然皮肤纹理','服装提取与换装边界','折峰折谷','全主体重打光','不锁死源图 RGB']) assert.ok(built.prompt.includes(text),text);
            assert.equal(built.prompt.includes('【有依据的衣片褶皱复刻】'),control!=='sketch');
            assert.equal(built.prompt.includes('当前没有深度图'),control==='sketch');
            assert.ok(!built.prompt.includes('唯一编辑底图'));
            assert.ok(!built.prompt.includes('只有一个最终模特'));
        }
    }
});

test('无演员或服装资产时使用缺省来源，不虚构指定资产',async()=>{
    const {api}=harness(),n=node({prompt:'自然人物近景'});
    for(const assets of [[],[ref('sketch','s')],[ref('actor-0','actor'),ref('depth','d')]]){
        const built=await api.createPreparer(n)(api.plans(n,assets)[0]);
        assert.ok(built.prompt.includes('未指定服装参考时'));
        assert.ok(!built.prompt.includes('【服装提取与换装边界】'));
        assert.equal(built.prompt.includes('未连接演员参考时'),!assets.some(r=>r.role==='actor-0'));
        assert.match(built.prompt,/只输出当前镜头的一张完整照片/);
    }
});
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
function sceneFetch(requests, choose=(shot,scenes)=>scenes[0].scene_id){
    return async(url,options)=>{
        assert.equal(url,'/api/canvas-llm');
        const body=JSON.parse(options.body); requests.push(body);
        const manifest=JSON.parse(body.message.match(/SCENE_MATCH_INPUT\n([^\n]+)/)[1]);
        return {ok:true,json:async()=>({text:JSON.stringify({matches:manifest.shots.map(shot=>({shot_id:shot.shot_id,scene_id:choose(shot,manifest.scenes),location:'靠窗第二根柱子前，保留门窗地标',framing:'平视侧拍，门框在右侧，前景柱体遮挡',lighting:'将原参考的暖色侧光与冷色阴影迁移到用户场景',reason:'柱体与门窗的空间关系匹配'}))})})};
    };
}
test('单图场景定位只分析一次，多个结果复用用户背景与参考色光',async()=>{
    const {api}=harness(),requests=[],n=node({count:3});
    const plans=api.plans(n,[ref('actor-0','actor'),ref('scene','room'),ref('sketch','sketch'),ref('reference','color')]);
    const prepare=api.createPreparer(n,{plans,matchFetch:sceneFetch(requests),depth:()=>{throw Error('显式线稿不提深度');}});
    const results=await Promise.all(plans.map(prepare));
    assert.equal(requests.length,1);
    assert.equal(requests[0].images.length,3,'只解析结构/色光和背景，不发送演员');
    assert.equal(new Set(results.map(r=>r.sceneMatch.sceneUrl)).size,1);
    for(const built of results){
        assert.equal(built.sceneMatch.sceneUrl,'room');
        assert.match(built.prompt,/用户场景图是唯一的背景身份/);
        assert.match(built.prompt,/不能换回原始参考照片的背景/);
        assert.match(built.prompt,/靠窗第二根柱子前/);
        assert.match(built.refs.find(r=>r.url==='color').role_label,/色彩光线迁移到用户场景/);
        assert.ok(!built.prompt.includes('背景必须依据这些证据从零重新生成'),'连接用户场景时不使用无场景重建规则');
    }
});
test('批量候选按镜头分组匹配，每镜只提交自己的背景',async()=>{
    const {api}=harness(),requests=[],n=node({storyboardMode:'batch'});
    const plans=api.plans(n,[ref('scene','room'),ref('scene','garden'),ref('sketch','s1'),ref('sketch','s2')]);
    let groups;
    const prepare=api.createPreparer(n,{plans,matchFetch:sceneFetch(requests,(shot,scenes)=>scenes[shot.shot_id==='H1' ? 0 : 1].scene_id),onSceneMatches:matches=>{groups=matches;}});
    const results=await Promise.all(plans.map(prepare));
    assert.equal(requests.length,1);
    assert.deepEqual(plain(results.map(r=>r.refs.filter(ref=>ref.inputRole==='scene').map(ref=>ref.url))),[['room'],['garden']]);
    assert.deepEqual(plain(groups.map(plan=>plan.sceneMatch.sceneId)),['S1','S2']);
    assert.equal(plans[0].assets.filter(ref=>ref.role==='scene').length,2,'候选快照不可被选择结果覆盖');
});
test('超过20张候选全部参与分批匹配并复选，不截断、不融合背景',async()=>{
    const {api,ctx}=harness(),requests=[],n=node({storyboardMode:'batch'});
    const assets=[...Array.from({length:25},(_,i)=>ref('scene','scene'+(i+1))),ref('depth','d1'),ref('depth','d2')];
    const plans=api.plans(n,assets);
    const matches=await ctx.window.CanvasFilmSceneMatcher.matchPlans(n,plans,{fetch:sceneFetch(requests,(shot,scenes)=>{
        const desired=shot.shot_id==='H1' ? 'S2' : 'S25';return scenes.find(scene=>scene.scene_id===desired)?.scene_id || scenes[0].scene_id;
    })});
    assert.equal(requests.length,4,'三个初筛批次 + 一个复选批次');
    assert.ok(requests.every(request=>request.images.length<=20));
    const visited=new Set(requests.flatMap(request=>request.images.filter(url=>url.startsWith('scene'))));
    assert.equal(visited.size,25);
    assert.deepEqual(plain(matches.map(plan=>plan.sceneMatch.sceneId)),['S2','S25']);
});
test('匹配结果未知编号、缺少镜头或位置时停止，避免未经匹配出图',async()=>{
    const {api}=harness(),n=node({storyboardMode:'batch'});
    const plans=api.plans(n,[ref('scene','scene'),ref('reference','photo')]);
    let depthCalls=0;
    for(const text of ['not-json','null','{"matches":[null]}','{"matches":[{"shot_id":"H1","scene_id":"S1"}]}','{"matches":[]}',JSON.stringify({matches:[{shot_id:'H1',scene_id:'S99'}]})]){
        const prepare=api.createPreparer(n,{plans,depth:async()=>{depthCalls++;return {url:'depth'};},matchFetch:async()=>({ok:true,json:async()=>({text})})});
        await assert.rejects(()=>prepare(plans[0]),/场景匹配/);
    }
    assert.equal(depthCalls,0);
});
test('已匹配镜头重试固定原场景，不重复选景或混入未选候选',async()=>{
    const {api}=harness(),requests=[],n=node({storyboardMode:'batch'});
    const plan=api.plans(n,[ref('scene','room'),ref('scene','garden'),ref('sketch','s1')])[0];
    const first=await api.createPreparer(n,{matchFetch:sceneFetch(requests,(_shot,scenes)=>scenes[1].scene_id)})(plan);
    const retried=await api.createPreparer(n,{matchFetch:()=>{throw Error('不应重新匹配');}})({...plan,sceneMatch:first.sceneMatch});
    assert.deepEqual(plain(retried.refs.filter(ref=>ref.inputRole==='scene').map(ref=>ref.url)),['garden']);
    assert.equal(requests.length,1);
});


test('颗粒默认/边界归一化与各级强度进入单图和批量快照',async()=>{
    for(const [value,expected] of [[undefined,0],[0,0],['7',7],[4.6,5],[-1,0],[99,10],['bad',0],[Infinity,0]]){
        const {film,api}=harness(),n=node({storyboardGrain:value}); film.normalize(n);
        assert.equal(n.storyboardGrain,expected);
        for(const mode of ['single','batch']){
            n.storyboardMode=mode;
            const plan=api.plans(n,[ref('depth','d'),ref('reference','r')])[0];
            const prepare=api.createPreparer(n); n.storyboardGrain=2;
            const built=await prepare(plan);
            assert.ok(built.prompt.includes(`额外强度 ${expected}/10`));
            assert.match(built.prompt,/随机间距、非周期分布/);
            assert.match(built.prompt,/禁止规则点阵/);
            if(!expected) assert.match(built.prompt,/不额外叠加颗粒；原始参考已有真实胶片颗粒/);
            n.storyboardGrain=expected;
        }
    }
    for(let level=1;level<=10;level++){
        const {api}=harness(),n=node({storyboardGrain:level,prompt:'一张照片'});
        const built=await api.createPreparer(n)(api.plans(n,[])[0]);
        assert.ok(built.prompt.includes(`额外强度 ${level}/10`));
        assert.match(built.prompt,/无原始彩色参考时不声称匹配原图色光/);
    }
});

test('强复刻保留截断与反差，不让身份或场景匹配扩大景别',async()=>{
    for(const scene of [false,true]){
        const {api}=harness(),n=node({actorCount:2});
        const plan=api.plans(n,[ref('depth','d'),ref('reference','r'),ref('actor-0','a'),...(scene ? [ref('scene','set')] : [])])[0];
        if(scene) plan.sceneMatch={sceneUrl:'set',location:'门边',framing:'中景',lighting:'柔光',reason:'对应'};
        const built=await api.createPreparer(n)(plan);
        for(const text of ['原图头部出框就保持出框','仅见局部侧脸不能补成完整正脸','原本可见的脸也不能额外遮掉','共用色光参考不得覆盖各镜头结构','整体反差、黑位深浅','不因此拉高整个画面的对比度']) assert.ok(built.prompt.includes(text),text);
    }
});
