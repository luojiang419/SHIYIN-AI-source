(function(){
    'use strict';

    const TYPES = ['film-storyboard','film-video'];
    const LINE_ART_TYPE = 'film-line-art';
    const ROLE_ORDER = {
        'film-storyboard': ['actor','outfit','prop','scene','sketch'],
        'film-video': ['storyboard','actor','outfit','prop'],
        'film-line-art': ['source'],
    };
    const TITLES = {
        'film-storyboard':'分镜合成',
        'film-video':'生成视频',
        'film-line-art':'生成线稿分镜',
    };
    const SIZES = {
        'film-storyboard': {w:520,h:0},
        'film-video': {w:520,h:0},
        'film-line-art': {w:520,h:0},
    };
    const MODEL_RULES = {
        default: {id:'default', name:'通用', prefix:'图', template:'{ref}是{role}', maxImages:20},
        jimeng: {id:'jimeng', name:'即梦', prefix:'图', template:'{ref}是{role}', maxImages:12},
        // 可灵最新 Prompt Syntax 2.0 使用 <<<image_N>>> 等 Omni 引用标签；编号
        // 必须与真实输入端口的上传顺序一致，不能再用脱离端口的自然图号。
        kling: {id:'kling', name:'可灵', prefix:'<<<image_', template:'<<<image_{index}>>>={role}', maxImages:12},
        minimax: {id:'minimax', name:'MiniMax H3', prefix:'Picture ', template:'<Picture {index}> is {role}', maxImages:9},
    };
    const LINE_ART_PROMPT = '这是导演审阅用的专业黑白线稿分镜转换任务。请把参考视频帧重绘为标准电影分镜线稿，不是照片滤镜，也不是简单边缘检测。必须保留景别、机位、透视、主体位置与大小、人物数量、人物距离与朝向、肢体动作、视线方向、必要道具和场景空间关系。人物统一替换为无身份、无外貌、无服装特征的中性分镜人偶：光滑空白椭圆头部、完全留白的脸、简洁几何体块和圆柱四肢，只用外轮廓、关节转折和少量结构线表达动作；禁止脸部、发型、肤色、服装、配饰和写实人体细节。背景只保留机位、景别、主体位置、前中后景、主要灯架、摄影机和遮挡关系所必需的长轮廓与几何形状，使用白底细黑线和少量排线，移除颜色、照片纹理、品牌、水印、字幕和无关杂物。禁止添加分镜编号、镜头参数、对白框、箭头、边框、表格或任何文字，只输出单张纯黑白分镜画面。';

    function esc(value){
        return String(value == null ? '' : value)
            .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
            .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }
    function clamp(value,min,max){ return Math.max(min,Math.min(max,Number(value) || min)); }
    function isType(type){ return TYPES.includes(type) || type === LINE_ART_TYPE; }
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
        } else if(node.type === LINE_ART_TYPE){
            node.apiProvider = String(node.apiProvider || '');
            node.model = String(node.model || '');
            node.aspectRatio = node.aspectRatio || 'source';
            node.resolution = node.resolution || '2k';
            node.quality = node.quality || 'high';
            node.batchStatus = String(node.batchStatus || 'idle');
            node.batchError = String(node.batchError || '');
            node.batchCompleted = Math.max(0, Number(node.batchCompleted) || 0);
        } else {
            node.duration = clamp(node.duration || 5, 1, 60);
            node.aspectRatio = node.aspectRatio || '16:9';
            // 空值会触发平台自身的不可控默认值，影视节点统一默认使用 1080P。
            node.resolution = String(node.resolution || '1080p');
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
    function actorAssetPorts(i, noun='演员'){
        const actor = actorLabel(i,noun);
        return [
            {role:`actor-${i}`,label:actorLabel(i,'演员'),title:`连接${actor}主体参考图`},
            {role:`outfit-${i}`,label:`服装${String.fromCharCode(65+i)}`,title:`连接${actor}服装参考图`},
            {role:`prop-${i}`,label:`道具${String.fromCharCode(65+i)}`,title:`连接${actor}道具参考图`},
        ];
    }
    function inputPorts(nodeOrType){
        const node = typeof nodeOrType === 'string' ? {type:nodeOrType,actorCount:1} : normalize(nodeOrType || {});
        const count = effectiveActorCount(node);
        if(node.type === 'film-storyboard'){
            return [
                ...Array.from({length:count}, (_,i) => actorAssetPorts(i,'演员')).flat(),
                {role:'scene',label:'场景',title:'连接场景参考图'},
                {role:'sketch',label:'线稿分镜',title:'连接线稿分镜参考图'},
            ];
        }
        if(node.type === 'film-video'){
            return [
                {role:'storyboard',label:'分镜图',title:'连接分镜图或首帧参考'},
                ...Array.from({length:count}, (_,i) => actorAssetPorts(i,'演员')).flat(),
            ];
        }
        if(node.type === LINE_ART_TYPE){
            return [{role:'source',label:'视频帧 / 分镜组',title:'连接视频帧组、分镜图组或图像输出'}];
        }
        return [];
    }
    function roleLabel(node, role, asset={}){
        const match = String(role || '').match(/^(actor|outfit|prop)-(\d+)$/);
        const isProductDetail = String(asset?.sourceRole || asset?.reference_type || '').toLowerCase() === 'detail'
            || asset?.isProductDetail === true;
        const withProductDetail = label => isProductDetail ? `${label}产品细节` : label;
        if(match){
            const index = Number(match[2]);
            if(match[1] === 'actor') return withProductDetail(actorLabel(index,'演员'));
            if(match[1] === 'outfit') return withProductDetail(`服装${String.fromCharCode(65 + index)}`);
            return withProductDetail(`道具${String.fromCharCode(65 + index)}`);
        }
        return withProductDetail(node.type === 'film-storyboard'
            ? ({scene:'场景',sketch:'线稿分镜'}[role] || role)
            : node.type === LINE_ART_TYPE
                ? ({source:'视频帧 / 分镜组'}[role] || role)
                : ({storyboard:'分镜图'}[role] || role));
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
            if(ref?.url) list.push({...ref, role, sourceRole:String(item?.sourceRole || ref?.sourceRole || ref?.role || ref?.reference_type || '')});
            byRole.set(role, list);
        });
        inputPorts(node).forEach(port => {
            // 同一输入端口允许挂接多张参考图；保持端口顺序，再保持同一端口
            // 内的真实连线/上传顺序，后续由 mapping() 统一分配 1-n 编号。
            const roleRefs = byRole.get(port.role) || [];
            roleRefs.forEach(ref => refs.push({...ref, inputRole:port.role, roleLabel:roleLabel(node, port.role, ref)}));
        });
        return refs;
    }
    function mapping(node, assets=[], options={}){
        const rule = modelRule(node.apiProvider || options.provider, node.model || options.model);
        const assetRefs = assetList(node, assets);
        const refs = (node.type === LINE_ART_TYPE ? assetRefs : assetRefs.slice(0, rule.maxImages)).map((ref,index) => ({
            ...ref,
            assetIndex:index + 1,
            asset_index:index + 1,
            input_role:ref.inputRole || '',
            role_label:ref.roleLabel || roleLabel(node, ref.inputRole),
        }));
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
        const hasProductDetail = map.refs.some(ref => ref.sourceRole === 'detail' || ref.isProductDetail === true);
        const prefix = map.text ? `资产映射：${map.text}。${hasProductDetail ? '产品主图与产品细节均为同一产品的证据，生成时必须优先保持产品结构、材质、颜色、Logo和文字真实一致。' : ''}` : '';
        return {prompt:[prefix,prompt].filter(Boolean).join('\n'), refs:map.refs, map};
    }
    function lineArtPrompt(node){
        return [LINE_ART_PROMPT,String(node?.prompt || '').trim()].filter(Boolean).join('\n');
    }
    function itemPreview(item){
        if(!item?.url) return '<i data-lucide="image"></i>';
        const url = esc(item.url);
        return `<img src="${url}" alt="" loading="lazy">`;
    }
    function mappingHtml(node, assets=[], options={}){
        const map = mapping(node, assets, options);
        if(!map.refs.length) return '<div class="film-empty-note">连接资产后会自动建立图像映射</div>';
        return `<div class="film-mapping-list">${map.refs.map((ref,index) => `<span class="film-mapping-chip"><b>${index + 1}. ${esc(ref.roleLabel || '参考资产')}</b><i>${itemPreview(ref)}</i><em>${esc(ref.name || '已连接')}</em></span>`).join('')}</div>`;
    }
    function promptHtml(node, options={}){
        const refs = (options.assets?.(node) || []).filter(item => (item?.ref || item)?.url);
        const kinds = refs.map(item => String((item?.ref || item)?.kind || 'image').toLowerCase());
        const hasPrompt = Boolean(String(node?.prompt || '').trim() || options.promptConnected?.(node));
        const autoParse = node.type === 'film-video' && !hasPrompt && kinds.includes('image') && kinds.every(kind => kind === 'image');
        const polish = node.type === 'film-video' ? `<button type="button" class="prompt-polish-btn film-prompt-polish${autoParse ? ' auto-parse' : ''}" data-film-action="polish" data-film-prompt-mode="${autoParse ? 'auto-parse' : 'polish'}" title="${autoParse ? '按图片顺序分析画面并生成视频提示词' : '按当前视频模型规范润色提示词'}"><i data-lucide="${autoParse ? 'scan-eye' : 'wand-sparkles'}"></i><span>${autoParse ? '自动解析' : '润色'}</span></button>` : '';
        return `<label class="film-prompt-field"><span>生成需求</span><div class="film-prompt-editor-wrap"><textarea data-film-field="prompt" rows="5" placeholder="输入镜头、动作、镜头运动、节奏和声音要求；输入 @ 可引用映射资产">${esc(node.prompt)}</textarea>${polish}</div></label>`;
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
        const isLineArt = node.type === LINE_ART_TYPE;
        const action = isLineArt ? '生成线稿分镜' : node.type === 'film-storyboard' ? '生成分镜图' : '生成视频';
        const parseText = node.type === 'film-storyboard' ? '解析画面' : '解析动作';
        const providerOptions = ['film-storyboard',LINE_ART_TYPE].includes(node.type)
            ? (options.imageProviderOptions || options.providerOptions)?.(node) || ''
            : options.providerOptions?.(node) || '';
        const modelOptions = ['film-storyboard',LINE_ART_TYPE].includes(node.type)
            ? (options.imageModelOptions || options.modelOptions)?.(node) || ''
            : options.modelOptions?.(node) || '';
        const lineArtAssets = isLineArt ? (options.assets?.(node) || []).filter(item => (item?.ref || item)?.url) : [];
        const lineArtStatus = node.batchStatus === 'running'
            ? `正在并行提交 ${lineArtAssets.length} 张图片…`
            : node.batchStatus === 'error'
                ? (node.batchError || '部分图片处理失败，可在输出节点重试')
                : node.batchStatus === 'done'
                    ? `已完成 ${Number(node.batchCompleted || lineArtAssets.length)} 张图片`
                    : (lineArtAssets.length ? `已连接 ${lineArtAssets.length} 张图片` : '可输入任意数量图片');
        return `<div class="film-node-panel ${node.type}">
            <div class="film-node-toolbar"><span class="film-node-kicker">影视制作</span>${isLineArt ? '<span class="film-line-art-badge">逐帧转换</span>' : '<button type="button" class="film-add-actor" data-film-action="add-actor"><i data-lucide="user-round-plus"></i>添加演员</button>'}</div>
            <div class="film-input-list">${inputPorts(node).map((port,index) => inputSlotHtml(node, port, {...options,index})).join('')}</div>
            ${isLineArt ? `<div class="film-line-art-batch-summary"><strong>${esc(lineArtStatus)}</strong><small>每张图片独立提交，批量并行生成</small></div>` : ''}
            <div class="film-mapping-title">资产映射 <small data-film-model-rule></small></div><div data-film-mapping>${mappingHtml(node, options.assets?.(node) || [], options)}</div>
            ${promptHtml(node, options)}
            <div class="film-node-actions">${isLineArt ? '' : `<button type="button" class="film-parse-button" data-film-action="parse"><i data-lucide="scan-eye"></i>${parseText}</button>`}<button type="button" class="film-run-button" data-film-action="run"><i data-lucide="${node.type === 'film-video' ? 'clapperboard' : 'wand-sparkles'}"></i>${node.running ? '生成中（可继续）' : action}</button></div>
            ${node.type === 'film-video' ? `<div class="film-video-settings"><select data-film-field="apiProvider">${providerOptions}</select><select data-film-field="model">${modelOptions}</select><label>时长<input data-film-field="duration" type="number" min="1" max="60" value="${node.duration}"></label><label>画幅<select data-film-field="aspectRatio"><option ${node.aspectRatio==='16:9'?'selected':''}>16:9</option><option ${node.aspectRatio==='9:16'?'selected':''}>9:16</option><option ${node.aspectRatio==='1:1'?'selected':''}>1:1</option><option ${node.aspectRatio==='4:3'?'selected':''}>4:3</option></select></label><label>分辨率<select data-film-field="resolution"><option value="480p" ${node.resolution==='480p'?'selected':''}>480P</option><option value="720p" ${node.resolution==='720p'?'selected':''}>720P</option><option value="1080p" ${node.resolution==='1080p'?'selected':''}>1080P（推荐）</option><option value="4k" ${node.resolution==='4k'?'selected':''}>4K</option></select></label></div>` : isLineArt ? `<div class="film-image-settings film-line-art-settings"><select data-film-field="apiProvider">${providerOptions}</select><select data-film-field="model">${modelOptions}</select><label>画幅<select data-film-field="aspectRatio"><option value="source" ${node.aspectRatio==='source'?'selected':''}>源画幅</option><option value="16:9" ${node.aspectRatio==='16:9'?'selected':''}>16:9</option><option value="1:1" ${node.aspectRatio==='1:1'?'selected':''}>1:1</option><option value="9:16" ${node.aspectRatio==='9:16'?'selected':''}>9:16</option><option value="3:2" ${node.aspectRatio==='3:2'?'selected':''}>3:2</option><option value="2:3" ${node.aspectRatio==='2:3'?'selected':''}>2:3</option></select></label><label>分辨率<select data-film-field="resolution"><option value="1k" ${node.resolution==='1k'?'selected':''}>1K</option><option value="2k" ${node.resolution==='2k'?'selected':''}>2K</option><option value="4k" ${node.resolution==='4k'?'selected':''}>4K</option></select></label><label>质量<select data-film-field="quality"><option value="auto" ${node.quality==='auto'?'selected':''}>自动</option><option value="medium" ${node.quality==='medium'?'selected':''}>标准</option><option value="high" ${node.quality==='high'?'selected':''}>高质量</option></select></label></div>` : `<div class="film-image-settings"><select data-film-field="apiProvider">${providerOptions}</select><select data-film-field="model">${modelOptions}</select><label>画幅<select data-film-field="aspectRatio"><option ${node.aspectRatio==='16:9'?'selected':''}>16:9</option><option ${node.aspectRatio==='9:16'?'selected':''}>9:16</option><option ${node.aspectRatio==='1:1'?'selected':''}>1:1</option><option ${node.aspectRatio==='3:4'?'selected':''}>3:4</option></select></label><label>分辨率<select data-film-field="resolution"><option ${node.resolution==='1k'?'selected':''}>1k</option><option ${node.resolution==='2k'?'selected':''}>2k</option><option ${node.resolution==='4k'?'selected':''}>4k</option></select></label><label>生成数量<select data-film-field="count">${[1,2,3,4].map(count => `<option value="${count}" ${node.count===count?'selected':''}>${count} 张</option>`).join('')}</select></label></div>`}
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
            const built=buildPrompt(node,options.assets?.(node)||[],options);
            const mention = built.map.rule.id === 'kling'
                ? `<<<image_${ref.assetIndex || (built.map.refs.indexOf(ref) + 1)}>>>`
                : (ref.roleLabel || ref.name || '参考资产');
            insertAtCursor(input,mention);
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
    function normalizeKlingPrompt(text, refs=[]){
        let output=String(text || '').trim();
        if(!output) return output;
        // 将旧版 @图N、图N/图片N 以及自然语言主体编号统一为 Kling
        // Prompt Syntax 2.0 的 Omni 标签。
        output=output
            .replace(/<<<\s*image_(\d+)\s*>>>/gi, '<<<image_$1>>>')
            .replace(/@图片(\d+)/g, '<<<image_$1>>>')
            .replace(/@图(\d+)/g, '<<<image_$1>>>')
            .replace(/(^|[^@\w])(?:图片|图)(\d+)/g, '$1<<<image_$2>>>')
            .replace(/<<<\s*element_(\d+)\s*>>>/gi, '<<<element_$1>>>')
            .replace(/(^|[^@\w])(?:主体|人物)(\d+)/g, '$1<<<element_$2>>>');
        const actors=refs.filter(ref=>/^actor-\d+$/.test(String(ref.inputRole || ''))).map(ref=>ref.roleLabel).filter(Boolean);
        if(actors.length){
            const generic=/一位年轻女性|年轻女性|一名女性|女性角色|女主角|女孩|女生|女子|一位年轻男性|年轻男性|一名男性|男性角色|男主角|男孩|男生|模特|人物/g;
            output=output.replace(generic, actors[0]);
            if(!output.includes(actors[0])) output=`${actors[0]}：${output}`;
        }
        return output;
    }
    async function parseScene(node, options={}){
        const assets=options.assets?.(node)||[];
        const map=mapping(node,assets,options);
        const mappedRefs=map.refs.filter(item=>item.url && (item.kind || 'image') === 'image').slice(0,20);
        const refs=mappedRefs.map(item=>item.url);
        if(!refs.length) throw new Error(node.type==='film-video'?'请先连接分镜图或演员参考图':'请先连接线稿分镜');
        const isKling=node.type==='film-video' && map.rule.id==='kling';
        // 只有锁定到“分镜图”输入端口的图片才是视频镜头参考。演员、服装、
        // 道具仍须传给模型以保持资产一致性，但它们的数量不能决定镜头数量。
        const storyboardRefs=mappedRefs.filter(item=>item.inputRole === 'storyboard');
        const shouldParseMultipleShots=node.type === 'film-video' && storyboardRefs.length > 1;
        const manifest=mappedRefs.map((item,index)=>`${isKling ? `<<<image_${index+1}>>>` : `图${index+1}`}=${item.roleLabel || '参考资产'}`).join('；');
        const message=node.type==='film-video'
            ? (isKling
                ? `你将收到按真实影视制作输入端顺序排列的参考资产：${manifest}。${shouldParseMultipleShots ? '分镜图输入端已连接多张参考图，请仅按这些分镜图的端口内顺序解析多镜头，并按“镜头1、镜头2……”组织连续动作。' : '分镜图输入端未连接多张参考图，请只解析一个连续镜头；演员、服装和道具仅用于资产一致性绑定，不得因其数量拆分多镜头。'}请按可灵 VIDEO 3.0 Omni 最新官方提示词规范输出可直接生成的视频提示词：先交代场景与主体；${shouldParseMultipleShots ? '每个镜头' : '该镜头'}写明时长、景别/视角、主体动作与动作先后、身体朝向和视线、镜头运动及速度、光线/环境和必要声音。图片引用必须使用 <<<image_N>>>；画面中可复用的演员、服装、道具或产品主体按首次出现顺序使用 <<<element_N>>>，并说明其来自哪个 <<<image_N>>>。只输出提示词，不解释分析过程。`
                : `你将收到一组已按顺序编号的影视资产（${manifest}）。${shouldParseMultipleShots ? '请仅按分镜图输入端中多张参考图的顺序解析多镜头。' : '请仅解析一个连续镜头；演员、服装和道具仅用于资产一致性绑定，不得因其数量拆分多镜头。'}再结合演员、服装和道具参考，预测镜头运镜、人物动作先后、身体朝向、视线、节奏与互动关系。输出一段可直接用于视频生成的中文动作描述，明确镜头运动和关键动作触发时机；不要解释分析过程。`)
            : `你将收到一组已按顺序编号的影视资产（${manifest}），其中演员、场景和线稿分镜必须在同一次综合解析中互相校验。请输出一段可直接用于图像生成的中文画面描述：明确每张图对应的角色/场景/分镜关系、人物身份与动作、道具位置、构图角度、光线和环境，并要求画面构图严格参照线稿分镜图；不要解释分析过程。`;
        const provider=options.visionProvider?.(node) || node.visionProvider || '';
        const model=options.visionModel?.(node) || node.visionModel || '';
        const response=await fetch('/api/canvas-llm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,images:refs.slice(0,20),image_labels:mappedRefs.map((item,index)=>`${isKling ? `<<<image_${index+1}>>>` : `图${index+1}`}=${item.roleLabel || '参考资产'}`),videos:[],provider,model,system_prompt:isKling ? `你是可灵 VIDEO 3.0 Omni 提示词导演。严格使用 <<<image_N>>> 引用图片，按首次出现顺序使用 <<<element_N>>> 绑定从画面解析出的稳定主体；每个主体必须说明来自哪个 <<<image_N>>>，不能把没有视觉证据的主体写入提示词。${shouldParseMultipleShots ? '只按分镜图输入端的多张参考图解析镜头编号、时长、景别、动作、运镜和声音。' : '只输出一个连续镜头；演员、服装和道具图片均为资产绑定，不得因其数量拆分多镜头。'}预测连续运动而不是静态画面。` : `你是影视分镜与动作分析助手。${shouldParseMultipleShots ? '只按分镜图输入端的多张参考图解析多镜头。' : '只输出一个连续镜头；演员、服装和道具图片均为资产绑定，不得因其数量拆分多镜头。'}输出简洁、准确、可执行的中文生成提示词。必须保留并正确使用图号与资产映射关系。`})});
        const data=await response.json().catch(()=>({}));
        if(!response.ok) throw new Error(data.detail || '视觉解析失败');
        node.prompt=isKling ? normalizeKlingPrompt(data.text,mappedRefs) : String(data.text || '').trim();
        return node.prompt;
    }
    async function autoParseVideoPrompt(node, assets=[], options={}){
        const refs = mapping(node, assets, options).refs.filter(item => item.url && (item.kind || 'image') === 'image').slice(0,20);
        if(!refs.length) throw new Error('自动解析至少需要一张图片');
        const provider = options.visionProvider?.(node) || node.visionProvider || '';
        const model = options.visionModel?.(node) || node.visionModel || '';
        const response = await fetch('/api/canvas-video-auto-parse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
            provider, model, video_provider:node.apiProvider || '', video_model:node.model || '',
            images:refs.map(item=>item.url), image_labels:refs.map((item,index)=>`参考素材${index + 1}：${item.roleLabel || '参考资产'}`),
            duration:Number(node.duration || 0) || null, aspect_ratio:node.aspectRatio || '', resolution:node.resolution || ''
        })});
        const data=await response.json().catch(()=>({}));
        if(!response.ok) throw new Error(data.detail || '自动解析失败');
        const text=String(data.text || '').trim();
        if(!text) throw new Error('自动解析未返回视频提示词');
        return text;
    }
    function bind(root,node,options={}){
        normalize(node);
        const prompt=root.querySelector('[data-film-field="prompt"]');
        if(prompt) bindMentionMenu(root,prompt,node,options);
        const polishButton=root.querySelector('[data-film-action="polish"]');
        if(polishButton && prompt && options.polishPrompt){
            const syncAction=()=>{
                const refs=(options.assets?.(node)||[]).filter(item=>(item?.ref||item)?.url);
                const kinds=refs.map(item=>String((item?.ref||item)?.kind||'image').toLowerCase());
                const hasPrompt=Boolean(String(node.prompt||'').trim() || options.promptConnected?.(node));
                const autoParse=!hasPrompt && kinds.includes('image') && kinds.every(kind=>kind==='image');
                polishButton.dataset.filmPromptMode=autoParse?'auto-parse':'polish';
                polishButton.classList.toggle('auto-parse',autoParse);
                polishButton.title=autoParse?'按图片顺序分析画面并生成视频提示词':'按当前视频模型规范润色提示词';
                const label=polishButton.querySelector('span'); if(label && !polishButton.disabled) label.textContent=autoParse?'自动解析':'润色';
                const icon=polishButton.querySelector('[data-lucide]'); if(icon) icon.setAttribute('data-lucide',autoParse?'scan-eye':'wand-sparkles');
            };
            prompt.addEventListener('input',syncAction);
            syncAction();
            polishButton.addEventListener('mousedown',event=>event.stopPropagation());
            polishButton.addEventListener('click',async event=>{
                event.preventDefault(); event.stopPropagation();
                if(polishButton.disabled) return;
                polishButton.disabled=true; polishButton.classList.add('is-loading');
                const mode=polishButton.dataset.filmPromptMode || 'polish';
                const label=polishButton.querySelector('span'); if(label) label.textContent=mode === 'auto-parse' ? '解析中…' : '润色中…';
                try {
                    prompt.value=mode === 'auto-parse'
                        ? await (options.autoParsePrompt ? options.autoParsePrompt(node,options.assets?.(node)||[]) : autoParseVideoPrompt(node,options.assets?.(node)||[],options))
                        : await options.polishPrompt(node,prompt.value,options.assets?.(node)||[]);
                    prompt.dispatchEvent(new Event('input',{bubbles:true}));
                } catch(error){ options.toast?.(error.message || (mode === 'auto-parse' ? '自动解析失败' : '提示词润色失败')); }
                finally { polishButton.disabled=false; polishButton.classList.remove('is-loading'); if(label) label.textContent=mode === 'auto-parse' ? '自动解析' : '润色'; }
            });
        }
        root.querySelectorAll('[data-film-field]').forEach(control=>{
            if(control===prompt) return;
            const eventName=control.matches('input')?'input':'change';
            control.addEventListener(eventName,event=>{
                const key=control.dataset.filmField;
                node[key]=key==='duration'
                    ? clamp(control.value,1,60)
                    : key==='count' ? clamp(control.value,1,4) : control.value;
                if(key==='apiProvider'){
                    const getDefault=['film-storyboard',LINE_ART_TYPE].includes(node.type) ? options.defaultImageModel : options.defaultModel;
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

    window.CanvasFilmNodes={TYPES,LINE_ART_TYPE,LINE_ART_PROMPT,MODEL_RULES,isType,isGenerator,canOutput,title,size,normalize,createNode,effectiveActorCount,inputPorts,roleLabel,modelRule,assetList,mapping,buildPrompt,lineArtPrompt,bodyHtml,bind,parseScene,autoParseVideoPrompt};
})();
