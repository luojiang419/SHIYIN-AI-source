const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const createStartup = require('../../static/js/canvas-startup.js');
const source = fs.readFileSync('static/js/canvas.js', 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
const cfg = {api_providers:[{id:'custom', enabled:true, image_models:['private-image'], video_models:['private-video']}], image_models:['private-image'], video_models:['private-video']};
const project = id => ({canvas:{id, nodes:[
    {id:'image-gen', type:'generator', apiProvider:'custom', model:'private-image', prompt:'unchanged'},
    {id:'video-gen', type:'video', apiProvider:'custom', model:'private-video'},
    {id:'legacy', type:'comfy', comfyWorkflow:'saved-workflow.json'}
], connections:[], viewport:{x:0,y:0,scale:1}}});
function harness(){
    let serial=0;
    const requests=[], frames=new Map(), idle=new Map(), timers=new Map(), warnings=[];
    const enqueue = map => callback => {const id=++serial; map.set(id,callback); return id;};
    const host = {
        document:{hidden:false}, performance:{now:() => 50},
        console:{warn:(...args) => warnings.push(args)},
        requestAnimationFrame:enqueue(frames), cancelAnimationFrame:id => frames.delete(id),
        requestIdleCallback:enqueue(idle), cancelIdleCallback:id => idle.delete(id),
        setTimeout:enqueue(timers), clearTimeout:id => timers.delete(id),
        fetch:(url,{signal}) => new Promise((resolve,reject) => {
            const request={url, signal, respond:(value,status=200) => resolve({ok:status===200,status,json:async () => value}), reject};
            signal.addEventListener('abort', () => reject(new DOMException('aborted','AbortError')), {once:true});
            requests.push(request);
        })
    };
    const flush = map => {const callbacks=[...map.values()]; map.clear(); callbacks.forEach(callback => callback());};
    return {host, requests, frames, idle, timers, warnings, flush, startup:createStartup(host)};
}
function fn(name){
    const start=source.search(new RegExp('(?:async )?function '+name+'\\('));
    assert.ok(start>=0, name);
    const end=source.indexOf('\n}',start);
    assert.ok(end>start, name+' end');
    return source.slice(start,end+2);
}
function editor(h){
    const calls=[];
    const ctx={window:{CanvasStartup:h.startup, location:{replace:() => calls.push('redirect')}},
        canvas:null, nodes:[], connections:[], selected:new Set(), canvasConfigRevision:0, canvasConfigRequestSequence:0,
        imageModels:['default-image'],chatModels:[],videoModels:['default-video'],msChatModels:[],
        DEFAULT_VIDEO_MODELS:['default-video'], apiProviders:[], managedProviderId:'comfly', models:{},
        runningHubWorkflowCache:{}, console:{error:()=>{},warn:()=>{}},
        loadLocalModelLists:()=>{}, migrateLegacySmartCanvasNodes:nodes=>({nodes,changed:false}),
        localViewportForCanvas:(_id,value)=>value, tr:key=>key,
        showCanvasStartupNotice:(_id,error)=>{if(error)calls.push('error');}, hideCanvasStartupNotice:()=>{},
        startCanvasSecondaryStartup:()=>calls.push('secondary'),
        canvasListUrlForProject:()=>'/list',
        scheduleSave:()=>calls.push('save'),
    };
    for(const name of ['setStatus','resetCascadeRuntimeState','rememberCanvasListProject','clearClassicHistory',
        'pruneCanvasRuntimeCollections','resetTransientRunState','sanitizeConnections','setCanvasMode',
        'renderCanvasList','requestedCanvasListProject','rememberedCanvasListProject']) ctx[name]=()=>{};
    vm.createContext(ctx);
    for(const name of ['uniqueModels','defaultApiProviders','imageApiProviders','resolveImageProviderId',
        'providerImageModels','resolveImageModel','sanitizeImageNodeProviderModel','videoApiProviders',
        'resolveVideoProviderId','providerVideoModels','sanitizeVideoNodeProviderModel','applyCanvasRuntimeConfig',
        'openCanvas']) vm.runInContext(fn(name),ctx);
    ctx.render=()=>{
        calls.push('render');
        ctx.nodes.forEach(node=>{ctx.sanitizeImageNodeProviderModel(node);ctx.sanitizeVideoNodeProviderModel(node);});
    };
    return {ctx,calls};
}
(async()=>{
    // 必需依赖并行，真实节点参数修正函数只在配置就绪后执行。
    const h=harness(), e=editor(h);
    h.startup.prefetch('A');
    assert.deepEqual(h.requests.map(r=>r.url),['/api/canvases/A','/api/runtime/config']);
    const open=e.ctx.openCanvas('A');
    assert.equal(h.requests.length,2);
    const before=project('A');
    const saved=structuredClone(before.canvas.nodes);
    h.requests[0].respond(before);
    await tick();
    assert.deepEqual(e.calls,[]);
    assert.equal(e.ctx.canvas,null);
    h.requests[1].respond(cfg);
    await open;
    assert.deepEqual(e.calls,['render']);
    assert.deepEqual(e.ctx.nodes,saved);
    assert.equal(e.ctx.nodes[2].comfyWorkflow,'saved-workflow.json');
    h.flush(h.frames); await tick(); assert.deepEqual(e.calls,['render']);
    h.flush(h.frames); await tick(); assert.deepEqual(e.calls,['render']);
    h.flush(h.idle); await tick(); assert.deepEqual(e.calls,['render','secondary']);
    h.startup.setVisible(true); h.flush(h.frames); h.flush(h.idle); await tick();
    assert.equal(e.calls.filter(x=>x==='secondary').length,1);
    assert.equal(h.timers.size,0);

    // A 的迟到结果不能覆盖 B；打开同一 ID 也必须是新请求。
    const switched=harness(), se=editor(switched);
    const a=se.ctx.openCanvas('A');
    const b=se.ctx.openCanvas('B');
    assert.equal(switched.requests[0].signal.aborted,true);
    switched.requests[0].respond(project('A')); switched.requests[1].respond(cfg);
    switched.requests[2].respond(project('B')); switched.requests[3].respond(cfg);
    await Promise.all([a,b]);
    assert.equal(se.ctx.canvas.id,'B'); assert.deepEqual(se.calls,['render']);
    const same=se.ctx.openCanvas('B');
    assert.equal(switched.requests.length,6);
    switched.requests[4].respond(project('B')); switched.requests[5].respond(cfg); await same;

    // 失败不渲染、不自动保存；重试读取新数据。404 才回列表。
    for(const failure of ['config','canvas','network','json','invalid','timeout']){
        const f=harness(), fe=editor(f), pending=fe.ctx.openCanvas('F');
        if(failure==='timeout') f.flush(f.timers);
        else if(failure==='network') f.requests[0].reject(new Error('offline'));
        else if(failure==='json') f.requests[1].reject(new SyntaxError('invalid JSON'));
        else if(failure==='invalid') f.requests[1].respond({});
        else f.requests[failure==='config'?1:0].respond({},failure==='canvas'?404:503);
        await pending;
        assert.equal(fe.ctx.canvas,null);
        assert.deepEqual(fe.calls,[failure==='canvas'?'redirect':'error']);
        assert.ok(f.requests.every(r=>r.signal.aborted));
        const retry=fe.ctx.openCanvas('F');
        f.requests[2].respond(project('F')); f.requests[3].respond(cfg); await retry;
        assert.equal(fe.ctx.canvas.id,'F');
        assert.ok(!fe.calls.includes('save'));
    }

    // 隐藏时保留后续任务，返回后执行一次；离开页面/新会话取消旧任务。
    const hidden=harness();
    const session=hidden.startup.open('hidden');
    hidden.requests[0].respond(project('hidden')); hidden.requests[1].respond(cfg); await session.ready;
    let background=0;
    hidden.startup.setVisible(false); session.afterPaint(()=>background++);
    hidden.flush(hidden.frames); hidden.flush(hidden.idle); await tick(); assert.equal(background,0);
    hidden.startup.setVisible(true); hidden.flush(hidden.frames); hidden.flush(hidden.frames);
    hidden.startup.setVisible(false); hidden.flush(hidden.idle); await tick(); assert.equal(background,0);
    hidden.startup.setVisible(true); hidden.flush(hidden.frames); hidden.flush(hidden.frames); hidden.flush(hidden.idle);
    await tick(); assert.equal(background,1);
    hidden.startup.cancel(); assert.equal(session.isCurrent(),false);
    const stale=hidden.startup.open('stale');
    hidden.requests[2].respond(project('stale')); hidden.requests[3].respond(cfg); await stale.ready;
    stale.afterPaint(()=>background++); hidden.flush(hidden.frames); hidden.startup.cancel();
    hidden.flush(hidden.frames); hidden.flush(hidden.idle); await tick(); assert.equal(background,1);

    // 在编辑器启动前到达的较新设置，不能被旧预取配置覆盖。
    const fresh=harness(), fre=editor(fresh);
    fresh.startup.prefetch('fresh');
    const newer=structuredClone(cfg); newer.api_providers[0].name='new settings';
    fre.ctx.applyCanvasRuntimeConfig(newer);
    const freshOpen=fre.ctx.openCanvas('fresh');
    fresh.requests[0].respond(project('fresh')); fresh.requests[1].respond(cfg); await freshOpen;
    assert.equal(fre.ctx.apiProviders[0].name,'new settings');

    // 配置刷新失败保留已有配置；连续刷新只允许最新响应生效。
    const refresh=harness(), re=editor(refresh);
    re.ctx.loadCanvasConfigCapabilities=async()=>{};
    vm.runInContext(fn('loadConfig'),re.ctx);
    re.ctx.applyCanvasRuntimeConfig(cfg);
    const failed=re.ctx.loadConfig(); refresh.requests[0].respond({},500);
    assert.equal(await failed,false); assert.equal(re.ctx.apiProviders[0].id,'custom');
    const old=re.ctx.loadConfig(), latest=re.ctx.loadConfig();
    refresh.requests[2].respond(newer); assert.equal(await latest,true);
    refresh.requests[1].respond(cfg); assert.equal(await old,false);
    assert.equal(re.ctx.apiProviders[0].name,'new settings');

    // 能力补齐只探测画布用到的平台，更新对应节点，不触发全量 render。
    const cap=editor(harness());
    vm.runInContext(fn('isMiniMaxH3VideoNode'),cap.ctx);
    vm.runInContext(fn('loadCanvasConfigCapabilities'),cap.ctx);
    const loaded=[], patched=[];
    cap.ctx.ensureRunningHubWorkflow=async id=>loaded.push(id);
    cap.ctx.loadMiniMaxH3Status=async()=>loaded.push('h3');
    cap.ctx.refreshNodes=ids=>patched.push(...ids);
    cap.ctx.nodes=[{id:'rh1',type:'rh',workflowId:'w1'},{id:'rh2',type:'rh',workflowId:'w1'},
        {id:'h3',type:'video',apiProvider:'minimax-h3'},{id:'unrelated',type:'prompt'}];
    await cap.ctx.loadCanvasConfigCapabilities();
    assert.deepEqual(loaded,['w1','h3']); assert.deepEqual(patched,['rh1','rh2','h3']);
    assert.deepEqual(cap.calls,[]);
    patched.length=0; await cap.ctx.loadCanvasConfigCapabilities({isCurrent:()=>false}); assert.deepEqual(patched,[]);
    cap.ctx.nodes=[]; loaded.length=0; await cap.ctx.loadCanvasConfigCapabilities(); assert.deepEqual(loaded,[]);

    // 不等 window.load；脚本在 DOM 不同状态下都只初始化一次。
    const init=source.slice(source.indexOf('async function initializeCanvasPage(){'));
    for(const readyState of ['loading','interactive','complete']){
        let ready;
        const calls=[];
        const ctx={window:{location:{search:'?id=dom'}},document:{readyState,
            addEventListener:(event,cb,options)=>{assert.equal(event,'DOMContentLoaded');assert.equal(options.once,true);ready=cb;}},
            localStorage:{getItem:()=>null},URLSearchParams,performance:{now:()=>1},CANVAS_THEME_KEY:'theme',tr:x=>x,
            openCanvas:async id=>calls.push(id)};
        for(const name of ['startCanvasStatsLoop','updateCanvasStats','applyTheme','loadClassicShortcutLocalFallback',
            'loadClassicShortcutSettings','applyQuickToolbarState','initOutputCompareEvents','initOutputPreviewZoomEvents','applyViewport'])ctx[name]=()=>{};
        vm.runInNewContext(init,ctx);
        if(readyState==='loading'){assert.deepEqual(calls,[]);await ready();}
        assert.deepEqual(calls,['dom']);assert.equal(ctx.window.onload,undefined);
    }
    // 同语言的重复通知不重绘，切换语言只通过一个入口刷新。
    let language='zh', renders=0;
    const langCtx={window:{StudioI18n:{lang:()=>language}},classicRenderedLanguage:'',
        document:{},canvas:{title:'fixture'},currentCanvasTitle:{},tr:x=>x,
        refreshGateViewControls:()=>{},renderCanvasList:()=>{},applyQuickToolbarState:()=>{},render:()=>renders++};
    langCtx.StudioI18n=langCtx.window.StudioI18n;
    vm.createContext(langCtx);
    vm.runInContext(fn('refreshCanvasLanguage'),langCtx);
    vm.runInContext(fn('applyLanguage'),langCtx);
    langCtx.StudioI18n.set=value=>{language=value;langCtx.refreshCanvasLanguage();};
    langCtx.refreshCanvasLanguage();langCtx.refreshCanvasLanguage();assert.equal(renders,1);
    langCtx.applyLanguage('en');assert.equal(renders,2);
    langCtx.refreshCanvasLanguage();assert.equal(renders,2);

    // 旧会话的资源检查和配置缓存回包，不能写入新会话。
    let resolveAssets;
    const assets={canvas:{id:'same'},nodes:[{}],missingAssetUrls:new Set(['keep']),
        canvasLocalAssetUrls:()=>['/assets/test.png'],console,
        fetch:()=>new Promise(resolve=>resolveAssets=resolve)};
    vm.createContext(assets);vm.runInContext(fn('refreshMissingCanvasAssets'),assets);
    const checking=assets.refreshMissingCanvasAssets();assets.nodes=[{}];
    resolveAssets({json:async()=>({exists:{'/assets/test.png':false}})});await checking;
    assert.deepEqual([...assets.missingAssetUrls],['keep']);
    let resolveWorkflow;
    const workflow={runningHubWorkflowCache:{},validRunningHubWorkflowId:x=>x,
        fetch:()=>new Promise(resolve=>resolveWorkflow=resolve)};
    vm.createContext(workflow);vm.runInContext(fn('ensureRunningHubWorkflow'),workflow);
    const loadingWorkflow=workflow.ensureRunningHubWorkflow('w');workflow.runningHubWorkflowCache={};
    resolveWorkflow({ok:true,json:async()=>({workflow:{title:'old'}})});await loadingWorkflow;
    assert.deepEqual(workflow.runningHubWorkflowCache,{});

    // 没有 requestIdleCallback 的浏览器仍在绘制之后执行，并清理计时器。
    const fallback=harness();
    delete fallback.host.requestIdleCallback;delete fallback.host.cancelIdleCallback;
    const fallbackSession=fallback.startup.open('fallback');
    fallback.requests[0].respond(project('fallback'));fallback.requests[1].respond(cfg);await fallbackSession.ready;
    let fallbackRuns=0;fallbackSession.afterPaint(()=>fallbackRuns++);
    fallback.flush(fallback.frames);fallback.flush(fallback.frames);fallback.flush(fallback.timers);await tick();
    assert.equal(fallbackRuns,1);assert.equal(fallback.timers.size,0);

    // 真实浏览器入口：无 ID 不请求；带 ID 时提前开始，编码路径且仅消费一次。
    const bootSource=fs.readFileSync('static/js/canvas-startup.js','utf8');
    const noId=harness();noId.host.location={search:''};
    vm.runInNewContext(bootSource,{window:noId.host,URLSearchParams,AbortController});
    assert.equal(noId.requests.length,0);
    const booted=harness();booted.host.location={search:'?id=A%2FB'};
    vm.runInNewContext(bootSource,{window:booted.host,URLSearchParams,AbortController});
    assert.deepEqual(booted.requests.map(r=>r.url),['/api/canvases/A%2FB','/api/runtime/config']);
    const bootSession=booted.host.CanvasStartup.open('A/B');
    assert.equal(booted.requests.length,2);
    booted.requests[0].respond(project('A/B'));booted.requests[1].respond(cfg);await bootSession.ready;

    // 已配置 H3 仍会为新建节点预热；后台探测期间点击生成必须等到同一个结果。
    cap.ctx.apiProviders=[{id:'minimax-h3'}];
    await cap.ctx.loadCanvasConfigCapabilities();assert.deepEqual(loaded,['h3']);
    let h3Response,h3Requests=0;
    const h3={minimaxH3StatusTask:null,minimaxH3State:{loaded:false,loading:false,generationEnabled:false},
        fetch:()=>{h3Requests++;return new Promise(resolve=>h3Response=resolve);},render:()=>{}};
    vm.createContext(h3);vm.runInContext(fn('loadMiniMaxH3Status'),h3);
    const preheat=h3.loadMiniMaxH3Status();
    let generationReady=false;
    const onGenerate=h3.loadMiniMaxH3Status().then(value=>{generationReady=value.generationEnabled;});
    await tick();assert.equal(h3Requests,1);assert.equal(generationReady,false);
    h3Response({ok:true,json:async()=>({generation_enabled:true})});
    await Promise.all([preheat,onGenerate]);assert.equal(generationReady,true);
    assert.equal(h3.minimaxH3StatusTask,null);

    // 使用假的可控时钟，不留下真实计时器或网络连接。
    console.log('startup lifecycle, data integrity, cancellation, retry, config races and selective hydration passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
