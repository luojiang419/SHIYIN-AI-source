(function(){
    const TYPE='linkfox-video';
    const MODELS={
        reference:[
            {id:'seedance2.0',label:'Seedance 2.0',durations:[5,10,15],resolutions:['480p','720p','1080p'],ratios:['16:9','9:16','adaptive'],voice:'optional',maxImages:9},
            {id:'seedance2.0fast',label:'Seedance 2.0 Fast',durations:[5,10,15],resolutions:['480p','720p'],ratios:['16:9','9:16'],voice:'optional',maxImages:9},
            {id:'可灵Omni',label:'可灵 Omni',durations:[5,10,15],resolutions:['720p','1080p'],ratios:['16:9','9:16','1:1'],voice:'fixed_false',maxImages:7},
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
    function createNode(point, extra={}){
        const mode=extra.mode || 'reference';
        const model=extra.model || MODELS[mode][0].id;
        return {id:'linkfox-video',type:TYPE,specialType:TYPE,title:'LinkFox 视频生成',x:point?.x||0,y:point?.y||0,w:480,h:0,mode,model,duration:5,resolution:'720p',aspectRatio:'16:9',voice:true,promptOptimizer:false,isPro:false,camera:'single',prompt:'',lastFrameImageUrl:'',inputs:[],images:[],running:false,runError:'',...extra};
    }
    function options(list, selected, emptyLabel){ return (list||[]).map(value=>{ const empty=!value && emptyLabel; const valueText=empty?'':value; const label=empty?emptyLabel:value; return `<option value="${esc(valueText)}" ${String(valueText)===String(selected)?'selected':''}>${esc(label)}</option>`; }).join(''); }
    function bodyHtml(node){
        const mode=node.mode==='first_last_frame'?'first_last_frame':'reference';
        const model=modelFor(node); const models=modelsFor(node);
        if(!models.some(item=>item.id===node.model)) node.model=models[0].id;
        const selectedModel=modelFor(node);
        const durations=selectedModel.durations; const resolutions=selectedModel.resolutions.length?selectedModel.resolutions:['']; const ratios=selectedModel.ratios.length?selectedModel.ratios:[''];
        const voiceFixed=selectedModel.voice!=='optional';
        return `<div class="linkfox-video-body">
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
                <button type="button" class="setting-check ${node.promptOptimizer?'active':''}" data-linkfox-toggle="promptOptimizer"><span class="check-dot"></span>提示词优化</button>
                <button type="button" class="setting-check ${node.isPro?'active':''}" data-linkfox-toggle="isPro"><span class="check-dot"></span>Pro 模式</button>
                <button type="button" class="setting-check ${node.camera==='multi'?'active':''}" data-linkfox-toggle="camera"><span class="check-dot"></span>多段运镜</button>
            </div>
            ${mode==='first_last_frame'?'<div class="linkfox-frame-note">首帧和尾帧请通过两个输入端口连接；可灵 2.6 尾帧仅支持 1080p 且关闭声音。</div>':'<div class="linkfox-frame-note">参考图模式支持多张图片，数量上限随模型变化。</div>'}
            <div class="linkfox-video-input-summary" data-linkfox-input-summary>等待连接图片…</div>
            <button type="button" class="gen-btn linkfox-video-run" data-linkfox-action="run" ${node.running?'disabled':''}>${node.running?'生成中…':'生成 LinkFox 视频'}</button>
            ${node.runError?`<div class="linkfox-video-error">${esc(node.runError)}</div>`:''}
        </div>`;
    }
    function buildRequest(node, refs){
        const urls=(refs||[]).map(ref=>typeof ref==='string'?ref:ref?.url).filter(Boolean);
        const payload={entry:'img2video',mode:node.mode||'reference',imageList:urls,videoType:node.model,videoTime:Number(node.duration||5),prompt:node.prompt||'',promptOptimizer:Boolean(node.promptOptimizer),isPro:Boolean(node.isPro),voice:Boolean(node.voice),camera:node.camera||'single',aspectRatio:node.aspectRatio||'',resolution:node.resolution||''};
        if(payload.mode==='first_last_frame'){ payload.imageUrl=urls[0]||''; payload.lastFrameImageUrl=urls[1]||node.lastFrameImageUrl||''; }
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
    window.CanvasLinkfoxVideo={TYPE,isType:type=>type===TYPE,createNode,bodyHtml,bind,buildRequest,modelsFor,modelFor};
})();
