(function(){
    const TYPE='linkfox-video';
    const activeTasks=new Map();
    function progressHtml(node){ return `<div class="muted-note" role="status" data-linkfox-task-status="${esc(node.id || '')}">${esc(node.linkfoxTaskStatus || '')}</div>`; }
    function reportTask(node,message,onChange){
        node.linkfoxTaskStatus=message;
        document.querySelectorAll('[data-linkfox-task-status]').forEach(el=>{if(el.dataset.linkfoxTaskStatus===String(node.id || '')) el.textContent=message;});
        return onChange?.();
    }
    function promptOriginKey(raw){
        const urls=raw.mode==='first_last_frame'?[raw.imageUrl,raw.lastFrameImageUrl].filter(Boolean):(raw.imageList || []);
        const value=JSON.stringify([String(raw.prompt || '').trim(),urls,raw.mode || 'reference']);
        let hash=2166136261;
        for(let i=0;i<value.length;i++) hash=Math.imul(hash ^ value.charCodeAt(i),16777619);
        return `${value.length}:${hash >>> 0}`;
    }
    function promptSettingsKey(request){
        return JSON.stringify([
            request.duration ?? request.videoTime,
            request.aspect_ratio ?? request.aspectRatio ?? '',
            request.resolution || '',
            Boolean(request.generate_audio ?? request.voice),
            request.linkfox_mode ?? request.mode ?? 'reference',
            request.linkfox_camera ?? request.camera ?? 'single'
        ]);
    }
    function rememberVideoPromptResult(node,request){
        if(!node || !request?.prompt_origin_key || !request?.prompt) return;
        node.videoPromptLastResult={originKey:request.prompt_origin_key,prompt:request.prompt,
            provider:request.provider_id || 'linkfox',model:request.model,
            settingsKey:promptSettingsKey(request)};
    }
    function taskPayload(raw,node){
        if(raw.entry!=='img2video') return raw;
        const urls=raw.mode==='first_last_frame'?[raw.imageUrl,raw.lastFrameImageUrl].filter(Boolean):raw.imageList;
        const originKey=promptOriginKey(raw);
        const previous=node?.videoPromptLastResult;
        const reuse=previous?.originKey===originKey;
        const base={provider_id:'linkfox',linkfox_direct:true,model:raw.videoType,duration:raw.videoTime,
            prompt:reuse ? previous.prompt : raw.prompt,
            images:(urls || []).map((url,i)=>({url,...(raw.mode==='first_last_frame'?{role:i?'last_frame':'first_frame'}:{})})),
            resolution:raw.resolution,aspect_ratio:raw.aspectRatio,generate_audio:raw.voice,
            linkfox_mode:raw.mode,linkfox_camera:raw.camera,linkfox_is_pro:raw.isPro,
            linkfox_prompt_optimizer:false,canvas_id:raw.canvas_id,node_id:raw.node_id};
        const sameTarget=reuse && previous.provider==='linkfox' && previous.model===base.model
            && previous.settingsKey===promptSettingsKey(base);
        return {...base,auto_adapt_prompt:!sameTarget,
            auto_parse_media:!String(raw.prompt || '').trim() && !reuse,prompt_origin_key:originKey,
            prompt_source_model:reuse ? previous.model : '',prompt_source_provider:reuse ? previous.provider : ''};
    }
    async function taskJson(url,options={}){
        const controller=new AbortController();
        const timer=setTimeout(()=>controller.abort(),options.method==='POST'?180000:30000);
        try {
            const response=await fetch(url,{...options,signal:controller.signal});
            const body=await response.json();
            if(!response.ok){ const error=new Error(body.detail || `LinkFox 请求失败（HTTP ${response.status}）`); error.httpStatus=response.status; throw error; }
            return body;
        } finally { clearTimeout(timer); }
    }
    function generate(node,raw,options={}){
        if(activeTasks.has(node)) return activeTasks.get(node);
        const work=(async()=>{
            const existing=node.linkfoxTaskId;
            const taskId=existing || `canvas_video_linkfox_${Date.now()}_${Math.random().toString(16).slice(2)}`;
            node.linkfoxTaskId=taskId;
            await reportTask(node,existing?'正在恢复已保存的 LinkFox 任务':'正在准备并提交 LinkFox 任务',options.onChange);
            let task;
            try {
                task=existing?await taskJson(`/api/canvas-video-tasks/${encodeURIComponent(taskId)}`):await taskJson('/api/canvas-video-tasks',{
                method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...taskPayload(raw,node),task_id:taskId})});
            } catch(error){
                // 提交响应丢失时只查询相同 ID，绝不自动重新 POST。
                try { task=await taskJson(`/api/canvas-video-tasks/${encodeURIComponent(taskId)}`); }
                catch(queryError){
                    if(queryError.httpStatus===404 && error.httpStatus>=400 && error.httpStatus<500){
                        node.linkfoxTaskId=''; await reportTask(node,error.message,options.onChange);
                    } else await reportTask(node,`${error.message}；任务记录 ${taskId} 已保留，再次运行仅续查。`,options.onChange);
                    throw error;
                }
            }
            for(let attempt=0;attempt<720;attempt++){
                const upstream=task.upstream_task_id || '';
                const suffix=upstream?` · taskId: ${upstream}`:'';
                await reportTask(node,(task.error || task.message || (task.status==='succeeded'?'视频已完成':'正在查询视频'))+suffix,options.onChange);
                if(task.status==='succeeded'){
                    if(!task.result?.videos?.length) throw new Error('LinkFox 任务完成但没有返回视频');
                    rememberVideoPromptResult(node,task.result.request);
                    node.linkfoxTaskId=''; await options.onChange?.(); return task.result;
                }
                if(['failed','interrupted','canceled','cancelled'].includes(task.status)){
                    // 已知上游任务的超时记录继续保留，避免用户误点造成重复付费。
                    if(task.status!=='interrupted') node.linkfoxTaskId='';
                    await options.onChange?.(); throw new Error(task.error || 'LinkFox 任务未完成');
                }
                await new Promise(resolve=>setTimeout(resolve,2500));
                try { task=await taskJson(`/api/canvas-video-tasks/${encodeURIComponent(taskId)}`); }
                catch(error){ await reportTask(node,`查询连接中断，正在恢复${suffix}：${error.message}`,options.onChange); }
            }
            throw new Error(`LinkFox 等待超时，已保留任务 ${taskId}，再次运行仅续查。`);
        })();
        activeTasks.set(node,work);
        return work.finally(()=>activeTasks.delete(node));
    }
    const MODELS={
        reference:[
            {id:'seedance2.0',label:'Seedance 2.0',durations:[5,10,15],resolutions:['480p','720p','1080p'],ratios:['16:9','9:16','adaptive'],voice:'optional',maxImages:9},
            {id:'seedance2.0fast',label:'Seedance 2.0 Fast',durations:[5,10,15],resolutions:['480p','720p'],ratios:['16:9','9:16'],voice:'optional',maxImages:9},
            {id:'可灵Omni',label:'可灵 Omni',durations:[5,10],resolutions:['720p','1080p'],ratios:['16:9','9:16','1:1'],voice:'fixed_false',maxImages:7},
            {id:'HappyHorse',label:'HappyHorse（百炼）',durations:[5,10,15],resolutions:['720p','1080p'],ratios:['16:9','9:16'],voice:'fixed_true',maxImages:9},
            {id:'海螺2.3',label:'海螺 2.3',durations:[6,10],resolutions:['768p','1080p'],ratios:[],voice:'fixed_false',maxImages:1},
            {id:'wan2.6',label:'Wan 2.6',durations:[5,10,15],resolutions:[],ratios:[],voice:'optional',maxImages:1},
        ],
        first_last_frame:[
            {id:'seedance2.0',label:'Seedance 2.0',durations:[5,10,15],resolutions:['480p','720p','1080p'],ratios:['16:9','9:16','adaptive'],voice:'optional',maxImages:2},
            {id:'seedance2.0fast',label:'Seedance 2.0 Fast',durations:[5,10,15],resolutions:['480p','720p'],ratios:['16:9','9:16'],voice:'optional',maxImages:2},
            {id:'可灵2.6',label:'可灵 2.6',durations:[5,10],resolutions:['720p','1080p'],ratios:['adaptive'],voice:'optional',maxImages:2},
        ]
    };
    const esc=value => (typeof window.escapeHtml==='function' ? window.escapeHtml(String(value??'')) : String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])));
    const modelFor=(node)=> (MODELS[node?.mode==='first_last_frame'?'first_last_frame':'reference'].find(item=>item.id===node?.model) || MODELS[node?.mode==='first_last_frame'?'first_last_frame':'reference'][0]);
    function modelsFor(node){ return MODELS[node?.mode==='first_last_frame'?'first_last_frame':'reference']; }
    function inputPorts(node){
        return [{role:'reference-image',label:node.mode==='first_last_frame'?'首帧':'参考图',title:'连接参考图片'},
            ...(node.mode==='first_last_frame'?[{role:'last-frame',label:'尾帧',title:'连接尾帧图片'}]:[])];
    }
    function inputRefs(node, nodes, connections, refsForNode){
        return (connections||[]).filter(connection=>connection.to===node.id).flatMap(connection=>{
            const source=nodes.find(item=>item.id===connection.from);
            return (source?refsForNode(source):[]).filter(ref=>ref?.url && (!ref.kind || ref.kind==='image'))
                .map(ref=>({...ref,inputRole:connection.inputRole||''}));
        });
    }
    function normalizeSettings(node){
        const model=modelFor(node);
        node.model=model.id;
        if(!model.durations.includes(Number(node.duration))) node.duration=model.durations[0];
        if(!model.resolutions.includes(node.resolution)) node.resolution=model.resolutions[0]||'';
        if(!model.ratios.includes(node.aspectRatio)) node.aspectRatio=model.ratios[0]||'';
        if(model.voice!=='optional') node.voice=model.voice==='fixed_true';
    }
    function createNode(point, extra={}){
        const mode=extra.mode || 'reference';
        const model=extra.model || MODELS[mode][0].id;
        return {id:'linkfox-video',type:TYPE,specialType:TYPE,title:'LinkFox 视频生成',x:point?.x||0,y:point?.y||0,w:480,h:0,mode,model,duration:5,resolution:'720p',aspectRatio:'16:9',voice:true,promptOptimizer:false,isPro:false,camera:'single',prompt:'',lastFrameImageUrl:'',inputs:[],images:[],running:false,runError:'',...extra};
    }
    function options(list, selected, emptyLabel){ return (list||[]).map(value=>{ const empty=!value && emptyLabel; const valueText=empty?'':value; const label=empty?emptyLabel:value; return `<option value="${esc(valueText)}" ${String(valueText)===String(selected)?'selected':''}>${esc(label)}</option>`; }).join(''); }
    function bodyHtml(node){
        normalizeSettings(node);
        const mode=node.mode==='first_last_frame'?'first_last_frame':'reference';
        const model=modelFor(node); const models=modelsFor(node);
        if(!models.some(item=>item.id===node.model)) node.model=models[0].id;
        const selectedModel=modelFor(node);
        const durations=selectedModel.durations; const resolutions=selectedModel.resolutions.length?selectedModel.resolutions:['']; const ratios=selectedModel.ratios.length?selectedModel.ratios:[''];
        const voiceFixed=selectedModel.voice!=='optional';
        return `<div class="linkfox-video-body">${progressHtml(node)}
            <div class="linkfox-video-badge">LinkFox · 图转视频</div>
            <label class="field"><div class="setting-title">生成模式</div><select class="select-lite" data-linkfox-field="mode"><option value="reference" ${mode==='reference'?'selected':''}>参考图</option><option value="first_last_frame" ${mode==='first_last_frame'?'selected':''}>首尾帧</option></select></label>
            <label class="field"><div class="setting-title">视频模型</div><select class="select-lite" data-linkfox-field="model">${models.map(item=>`<option value="${esc(item.id)}" ${item.id===node.model?'selected':''}>${esc(item.label)}</option>`).join('')}</select></label>
            <div class="linkfox-video-grid">
                <label class="field"><div class="setting-title">时长</div><select class="select-lite" data-linkfox-field="duration">${options(durations,node.duration||durations[0]).replace(/>(\d+)</g,'>$1 秒<')}</select></label>
                <label class="field"><div class="setting-title">分辨率</div><select class="select-lite" data-linkfox-field="resolution">${options(resolutions,(selectedModel.resolutions.includes(node.resolution)?node.resolution:(selectedModel.resolutions[0]||'')),'按模型')}</select></label>
                <label class="field"><div class="setting-title">比例</div><select class="select-lite" data-linkfox-field="aspectRatio">${options(ratios,selectedModel.ratios.includes(node.aspectRatio)?node.aspectRatio:(selectedModel.ratios[0]||''),'按模型')}</select></label>
            </div>
            <label class="field"><div class="setting-title">动态效果提示词</div><textarea class="setting-textarea linkfox-video-prompt" data-linkfox-field="prompt" rows="3" placeholder="描述图片如何运动">${esc(node.prompt||'')}</textarea></label>
            <div class="linkfox-video-grid linkfox-video-toggles">
                <button type="button" class="setting-check ${node.voice?'active':''}" data-linkfox-toggle="voice" ${voiceFixed?'disabled':''}><span class="check-dot"></span>声音${voiceFixed?'（模型固定）':''}</button>
                <button type="button" class="setting-check ${node.isPro?'active':''}" data-linkfox-toggle="isPro"><span class="check-dot"></span>Pro 模式</button>
                <button type="button" class="setting-check ${node.camera==='multi'?'active':''}" data-linkfox-toggle="camera"><span class="check-dot"></span>多段运镜</button>
            </div>
            ${mode==='first_last_frame'?'<div class="linkfox-frame-note">首帧和尾帧请通过两个输入端口连接；可灵 2.6 尾帧仅支持 1080p 且关闭声音。</div>':'<div class="linkfox-frame-note">参考图模式支持多张图片，数量上限随模型变化。</div>'}
            <div class="linkfox-config-hint">未配置 API Key 时，请打开“API 设置”中的 LinkFox 视频生成配置。</div>
            <div class="linkfox-video-input-summary" data-linkfox-input-summary>等待连接图片…</div>
            <button type="button" class="gen-btn linkfox-video-run" data-linkfox-action="run" ${node.running?'disabled':''}>${node.running?'生成中…':'生成 LinkFox 视频'}</button>
            ${node.runError?`<div class="linkfox-video-error">${esc(node.runError)}</div>`:''}
        </div>`;
    }
    function buildRequest(node, refs){
        normalizeSettings(node);
        const images=(refs||[]).map(ref=>typeof ref==='string'?{url:ref}:ref).filter(ref=>ref?.url && (!ref.kind || ref.kind==='image'));
        const urls=images.map(ref=>ref.url);
        if(!urls.length) throw new Error('请至少连接一张图片');
        const limit=node.mode==='first_last_frame'?2:modelFor(node).maxImages;
        if(urls.length>limit) throw new Error(`当前模式最多支持 ${limit} 张图片，请减少连接图片`);
        const payload={entry:'img2video',mode:node.mode||'reference',imageList:urls,videoType:node.model,videoTime:Number(node.duration||5),prompt:node.prompt||'',promptOptimizer:false,isPro:Boolean(node.isPro),voice:Boolean(node.voice),camera:node.camera||'single',aspectRatio:node.aspectRatio||'',resolution:node.resolution||''};
        if(payload.mode==='first_last_frame'){
            const heads=images.filter(ref=>ref.inputRole!=='last-frame');
            const tails=images.filter(ref=>ref.inputRole==='last-frame');
            if(!heads.length) throw new Error('请连接首帧图片');
            if(tails.length>1 || (tails.length && heads.length>1)) throw new Error('首帧和尾帧端口各支持一张图片');
            payload.imageUrl=heads[0].url;
            payload.lastFrameImageUrl=tails[0]?.url||heads[1]?.url||node.lastFrameImageUrl||'';
            payload.imageList=[payload.imageUrl,...(payload.lastFrameImageUrl?[payload.lastFrameImageUrl]:[])];
        }
        return payload;
    }
    function bind(root,node,options={}){
        const rerender=()=>{ options.onChange?.(node,{render:true}); };
        root.querySelectorAll('[data-linkfox-field]').forEach(control=>{
            control.addEventListener('mousedown',e=>e.stopPropagation()); control.addEventListener('click',e=>e.stopPropagation());
            control.addEventListener('change',e=>{ e.stopPropagation(); const field=control.dataset.linkfoxField; let value=control.value; if(field==='duration') value=Number(value); node[field]=value; if(field==='mode'){ const list=modelsFor(node); if(!list.some(item=>item.id===node.model)) node.model=list[0].id; } rerender(); });
            if(control.dataset.linkfoxField==='prompt') control.addEventListener('input',e=>{e.stopPropagation();node.prompt=control.value;options.onChange?.(node,{render:false});});
        });
        root.querySelectorAll('[data-linkfox-toggle]').forEach(button=>button.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();const field=button.dataset.linkfoxToggle;if(button.disabled)return;if(field==='camera')node.camera=node.camera==='multi'?'single':'multi';else node[field]=!node[field];rerender();}));
        root.querySelector('[data-linkfox-action="run"]')?.addEventListener('click',e=>{e.preventDefault();e.stopPropagation();options.run?.(node);});
        const refs=options.refs?.(node)||[]; const summary=root.querySelector('[data-linkfox-input-summary]'); if(summary) summary.textContent=refs.length?`已连接 ${refs.length} 张图片（模型上限 ${modelFor(node).maxImages} 张）`:'等待连接图片…';
    }
    function normalizeUnified(node){
        if(node.model==='可灵2.6') node.linkfoxMode='first_last_frame';
        else if(!MODELS[node.linkfoxMode || 'reference']?.some(model=>model.id===node.model)) node.linkfoxMode='reference';
        const view={...node,mode:node.linkfoxMode || 'reference',voice:node.generateAudio};
        const spec=modelFor(view);
        if(!spec.durations.includes(Number(view.duration))) view.duration=spec.durations.reduce((best,value)=>Math.abs(value-Number(view.duration || 5))<Math.abs(best-Number(view.duration || 5))?value:best);
        if(view.resolution && !spec.resolutions.includes(view.resolution)) view.resolution=spec.resolutions.at(-1) || '';
        normalizeSettings(view);
        if(view.model==='海螺2.3' && view.resolution==='1080p') view.duration=6;
        if(view.model==='可灵2.6' && view.resolution==='720p') view.voice=false;
        Object.assign(node,{model:view.model,duration:view.duration,resolution:view.resolution,
            aspectRatio:view.aspectRatio,generateAudio:view.voice,useFrameRoles:false});
        return view;
    }
    function unifiedSettingsHtml(node){
        const view=normalizeUnified(node), spec=modelFor(view);
        const labels={reference:'参考图',first_last_frame:'首尾帧',single:'单镜头',multi:'多镜头',adaptive:'自适应'};
        const field=(key,label,values,value)=>`<label class="field"><div class="setting-title">${label}</div><select class="select-lite" data-linkfox-unified="${key}">${values.map(item=>`<option value="${esc(item)}" ${String(item)===String(value)?'selected':''}>${esc(labels[item] || item || '按模型')}</option>`).join('')}</select></label>`;
        const modes=MODELS.first_last_frame.some(m=>m.id===node.model)?['reference','first_last_frame']:['reference'];
        if(node.model==='可灵2.6') modes.splice(0,1);
        return `<div class="linkfox-unified-settings">${progressHtml(node)}<div class="gen-settings-row">${field('linkfoxMode','模式',modes,view.mode)}${field('duration','秒',spec.durations,node.duration)}</div>
            <div class="gen-settings-row">${field('resolution','分辨率',spec.resolutions.length?spec.resolutions:[''],node.resolution)}${field('aspectRatio','画幅',spec.ratios.length?spec.ratios:[''],node.aspectRatio)}</div>
            <div class="gen-settings-row"><label class="field linkfox-audio-toggle"><input type="checkbox" data-linkfox-unified="generateAudio" ${node.generateAudio?'checked':''} ${spec.voice!=='optional' || (node.model==='可灵2.6' && node.resolution==='720p')?'disabled':''}>声音${spec.voice!=='optional'?'（模型固定）':''}</label>${field('linkfoxCamera','镜头', ['single','multi'],node.linkfoxCamera || 'single')}</div>
            <div class="muted-note">LinkFox · ${view.mode==='first_last_frame'?'首帧＋可选尾帧':`最多 ${spec.maxImages} 张参考图`}。源视频会先解析动作与镜头；无图片时提取起始画面。${node.model==='可灵2.6'?'尾帧要求1080p并关闭声音。':''}</div></div>`;
    }
    function bindUnified(root,node,onChange){
        root.querySelectorAll('[data-linkfox-unified]').forEach(control=>{
            control.addEventListener('mousedown',event=>event.stopPropagation());
            control.addEventListener('change',event=>{
                event.stopPropagation();const key=control.dataset.linkfoxUnified;
                node[key]=control.type==='checkbox'?control.checked:key==='duration'?Number(control.value):control.value;
                normalizeUnified(node);onChange?.();
            });
        });
    }
    window.CanvasLinkfoxVideo={TYPE,isType:type=>type===TYPE,createNode,bodyHtml,bind,buildRequest,modelsFor,modelFor,inputPorts,inputRefs,normalizeUnified,unifiedSettingsHtml,bindUnified,generate,taskPayload,rememberVideoPromptResult};
})();
