(function(){
    'use strict';
    const SHOT_ROLES = new Set(['sketch','depth','reference']);
    const REALISM = '生成一张独立的实景摄影画面。严格保持当前镜头的景别、机位、透视、人物数量、位置比例、身体朝向、视线、肢体动作和遮挡关系；线稿约束空间与模特姿势，深度图还辅助核对有依据的衣片起伏，控制图不得出现在成片中。演员图只定义对应演员身份和外貌，服装、道具按演员编号绑定，禁止借用原始参考图中人物的脸和服装覆盖已指定资产。没有指定替换资产时，保留参考画面中可辨认的主体特征。';
    const REBUILD = '原始参考图只提供构图、环境语义、色彩与光线氛围证据：逐一还原对应画面的主色、色温、明暗分布、曝光、光源方向、软硬程度、阴影和空气感，禁止擅自改成统一滤镜。背景必须依据这些证据从零重新生成高清真实材质、空间结构和自然细节。禁止以原图为底板扩图、超分辨率放大、修补或直接沿用原背景像素；不得复制低清模糊、压缩噪点、涂抹纹理。保留合理的光学景深，不能把背景重建理解为所有平面都锐化。';
    const USER_SCENE='用户场景图是唯一的背景身份与空间依据：固定建筑结构、门窗/柱体位置、墙地材质、家具与地标必须保持一致，不得融合其他候选背景，也不能换回原始参考照片的背景。根据线稿/深度图背景特征，在所选用户场景内使用匹配位置拍摄，保持对应机位、景别、透视、人物落点和遮挡。原始参考照片只提供该镜头的色彩与光线氛围：将其主色、色温、曝光、光源方向、明暗分布、阴影软硬和空气感应用到用户场景中，允许重新布光但不得因此改变场景几何与材质身份。高清重建指在此固定场景和位置重新渲染真实细节，不是重新设计环境；禁止使用模糊原图底板扩图、放大或涂抹背景。无彩色参考时沿用用户场景的合理色光，不从灰度控制图推断颜色。';

    // 适配一键复刻 v3.1 的材质与身份规则；分镜保持自己的图号、多演员和镜头空间契约。
    function fidelityPrompt(refs){
        const has=role=>refs.some(ref=>ref.inputRole===role);
        const hasActor=refs.some(ref=>/^actor-\d+$/.test(ref.inputRole));
        const hasOutfit=refs.some(ref=>/^outfit-\d+$/.test(ref.inputRole));
        return [
            '【人物与服装高保真：按当前资产映射分别使用】各演员及其服装、道具严格按编号分别绑定，多张同角色图片只作为对应资产的互补证据，不混脸、不串衣、不增加人物。身份、服装设计、动作结构、场景与色光各归其来源，任何一张参考图都不能覆盖所有属性。用户明确指定的换装范围与保留项优先于默认范围，其余属性仍按角色分工。',
            hasActor ? '演员参考只定义对应人物的五官比例、脸型、年龄感、妆容、发型、肤色与身体特征，不借用服装参考中其他模特的脸和身材，也不继承演员照片的站姿、背景或棚拍光。保留身份特征与自然不对称，不美化重塑、不统一瘦脸或改变年龄；表情动作、头脸朝向与视线服从当前镜头。' : '未连接演员参考时，保留当前彩色参考中可辨认的人物身份；只有线稿/深度时不把中性人偶或灰度解释为指定身份和肤色，按生成需求建立自然人物，同批保持一致。',
            '人物质感随景别和实际可见尺度呈现：近景保留自然皮肤纹理、细小肤色变化、唇部与眼睑结构、发丝层次；远景保留可信轮廓和整体受光，不强加看不见的毛孔。避免磨皮蜡像、塑料皮肤、过度锐化和凭空增加斑点。',
            hasOutfit ? '【服装提取与换装边界】服装参考只提供对应目标衣物的类别、版型、颜色、材质、织纹、纹样、领袖、门襟、口袋、下摆、缝线和装饰。默认只替换主要目标衣物对应区域，不因参考同时出现鞋包、下装或内搭就自动替换整套；未指定替换的衣物与配饰优先保留对应演员参考，缺省时以当前彩色镜头参考为补充。完整去除待换旧衣的款式与纹样，不只换色、不在旧衣外叠贴新衣。平铺/人台图转成真实穿着，保持衣长、袖型、开合与图案比例，不复制衣架、人台、包装折痕或平铺轮廓；他人穿着图只提取衣物设计，不沿用其动作产生的暂时褶皱。保留设计性百褶、压褶、抽褶、绗缝和结构缝线；不可见细节只作最小一致补全，不新增无依据的口袋与装饰。' : '未指定服装参考时，保留对应演员参考的服装设计；缺省时采用当前彩色镜头参考中可辨认的服装，不凭灰度控制图猜测衣色或新造纹样。无彩色资产时按生成需求确定服装。',
            has('depth') ? '【有依据的衣片褶皱复刻】深度图除姿势与空间外，也用于核对清楚可辨认的衣物起伏；灰度只表示相对深度，不是衣色、肤色、亮度或材质，人物深度图主体外纯黑区域不代表黑色背景。在新旧服装可对应衣片内，保留有证据的褶皱锚点、起止点、走向、曲率、折峰折谷、宽窄间距、分叉交汇和叠压层级，不任意抹平。对应彩色镜头参考只辅助核对形状，不借用旧衣纹样；深度被平滑、遮挡或缺少细褶证据时，仅按可见受力补全，不凭空逐褶编造，也不把均匀灰度渐变当折痕。' : '【按姿势形成衣片褶皱】当前没有深度图，不要求逐褶对齐不存在的深度证据。线稿只约束可辨认动作、轮廓与接触点，不把线条当织纹；结合当前彩色镜头参考的可见起伏与面料受力形成褶皱，不复制服装参考模特另一套动作的暂时褶皱。',
            '逐区核对肩部牵拉、腋下挤压、肘内堆褶、肘外拉伸、袖口收束、胸腹牵引、腰侧堆叠、手与包带压痕、下摆垂坠，锚定在对应身体部位和真实接触点。先匹配衣片起伏，再呈现新面料织纹、印花、缝线与光泽；图案随折峰折谷弯曲、缩短和遮挡，不能把旧照片阴影当新面料贴图。长袖变无袖、衣长/松量或厚度变化导致起伏不成立时，仅对不对应衣片及必要材料适配处局部调整；露出皮肤不得残留袖褶，不能为保留旧褶皱把新衣做成旧款。保持新衣结构性领袖与设计性褶裥。',
            '【全主体重打光与材质响应】服从本镜头已确定的场景位置与色光来源，对脸部鼻影、眼窝、下颌、颈部、手背、发丝、全部衣物与配饰一起重新形成受光，消除各资产照片不属于当前环境的补光、高光和阴影。保持皮肤与服装固有颜色，允许环境光带来真实冷暖明暗，不锁死源图 RGB，不靠全身统一染色或压暗融合。依据面料呈现织纹尺度、厚度、垂坠和粗糙度：棉麻、针织、丝缎、皮革各有反光，皮肤、头发、金属和玻璃也分别响应，不能全都塑料亮面。',
            '人物与服装的清晰度、景深、颗粒和边缘过渡须与当前镜头一致，去除旧背景污染、白边黑边、重影和机械轮廓光。手指与衣物、包带与身体、脚底与地面或身体与座面的接触可信；投影方向和软硬服从局部光源，禁止悬浮、双重阴影、断裂配饰与粘连手指。以上质感增强不改变镜头机位、人物数量、姿势、遮挡及已选场景，不要求沿用源图像素。'
        ].join('\n');
    }

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
            built.prompt=[built.prompt,REALISM,matched.sceneMatch ? USER_SCENE : assets.some(ref=>ref.role==='reference') ? REBUILD : '依照线稿/深度图重建真实立体空间，使用指定场景的材质与光线；没有色彩参考时采用自然且物理合理的摄影光线。',matchGuide,fidelityPrompt(built.refs),'只输出当前镜头的一张完整照片，禁止拼贴、多格分镜、线稿、灰度深度图、文字编号和水印。'].filter(Boolean).join('\n');
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
