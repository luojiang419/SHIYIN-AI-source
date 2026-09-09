(function(){
    'use strict';
    const locks=new WeakSet();
    const copy=value=>JSON.parse(JSON.stringify(value));
    const uid=()=>globalThis.crypto.randomUUID();
    const PREPARE='film-prepare-assets', CONFIRM='film-confirm-shots';

    function reconcile(source,canvasId){
        const previous=source.prepare.workflowSnapshot || {};
        const s=copy(previous);
        s.scriptId=`canvas:${canvasId}:${source.prepare.id}`;
        s.localVersion=1;
        s.name=source.group.title || '画布镜头';
        s.parameters={aspectRatio:'16:9',imageSize:'2k',quality:'high',...s.parameters};
        s.assets ||= []; s.bindings ||= []; s.guides ||= []; s.tasks ||= [];
        const claimed=new Set();
        s.shots=source.frames.map((frame,index)=>{
            const old=(previous.shots || []).find(shot=>!claimed.has(shot.id) && (shot.sourceNodeId===frame.id || (!shot.sourceNodeId && shot.frame===frame.url)));
            if(old) claimed.add(old.id);
            const same=old && old.frame===frame.url;
            return {...(same?old:{}),id:old?.id || `shot:${frame.id}`,sourceNodeId:frame.id,
                frame:frame.url,number:index+1,content:same?old.content:frame.bridgeCaption || '',
                durationSeconds:same?old.durationSeconds || 5:5,confirmed:same?!!old.confirmed:false};
        });
        const ids=new Set(s.shots.map(shot=>shot.id));
        const unchanged=new Set(s.shots.filter(shot=>(previous.shots || []).some(old=>old.id===shot.id && old.frame===shot.frame)).map(shot=>shot.id));
        s.bindings=s.bindings.filter(binding=>unchanged.has(binding.shotId));
        s.guides=s.guides.filter(guide=>unchanged.has(guide.shotId));
        s.tasks=s.tasks.filter(task=>ids.has(task.shotId));
        s.boundAssets=s.assets;
        s.groups=[];
        s.message=`已接收 ${s.shots.length} 张图片 · 按连线和组内顺序排列 · 数据保存在当前画布`;
        return s;
    }

    async function execute(node,payload,source,ctx,hooks){
        const parent=source.prepare;
        if(locks.has(parent)) throw new Error('此工作流正在处理另一项操作，请完成后再试');
        locks.add(parent);
        const action=payload.action;
        let s=reconcile(source,ctx.canvasId);
        const selected=payload.shot_id?s.shots.filter(shot=>shot.id===payload.shot_id):s.shots;
        const publish=()=>{
            if(!hooks.current()) return;
            parent.workflowSnapshot=s;
            parent.workflowScriptId=s.scriptId;
            for(const target of ctx.nodes){
                if(window.CanvasFilmWorkflow.sourceFor(target,ctx.nodes,ctx.connections)?.prepare!==parent) continue;
                target.workflowSnapshot=s; target.workflowScriptId=s.scriptId;
                delete target.workflowJob;
            }
            hooks.notify();
        };
        const live=()=>{if(!hooks.current()) throw new Error('输入已变更，旧操作已停止；已生成结果保留在画布输出节点');};
        const llm=async(message,images=[])=>{
            const response=await fetch('/api/canvas-llm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
                message,images,videos:[],...(ctx.vision?.() || {}),system_prompt:'你是影视镜头与资产分析助手。只根据实际图片与用户要求回答，不虚构图片内容。'
            })});
            const result=await response.json();
            if(!response.ok || !String(result.text || '').trim()) throw new Error(result.detail || '解析没有返回内容');
            live(); return String(result.text).trim();
        };
        try {
            if(payload.shot_id && !selected.length) throw new Error('该镜头已移除，请刷新后操作');
            switch(action){
                case 'sync': case 'snapshot':
                    s.tasks.forEach(task=>{if(['running','queued','submitting'].includes(task.status)){task.status='interrupted';task.error='页面已重新打开，请在画布生成节点查看任务结果，核对后再重试';}}); break;
                case 'parameters':
                    Object.assign(s.parameters,payload.parameters);
                    if('imageProvider' in payload.parameters) delete s.parameters.imageModel;
                    if('videoProvider' in payload.parameters) delete s.parameters.videoModel;
                    break;
                case 'edit-shot':
                    for(const shot of selected){
                        const values={...payload.parameters};
                        if('durationSeconds' in values){
                            const duration=Number(values.durationSeconds);
                            if(!Number.isFinite(duration) || duration<1 || duration>120) throw new Error('镜头时长需要在 1–120 秒之间');
                            values.durationSeconds=duration;
                        }
                        Object.assign(shot,values); shot.confirmed=false;
                    } break;
                case 'confirm': selected.forEach(shot=>{shot.confirmed=payload.confirmed!==false;}); break;
                case 'video-prompt': selected.forEach(shot=>{shot.draft=payload.prompt;}); break;
                case 'import-asset':
                    if(!payload.asset_url) throw new Error('请选择图片资产');
                    s.assets.push({id:uid(),url:payload.asset_url,name:payload.name || '图片资产',type:payload.asset_type || 'reference',description:''}); break;
                case 'edit-asset': {
                    const asset=s.assets.find(item=>item.id===payload.asset_id);
                    if(!asset) throw new Error('资产已移除');
                    Object.assign(asset,payload.parameters); break;
                }
                case 'delete-asset':
                    s.assets=s.assets.filter(asset=>asset.id!==payload.asset_id);
                    s.bindings=s.bindings.filter(binding=>binding.assetId!==payload.asset_id); break;
                case 'bind-asset':
                    if(!s.assets.some(asset=>asset.id===payload.asset_id)) throw new Error('资产已移除');
                    for(const shot of selected) if(!s.bindings.some(b=>b.shotId===shot.id && b.assetId===payload.asset_id)){s.bindings.push({shotId:shot.id,assetId:payload.asset_id});shot.confirmed=false;}
                    break;
                case 'unbind-asset': s.bindings=s.bindings.filter(b=>!(selected.some(shot=>shot.id===b.shotId) && b.assetId===payload.asset_id)); selected.forEach(shot=>{shot.confirmed=false;}); break;
                case 'analyze': case 'build-prompts':
                    for(const shot of selected){
                        live();
                        const prompt=action==='analyze'
                            ? '解析这张原帧：描述主体、服装、道具、场景、构图、景别、机位、光线与可见动作。用简洁中文直接描述画面。'
                            : `为此镜头编写可直接使用的视频提示词。时长 ${shot.durationSeconds} 秒，明确主体动作、运镜、光线和声音。格式 ${s.parameters.promptFormat || '通用中文'}。镜头描述：${shot.content || ''}；画面动作：${shot.visual || ''}；风格：${s.parameters.globalStyle || ''}；约束：${s.parameters.constraints || ''}；故事：${s.parameters.freeCreationStoryOverride || ''}`;
                        const result=await llm(prompt,[shot.replica || shot.frame]);
                        if(action==='analyze'){shot.content=result;shot.confirmed=false;}
                        else {shot.prompt=result;shot.draft=result;}
                        publish();
                    } break;
                case 'depth':
                    for(const shot of selected){
                        live();
                        const result=await ctx.depth({url:shot.frame,name:`镜头${shot.number}.png`}); live();
                        let guide=s.guides.find(item=>item.shotId===shot.id);
                        if(!guide){guide={shotId:shot.id};s.guides.push(guide);}
                        guide.depth=result.url; publish();
                    } break;
                case 'match': {
                    if(!s.assets.length) throw new Error('请先在右侧导入演员、服装、场景或道具资产');
                    if(s.assets.length>18) throw new Error('自动匹配一次最多支持 18 个候选资产，请手动绑定或减少候选');
                    for(const shot of selected){
                        live();
                        const result=await llm(`第一张是镜头原帧，后续是候选资产。选择适合此镜头的资产，返回纯 JSON 数字数组（从 1 开始），无匹配返回 []。候选：${s.assets.map((a,i)=>`${i+1}=${a.name}(${a.type}) ${a.description || ''}`).join('；')}`,[shot.frame,...s.assets.map(a=>a.url)]);
                        const ids=JSON.parse(result.replace(/^```(?:json)?\s*|\s*```$/g,''));
                        if(!Array.isArray(ids) || ids.some(id=>!Number.isInteger(id) || id<1 || id>s.assets.length)) throw new Error('匹配返回格式不正确，请重试或手动绑定');
                        for(const index of ids){const asset=s.assets[index-1];if(!s.bindings.some(b=>b.shotId===shot.id && b.assetId===asset.id))s.bindings.push({shotId:shot.id,assetId:asset.id});}
                        publish();
                    } break;
                }
                case 'replicate': case 'generate': {
                    if(action==='generate' && node.type!=='film-video') throw new Error('请从视频生成节点执行');
                    const shots=action==='generate'?selected.filter(shot=>shot.confirmed):selected;
                    if(!shots.length) throw new Error('请先确认需要生成的镜头');
                    for(const shot of shots){
                        live();
                        const assets=s.bindings.filter(b=>b.shotId===shot.id).map(b=>s.assets.find(a=>a.id===b.assetId)).filter(Boolean);
                        const task={id:uid(),shotId:shot.id,status:'running'};
                        if(action==='generate') s.tasks.unshift(task);
                        publish();
                        try {
                            const result=await ctx.generate({node,shot,assets,parameters:s.parameters,depth:s.guides.find(g=>g.shotId===shot.id)?.depth,video:action==='generate'});
                            live();
                            if(!result?.url) throw new Error('生成未返回结果，请检查画布生成节点');
                            if(action==='replicate'){shot.replica=result.url;shot.confirmed=false;delete shot.replicaError;}
                            else Object.assign(task,{url:result.url,status:'completed'});
                        } catch(error){
                            if(action==='replicate') shot.replicaError=error.message;
                            else Object.assign(task,{status:'failed',error:error.message});
                            publish();throw error;
                        }
                        publish();
                    } break;
                }
                case 'prompt-format': s.parameters.promptFormat=payload.format; break;
                case 'delete-task': s.tasks=s.tasks.filter(task=>task.id!==payload.task_id); break;
                default: throw new Error('当前画布不支持此操作，请刷新页面');
            }
            s.boundAssets=s.assets;
            live(); publish();
            return {ok:true,project_id:'',snapshot:s};
        } finally {locks.delete(parent);}
    }

    function paramsHtml(node,s,{esc,select,text,check,button},ctx){
        const p=s.parameters || {};
        if(node.type===PREPARE){
            const providers=ctx?.imageProviders?.() || [], provider=providers.find(v=>v.id===p.imageProvider) || providers[0];
            return `<small>解析使用设置中的视觉模型；生成使用下方图片模型。</small>${select('图片平台','imageProvider',providers.map(v=>({id:v.id,label:v.name})),provider?.id)}${select('图片模型','imageModel',provider?.models || [],p.imageModel || provider?.models?.[0])}
                ${select('画幅','aspectRatio',['16:9','9:16','1:1','3:4','4:5'],p.aspectRatio)}${select('分辨率','imageSize',['1k','2k','4k'],p.imageSize)}
                ${text('生成补充要求','replicationInstructions',p.replicationInstructions,4)}<h4>资产库</h4><label>导入类型<select data-wf-asset-type>${[['character','演员'],['product','服装 / 产品'],['scene','场景'],['prop','道具'],['reference','参考图']].map(([id,label])=>`<option value="${id}">${label}</option>`).join('')}</select></label>
                <label class="wf-upload">导入资产<input type="file" accept="image/*" data-wf-upload></label><div class="wf-assets">${(s.assets || []).map(a=>`<div class="wf-asset" draggable="true" data-wf-asset="${esc(a.id)}"><img loading="lazy" src="${esc(a.url)}" alt="${esc(a.name)}"><span>${esc(a.name)}</span><details><summary>编辑资产</summary><label>名称<input data-wf-asset-field="name" data-asset="${esc(a.id)}" value="${esc(a.name)}"></label><label>描述<textarea data-wf-asset-field="description" data-asset="${esc(a.id)}">${esc(a.description)}</textarea></label>${button('delete-asset','移除资产','',`data-asset="${esc(a.id)}"`)}</details></div>`).join('') || '<p>导入资产后可拖入镜头，或点击“匹配资产”自动选择。</p>'}</div>`;
        }
        if(node.type===CONFIRM) return `${text('全片风格','globalStyle',p.globalStyle,3)}${text('约束','constraints',p.constraints,3)}${text('故事内容','freeCreationStoryOverride',p.freeCreationStoryOverride || (s.shots || []).map(shot=>shot.content).join('\n'),7)}${select('提示词格式','promptFormat',[{id:'sd2',label:'Seedance'},{id:'kling',label:'可灵'},{id:'h3',label:'MiniMax H3'}],p.promptFormat || 'sd2')}<p>编辑描述和时长后确认镜头，再连接视频生成节点。</p>`;
        const providers=ctx?.videoProviders?.() || [], provider=providers.find(v=>v.id===p.videoProvider) || providers[0];
        return `${select('视频平台','videoProvider',providers.map(v=>({id:v.id,label:v.name})),provider?.id)}${select('视频模型','videoModel',provider?.models || [],p.videoModel || provider?.models?.[0])}${select('画幅','aspectRatio',['16:9','9:16','1:1'],p.aspectRatio)}${select('视频分辨率','videoResolution',['720p','1080p'],p.videoResolution || '1080p')}<p>仅生成已确认镜头，进度与结果也保留在画布生成节点。</p><div class="wf-works">${(s.tasks || []).map(t=>`<div class="wf-work"><span>${esc(t.status)}</span>${t.url?`<video controls preload="none" src="${esc(t.url)}"></video><a href="${esc(t.url)}" download>下载视频</a>`:''}${t.error?`<p class="wf-error">${esc(t.error)}</p>`:''}${button('delete-task','移除记录','',`data-task="${esc(t.id)}"`)}</div>`).join('')}</div>`;
    }
    window.CanvasLocalWorkflow={execute,reconcile,paramsHtml};
})();
