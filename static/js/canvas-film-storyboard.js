(function(){
    'use strict';
    const SHOT_ROLES = new Set(['sketch','depth','reference']);
    const REALISM = '生成一张独立的实景摄影画面。严格保持当前镜头的景别、机位、透视、人物数量、位置比例、身体朝向、视线、肢体动作和遮挡关系；线稿/深度图只约束空间与模特姿势，不得出现在成片中。演员图只定义对应演员身份和外貌，服装、道具按演员编号绑定，禁止借用原始参考图中人物的脸和服装覆盖已指定资产。没有指定替换资产时，保留参考画面中可辨认的主体特征。';
    const REBUILD = '原始参考图只提供构图、环境语义、色彩与光线氛围证据：逐一还原对应画面的主色、色温、明暗分布、曝光、光源方向、软硬程度、阴影和空气感，禁止擅自改成统一滤镜。背景必须依据这些证据从零重新生成高清真实材质、空间结构和自然细节。禁止以原图为底板扩图、超分辨率放大、修补或直接沿用原背景像素；不得复制低清模糊、压缩噪点、涂抹纹理。保留合理的光学景深，不能把背景重建理解为所有平面都锐化。';
    const USER_SCENE='用户场景图是唯一的背景身份与空间依据：固定建筑结构、门窗/柱体位置、墙地材质、家具与地标必须保持一致，不得融合其他候选背景，也不能换回原始参考照片的背景。根据线稿/深度图背景特征，在所选用户场景内使用匹配位置拍摄，保持对应机位、景别、透视、人物落点和遮挡。原始参考照片只提供该镜头的色彩与光线氛围：将其主色、色温、曝光、光源方向、明暗分布、阴影软硬和空气感应用到用户场景中，允许重新布光但不得因此改变场景几何与材质身份。高清重建指在此固定场景和位置重新渲染真实细节，不是重新设计环境；禁止使用模糊原图底板扩图、放大或涂抹背景。无彩色参考时沿用用户场景的合理色光，不从灰度控制图推断颜色。';

    function plans(node, assets){
        const refs=window.CanvasFilmNodes.assetList(node,assets).filter(ref=>ref.url && (!ref.kind || ref.kind==='image'));
        const shared=refs.filter(ref=>!SHOT_ROLES.has(ref.inputRole));
        const controls=refs.filter(ref=>['sketch','depth'].includes(ref.inputRole));
        const photos=refs.filter(ref=>ref.inputRole==='reference');
        const make=(items,index,source)=>({index,source:source || items.find(ref=>SHOT_ROLES.has(ref.inputRole)) || items[0],assets:items.map(ref=>({...ref,role:ref.inputRole}))});
        if(node.storyboardMode!=='batch'){
            if(!refs.length && !String(node.prompt || '').trim()) throw new Error('请连接线稿、深度图或参考图，或输入生成需求');
            return Array.from({length:Math.max(1,Math.min(4,Number(node.count)||1))},(_,index)=>make(refs,index));
        }
        if(!controls.length && !photos.length) throw new Error('批量模式请连接线稿分镜、深度图或参考图，可直接连接编组输出');
        if(controls.length && photos.length>1 && photos.length!==controls.length) throw new Error(`已连接 ${controls.length} 张线稿/深度图和 ${photos.length} 张参考图。参考图需为 1 张共用色光，或与镜头等量按顺序配对`);
        const sources=controls.length ? controls : photos;
        return sources.map((source,index)=>make([...shared,source,...(controls.length && photos.length ? [photos[photos.length===1 ? 0 : index]] : [])],index,source));
    }
    function summary(node, assets){
        try {
            const items=plans(node,assets);
            const scenes=new Set(items.flatMap(plan=>plan.assets.filter(ref=>ref.role==='scene').map(ref=>ref.url))).size;
            return (node.storyboardMode==='batch' ? `已识别 ${items.length} 个镜头 · 每镜 1 张 · 共用演员与服化道` : `单图合成 · 生成 ${items.length} 张`)+(scenes ? ` · AI 匹配 ${scenes} 张场景图` : '');
        } catch(error){ return error.message; }
    }
    function createPreparer(node, options={}){
        // 每次点击独立快照与缓存，输入或全局参数变化不会复用上一批控制图。
        const snapshot={...node};
        const cache=new Map();
        let depthQueue=Promise.resolve();
        let sceneMatching=null;
        return async plan=>{
            let matched=plan;
            if(plan.assets.some(ref=>ref.role==='scene')){
                if(plan.sceneMatch && plan.assets.some(ref=>ref.role==='scene' && ref.url===plan.sceneMatch.sceneUrl)){
                    matched={...plan,assets:plan.assets.filter(ref=>ref.role!=='scene' || ref.url===plan.sceneMatch.sceneUrl)};
                } else {
                    if(!sceneMatching){
                        sceneMatching=window.CanvasFilmSceneMatcher.matchPlans(snapshot,options.plans || [plan],{
                            fetch:options.matchFetch,onProgress:message=>options.onProgress?.(plan,message)
                        }).then(matches=>{ options.onSceneMatches?.(matches); return matches; });
                    }
                    matched=(await sceneMatching).find(item=>item.index===plan.index);
                    if(!matched) throw new Error('场景匹配未包含当前镜头');
                }
            }
            let assets=matched.assets.map(ref=>({...ref}));
            const explicitControl=assets.some(ref=>['sketch','depth'].includes(ref.role));
            if(!explicitControl){
                const depths=await Promise.all(assets.filter(ref=>ref.role==='reference').map(async ref=>{
                    if(!cache.has(ref.url)){
                        const work=depthQueue.then(()=>{
                            options.onProgress?.(plan,'正在提取参考图深度');
                            return options.depth(ref, message=>options.onProgress?.(plan,message));
                        });
                        cache.set(ref.url,work);
                        depthQueue=work.catch(()=>{});
                    }
                    const depth=await cache.get(ref.url);
                    if(!depth?.url) throw new Error('参考图未返回深度图，请检查深度组件后重试');
                    return {...depth,kind:'image',role:'depth'};
                }));
                assets=[...assets,...depths];
            }
            const limit=window.CanvasFilmNodes.modelRule(snapshot.apiProvider,snapshot.model).maxImages;
            if(assets.length>limit) throw new Error(`镜头 ${plan.index+1} 需要 ${assets.length} 张资产，当前模型最多 ${limit} 张，请减少共用资产`);
            const built=window.CanvasFilmNodes.buildPrompt(snapshot,assets);
            built.refs=built.refs.map(ref=>({...ref,role:ref.inputRole==='depth' ? 'control_map' : ref.role,
                role_label:ref.inputRole==='scene' ? '选定用户场景：锁定空间结构、材质与地标，在匹配位置重新布光' : ref.inputRole==='depth' ? '深度图：只控制模特姿势与空间结构' : ref.inputRole==='reference' ? (matched.sceneMatch ? '原始参考图：色彩光线迁移到用户场景，不使用此图背景' : '原始参考图：只参考构图色彩光线，背景从零重建') : ref.role_label}));
            built.sceneMatch=matched.sceneMatch || null;
            const matchGuide=matched.sceneMatch ? `场景取景匹配：位置=${matched.sceneMatch.location}；机位与背景结构=${matched.sceneMatch.framing}；光线色彩迁移=${matched.sceneMatch.lighting}；匹配依据=${matched.sceneMatch.reason}。` : '';
            built.prompt=[built.prompt,REALISM,matched.sceneMatch ? USER_SCENE : assets.some(ref=>ref.role==='reference') ? REBUILD : '依照线稿/深度图重建真实立体空间，使用指定场景的材质与光线；没有色彩参考时采用自然且物理合理的摄影光线。',matchGuide,'只输出当前镜头的一张完整照片，禁止拼贴、多格分镜、线稿、灰度深度图、文字编号和水印。'].filter(Boolean).join('\n');
            return built;
        };
    }
    function alignPorts(root){
        if(!root?.querySelectorAll) return;
        const roots=root.matches?.('.film-storyboard-node,.smart-film-storyboard-node') ? [root] : root.querySelectorAll('.film-storyboard-node,.smart-film-storyboard-node');
        roots.forEach(el=>{
            el.querySelectorAll('.film-role-port').forEach(port=>{
                const row=el.querySelector(`.film-input-row[data-input-role="${port.dataset.inputRole}"]`);
                const parent=port.offsetParent;
                if(!row || !parent?.offsetWidth) return;
                const scale=parent.getBoundingClientRect().width/parent.offsetWidth;
                if(!scale) return;
                const p=port.getBoundingClientRect(),r=row.getBoundingClientRect();
                const delta=(r.top+r.height/2-p.top-p.height/2)/scale;
                if(Math.abs(delta)>.1) port.style.top=`${port.offsetTop+delta}px`;
            });
        });
    }
    window.CanvasFilmStoryboard={plans,summary,createPreparer,alignPorts};
})();
