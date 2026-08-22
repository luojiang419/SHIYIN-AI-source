(function(){
    'use strict';

    const TYPES = ['film-storyboard','film-video'];
    const ROLE_ORDER = {
        'film-storyboard': ['actor','scene','sketch'],
        'film-video': ['storyboard','actor','outfit','prop'],
    };
    const TITLES = {
        'film-storyboard':'分镜合成',
        'film-video':'生成视频',
    };
    const SIZES = {
        'film-storyboard': {w:520,h:0},
        'film-video': {w:520,h:0},
    };
    const MODEL_RULES = {
        default: {id:'default', name:'通用', prefix:'图', template:'{ref}是{role}', maxImages:20},
        jimeng: {id:'jimeng', name:'即梦', prefix:'图', template:'{ref}是{role}', maxImages:12},
        kling: {id:'kling', name:'可灵', prefix:'图片', template:'{ref}对应{role}', maxImages:12},
        minimax: {id:'minimax', name:'MiniMax H3', prefix:'Picture ', template:'<Picture {index}> is {role}', maxImages:9},
    };

    function esc(value){
        return String(value == null ? '' : value)
            .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
            .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }
    function clamp(value,min,max){ return Math.max(min,Math.min(max,Number(value) || min)); }
    function isType(type){ return TYPES.includes(type); }
    function title(type){ return TITLES[type] || ''; }
    function size(type){ return SIZES[type] || {w:520,h:0}; }
    function isGenerator(type){ return isType(type); }
    function canOutput(type){ return isType(type); }

    function actorLabel(index, noun='演员'){
        return `${noun}${String.fromCharCode(65 + Math.max(0, Number(index) || 0))}`;
    }
    function normalize(node){
        if(!node || !isType(node.type)) return node;
        node.actorCount = clamp(node.actorCount || 1, 1, 8);
        node.prompt = String(node.prompt || '');
        node.running = Boolean(node.running);
        node.runError = String(node.runError || '');
        node.generatedOutputs = Array.isArray(node.generatedOutputs) ? node.generatedOutputs : [];
        node.visionProvider = String(node.visionProvider || '');
        node.visionModel = String(node.visionModel || '');
        if(node.type === 'film-storyboard'){
            node.aspectRatio = node.aspectRatio || '16:9';
            node.resolution = node.resolution || '2k';
            node.quality = node.quality || 'high';
            node.count = clamp(node.count || 1, 1, 4);
        } else {
            node.duration = clamp(node.duration || 5, 1, 60);
            node.aspectRatio = node.aspectRatio || '16:9';
            // 空值会触发部分平台的高分辨率默认值，影视节点默认锁定为 720P。
            node.resolution = String(node.resolution || '720p');
            node.apiProvider = String(node.apiProvider || '');
            node.model = String(node.model || '');
            node.enhancePrompt = node.enhancePrompt !== false;
            node.multimodal = Boolean(node.multimodal);
            node.useFrameRoles = Boolean(node.useFrameRoles);
        }
        return node;
    }
    function createNode(type, point={}, defaults={}){
        if(!isType(type)) return null;
        const node = normalize({
            id:'', type, x:Number(point.x || 0), y:Number(point.y || 0), actorCount:1,
            prompt:'', inputs:[], generatedOutputs:[], running:false, runError:'', ...defaults,
        });
        return node;
    }
    function effectiveActorCount(node){
        const explicit = clamp(node?.actorCount || 1, 1, 8);
        const inherited = clamp(node?.autoActorCount || 0, 0, 8);
        return Math.max(explicit, inherited);
    }
    function inputPorts(nodeOrType){
        const node = typeof nodeOrType === 'string' ? {type:nodeOrType,actorCount:1} : normalize(nodeOrType || {});
        const count = effectiveActorCount(node);
        if(node.type === 'film-storyboard'){
            return [
                ...Array.from({length:count}, (_,i) => ({role:`actor-${i}`,label:actorLabel(i,'演员'),title:`连接${actorLabel(i,'演员')}参考图`})),
                {role:'scene',label:'场景',title:'连接场景参考图'},
                {role:'sketch',label:'线稿分镜',title:'连接线稿分镜参考图'},
            ];
        }
        if(node.type === 'film-video'){
            return [
                {role:'storyboard',label:'分镜图',title:'连接分镜图或首帧参考'},
                ...Array.from({length:count}, (_,i) => [
                    {role:`actor-${i}`,label:actorLabel(i,'演员'),title:`连接${actorLabel(i,'演员')}主体参考图`},
                    {role:`outfit-${i}`,label:`服装${String.fromCharCode(65+i)}`,title:`连接${actorLabel(i,'演员')}服装参考图`},
                    {role:`prop-${i}`,label:`道具${String.fromCharCode(65+i)}`,title:`连接${actorLabel(i,'演员')}道具参考图`},
                ]).flat(),
            ];
        }
        return [];
    }
    function roleLabel(node, role){
        const match = String(role || '').match(/^(actor|outfit|prop)-(\d+)$/);
        if(match){
            const index = Number(match[2]);
            if(match[1] === 'actor') return actorLabel(index, node.type === 'film-video' ? '演员' : '模特');
            if(match[1] === 'outfit') return `服装${String.fromCharCode(65 + index)}`;
            return `道具${String.fromCharCode(65 + index)}`;
        }
        return node.type === 'film-storyboard'
            ? ({scene:'场景',sketch:'线稿分镜'}[role] || role)
            : ({storyboard:'分镜图'}[role] || role);
    }
    function modelRule(provider='', model=''){
        const text = `${provider} ${model}`.toLowerCase();
        if(text.includes('minimax') || text.includes('h3')) return MODEL_RULES.minimax;
        if(text.includes('kling') || text.includes('可灵')) return MODEL_RULES.kling;
        if(text.includes('jimeng') || text.includes('即梦') || text.includes('seedance')) return MODEL_RULES.jimeng;
        return MODEL_RULES.default;
    }
    function assetList(node, assets=[]){
        normalize(node);
        const refs = [];
        const byRole = new Map();
        (assets || []).forEach(item => {
            const role = String(item?.role || item?.inputRole || '');
            const list = byRole.get(role) || [];
            const ref = item?.ref || item;
            if(ref?.url) list.push({...ref, role});
            byRole.set(role, list);
        });
        inputPorts(node).forEach(port => {
            // 分镜合成可能一次返回多张图，但视频节点的“分镜图”输入只代表
            // 最近一次生成的最后一张分镜，避免把整组抽卡结果全部作为参考图提交。
            const roleRefs = port.role === 'storyboard'
                ? (byRole.get(port.role) || []).slice(-1)
                : (byRole.get(port.role) || []);
            roleRefs.forEach(ref => refs.push({...ref, inputRole:port.role, roleLabel:roleLabel(node, port.role)}));
        });
        return refs;
    }
    function mapping(node, assets=[], options={}){
        const rule = modelRule(node.apiProvider || options.provider, node.model || options.model);
        const refs = assetList(node, assets).slice(0, rule.maxImages);
        const lines = refs.map((ref,index) => {
            const n = index + 1;
            const refLabel = rule.id === 'minimax' ? `${n}` : `${rule.prefix}${n}`;
            return rule.template.replace('{index}',String(n)).replace('{ref}',refLabel).replace('{role}',ref.roleLabel || roleLabel(node,ref.inputRole));
        });
        return {rule, refs, lines, text:lines.join(rule.id === 'minimax' ? '; ' : '，')};
    }
    function buildPrompt(node, assets=[], options={}){
        const map = mapping(node, assets, options);
        const prompt = String(node.prompt || '').trim();
        const prefix = map.text ? `资产映射：${map.text}。` : '';
        return {prompt:[prefix,prompt].filter(Boolean).join('\n'), refs:map.refs, map};
    }
    function itemPreview(item){
        if(!item?.url) return '<i data-lucide="image"></i>';
        const url = esc(item.url);
        return `<img src="${url}" alt="" loading="lazy">`;
    }
    function mappingHtml(node, assets=[], options={}){
        const map = mapping(node, assets, options);
        if(!map.refs.length) return '<div class="film-empty-note">连接资产后会自动建立图像映射</div>';
        return `<div class="film-mapping-list">${map.refs.map(ref => `<span class="film-mapping-chip"><b>${esc(ref.roleLabel || '参考资产')}</b><i>${itemPreview(ref)}</i><em>${esc(ref.name || '已连接')}</em></span>`).join('')}</div>`;
    }
    function promptHtml(node){
        return `<label class="film-prompt-field"><span>生成需求</span><textarea data-film-field="prompt" rows="5" placeholder="输入镜头、动作、镜头运动、节奏和声音要求；输入 @ 可引用映射资产">${esc(node.prompt)}</textarea></label>`;
    }
    function inputSlotHtml(node, port, options={}){
        const assets = options.assets?.(node) || [];
        const count = assets.filter(item => String(item?.role || item?.inputRole || '') === port.role && item?.url).length;
        const connected = Boolean(count || options.connected?.(node, port.role));
        const state = connected ? '已连接' : '可选输入';
        const stateHtml = connected ? '<span class="film-input-status-dot" aria-hidden="true"></span>已连接' : state;
        return `<div class="film-input-row" data-input-role="${esc(port.role)}" data-port-index="${Number(options.index || 0)}"><span><i data-lucide="${connected ? 'circle-check' : 'circle-dashed'}"></i><strong>${esc(port.label)}</strong></span><b class="${connected ? 'has-input' : ''}">${stateHtml}</b></div>`;
    }
    function bodyHtml(node, options={}){
        normalize(node);
        const action = node.type === 'film-storyboard' ? '生成分镜图' : '生成视频';
        const parseText = node.type === 'film-storyboard' ? '解析画面' : '解析动作';
        const providerOptions = node.type === 'film-storyboard'
            ? (options.imageProviderOptions || options.providerOptions)?.(node) || ''
            : options.providerOptions?.(node) || '';
        const modelOptions = node.type === 'film-storyboard'
            ? (options.imageModelOptions || options.modelOptions)?.(node) || ''
            : options.modelOptions?.(node) || '';
        return `<div class="film-node-panel ${node.type}">
            <div class="film-node-toolbar"><span class="film-node-kicker">影视制作</span><button type="button" class="film-add-actor" data-film-action="add-actor"><i data-lucide="user-round-plus"></i>添加演员</button></div>
            <div class="film-input-list">${inputPorts(node).map((port,index) => inputSlotHtml(node, port, {...options,index})).join('')}</div>
            <div class="film-mapping-title">资产映射 <small data-film-model-rule></small></div><div data-film-mapping>${mappingHtml(node, options.assets?.(node) || [], options)}</div>
            ${promptHtml(node)}
            <div class="film-node-actions"><button type="button" class="film-parse-button" data-film-action="parse"><i data-lucide="scan-eye"></i>${parseText}</button><button type="button" class="film-run-button" data-film-action="run"><i data-lucide="${node.type === 'film-video' ? 'clapperboard' : 'wand-sparkles'}"></i>${node.running ? '生成中（可继续）' : action}</button></div>
            ${node.type === 'film-video' ? `<div class="film-video-settings"><select data-film-field="apiProvider">${providerOptions}</select><select data-film-field="model">${modelOptions}</select><label>时长<input data-film-field="duration" type="number" min="1" max="60" value="${node.duration}"></label><label>画幅<select data-film-field="aspectRatio"><option ${node.aspectRatio==='16:9'?'selected':''}>16:9</option><option ${node.aspectRatio==='9:16'?'selected':''}>9:16</option><option ${node.aspectRatio==='1:1'?'selected':''}>1:1</option><option ${node.aspectRatio==='4:3'?'selected':''}>4:3</option></select></label><label>分辨率<select data-film-field="resolution"><option value="480p" ${node.resolution==='480p'?'selected':''}>480P</option><option value="720p" ${node.resolution==='720p'?'selected':''}>720P（推荐）</option><option value="1080p" ${node.resolution==='1080p'?'selected':''}>1080P</option></select></label></div>` : `<div class="film-image-settings"><select data-film-field="apiProvider">${providerOptions}</select><select data-film-field="model">${modelOptions}</select><label>画幅<select data-film-field="aspectRatio"><option ${node.aspectRatio==='16:9'?'selected':''}>16:9</option><option ${node.aspectRatio==='9:16'?'selected':''}>9:16</option><option ${node.aspectRatio==='1:1'?'selected':''}>1:1</option><option ${node.aspectRatio==='3:4'?'selected':''}>3:4</option></select></label><label>分辨率<select data-film-field="resolution"><option ${node.resolution==='1k'?'selected':''}>1k</option><option ${node.resolution==='2k'?'selected':''}>2k</option><option ${node.resolution==='4k'?'selected':''}>4k</option></select></label><label>生成数量<select data-film-field="count">${[1,2,3,4].map(count => `<option value="${count}" ${node.count===count?'selected':''}>${count} 张</option>`).join('')}</select></label></div>`}
            ${node.runError ? `<div class="film-error">${esc(node.runError)}</div>` : ''}
        </div>`;
    }
    function notify(options,node,render=false){ options.onChange?.(node,{render}); }
    function insertAtCursor(input,text){
        const start=Number.isFinite(input.selectionStart)?input.selectionStart:input.value.length;
        const end=Number.isFinite(input.selectionEnd)?input.selectionEnd:start;
        input.value=input.value.slice(0,start)+text+input.value.slice(end);
        const cursor=start+text.length;
        input.setSelectionRange(cursor,cursor);
        input.dispatchEvent(new Event('input',{bubbles:true}));
    }
    function bindMentionMenu(root,input,node,options){
        let menu=root.querySelector('.film-mention-menu');
        let mentionStart=-1;
        let activeIndex=0;
        let currentRefs=[];
        if(!menu){ menu=document.createElement('div'); menu.className='film-mention-menu'; root.appendChild(menu); }
        const close=()=>{menu.classList.remove('open');menu.innerHTML='';mentionStart=-1;currentRefs=[];activeIndex=0;};
        const mentionState=()=>{
            const cursor=Number.isFinite(input.selectionStart) ? input.selectionStart : input.value.length;
            const before=input.value.slice(0,cursor);
            const match=before.match(/@([^\s@]*)$/);
            if(!match) return null;
            return {start:cursor-match[0].length,query:match[1] || ''};
        };
        const choose=index=>{
            const ref=currentRefs[index];
            if(!ref) return;
            const start=mentionStart >= 0 ? mentionStart : input.selectionStart;
            const end=Number.isFinite(input.selectionStart) ? input.selectionStart : input.value.length;
            input.setSelectionRange(start,end);
            insertAtCursor(input,ref.roleLabel || ref.name || '参考资产');
            close();
        };
        const renderMenu=()=>{
            const built=buildPrompt(node,options.assets?.(node)||[],options);
            const state=mentionState();
            if(!state || !built.map.refs.length){ close(); return; }
            mentionStart=state.start;
            const query=state.query.toLocaleLowerCase();
            currentRefs=built.map.refs.filter(ref=>{
                const haystack=`${ref.roleLabel || ''} ${ref.name || ''}`.toLocaleLowerCase();
                return !query || haystack.includes(query);
            });
            if(!currentRefs.length){ close(); return; }
            activeIndex=Math.min(activeIndex,currentRefs.length-1);
            menu.innerHTML=currentRefs.map((ref,index)=>`<button type="button" class="${index===activeIndex?'is-active':''}" data-film-mention-index="${index}"><b>${esc(ref.roleLabel || '参考资产')}</b><span>${esc(ref.name || '已连接')}</span></button>`).join('');
            menu.classList.add('open');
            menu.querySelectorAll('[data-film-mention-index]').forEach(button=>button.addEventListener('mousedown',event=>{
                event.preventDefault(); event.stopPropagation();
                choose(Number(button.dataset.filmMentionIndex));
            }));
        };
        input.addEventListener('input',()=>{
            node.prompt=input.value; notify(options,node,false);
            if(mentionState()) renderMenu(); else close();
        });
        input.addEventListener('keydown',event=>{
            if(!menu.classList.contains('open')){ if(event.key==='Escape') close(); return; }
            if(event.key==='ArrowDown' || event.key==='ArrowUp'){
                event.preventDefault();
                activeIndex=(activeIndex + (event.key==='ArrowDown' ? 1 : currentRefs.length - 1)) % currentRefs.length;
                renderMenu();
            } else if(event.key==='Enter'){
                event.preventDefault(); choose(activeIndex);
            } else if(event.key==='Escape'){
                event.preventDefault(); close();
            }
        });
        root.addEventListener('mousedown',event=>{ if(!event.target.closest('.film-mention-menu') && event.target!==input) close(); });
    }
    async function parseScene(node, options={}){
        const assets=options.assets?.(node)||[];
        const mappedRefs=assetList(node,assets).filter(item=>item.url && (item.kind || 'image') === 'image').slice(0,20);
        const refs=mappedRefs.map(item=>item.url);
        if(!refs.length) throw new Error(node.type==='film-video'?'请先连接分镜图或演员参考图':'请先连接线稿分镜');
        const manifest=mappedRefs.map((item,index)=>`图${index+1}=${item.roleLabel || '参考资产'}`).join('；');
        const message=node.type==='film-video'
            ? `你将收到一组已按顺序编号的影视资产（${manifest}）。请先解析其中的分镜图，再结合演员、服装和道具参考，预测镜头运镜、人物动作先后、身体朝向、视线、节奏与互动关系。输出一段可直接用于视频生成的中文动作描述，明确镜头运动和关键动作触发时机；不要解释分析过程。`
            : `你将收到一组已按顺序编号的影视资产（${manifest}），其中演员、场景和线稿分镜必须在同一次综合解析中互相校验。请输出一段可直接用于图像生成的中文画面描述：明确每张图对应的角色/场景/分镜关系、人物身份与动作、道具位置、构图角度、光线和环境，并要求画面构图严格参照线稿分镜图；不要解释分析过程。`;
        const provider=options.visionProvider?.(node) || node.visionProvider || '';
        const model=options.visionModel?.(node) || node.visionModel || '';
        const response=await fetch('/api/canvas-llm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,images:refs.slice(0,20),videos:[],provider,model,system_prompt:'你是影视分镜与动作分析助手。输出简洁、准确、可执行的中文生成提示词。必须保留并正确使用图号与资产映射关系。'})});
        const data=await response.json().catch(()=>({}));
        if(!response.ok) throw new Error(data.detail || '视觉解析失败');
        node.prompt=String(data.text || '').trim();
        return node.prompt;
    }
    function bind(root,node,options={}){
        normalize(node);
        const prompt=root.querySelector('[data-film-field="prompt"]');
        if(prompt) bindMentionMenu(root,prompt,node,options);
        root.querySelectorAll('[data-film-field]').forEach(control=>{
            if(control===prompt) return;
            const eventName=control.matches('input')?'input':'change';
            control.addEventListener(eventName,event=>{
                const key=control.dataset.filmField;
                node[key]=key==='duration'
                    ? clamp(control.value,1,60)
                    : key==='count' ? clamp(control.value,1,4) : control.value;
                if(key==='apiProvider'){
                    const getDefault=node.type === 'film-storyboard' ? options.defaultImageModel : options.defaultModel;
                    node.model=getDefault?.(control.value,node) || '';
                }
                notify(options,node,key==='apiProvider' || key==='model');
                event.stopPropagation();
            });
        });
        root.querySelector('[data-film-action="add-actor"]')?.addEventListener('click',event=>{
            event.preventDefault(); event.stopPropagation();
            node.actorCount=clamp((node.actorCount||1)+1,1,8); notify(options,node,true);
        });
        root.querySelector('[data-film-action="parse"]')?.addEventListener('click',async event=>{
            event.preventDefault(); event.stopPropagation();
            const button=event.currentTarget; button.disabled=true;
            try { await parseScene(node,options); notify(options,node,true); }
            catch(error){ node.runError=error.message || '视觉解析失败'; options.toast?.(node.runError); notify(options,node,true); }
            finally { button.disabled=false; }
        });
        root.querySelector('[data-film-action="run"]')?.addEventListener('click',event=>{
            event.preventDefault(); event.stopPropagation(); options.run?.(node);
        });
        const rule=modelRule(node.apiProvider || options.provider,node.model || options.model);
        const ruleEl=root.querySelector('[data-film-model-rule]'); if(ruleEl) ruleEl.textContent=`当前规则：${rule.name}`;
    }

    window.CanvasFilmNodes={TYPES,MODEL_RULES,isType,isGenerator,canOutput,title,size,normalize,createNode,effectiveActorCount,inputPorts,roleLabel,modelRule,assetList,mapping,buildPrompt,bodyHtml,bind,parseScene};
})();
