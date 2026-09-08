(function(){
    'use strict';
    const PREPARE='film-prepare-assets', CONFIRM='film-confirm-shots';
    const TITLES={[PREPARE]:'准备资产',[CONFIRM]:'确认镜头'};
    const active=new Map();
    const hydrated=new WeakSet();
    const initialized=new WeakSet();
    const reconnects=new Map();
    const resumedJobs=new Set();
    const jobActions=new Set(['analyze','depth','match','replicate','build-prompts','generate','import-asset','bind-asset','export-timeline','export-video']);
    let context=null;
    let fullscreen=null, fullscreenRefreshPending=false;
    const scrollPositions=new WeakMap();
    const actionQueues=new WeakMap();
    const controlKey=el=>JSON.stringify([el.tagName,el.type,Object.entries(el.dataset).filter(([key])=>key!=='wfDirty').sort()]);
    const esc=value=>String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    function incoming(node,nodes,edges,type){ return edges.filter(e=>e.to===node.id).map(e=>nodes.find(n=>n.id===e.from)).filter(n=>n && (!type || n.type===type)); }
    function isStep(type){ return type===PREPARE || type===CONFIRM; }
    function isList(node,nodes=context?.nodes || [],edges=context?.connections || []){ return node?.type==='film-video' && incoming(node,nodes,edges,CONFIRM).length===1; }
    function handles(node,nodes,edges){ return isStep(node?.type) || isList(node,nodes,edges); }
    function prepareFor(node,nodes,edges){
        if(node.type===PREPARE) return node;
        const parent=incoming(node,nodes,edges,node.type==='film-video'?CONFIRM:PREPARE);
        return parent.length===1 ? (parent[0].type===PREPARE ? parent[0] : prepareFor(parent[0],nodes,edges)) : null;
    }
    function framesFor(group,nodes,seen=new Set()){
        if(!group || seen.has(group.id)) return [];
        seen.add(group.id);
        return (group.items || []).flatMap(id=>{
            const n=nodes.find(item=>item.id===id);
            return n?.type==='group' ? framesFor(n,nodes,seen) : n?.type==='image' && n.url && (!n.mediaKind || n.mediaKind==='image') ? [n] : [];
        });
    }
    function sourceFor(node,nodes,edges){
        const prepare=prepareFor(node,nodes,edges);
        if(!prepare) return null;
        const sources=incoming(prepare,nodes,edges,'group').filter(n=>!n.workflowFunctionGroup);
        if(sources.length!==1) return null;
        const group=sources[0], frames=framesFor(group,nodes);
        return {prepare,group,frames,fingerprint:JSON.stringify([group.id,frames.map(n=>[n.id,n.url,n.bridgeCaption || ''])])};
    }
    function canConnect(from,to,role,nodes,edges){
        if(to.type===PREPARE) return from.type==='group' && !from.workflowFunctionGroup && (!role || role==='workflow');
        if(to.type===CONFIRM) return from.type===PREPARE && (!role || role==='workflow');
        if(from.type===CONFIRM && to.type==='film-video') return !role || role==='workflow' || role==='storyboard';
        if(isStep(from.type)) return false;
        if(to.type==='film-video' && isList(to,nodes,edges)) return false;
        return null;
    }
    function ports(node){
        return handles(node) ? [{id:'workflow',role:'workflow',label:node.type===PREPARE?'图片组':node.type===CONFIRM?'准备资产':'确认镜头',title:'工作流数据输入'}] : null;
    }
    function graph(ctx){
        const keys=['id','type','items','url','mediaKind','name','title','bridgeFrameStableId','bridgeSourceAssetId','bridgeCaption','bridgeBoardId','bridgeBoardName','bridgeProjectId','workflowFunctionGroup','workflowProjectId','workflowScriptId','workflowSourceKey'];
        return {nodes:ctx.nodes.map(n=>Object.fromEntries(keys.filter(k=>n[k]!==undefined).map(k=>[k,n[k]]))),connections:ctx.connections};
    }
    function notify(ids=[]){ context?.changed?.(ids); scheduleFullscreenRefresh(); }
    function scheduleFullscreenRefresh(){
        if(!fullscreen || fullscreenRefreshPending) return;
        fullscreenRefreshPending=true;
        queueMicrotask(()=>{fullscreenRefreshPending=false;refreshFullscreen();});
    }
    function closeFullscreen(){
        if(!fullscreen) return;
        const {dialog,node}=fullscreen;
        // 退出前提交仍在输入中的字段，沿用原有 change 保存路径。
        dialog.querySelectorAll('[data-wf-dirty]').forEach(el=>el.dispatchEvent(new Event('change',{bubbles:true})));
        fullscreen=null;
        dialog.close(); dialog.remove();
        context?.changed?.([node.id]);
        document.querySelector(`.node[data-id="${CSS.escape(node.id)}"] [data-wf-fullscreen]`)?.focus({preventScroll:true});
    }
    function refreshFullscreen(){
        if(!fullscreen) return;
        const {dialog,node,canvasId}=fullscreen;
        if(context?.canvasId!==canvasId || !context.nodes.includes(node)) {closeFullscreen();return;}
        const host=dialog.querySelector('.wf-fullscreen-body');
        const old=host.querySelector('.film-workflow-panel');
        const controls=old ? [...old.querySelectorAll('input,select,textarea')] : [];
        const drafts=controls.map(el=>({key:controlKey(el),value:el.value,checked:el.checked,dirty:el.hasAttribute('data-wf-dirty'),local:el.matches('[data-wf-asset-type],[data-wf-format]'),focused:el===document.activeElement,start:el.selectionStart,end:el.selectionEnd})).filter(state=>state.dirty || state.focused || state.local);
        old?.querySelectorAll('.wf-shot-scroll,.wf-parameters').forEach(el=>scrollPositions.set(node,{...(scrollPositions.get(node) || {}),[el.className]:el.scrollTop}));
        const opened=old ? [...old.querySelectorAll('details')].map(el=>el.open) : [];
        host.innerHTML=bodyHtml(node);
        bind(host,node);
        const next=new Map([...host.querySelectorAll('input,select,textarea')].map(el=>[controlKey(el),el]));
        for(const state of drafts){
            const el=next.get(state.key); if(!el || el.type==='file') continue;
            if(state.dirty || state.local){el.value=state.value;el.checked=state.checked;}
            if(state.dirty)el.dataset.wfDirty='true';
            if(state.focused && !el.disabled){el.focus({preventScroll:true});if(state.start!=null)el.setSelectionRange(state.start,state.end);}
        }
        host.querySelectorAll('details').forEach((el,index)=>{el.open=opened[index] || false;});
    }
    function openFullscreen(node){
        if(!isStep(node.type)) return;
        closeFullscreen();
        const dialog=document.createElement('dialog');
        dialog.className='wf-fullscreen';
        dialog.setAttribute('aria-label',`${TITLES[node.type]} · 全屏编辑`);
        dialog.innerHTML=`<header class="wf-fullscreen-head"><h2>${TITLES[node.type]} <small>全屏编辑</small></h2><button type="button" data-wf-close>退出全屏 <small>Esc</small></button></header><div class="wf-fullscreen-body"></div>`;
        document.body.append(dialog);
        fullscreen={dialog,node,canvasId:context?.canvasId};
        dialog.querySelector('[data-wf-close]').addEventListener('click',closeFullscreen);
        dialog.addEventListener('cancel',event=>{event.preventDefault();closeFullscreen();});
        ['keydown','keyup','wheel','pointerdown','mousedown','click','dblclick','drop','dragover'].forEach(type=>dialog.addEventListener(type,event=>event.stopPropagation()));
        refreshFullscreen();dialog.showModal();
        dialog.querySelector('[data-wf-close]').focus();
    }
    function sync(ctx){
        context=ctx;
        scheduleFullscreenRefresh();
        for(const [node,retry] of reconnects){
            if(retry.canvasId!==ctx.canvasId || !ctx.nodes.includes(node) || sourceFor(node,ctx.nodes,ctx.connections)?.fingerprint!==retry.fingerprint){
                clearTimeout(retry.timer); reconnects.delete(node);
            }
        }
        if(!ctx.nodes.some(n=>isStep(n.type) || n.workflowList)) return;
        const changed=[];
        const byId=new Map(ctx.nodes.map(n=>[n.id,n]));
        for(const edge of ctx.connections){
            const from=byId.get(edge.from)?.type,to=byId.get(edge.to)?.type;
            if(((from==='group' && to===PREPARE) || (from===PREPARE && to===CONFIRM) || (from===CONFIRM && to==='film-video')) && edge.inputRole!=='workflow'){
                edge.inputRole='workflow'; ctx.connectionsChanged?.();
            }
        }
        for(const node of ctx.nodes.filter(n=>n.type===PREPARE)){
            if(!initialized.has(node)){ initialized.add(node); delete node.workflowAttempt; }
            if(!active.has(node.id)) node.workflowBusy=false;
            const source=sourceFor(node,ctx.nodes,ctx.connections);
            if(!source?.frames.length) continue;
            if(node.workflowGroupId && node.workflowGroupId!==source.group.id){
                node.workflowSessions ||= {};
                node.workflowSessions[node.workflowGroupId]={scriptId:node.workflowScriptId,projectId:node.workflowProjectId,snapshot:node.workflowSnapshot,fingerprint:node.workflowFingerprint};
                const saved=node.workflowSessions[source.group.id] || {};
                node.workflowScriptId=saved.scriptId || ''; node.workflowSnapshot=saved.snapshot || null; node.workflowFingerprint=saved.fingerprint || '';
                node.workflowProjectId=saved.projectId || source.group.bridgeProjectId || ''; delete node.workflowAttempt;
            }
            node.workflowGroupId=source.group.id;
            node.workflowSourceKeys ||= {};
            node.workflowSourceKey=node.workflowSourceKeys[source.group.id] ||= `${ctx.canvasId}:${node.id}:${source.group.id}`;
            if(node.workflowFingerprint!==source.fingerprint && !active.has(node.id) && node.workflowAttempt!==source.fingerprint){
                node.workflowAttempt=source.fingerprint;
                // 接线只建立/同步脚本，绝不执行解析或付费生成。
                queueMicrotask(()=>request(node,'sync').catch(()=>{}));
            } else if(node.workflowScriptId && node.workflowFingerprint===source.fingerprint && !hydrated.has(node)){
                hydrated.add(node);
                queueMicrotask(()=>request(node,'snapshot').catch(()=>{}));
            }
        }
        for(const node of ctx.nodes.filter(n=>n.type===CONFIRM || n.type==='film-video')){
            if(!active.has(node.id)) node.workflowBusy=false;
            const list=isList(node,ctx.nodes,ctx.connections);
            if(node.type==='film-video' && node.workflowList!==list && (list || node.workflowList===true)){
                if(list){ node.workflowSingleWidth=node.w; node.workflowSingleOutputs=node.generatedOutputs || []; node.w=Math.max(960,node.w || 0); }
                else { node.w=node.workflowSingleWidth || 520; node.generatedOutputs=node.workflowSingleOutputs || []; }
                node.workflowList=list; changed.push(node.id);
            }
            if(node.type==='film-video' && !list) continue;
            const source=sourceFor(node,ctx.nodes,ctx.connections);
            const parent=source?.prepare;
            if(node.workflowSnapshot!==parent?.workflowSnapshot || node.workflowScriptId!==parent?.workflowScriptId){
                node.workflowSnapshot=parent?.workflowSnapshot || null;
                node.workflowScriptId=parent?.workflowScriptId || '';
                node.workflowProjectId=parent?.workflowProjectId || '';
                changed.push(node.id);
            }
        }
        if(changed.length) ctx.invalidate?.(changed);
        for(const node of ctx.nodes){
            if(!handles(node) || !node.workflowJob || active.has(node.id)) continue;
            const key=`${ctx.canvasId}:${node.id}:${node.workflowJob.id}`;
            const source=sourceFor(node,ctx.nodes,ctx.connections);
            if(source?.prepare.workflowScriptId!==node.workflowJob.scriptId || resumedJobs.has(key)) continue;
            resumedJobs.add(key);
            queueMicrotask(()=>request(node,'job',{job_id:node.workflowJob?.id}).catch(()=>{}));
        }
    }
    async function request(node,action,extra={}){
        const ctx=context;
        if(!ctx?.canvasId || (active.has(node.id) && action!=='cancel-task')) return;
        const source=sourceFor(node,ctx.nodes,ctx.connections);
        if(!source?.frames.length) throw new Error('请先连接图片组 → 准备资产 → 确认镜头');
        if(action!=='sync' && !source.prepare.workflowScriptId) throw new Error('脚本正在建立，请稍后再操作');
        const previousRetry=reconnects.get(node);
        if(previousRetry){ clearTimeout(previousRetry.timer); reconnects.delete(node); }
        const sourceFingerprint=source.fingerprint, requestId=globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
        const payload={canvas_id:ctx.canvasId,node_id:node.id,action,request_id:requestId,graph:graph(ctx),...extra};
        const activeKey=action==='cancel-task'?`${node.id}:cancel`:node.id;
        // 先保存幂等请求 ID；提交响应丢失或刷新页面后，可查询同一任务，避免盲目重复提交。
        if(jobActions.has(action)) node.workflowJob={id:requestId,scriptId:source.prepare.workflowScriptId};
        active.set(activeKey,requestId); node.workflowError=''; node.workflowBusy=true; notify([node.id]);
        const current=()=>context?.canvasId===ctx.canvasId && context.nodes.includes(node) && sourceFor(node,context.nodes,context.connections)?.fingerprint===sourceFingerprint;
        const send=async body=>{
            const response=await fetch('/api/canvas-film-workflow',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
            const result=await response.json();
            if(!response.ok || !result.ok){ const error=new Error(result.detail || 'film 工作流请求失败');error.workflowRejected=true;error.retryable=result.retryable===true;throw error; }
            return result;
        };
        const apply=result=>{
            if(!current()) return;
            if(result.snapshot){
                source.prepare.workflowScriptId=result.snapshot.scriptId;
                source.prepare.workflowSnapshot=result.snapshot;
                source.prepare.workflowProjectId=result.project_id || source.prepare.workflowProjectId;
                source.prepare.workflowFingerprint=sourceFingerprint;
                payload.graph=graph(context);
                // 视频输出落盘到 SHIYIN 媒体目录，可保存工程、回传和离线预览。
                for(const target of context.nodes.filter(n=>isList(n) && prepareFor(n,context.nodes,context.connections)===source.prepare)){
                    target.generatedOutputs=(result.snapshot.tasks || []).filter(t=>t.url).map(t=>({url:t.url,kind:'video',mediaKind:'video',name:`镜头视频 ${t.shotId}`,workflowTaskId:t.id}));
                }
                sync(context); notify([node.id,source.prepare.id,...context.nodes.filter(n=>handles(n)).map(n=>n.id)]);
            }
        };
        try {
            let result=await send(payload); apply(result);
            if(jobActions.has(action) && !result.job) delete node.workflowJob;
            if(result.job){
                node.workflowJob={id:result.job.id,scriptId:source.prepare.workflowScriptId};
                notify([node.id]);
                while(result.job.status==='running'){
                    await new Promise(resolve=>setTimeout(resolve,1500));
                    result=await send({...payload,action:'job',job_id:node.workflowJob.id});
                    apply(result);
                    if(!current()) break;
                }
                if(result.job.status!=='running') delete node.workflowJob;
                if(result.job.status==='failed') throw new Error(result.job.error || '任务失败');
            }
            return result;
        } catch(error){
            if(current()){
                node.workflowError=error.message;
                if(error.workflowRejected && !error.retryable && (jobActions.has(action) || error.message.includes('任务已失效'))) delete node.workflowJob;
                if((action==='sync' || action==='snapshot') && (error.retryable || !error.workflowRejected)){
                    const delay=Math.min(30000,(previousRetry?.delay || 1500)*2);
                    const retry={canvasId:ctx.canvasId,fingerprint:sourceFingerprint,delay};
                    retry.timer=setTimeout(()=>{
                        if(reconnects.get(node)!==retry) return;
                        if(current()) request(node,action).catch(()=>{});
                        else reconnects.delete(node);
                    },delay);
                    reconnects.set(node,retry);
                }
            }
            throw error;
        }
        finally {
            active.delete(activeKey); node.workflowBusy=active.has(node.id);
            if(context?.canvasId===ctx.canvasId && context.nodes.includes(node)){sync(context);notify([node.id]);}
        }
    }
    function select(label,key,values,current){
        const options=values.map(v=>typeof v==='object'?v:{id:v,label:v});
        if(current!==undefined && current!=='' && !options.some(v=>String(v.id)===String(current))) options.unshift({id:current,label:current});
        return `<label>${esc(label)}<select data-wf-param="${key}">${options.map(v=>`<option value="${esc(v.id)}" ${String(v.id)===String(current)?'selected':''}>${esc(v.label)}</option>`).join('')}</select></label>`;
    }
    const text=(label,key,value,rows=2)=>`<label>${esc(label)}<textarea rows="${rows}" data-wf-param="${key}">${esc(value)}</textarea></label>`;
    const check=(label,key,value)=>`<label class="wf-check"><input type="checkbox" data-wf-param="${key}" ${value?'checked':''}>${esc(label)}</label>`;
    const button=(action,label,shotId='',attrs='')=>`<button type="button" data-wf-action="${action}" ${shotId?`data-shot="${esc(shotId)}"`:''} ${attrs}>${esc(label)}</button>`;
    function paramsHtml(node,s){
        const p=s.parameters || {}, o=s.options || {};
        const settings=o.settings || {};
        const modelSelection=(label,key,options,current)=>options?.length?select(label,key,options.map(v=>({id:v.id,label:v.name})),current).replace('data-wf-param','data-wf-setting'):'';
        const visionSelection=modelSelection('解析模型','visionModelId',settings.visionModels,settings.selectedVisionModelId);
        if(node.type===PREPARE) return `${visionSelection}${select('复刻模式','generationMode',[{id:'quick',label:'快速多图复刻'},{id:'precise',label:'精确匹配资产'}],p.generationMode)}
            ${select('图片模型','model',o.models || [],p.model)}${select('原帧类型','sourceFrameMode',[{id:'colorReference',label:'彩色原帧'},{id:'lineArt',label:'黑白线稿'}],p.sourceFrameMode)}
            ${check('跟随原帧画幅','inheritSourceAspectRatio',p.inheritSourceAspectRatio)}${select('画幅','aspectRatio',o.aspectRatios || [],p.aspectRatio)}
            ${select('分辨率','imageSize',o.imageSizes || [],p.imageSize)}${select('质量','quality',o.qualities || [],p.quality)}
            ${check('多视图增强','multiViewEnhancementEnabled',p.multiViewEnhancementEnabled)}${p.sourceFrameMode==='lineArt'?select('全片色彩预设','colorStylePresetId',o.colorStyles || [],p.colorStylePresetId):''}
            ${text('复刻补充要求','replicationInstructions',p.replicationInstructions,4)}<h4>资产库</h4>
            <label>导入类型<select data-wf-asset-type>${[['character','演员'],['product','服装 / 产品'],['scene','场景'],['prop','道具'],['reference','参考图']].map(([id,label])=>`<option value="${id}">${label}</option>`).join('')}</select></label>
            <label class="wf-upload">导入资产<input type="file" accept="image/*" data-wf-upload></label>
            ${button('open-assets','打开资产目录')}<div class="wf-assets">${(s.assets || []).map(a=>`<div class="wf-asset" draggable="true" data-wf-asset="${esc(a.id)}"><img loading="lazy" src="${esc(a.url)}" alt=""><span>${esc(a.name)}</span><details><summary>编辑资产</summary><label>名称<input data-wf-asset-field="name" data-asset="${esc(a.id)}" value="${esc(a.name)}"></label><label>描述<textarea data-wf-asset-field="description" data-asset="${esc(a.id)}">${esc(a.description)}</textarea></label>${button('delete-asset','删除资产','',`data-asset="${esc(a.id)}"`)}</details></div>`).join('') || '<p>暂无资产，导入后可拖到镜头。</p>'}</div>`;
        if(node.type===CONFIRM) return `${visionSelection}${check('自由创作','freeCreationEnabled',p.freeCreationEnabled)}${text('全片风格','globalStyle',p.globalStyle,3)}${text('约束','constraints',p.constraints,3)}
            ${p.freeCreationEnabled?text('故事内容','freeCreationStoryOverride',p.freeCreationStoryOverride || s.story,9):`<h4>故事内容</h4><div class="wf-story">${esc(s.story || (s.shots || []).map(shot=>shot.content).join('\n'))}</div>`}
            <label>提示词格式<select data-wf-format>${['sd2','kling','h3'].map(v=>`<option value="${v}">${v==='sd2'?'Seedance':v==='kling'?'可灵':'MiniMax H3'}</option>`).join('')}</select></label>
            ${button('prompt-format','应用提示词格式')}<p>按镜头选择“分组起点 / 终点”组合连续镜头。</p>`;
        const video=o.video;
        const videoFields=video?`${modelSelection('视频平台 / 接口','videoGenerationModelId',settings.videoGenerationModels,settings.selectedVideoGenerationModelId)}
            ${select('视频模型','model',(video.models || []).map(m=>({id:m.id,label:m.name})),video.selectedModelId).replace('data-wf-param','data-wf-video-model')}
            ${(video.parameters || []).map(field=>field.options?.length ? select(field.label,field.key,field.options.map(v=>({id:v.value,label:v.label})),field.value).replace('data-wf-param','data-wf-video-param'):
                `<label>${esc(field.label)}<input type="${field.component==='number'?'number':'text'}" data-wf-video-param="${esc(field.key)}" value="${esc(field.value)}" ${field.min!=null?`min="${field.min}"`:''} ${field.max!=null?`max="${field.max}"`:''} ${field.step!=null?`step="${field.step}"`:''}></label>`).join('')}`:
            `${select('画幅','videoAspectRatio',['16:9','9:16','1:1','4:3','3:4'],p.videoAspectRatio)}
            ${select('分辨率','videoResolution',['720p','1080p',p.videoResolution].filter(Boolean),p.videoResolution)}
            <label>采样步数<input type="number" min="1" max="100" data-wf-param="videoSteps" value="${esc(p.videoSteps || 12)}"></label>`;
        return `<p>${esc(o.videoBackend || 'film 视频生成')}</p><small>${esc(video?.backend?.message || o.videoSummary || '')}</small>${videoFields}
            <h4>作品管理</h4><div class="wf-mini-actions">${button('export-timeline','导出时间线')}${button('export-video','导出成片')}${button('open-output','打开作品目录')}</div><div class="wf-works">${(s.tasks || []).map(t=>`<div class="wf-work" data-wf-task="${esc(t.id)}"><span>${esc(t.status)}</span>${t.url?`<video controls preload="none" src="${esc(t.url)}"></video><a href="${esc(t.url)}" download>下载视频</a><details><summary>剪辑入点 / 出点</summary><label>入点（秒）<input type="number" min="0" step="0.1" data-wf-trim="in" value="${Number(t.inMs || 0)/1000}"></label><label>出点（秒）<input type="number" min="0" step="0.1" data-wf-trim="out" value="${Number(t.outMs || t.sourceDurationMs || Number(t.duration || 5)*1000)/1000}"></label>${button('trim-task','保存剪辑范围','',`data-task="${esc(t.id)}"`)}</details>`:''}${t.error?`<p class="wf-error">${esc(t.error)}</p>`:''}
            ${button(['running','queued','submitting'].includes(t.status)?'cancel-task':'delete-task',['running','queued','submitting'].includes(t.status)?'取消任务':'删除作品','',`data-task="${esc(t.id)}"`)}</div>`).join('') || '<p>生成完成后在此管理作品。</p>'}</div>`;
    }
    function shotsHtml(node,s){
        const all=node.type==='film-video' && s.groups?.length ? (s.shots || []).filter(shot=>s.groups.some(group=>group.id===shot.id)) : s.shots || [];
        const start=Math.max(0,Number(node.workflowPage)||0)*12, shots=all.slice(start,start+12);
        if(!all.length) return '<div class="wf-empty">连接图片组后自动建立拍摄脚本。<br>film 需运行并打开源项目。</div>';
        return `<div class="wf-page">${button('previous','上一页')}<span>${Math.floor(start/12)+1} / ${Math.max(1,Math.ceil(all.length/12))} · ${all.length} 个镜头</span>${button('next','下一页')}</div>`+shots.map(shot=>{
            const id=esc(shot.id), guide=(s.guides || []).find(g=>g.shotId===shot.id);
            const tasks=(s.tasks || []).filter(t=>t.shotId===shot.id), task=tasks[0];
            const bound=(s.bindings || []).filter(b=>b.shotId===shot.id).map(b=>(s.boundAssets || []).find(a=>a.id===b.assetId)).filter(Boolean);
            const field=(label,key,value)=>`<label>${label}<textarea rows="2" data-wf-shot-field="${key}" data-shot="${id}">${esc(value)}</textarea></label>`;
            return `<article class="wf-shot" data-wf-shot="${id}"><header><strong>镜头 ${esc(shot.number)}</strong><label class="wf-check"><input type="checkbox" data-wf-confirm="${id}" ${shot.confirmed?'checked':''}>已确认</label></header>
                <div class="wf-shot-main"><div class="wf-frame"><img loading="lazy" src="${esc(shot.replica || shot.frame)}" alt="镜头 ${esc(shot.number)}">${shot.replica?'<small>准备后的分镜</small>':''}</div><div class="wf-shot-details">
                ${node.type===PREPARE?`<p>${esc(shot.content)}</p><div class="wf-mini-actions">${button('analyze','解析原帧',shot.id)}${button('depth','提取深度',shot.id)}${button('replicate','生成分镜',shot.id)}</div>
                    ${guide?.depth?`<img class="wf-depth" loading="lazy" src="${esc(guide.depth)}" alt="深度图">`:''}
                    ${guide?.error?`<p class="wf-error">${esc(guide.error)}</p>`:''}
                    ${(guide?.elements || []).map(element=>`<label class="wf-check"><input type="checkbox" data-wf-element="${esc(element.id)}" data-shot="${id}" ${element.selected?'checked':''}>${esc(element.label || element.name || element.description)}</label>`).join('')}
                    ${(guide?.subjects || []).map(subject=>`<label>${esc(subject.name || subject.label || subject.id)}<select data-wf-subject="${esc(subject.id)}" data-shot="${id}">${['undecided','keep','replace','remove'].map((v,i)=>`<option value="${v}" ${subject.decision===v?'selected':''}>${['待定','保留','替换','移除'][i]}</option>`).join('')}</select></label>`).join('')}
                    <div class="wf-bound">${bound.map(a=>`<span>${esc(a.name)}${button('unbind-asset','移除',shot.id,`data-asset="${esc(a.id)}"`)}</span>`).join('')}</div>
                    <select data-wf-binding="${id}"><option value="">选择资产绑定到镜头…</option>${(s.assets || []).map(a=>`<option value="${esc(a.id)}">${esc(a.name)}</option>`).join('')}</select><small>也可将右侧资产拖入此镜头</small>`:
                node.type===CONFIRM?`${field('镜头描述','content',shot.content)}${field('画面 / 动作','visual',shot.visual)}${field('提示词','prompt',shot.prompt)}<label>时长（秒）<input type="number" min="1" max="120" step="0.1" data-wf-shot-field="durationSeconds" data-shot="${id}" value="${esc(shot.durationSeconds)}"></label><div class="wf-mini-actions">${button('group-start','分组起点',shot.id)}${button('group-end','分组终点',shot.id)}${button('group-clear','取消分组',shot.id)}</div>`:
                `${field('视频提示词','videoPrompt',shot.draft || shot.prompt)}<span class="wf-task-status">${esc(task?.status || '待生成')}</span>${button('generate','生成此镜头',shot.id,shot.confirmed?'':'disabled')}${task?.url?`<video controls preload="none" src="${esc(task.url)}"></video>`:''}${task?.error?`<p class="wf-error">${esc(task.error)}</p>`:''}`}
                ${shot.replicaError?`<p class="wf-error">${esc(shot.replicaError)}</p>`:''}</div></div></article>`;
        }).join('');
    }
    function bodyHtml(node){
        const s=node.workflowSnapshot || {}, source=sourceFor(node,context?.nodes || [],context?.connections || []);
        return `<section class="film-workflow-panel" data-workflow-node="${esc(node.id)}"><div class="wf-status"><span>${esc(s.name || '影视制作工作流')}</span><span>${node.workflowBusy?'执行中…':source?.frames.length?'已连接':'等待连接'}</span></div>
            ${node.workflowError?`<div class="wf-error" role="alert">${esc(node.workflowError)}</div>`:''}
            <div class="wf-layout"><div class="wf-operations"><div class="wf-actions">${button('refresh','同步 / 刷新')}
            ${node.type===PREPARE?`${button('analyze','解析全部原帧')}${button('depth','提取全部深度')}${button('match','匹配资产')}${button('replicate','生成全部分镜')}`:node.type===CONFIRM?`${button('confirm','确认全部镜头')}${button('build-prompts','构建全部提示词')}`:button('generate','一键生成全部','','class="wf-primary"')}
            </div><div class="wf-shot-scroll">${shotsHtml(node,s)}</div></div><aside class="wf-parameters"><h4>参数与${node.type===PREPARE?'资产':node.type===CONFIRM?'故事':'作品'}</h4>${paramsHtml(node,s)}</aside></div>
            <footer>${esc(node.workflowBusy?'film 正在执行任务，结果将自动更新':s.message || '连接传递数据，点击按钮执行生成')}</footer></section>`;
    }
    function bind(root,node){
        const panel=root.querySelector('.film-workflow-panel'); if(!panel) return;
        if(isStep(node.type) && root.classList.contains('node')){
            const expand=document.createElement('button');
            expand.type='button';expand.dataset.wfFullscreen='';expand.className='wf-fullscreen-button';
            expand.textContent='全屏编辑';expand.setAttribute('aria-label',`${TITLES[node.type]}全屏编辑`);
            ['pointerdown','mousedown'].forEach(type=>expand.addEventListener(type,event=>event.stopPropagation()));
            expand.addEventListener('click',event=>{event.stopPropagation();openFullscreen(node);});
            root.querySelector('.node-head-actions')?.prepend(expand);
        }
        const inFullscreen=!!root.closest('.wf-fullscreen');
        const saved=scrollPositions.get(node) || {};
        panel.querySelectorAll('.wf-shot-scroll,.wf-parameters').forEach(el=>{
            const key=el.className;
            el.scrollTop=saved[key] || 0;
            el.addEventListener('scroll',()=>{
                if(fullscreen?.node===node && !inFullscreen) return;
                scrollPositions.set(node,{...(scrollPositions.get(node) || {}),[key]:el.scrollTop});
            },{passive:true});
        });
        panel.addEventListener('input',event=>{if(event.target.matches('input:not([type=file]),textarea,select'))event.target.dataset.wfDirty='true';});
        panel.addEventListener('change',event=>{delete event.target.dataset.wfDirty;},true);
        const run=(action,extra={})=>{
            // 生成类动作不能因连点排队重复消费；仅连续编辑需要串行保存。
            if(jobActions.has(action) && (active.has(node.id) || actionQueues.has(node))) return Promise.resolve();
            const canvasId=context?.canvasId;
            const execute=async()=>{
                while(action!=='cancel-task' && active.has(node.id)) await new Promise(resolve=>setTimeout(resolve,30));
                if(context?.canvasId!==canvasId || !context.nodes.includes(node)) return;
                return request(node,action,extra);
            };
            const pending=(action==='cancel-task'?execute():(actionQueues.get(node) || Promise.resolve()).then(execute))
                .catch(error=>{node.workflowError=error.message;notify([node.id]);});
            if(action!=='cancel-task'){
                actionQueues.set(node,pending);
                pending.finally(()=>{if(actionQueues.get(node)===pending)actionQueues.delete(node);});
            }
            return pending;
        };
        ['pointerdown','mousedown','dblclick','wheel'].forEach(type=>panel.addEventListener(type,event=>event.stopPropagation(),{passive:type==='wheel'}));
        panel.querySelectorAll('[data-wf-action]').forEach(control=>control.addEventListener('click',()=>{
            const action=control.dataset.wfAction;
            if(action==='previous' || action==='next'){
                const max=Math.max(0,Math.ceil((node.workflowSnapshot?.shots?.length || 0)/12)-1);
                node.workflowPage=Math.max(0,Math.min(max,(node.workflowPage || 0)+(action==='next'?1:-1)));
                scrollPositions.set(node,{...(scrollPositions.get(node) || {}),'wf-shot-scroll':0});
                panel.querySelector('.wf-shot-scroll').scrollTop=0; notify([node.id]); return;
            }
            const extra={shot_id:control.dataset.shot || ''};
            if(control.dataset.asset) extra.asset_id=control.dataset.asset;
            if(control.dataset.task) extra.task_id=control.dataset.task;
            if(['delete-asset','delete-task'].includes(action) && !window.confirm('删除后会同步更新 film 中的记录与文件。确认删除？')) return;
            if(action==='trim-task'){
                const task=control.closest('[data-wf-task]');
                extra.parameters={inMs:Math.round(Number(task.querySelector('[data-wf-trim="in"]').value)*1000),outMs:Math.round(Number(task.querySelector('[data-wf-trim="out"]').value)*1000)};
            }
            if(action==='prompt-format') extra.format=panel.querySelector('[data-wf-format]').value;
            if(action==='refresh'){
                const source=sourceFor(node,context.nodes,context.connections);
                if(node.workflowJob) { run('job',{job_id:node.workflowJob.id}); return; }
                run(source?.prepare.workflowScriptId && source.prepare.workflowFingerprint===source.fingerprint?'snapshot':'sync',extra);
            } else run(action,extra);
        }));
        panel.querySelectorAll('[data-wf-param]').forEach(control=>control.addEventListener('change',()=>run('parameters',{parameters:{[control.dataset.wfParam]:control.type==='checkbox'?control.checked:control.type==='number'?Number(control.value):control.value}})));
        panel.querySelectorAll('[data-wf-setting]').forEach(control=>control.addEventListener('change',()=>run('settings',{selection:{[control.dataset.wfSetting]:control.value}})));
        panel.querySelectorAll('[data-wf-video-param]').forEach(control=>control.addEventListener('change',()=>run('video-parameters',{parameters:{[control.dataset.wfVideoParam]:control.value}})));
        panel.querySelector('[data-wf-video-model]')?.addEventListener('change',event=>run('video-parameters',{model:event.target.value}));
        panel.querySelectorAll('[data-wf-shot-field]').forEach(control=>control.addEventListener('change',()=>{
            const key=control.dataset.wfShotField;
            run(key==='videoPrompt'?'video-prompt':'edit-shot',{shot_id:control.dataset.shot,...(key==='videoPrompt'?{prompt:control.value}:{parameters:{[key]:control.type==='number'?Number(control.value):control.value}})});
        }));
        panel.querySelectorAll('[data-wf-confirm]').forEach(control=>control.addEventListener('change',()=>run('confirm',{shot_id:control.dataset.wfConfirm,confirmed:control.checked})));
        panel.querySelectorAll('[data-wf-subject]').forEach(control=>control.addEventListener('change',()=>run('subject',{shot_id:control.dataset.shot,subject_id:control.dataset.wfSubject,decision:control.value})));
        panel.querySelectorAll('[data-wf-element]').forEach(control=>control.addEventListener('change',()=>run('preserved-element',{shot_id:control.dataset.shot,element_id:control.dataset.wfElement,selected:control.checked})));
        panel.querySelectorAll('[data-wf-asset-field]').forEach(control=>control.addEventListener('change',()=>run('edit-asset',{asset_id:control.dataset.asset,parameters:{[control.dataset.wfAssetField]:control.value}})));
        panel.querySelectorAll('[data-wf-binding]').forEach(control=>control.addEventListener('change',()=>{if(control.value)run('bind-asset',{shot_id:control.dataset.wfBinding,asset_id:control.value});}));
        panel.querySelectorAll('[data-wf-asset]').forEach(control=>control.addEventListener('dragstart',event=>{event.dataTransfer.setData('application/x-film-asset',control.dataset.wfAsset);event.stopPropagation();}));
        panel.querySelectorAll('[data-wf-shot]').forEach(control=>{
            control.addEventListener('dragover',event=>{event.preventDefault();event.stopPropagation();});
            control.addEventListener('drop',event=>{event.preventDefault();event.stopPropagation();const id=event.dataTransfer.getData('application/x-film-asset');if(id)run('bind-asset',{shot_id:control.dataset.wfShot,asset_id:id});});
        });
        panel.querySelector('[data-wf-upload]')?.addEventListener('change',async event=>{
            const file=event.target.files?.[0]; if(!file) return;
            try { const url=await context.upload(file); await run('import-asset',{asset_url:url,name:file.name,asset_type:panel.querySelector('[data-wf-asset-type]').value}); }
            catch(error){node.workflowError=error.message;notify([node.id]);}
        });
        if(node.workflowBusy) panel.querySelectorAll('button,input,select,textarea').forEach(el=>{el.disabled=el.dataset.wfAction!=='cancel-task';});
    }
    window.CanvasFilmWorkflow={PREPARE,CONFIRM,isStep,isList,handles,sourceFor,framesFor,canConnect,ports,sync,bodyHtml,bind,request,title:type=>TITLES[type] || '',size:type=>isStep(type)?{w:960,h:0}:null};
})();
