(function(){
    'use strict';

    const TYPES = ['ecom-model','ecom-product','ecom-scene','ecom-compose','ecom-video'];
    const PRODUCT_ROLES = [
        ['full_garment','连衣裙 / 套装'],
        ['upper_garment','上装'],
        ['lower_garment','下装'],
        ['shoes','鞋靴'],
        ['accessory','首饰 / 配饰'],
        ['prop','手持商品'],
        ['scene_prop','场景道具'],
    ];
    const TITLES = {
        'ecom-model':'电商模特',
        'ecom-product':'电商产品',
        'ecom-scene':'电商场景',
        'ecom-compose':'A+ 图合成',
        'ecom-video':'电商视频',
    };
    const SIZES = {
        'ecom-model':{w:320,h:0},
        'ecom-product':{w:340,h:0},
        'ecom-scene':{w:360,h:0},
        'ecom-compose':{w:440,h:0},
        'ecom-video':{w:400,h:0},
    };
    const INPUT_PORTS = {
        'ecom-model':[
            {role:'model-reference',label:'输入',title:'连接人物图片、生成图片或素材组'},
        ],
        'ecom-product':[
            {role:'product-reference',label:'输入',title:'连接商品图片、生成图片或素材组'},
        ],
        'ecom-scene':[
            {role:'scene-reference',label:'输入',title:'连接场景图片、生成图片或素材组'},
        ],
        'ecom-compose':[
            {role:'ecom-model',label:'模特',title:'连接电商模特、人物图或模特形象图'},
            {role:'ecom-product',label:'商品',title:'连接电商产品或商品图'},
            {role:'ecom-scene',label:'场景',title:'连接电商场景或背景图'},
            {role:'ecom-pose',label:'动作',title:'可选：连接姿势参考图'},
        ],
        'ecom-video':[
            {role:'video-input',label:'输入',title:'连接 A+ 成片、图片或提示词'},
        ],
    };
    const IMAGE_NAME_PATTERN = /\.(png|jpe?g|webp|gif|bmp|avif|tiff?)$/i;

    function esc(value){
        return String(value == null ? '' : value)
            .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
            .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }
    function clamp(value, min, max){
        return Math.max(min, Math.min(max, Number(value) || min));
    }
    function outputUrl(item){
        return typeof item === 'string' ? item : String(item?.url || item?.path || item?.src || '');
    }
    function normalizeItem(item, index=0){
        if(typeof item === 'string') return {url:item,name:`reference-${index + 1}.png`,kind:'image'};
        return {
            ...item,
            url:String(item?.url || item?.path || item?.src || ''),
            name:String(item?.name || item?.filename || `reference-${index + 1}.png`),
            kind:'image',
        };
    }
    function normalize(node){
        if(!node || !TYPES.includes(node.type)) return node;
        node.ecomItems = (Array.isArray(node.ecomItems) ? node.ecomItems : []).map(normalizeItem).filter(item => item.url);
        node.generatedOutputs = Array.isArray(node.generatedOutputs) ? node.generatedOutputs.filter(outputUrl) : [];
        node.running = Boolean(node.running);
        node.runError = String(node.runError || '');
        if(node.type === 'ecom-model'){
            node.ecomModelRole = ['subject','model_identity'].includes(node.ecomModelRole) ? node.ecomModelRole : 'subject';
            node.ecomDescription = String(node.ecomDescription || '');
        }
        if(node.type === 'ecom-product'){
            node.ecomProductRole = PRODUCT_ROLES.some(([id]) => id === node.ecomProductRole) ? node.ecomProductRole : 'full_garment';
            node.ecomDescription = String(node.ecomDescription || '');
        }
        if(node.type === 'ecom-scene'){
            node.scenePrompt = String(node.scenePrompt || '干净高级的电商摄影棚，真实材质，柔和商业布光，主体清晰，保留自然接触阴影');
            node.aspectRatio = node.aspectRatio || '16:9';
            node.resolution = node.resolution || '2k';
            node.quality = node.quality || 'high';
        }
        if(node.type === 'ecom-compose'){
            node.instruction = String(node.instruction || '生成可直接用于电商详情页与社交推广的高质感 A+ 商品图；严格保持人物、商品、Logo、文字、材质与颜色准确，并让场景光影、透视和接触阴影自然统一。');
            node.videoPrompt = String(node.videoPrompt || '商业广告镜头缓慢推进，轻微环绕主体，保持人物与商品结构稳定，材质和 Logo 清晰，光影自然，不添加文字或无关物体。');
            node.aspectRatio = node.aspectRatio || '3:4';
            node.resolution = node.resolution || '2k';
            node.quality = node.quality || 'high';
            node.count = clamp(node.count || 1, 1, 4);
        }
        return node;
    }
    function createNode(type, point={}, videoDefaults={}){
        if(!TYPES.includes(type)) return null;
        const base = {id:'',type,x:Number(point.x || 0),y:Number(point.y || 0),ecomItems:[],generatedOutputs:[],running:false,runError:''};
        if(type === 'ecom-model') Object.assign(base,{ecomModelRole:'subject',ecomDescription:''});
        if(type === 'ecom-product') Object.assign(base,{ecomProductRole:'full_garment',ecomDescription:''});
        if(type === 'ecom-scene') Object.assign(base,{scenePrompt:'干净高级的电商摄影棚，真实材质，柔和商业布光，主体清晰，保留自然接触阴影',aspectRatio:'16:9',resolution:'2k',quality:'high'});
        if(type === 'ecom-compose') Object.assign(base,{instruction:'生成可直接用于电商详情页与社交推广的高质感 A+ 商品图；严格保持人物、商品、Logo、文字、材质与颜色准确，并让场景光影、透视和接触阴影自然统一。',videoPrompt:'商业广告镜头缓慢推进，轻微环绕主体，保持人物与商品结构稳定，材质和 Logo 清晰，光影自然，不添加文字或无关物体。',aspectRatio:'3:4',resolution:'2k',quality:'high',count:1,inputs:[]});
        if(type === 'ecom-video') Object.assign(base,{
            apiProvider:videoDefaults.apiProvider || 'comfly',
            model:videoDefaults.model || 'veo3-fast',duration:5,aspectRatio:'9:16',resolution:'',
            enhancePrompt:true,enableUpsample:false,watermark:false,cameraFixed:false,generateAudio:false,
            useFrameRoles:false,multimodal:false,tempShLinks:[],inputs:[],running:false,
        });
        return normalize(base);
    }
    function title(type){ return TITLES[type] || ''; }
    function size(type){ return SIZES[type] || null; }
    function isType(type){ return TYPES.includes(type); }
    function isMediaOutput(type){ return ['ecom-model','ecom-product','ecom-scene','ecom-compose','ecom-video'].includes(type); }
    function isGenerator(type){ return ['ecom-compose','ecom-video'].includes(type); }
    function inputPorts(type){
        return (INPUT_PORTS[type] || []).map(port => ({...port}));
    }
    function canOutput(type){ return isType(type); }

    function itemGrid(items, emptyText){
        if(!items.length) return `<div class="ecom-node-empty"><i data-lucide="image-plus"></i><span>${esc(emptyText)}</span></div>`;
        return `<div class="ecom-node-grid">${items.map((item,index) => `
            <div class="ecom-node-thumb" title="${esc(item.name || '')}">
                <img src="${esc(item.url)}" alt="" loading="lazy">
                <button type="button" data-ecom-remove="${index}" title="移除"><i data-lucide="x"></i></button>
                <span>${index + 1}</span>
            </div>`).join('')}</div>`;
    }
    function outputsGrid(node, emptyText='尚未生成结果'){
        const outputs = (node.generatedOutputs || []).map((item,index) => ({url:outputUrl(item),name:`result-${index + 1}`})).filter(item => item.url);
        if(!outputs.length) return `<div class="ecom-node-result-empty">${esc(emptyText)}</div>`;
        return `<div class="ecom-node-result-grid">${outputs.map((item,index) => `<div class="ecom-node-result"><img src="${esc(item.url)}" alt="生成结果 ${index + 1}" loading="lazy"><span>${index + 1}</span></div>`).join('')}</div>`;
    }
    function statusHtml(node){
        if(node.running) return '<div class="ecom-node-status running"><span></span>任务执行中，可在后台继续等待</div>';
        if(node.runError) return `<div class="ecom-node-status failed"><span></span>${esc(node.runError)}</div>`;
        if(node.ecomTaskId) return `<div class="ecom-node-status done"><span></span>最近任务 ${esc(String(node.ecomTaskId).slice(-8))}</div>`;
        return '';
    }
    function bodyHtml(node){
        normalize(node);
        if(node.type === 'ecom-model') return `
            <div class="ecom-node-panel">
                <div class="ecom-node-toolbar"><strong>人物参考</strong><label class="ecom-node-upload"><i data-lucide="upload"></i>上传<input type="file" accept="image/*" multiple data-ecom-file></label></div>
                ${itemGrid(node.ecomItems,'上传主体图；可追加一张脸部身份参考')}
                <label class="ecom-node-field"><span>参考用途</span><select data-ecom-field="ecomModelRole"><option value="subject" ${node.ecomModelRole === 'subject' ? 'selected' : ''}>主体 / 模特（保留身体与构图）</option><option value="model_identity" ${node.ecomModelRole === 'model_identity' ? 'selected' : ''}>模特形象（仅提供脸部身份）</option></select></label>
                <label class="ecom-node-field"><span>人物补充说明</span><textarea data-ecom-field="ecomDescription" placeholder="例如：保持发型、体型与自然肤质">${esc(node.ecomDescription)}</textarea></label>
            </div>`;
        if(node.type === 'ecom-product') return `
            <div class="ecom-node-panel">
                <div class="ecom-node-toolbar"><strong>商品参考</strong><label class="ecom-node-upload"><i data-lucide="upload"></i>多图上传<input type="file" accept="image/*" multiple data-ecom-file></label></div>
                ${itemGrid(node.ecomItems,'上传商品主图、细节图或不同角度')}
                <label class="ecom-node-field"><span>主商品类型</span><select data-ecom-field="ecomProductRole">${PRODUCT_ROLES.map(([id,label]) => `<option value="${id}" ${node.ecomProductRole === id ? 'selected' : ''}>${esc(label)}</option>`).join('')}</select></label>
                <label class="ecom-node-field"><span>商品补充说明</span><textarea data-ecom-field="ecomDescription" placeholder="例如：保持正面 Logo、金属拉链和面料纹理">${esc(node.ecomDescription)}</textarea></label>
                <div class="ecom-node-hint">第一张作为主商品，其余图片自动作为该商品细节证据。</div>
            </div>`;
        if(node.type === 'ecom-scene') return `
            <div class="ecom-node-panel">
                <div class="ecom-node-toolbar"><strong>场景参考</strong><label class="ecom-node-upload"><i data-lucide="upload"></i>上传<input type="file" accept="image/*" data-ecom-file></label></div>
                ${itemGrid(node.ecomItems.slice(0,1),'上传场景图，或在下方直接生成')}
                <label class="ecom-node-field"><span>场景描述</span><textarea data-ecom-field="scenePrompt" placeholder="描述环境、材质、布光和氛围">${esc(node.scenePrompt)}</textarea></label>
                <div class="ecom-node-params"><select data-ecom-field="aspectRatio">${['1:1','3:4','4:5','4:3','9:16','16:9'].map(value => `<option value="${value}" ${node.aspectRatio === value ? 'selected' : ''}>${value}</option>`).join('')}</select><select data-ecom-field="resolution">${['1k','2k','4k'].map(value => `<option value="${value}" ${node.resolution === value ? 'selected' : ''}>${value.toUpperCase()}</option>`).join('')}</select><select data-ecom-field="quality">${['auto','medium','high'].map(value => `<option value="${value}" ${node.quality === value ? 'selected' : ''}>${value.toUpperCase()}</option>`).join('')}</select></div>
                <button class="ecom-node-run" type="button" data-ecom-action="run-scene" ${node.running ? 'disabled' : ''}><i data-lucide="sparkles"></i>${node.running ? '生成中…' : '生成场景'}</button>
                ${statusHtml(node)}
            </div>`;
        if(node.type === 'ecom-compose') return `
            <div class="ecom-node-panel ecom-compose-panel">
                <div class="ecom-compose-summary" data-ecom-summary><span>模特 0</span><span>商品 0</span><span>场景 0</span><span>动作 0</span></div>
                <label class="ecom-node-field"><span>合成要求</span><textarea data-ecom-field="instruction" rows="4">${esc(node.instruction)}</textarea></label>
                <label class="ecom-node-field"><span>视频镜头提示词</span><textarea data-ecom-field="videoPrompt" rows="3">${esc(node.videoPrompt)}</textarea></label>
                <div class="ecom-node-params"><select data-ecom-field="aspectRatio">${['1:1','2:3','3:4','4:3','4:5','9:16','16:9'].map(value => `<option value="${value}" ${node.aspectRatio === value ? 'selected' : ''}>${value}</option>`).join('')}</select><select data-ecom-field="resolution">${['1k','2k','4k'].map(value => `<option value="${value}" ${node.resolution === value ? 'selected' : ''}>${value.toUpperCase()}</option>`).join('')}</select><select data-ecom-field="quality">${['auto','medium','high'].map(value => `<option value="${value}" ${node.quality === value ? 'selected' : ''}>${value.toUpperCase()}</option>`).join('')}</select><label class="ecom-count">数量<input data-ecom-field="count" type="number" min="1" max="4" value="${node.count}"></label></div>
                <button class="ecom-node-run" type="button" data-ecom-action="run-compose" ${node.running ? 'disabled' : ''}><i data-lucide="wand-sparkles"></i>${node.running ? '合成中…' : '生成 A+ 图'}</button>
                ${statusHtml(node)}
                ${outputsGrid(node)}
            </div>`;
        return '';
    }

    async function uploadFiles(files, limit){
        const accepted = [...(files || [])].filter(file => {
            const type = String(file?.type || '').toLowerCase();
            const name = String(file?.name || '');
            return type.startsWith('image/') || IMAGE_NAME_PATTERN.test(name);
        }).slice(0, limit);
        if(!accepted.length) return [];
        const form = new FormData();
        accepted.forEach(file => form.append('files', file));
        const response = await fetch('/api/ai/upload',{method:'POST',body:form});
        let data = {};
        try { data = await response.json(); } catch(_) {}
        if(!response.ok) throw new Error(String(data?.detail || data?.message || `图片上传失败（${response.status}）`));
        return (data.files || []).map(normalizeItem).filter(item => item.url);
    }
    function notify(options, node, render=false){ options.onChange?.(node,{render}); }
    function bind(root, node, options={}){
        if(!root || !node || !isType(node.type) || node.type === 'ecom-video') return;
        normalize(node);
        root.querySelectorAll('[data-ecom-field]').forEach(control => {
            const eventName = control.matches('textarea,input') ? 'input' : 'change';
            control.addEventListener(eventName,event => {
                const key = control.dataset.ecomField;
                node[key] = key === 'count' ? clamp(control.value,1,4) : control.value;
                notify(options,node,false);
                event.stopPropagation();
            });
        });
        const fileInput = root.querySelector('[data-ecom-file]');
        if(fileInput) fileInput.addEventListener('change',async event => {
            try {
                const limit = node.type === 'ecom-model' ? 2 : node.type === 'ecom-product' ? 8 : 1;
                const uploaded = await uploadFiles(fileInput.files,limit);
                node.ecomItems = node.type === 'ecom-scene' ? uploaded.slice(0,1) : [...node.ecomItems,...uploaded].slice(0,limit);
                node.runError = '';
                notify(options,node,true);
            } catch(error){ options.toast?.(error.message || '图片上传失败'); }
            finally { fileInput.value = ''; }
            event.stopPropagation();
        });
        root.querySelectorAll('[data-ecom-remove]').forEach(button => button.addEventListener('click',event => {
            node.ecomItems.splice(Number(button.dataset.ecomRemove),1);
            notify(options,node,true);
            event.stopPropagation();
        }));
        root.querySelector('[data-ecom-action="run-scene"]')?.addEventListener('click',event => { event.stopPropagation(); options.runScene?.(node); });
        root.querySelector('[data-ecom-action="run-compose"]')?.addEventListener('click',event => { event.stopPropagation(); options.runCompose?.(node); });
        if(node.type === 'ecom-compose'){
            const summary = options.composeSummary?.(node) || {};
            const el = root.querySelector('[data-ecom-summary]');
            if(el) el.innerHTML = `<span>模特 ${Number(summary.model || 0)}</span><span>商品 ${Number(summary.product || 0)}</span><span>场景 ${Number(summary.scene || 0)}</span><span>动作 ${Number(summary.pose || 0)}</span>`;
        }
    }
    function mediaRefs(node, options={}){
        normalize(node);
        const extraItems = Array.isArray(options.extraItems) ? options.extraItems : [];
        const items = [...node.ecomItems, ...extraItems]
            .map(normalizeItem)
            .filter(item => item.url)
            .filter((item,index,list) => list.findIndex(candidate => candidate.url === item.url) === index);
        if(node.type === 'ecom-model'){
            return items.slice(0,node.ecomModelRole === 'subject' ? 2 : 1).map((item,index) => {
                const role = index === 1 ? 'model_identity' : node.ecomModelRole;
                return {...item,role,reference_type:role,reference_id:`${node.id}_${role}_${index + 1}`,instruction:node.ecomDescription || ''};
            });
        }
        if(node.type === 'ecom-product'){
            const primaryId = `${node.id}_product_1`;
            return items.map((item,index) => ({
                ...item,
                role:index === 0 ? node.ecomProductRole : 'detail',
                reference_type:index === 0 ? node.ecomProductRole : 'detail',
                reference_id:index === 0 ? primaryId : `${node.id}_detail_${index + 1}`,
                detail_target_id:index === 0 ? '' : primaryId,
                instruction:node.ecomDescription || '',
            }));
        }
        if(node.type === 'ecom-scene') return items.slice(0,1).map((item,index) => ({...item,role:'scene',reference_type:'scene',reference_id:`${node.id}_scene_${index + 1}`,instruction:node.scenePrompt || ''}));
        if(node.type === 'ecom-compose') return (node.generatedOutputs || []).map((item,index) => ({url:outputUrl(item),name:`ecommerce-compose-${index + 1}.png`,kind:'image'})).filter(item => item.url);
        return [];
    }

    window.CanvasEcommerceNodes = {
        TYPES,PRODUCT_ROLES,isType,isGenerator,isMediaOutput,canOutput,inputPorts,title,size,normalize,
        createNode,bodyHtml,bind,mediaRefs,outputUrl,
    };
})();
