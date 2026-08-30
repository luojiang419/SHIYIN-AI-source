(function(){
    'use strict';

    const DEFAULT_PANORAMA_PROMPT = '生成一个完整球面 720° 全景 VR 场景，使用标准 2:1 等距柱状投影，水平左右边缘像素级无缝衔接，上下极点自然连续，无接缝、无重复主体、无文字水印；空间结构真实、尺度统一、光照方向一致，封闭场景保留合理出入口。';
    const DEFAULT_RELIGHT_PROMPT = '只重塑原图的光照、阴影、色温和氛围，严格保持主体身份、五官、姿势、服装、材质、构图、机位、背景结构、文字与标志不变，不新增或删除任何物体。';
    const DEFAULT_ANGLE_PROMPT = 'Image 1 is one frozen physical 3D scene. Re-render that same world from the requested camera; change camera extrinsics only.';
    const DEFAULT_POSE_REPLICATE_PROMPT = [
        'POSE REPLICATION TASK: Transfer the exact body pose from the action reference to the person in the target image.',
        '',
        'REFERENCE ORDER:',
        '- Image 1: DWPose skeleton extracted from the action reference. Use it as the precise joint-position constraint.',
        '- Image 2: Original action reference. Use it to understand body orientation, hand gestures and occlusion.',
        '- Image 3: Target image. Preserve this person and this scene.',
        '',
        'REQUIREMENTS:',
        '1. Rebuild the target person with the exact pose from Images 1 and 2: head angle, gaze, shoulders, elbows, wrists, fingers, torso, hips, knees and feet.',
        '2. Preserve the target identity, face, hairstyle, body type, clothing, accessories, shoes, background, camera, lighting and image style.',
        '3. Do not copy the source person identity, clothing or background.',
        '4. Keep anatomical left/right semantics; never mirror the pose.',
        '5. Produce a photorealistic result with natural anatomy, correct limb connections and no extra fingers or limbs.'
    ].join('\n');
    const DWPOSE_MODEL_WAIT_TIMEOUT_MS = 15 * 60 * 1000;
    const panoramaStates = new WeakMap();
    const poseTasks = new Map();

    function esc(value){
        return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
    }
    function clamp(value, min, max){ return Math.max(min, Math.min(max, Number(value) || 0)); }
    function nameFromUrl(url, fallback='image.png'){
        try {
            const pathname = new URL(String(url || ''), location.href).pathname;
            return decodeURIComponent(pathname.split('/').pop() || fallback);
        } catch(_) { return fallback; }
    }
    function sourceSignature(item){
        if(!item?.url) return '';
        return `${item.url}|${item.name || ''}|${item.natural_w || ''}x${item.natural_h || ''}`;
    }
    async function responseError(response, fallback){
        const data = await response.clone().json().catch(() => null);
        return data?.detail || data?.error || await response.text().catch(() => '') || fallback;
    }
    async function uploadBlob(blob, filename){
        const form = new FormData();
        form.append('files', blob, filename || 'canvas-reference.png');
        const response = await fetch('/api/ai/upload', {method:'POST', body:form});
        if(!response.ok) throw new Error(await responseError(response, '参考图上传失败'));
        const data = await response.json();
        const file = data.files?.[0];
        if(!file?.url) throw new Error('上传接口没有返回图片');
        return {...file, kind:'image'};
    }
    async function uploadFile(file){
        if(!file) throw new Error('请选择图片');
        if(!String(file.type || '').startsWith('image/')) throw new Error('仅支持图片文件');
        return uploadBlob(file, file.name || 'panorama.png');
    }
    function panoramaSource(node, options){
        const upstream = options.getInputImage?.(node);
        if(upstream?.url) return upstream;
        if(node.panoramaSourceUrl) return {
            url:node.panoramaSourceUrl,
            name:node.panoramaSourceName || nameFromUrl(node.panoramaSourceUrl, 'panorama.png'),
            natural_w:node.panoramaSourceWidth || 0,
            natural_h:node.panoramaSourceHeight || 0,
            kind:'image'
        };
        return null;
    }
    function poseSource(node, options, inputRole=''){
        const upstream = options.getInputImage?.(node, inputRole);
        if(upstream?.url) return upstream;
        if(node.poseSourceUrl) return {
            url:node.poseSourceUrl,
            name:node.poseSourceName || nameFromUrl(node.poseSourceUrl, 'pose-source.png'),
            natural_w:node.poseSourceWidth || 0,
            natural_h:node.poseSourceHeight || 0,
            kind:'image'
        };
        return null;
    }
    function editSource(node, options, prefix){
        const upstream = options.getInputImage?.(node);
        if(upstream?.url) return upstream;
        const url = node[`${prefix}SourceUrl`];
        if(!url) return null;
        return {
            url,
            name:node[`${prefix}SourceName`] || nameFromUrl(url, `${prefix}-source.png`),
            natural_w:node[`${prefix}SourceWidth`] || 0,
            natural_h:node[`${prefix}SourceHeight`] || 0,
            kind:'image'
        };
    }
    function specialTitle(node){
        const type = node?.specialType || node?.type;
        if(type === 'dwpose') return '动作提取';
        if(type === 'pose-replicate' || type === 'poseReplicate') return '一键复刻';
        if(type === 'relight') return '灯光重塑';
        if(type === 'angle') return '角度调整';
        return '720°取景器';
    }
    function outputItem(node){
        const item = Array.isArray(node?.images) ? node.images.find(img => img?.url) : null;
        if(item?.url) return item;
        if(node?.outputUrl) return {url:node.outputUrl, name:node.outputName || 'reference.png', kind:'image', natural_w:node.outputWidth || 0, natural_h:node.outputHeight || 0};
        return null;
    }
    function setOutputItem(node, file, options){
        const item = {...file, kind:'image'};
        if(options.smart){
            node.images = [item];
            node.title = specialTitle(node);
        } else {
            node.outputUrl = item.url;
            node.outputName = item.name || 'reference.png';
            node.outputWidth = item.natural_w || 0;
            node.outputHeight = item.natural_h || 0;
        }
        options.onOutput?.(node, item);
    }
    function clearOutputItem(node, options){
        const hadOutput = Boolean(outputItem(node)?.url);
        if(options.smart) node.images = [];
        delete node.outputUrl;
        delete node.outputName;
        delete node.outputWidth;
        delete node.outputHeight;
        delete node.specialGeneratedSourceSignature;
        delete node.specialGeneratedControlSignature;
        if(hadOutput) options.onOutput?.(node, null);
    }
    function normalizePanorama(node){
        if(!node.panoramaPrompt) node.panoramaPrompt = DEFAULT_PANORAMA_PROMPT;
        node.panoramaYaw = Number.isFinite(Number(node.panoramaYaw)) ? Number(node.panoramaYaw) : 0;
        node.panoramaPitch = clamp(Number.isFinite(Number(node.panoramaPitch)) ? node.panoramaPitch : 0, -85, 85);
        node.panoramaFov = clamp(Number.isFinite(Number(node.panoramaFov)) ? node.panoramaFov : 72, 35, 100);
        node.panoramaAspect = ['16:9','9:16','1:1','4:3','3:4'].includes(node.panoramaAspect) ? node.panoramaAspect : '16:9';
        node.mannequinX = clamp(Number.isFinite(Number(node.mannequinX)) ? node.mannequinX : 0.5, 0.04, 0.96);
        node.mannequinY = clamp(Number.isFinite(Number(node.mannequinY)) ? node.mannequinY : 0.68, 0.12, 0.96);
        node.mannequinScale = clamp(Number.isFinite(Number(node.mannequinScale)) ? node.mannequinScale : 0.32, 0.12, 0.7);
        node.panoramaResolution = ['1280x720','1024x1024','720x1280','1440x1080','1080x1440'].includes(node.panoramaResolution) ? node.panoramaResolution : '1280x720';
        return node;
    }
    function panoramaBodyHtml(node){
        normalizePanorama(node);
        const source = node.panoramaSourceUrl || '';
        const output = outputItem(node);
        return `<div class="special-node panorama-special" data-special-node="panorama">
            <input class="special-file-input" type="file" accept="image/*" data-special-file="panorama" hidden>
            <div class="special-stage-wrap" data-panorama-stage>
                <canvas class="special-panorama-canvas"></canvas>
                <canvas class="special-overlay-canvas"></canvas>
                <div class="special-empty ${source ? 'hidden' : ''}" data-panorama-empty><i data-lucide="scan-line"></i><strong>导入或连接 2:1 全景图</strong><span>拖动选角 · 滚轮变焦 · 点击放置人偶</span></div>
                <div class="special-angle-badge">水平 <b data-yaw-label>${Math.round(node.panoramaYaw)}°</b> · 俯仰 <b data-pitch-label>${Math.round(node.panoramaPitch)}°</b> · FOV <b data-fov-label>${Math.round(node.panoramaFov)}°</b></div>
            </div>
            <div class="special-toolbar">
                <button type="button" data-special-action="upload-panorama"><i data-lucide="upload"></i><span>导入全景</span></button>
                <button type="button" data-special-action="generate-panorama" ${node.panoramaGenerating ? 'disabled' : ''}><i data-lucide="${node.panoramaGenerating ? 'loader-2' : 'sparkles'}"></i><span>${node.panoramaGenerating ? '生成中' : '生成720°'}</span></button>
                <button type="button" data-special-action="toggle-mannequin" class="${node.mannequinEnabled ? 'active' : ''}"><i data-lucide="person-standing"></i><span>${node.mannequinEnabled ? '移除人偶' : '添加人偶'}</span></button>
                <button type="button" data-special-action="reset-view"><i data-lucide="rotate-ccw"></i><span>复位</span></button>
            </div>
            <div class="special-settings-grid">
                <label><span>画幅</span><select data-special-field="panoramaAspect"><option value="16:9" ${node.panoramaAspect === '16:9' ? 'selected' : ''}>16:9</option><option value="9:16" ${node.panoramaAspect === '9:16' ? 'selected' : ''}>9:16</option><option value="1:1" ${node.panoramaAspect === '1:1' ? 'selected' : ''}>1:1</option><option value="4:3" ${node.panoramaAspect === '4:3' ? 'selected' : ''}>4:3</option><option value="3:4" ${node.panoramaAspect === '3:4' ? 'selected' : ''}>3:4</option></select></label>
                <label><span>导出</span><select data-special-field="panoramaResolution"><option value="1280x720" ${node.panoramaResolution === '1280x720' ? 'selected' : ''}>1280×720</option><option value="1024x1024" ${node.panoramaResolution === '1024x1024' ? 'selected' : ''}>1024×1024</option><option value="720x1280" ${node.panoramaResolution === '720x1280' ? 'selected' : ''}>720×1280</option><option value="1440x1080" ${node.panoramaResolution === '1440x1080' ? 'selected' : ''}>1440×1080</option><option value="1080x1440" ${node.panoramaResolution === '1080x1440' ? 'selected' : ''}>1080×1440</option></select></label>
                <label class="special-range"><span>焦距</span><input type="range" min="35" max="100" step="1" value="${node.panoramaFov}" data-special-field="panoramaFov"></label>
                <label class="special-range ${node.mannequinEnabled ? '' : 'disabled'}"><span>人偶大小</span><input type="range" min="12" max="70" step="1" value="${Math.round(node.mannequinScale * 100)}" data-special-field="mannequinScale" ${node.mannequinEnabled ? '' : 'disabled'}></label>
            </div>
            <textarea class="special-prompt" data-special-field="panoramaPrompt" rows="2" placeholder="描述全景场景">${esc(node.panoramaPrompt)}</textarea>
            <div class="special-output-row">
                <span>${output?.url ? `位置参考图已就绪 · ${esc(output.name || 'reference.png')}` : '选择视角后导出，输出会作为下游位置参考图'}</span>
                <button type="button" class="special-primary" data-special-action="export-reference" ${node.panoramaExporting ? 'disabled' : ''}><i data-lucide="${node.panoramaExporting ? 'loader-2' : 'camera'}"></i><span>${node.panoramaExporting ? '合成中' : '导出参考图'}</span></button>
            </div>
        </div>`;
    }
    function poseBodyHtml(node){
        const output = outputItem(node);
        const status = node.poseStatus || (output?.url ? 'done' : 'idle');
        const label = status === 'running' ? (node.posePreparing || '正在提取身体、手部和面部关键点…') : status === 'failed' ? (node.poseError || '动作提取失败') : output?.url ? '骨架图已就绪，将自动传递给下游节点' : '连接或导入人物图片后自动提取骨架';
        return `<div class="special-node pose-special" data-special-node="dwpose">
            <input class="special-file-input" type="file" accept="image/*" data-special-file="dwpose" hidden>
            <div class="pose-preview ${output?.url ? 'has-output' : ''}">
                ${output?.url ? `<img src="${esc(output.url)}" alt="DWPose 骨架图" draggable="false">` : `<div class="special-empty"><i data-lucide="person-standing"></i><strong>DWPose 动作提取</strong><span>本地 CPU 推理 · 数据不离开设备</span></div>`}
                ${status === 'running' ? '<div class="pose-running"><i data-lucide="loader-2"></i></div>' : ''}
            </div>
            <div class="special-toolbar">
                <button type="button" data-special-action="upload-pose"><i data-lucide="upload"></i><span>导入人物图</span></button>
                <button type="button" data-special-action="retry-pose" ${status === 'running' ? 'disabled' : ''}><i data-lucide="refresh-cw"></i><span>重新提取</span></button>
                <button type="button" data-special-action="export-pose" ${!output?.url || status === 'running' ? 'disabled' : ''}><i data-lucide="square-arrow-out-up-right"></i><span>导出骨架图</span></button>
            </div>
            <div class="pose-status ${status}"><span class="pose-dot"></span><span>${esc(label)}</span></div>
            <div class="special-output-row"><span>${output?.url ? esc(output.name || 'dwpose.png') : '输出：黑底彩色骨架参考图'}</span><b>${output?.natural_w && output?.natural_h ? `${output.natural_w}×${output.natural_h}` : ''}</b></div>
        </div>`;
    }

    function director3dBodyHtml(node){
        return window.Director3DNode?.bodyHtml?.(node) || '<div class="special-empty"><strong>3D导演台加载失败</strong><span>请刷新页面后重试</span></div>';
    }

    function bindDirector3d(root, node, options={}){
        if(!root || !node || !window.Director3DNode) return;
        window.Director3DNode.bind(root, node, {
            ...options,
            uploadBlob: options.uploadBlob || uploadBlob,
            createDirectorOutputNode: options.createDirectorOutputNode,
        });
    }
    function poseReplicateImageCard(item, role, emptyIcon, emptyText){
        const url = item?.url || '';
        return `<div class="pose-replicate-column">
            <div class="pose-replicate-column-title">${role === 'pose-reference' ? '动作参考' : role === 'pose-skeleton' ? '姿势骨架' : '目标图'}</div>
            <div class="pose-replicate-input-card ${url ? 'has-image' : ''}" data-pose-replicate-slot="${role}">
                ${url ? `<img src="${esc(url)}" alt="${esc(role)}" draggable="false">` : `<i data-lucide="${emptyIcon}"></i><strong>${esc(emptyText)}</strong><span>${role === 'pose-skeleton' ? '连接动作参考后自动生成' : '请从对应端口连接图片'}</span>`}
            </div>
        </div>`;
    }
    function poseReplicateBodyHtml(node){
        const action = node.poseReferenceUrl ? {url:node.poseReferenceUrl} : null;
        const skeleton = node.poseSkeletonUrl ? {url:node.poseSkeletonUrl} : null;
        const target = node.targetImageUrl ? {url:node.targetImageUrl} : null;
        const status = node.poseStatus || 'idle';
        const ready = Boolean(action?.url && skeleton?.url && target?.url);
        const activeRuns = Math.max(0, Number(node.poseReplicateActiveRuns) || 0);
        const statusText = status === 'running'
            ? (node.posePreparing || '正在自动提取动作骨架…')
            : status === 'failed'
                ? (node.poseError || '动作骨架提取失败')
                : ready
                    ? '动作骨架和目标图已就绪，可连续点击并发抽卡'
                    : action?.url && !skeleton?.url
                        ? '动作参考已连接，等待骨架提取'
                        : '请连接动作参考和目标图';
        const ratios = ['1:1','16:9','9:16','4:3','3:4','3:2','2:3'];
        const resolutions = ['1k','2k','4k'];
        node.poseReplicateRatio = ratios.includes(node.poseReplicateRatio) ? node.poseReplicateRatio : '1:1';
        node.poseReplicateResolution = resolutions.includes(node.poseReplicateResolution) ? node.poseReplicateResolution : '2k';
        if(!node.poseReplicatePrompt) node.poseReplicatePrompt = DEFAULT_POSE_REPLICATE_PROMPT;
        return `<div class="special-node pose-replicate-special" data-special-node="pose-replicate">
            <div class="pose-replicate-inputs">
                ${poseReplicateImageCard(action, 'pose-reference', 'person-standing', '连接动作参考')}
                ${poseReplicateImageCard(skeleton, 'pose-skeleton', status === 'running' ? 'loader-2' : 'scan-line', status === 'running' ? '骨架提取中' : status === 'failed' ? '提取失败' : '等待自动提取')}
                ${poseReplicateImageCard(target, 'target-image', 'image', '连接目标图')}
            </div>
            <div class="pose-status ${status}"><span class="pose-dot"></span><span>${esc(statusText)}</span></div>
            <textarea class="special-prompt pose-replicate-prompt" data-pose-replicate-field="poseReplicatePrompt" rows="4" placeholder="复刻提示词">${esc(node.poseReplicatePrompt)}</textarea>
            <div class="pose-replicate-controls">
                <label><span>画幅</span><select data-pose-replicate-field="poseReplicateRatio">${ratios.map(value => `<option value="${value}" ${node.poseReplicateRatio === value ? 'selected' : ''}>${value}</option>`).join('')}</select></label>
                <label><span>分辨率</span><select data-pose-replicate-field="poseReplicateResolution">${resolutions.map(value => `<option value="${value}" ${node.poseReplicateResolution === value ? 'selected' : ''}>${value.toUpperCase()}</option>`).join('')}</select></label>
                <span class="pose-replicate-model-hint"><i data-lucide="sparkles"></i>使用当前图片生成模型</span>
            </div>
            <div class="special-output-row pose-replicate-run-row">
                <span>${activeRuns ? `${activeRuns} 个复刻任务正在并发生成` : '每次点击都会创建一个独立输出节点'}</span>
                <button type="button" class="special-primary" data-special-action="run-pose-replicate" ${ready ? '' : 'disabled'}><i data-lucide="wand-sparkles"></i><span>一键复刻</span></button>
            </div>
        </div>`;
    }

    const RELIGHT_DIRECTIONS = {
        left:['左侧主光','camera-left key light'], right:['右侧主光','camera-right key light'],
        top:['顶部光','top-down light'], bottom:['底部光','bottom-up light'],
        front:['正面柔光','frontal beauty light'], back:['逆光','backlight with controlled silhouette'],
        rim:['轮廓光','clean rim light around the subject']
    };
    const RELIGHT_MOODS = {
        natural:'自然真实光照', studio:'专业影棚布光', cinematic:'电影级层次光影',
        sunset:'日落金色时刻', night:'低调夜景照明', neon:'霓虹双色氛围'
    };
    const EDIT_RESOLUTIONS = ['1k','2k','4k'];
    const EDIT_QUALITIES = ['standard','high'];
    const EDIT_RATIOS = ['source','1:1','16:9','9:16','4:3','3:4'];
    function normalizeEditGeneration(node){
        node.editResolution = EDIT_RESOLUTIONS.includes(String(node.editResolution)) ? String(node.editResolution) : '2k';
        node.editQuality = EDIT_QUALITIES.includes(String(node.editQuality)) ? String(node.editQuality) : 'high';
        node.editRatio = EDIT_RATIOS.includes(String(node.editRatio)) ? String(node.editRatio) : 'source';
        node.editModel = String(node.editModel || '');
        return node;
    }
    function editGenerationControlsHtml(node){
        normalizeEditGeneration(node);
        return `<div class="special-settings-grid edit-generation-settings">
            <label><span>分辨率</span><select data-edit-field="editResolution"><option value="1k" ${node.editResolution === '1k' ? 'selected' : ''}>1K</option><option value="2k" ${node.editResolution === '2k' ? 'selected' : ''}>2K</option><option value="4k" ${node.editResolution === '4k' ? 'selected' : ''}>4K</option></select></label>
            <label><span>质量</span><select data-edit-field="editQuality"><option value="standard" ${node.editQuality === 'standard' ? 'selected' : ''}>标准</option><option value="high" ${node.editQuality === 'high' ? 'selected' : ''}>高质量</option></select></label>
            <label><span>输出画幅</span><select data-edit-field="editRatio"><option value="source" ${node.editRatio === 'source' ? 'selected' : ''}>跟随原图</option><option value="1:1" ${node.editRatio === '1:1' ? 'selected' : ''}>1:1</option><option value="16:9" ${node.editRatio === '16:9' ? 'selected' : ''}>16:9</option><option value="9:16" ${node.editRatio === '9:16' ? 'selected' : ''}>9:16</option><option value="4:3" ${node.editRatio === '4:3' ? 'selected' : ''}>4:3</option><option value="3:4" ${node.editRatio === '3:4' ? 'selected' : ''}>3:4</option></select></label>
            <label class="edit-model-field"><span>模型覆盖</span><input type="text" value="${esc(node.editModel)}" data-edit-field="editModel" placeholder="留空使用画布默认模型"></label>
        </div>`;
    }
    function normalizeRelight(node){
        node.relightDirection = RELIGHT_DIRECTIONS[node.relightDirection] ? node.relightDirection : 'left';
        node.relightTemperature = clamp(Number.isFinite(Number(node.relightTemperature)) ? node.relightTemperature : 18, -100, 100);
        node.relightIntensity = clamp(Number.isFinite(Number(node.relightIntensity)) ? node.relightIntensity : 68, 10, 100);
        node.relightSoftness = ['soft','balanced','hard'].includes(node.relightSoftness) ? node.relightSoftness : 'balanced';
        node.relightMood = RELIGHT_MOODS[node.relightMood] ? node.relightMood : 'cinematic';
        node.relightPreserve = node.relightPreserve !== false;
        node.relightNotes = String(node.relightNotes || '');
        return node;
    }
    function relightTemperatureText(value){
        const number = Number(value) || 0;
        if(number <= -55) return '冷蓝 7600K';
        if(number <= -15) return '清冷 6500K';
        if(number < 15) return '中性 5600K';
        if(number < 55) return '暖光 4300K';
        return '金色 3200K';
    }
    function buildRelightPrompt(node){
        normalizeRelight(node);
        const direction = RELIGHT_DIRECTIONS[node.relightDirection];
        const softness = node.relightSoftness === 'soft' ? '大面积柔光、阴影边缘柔和' : node.relightSoftness === 'hard' ? '硬质聚光、阴影轮廓清晰' : '软硬平衡、明暗过渡自然';
        const intensity = node.relightIntensity >= 80 ? '高强度主光' : node.relightIntensity >= 45 ? '中等强度主光' : '低强度补光';
        const preserve = node.relightPreserve ? '以原图为严格结构约束，只允许光照相关像素发生变化；人物身份、产品造型、纹理、文字和构图必须保持一致。' : '允许为了合理受光而轻微调整局部细节，但不得改变主体身份和核心造型。';
        return [
            DEFAULT_RELIGHT_PROMPT,
            `主光方向：${direction[0]}（${direction[1]}）。`,
            `光照参数：${intensity}，强度 ${Math.round(node.relightIntensity)}%，${relightTemperatureText(node.relightTemperature)}，${softness}。`,
            `氛围目标：${RELIGHT_MOODS[node.relightMood]}。阴影方向、接触阴影、反射、高光和环境色必须符合统一的三维光照逻辑。`,
            preserve,
            node.relightNotes ? `补充要求：${node.relightNotes.trim()}` : ''
        ].filter(Boolean).join('\n');
    }
    function relightPreviewStatusText(source, output){
        if(output?.url) return `灯光重塑结果已就绪 · ${output.name || 'relight.png'}`;
        if(source?.url) return `已连接 ${source.name || '图片'} · 调整参数后点击生成`;
        return '连接或导入一张图片，预览会直接显示在节点内';
    }
    function updateRelightPreview(root, node, options, source){
        const output = outputItem(node);
        const item = output || source;
        const stage = root.querySelector('[data-relight-stage]') || root.querySelector('[data-edit-stage]');
        const image = root.querySelector('[data-relight-preview]') || root.querySelector('[data-edit-preview]');
        const empty = root.querySelector('[data-relight-empty]') || root.querySelector('[data-edit-empty]');
        const overlay = root.querySelector('[data-relight-overlay]');
        const badge = root.querySelector('[data-relight-chip]') || root.querySelector('[data-edit-badge]');
        const status = root.querySelector('[data-relight-status]');
        const sourceLabel = root.querySelector('[data-relight-source-label]');
        const outputLabel = root.querySelector('[data-relight-output-label]');
        if(image){
            if(item?.url){
                const originalUrl = String(item.url);
                let displayUrl = originalUrl;
                try { displayUrl = options.resolveUrl?.(originalUrl) || originalUrl; } catch(_) {}
                image.dataset.originalSrc = originalUrl;
                image.onerror = () => {
                    if(image.src && image.src !== originalUrl && image.dataset.previewFallback !== originalUrl){
                        image.dataset.previewFallback = originalUrl;
                        image.src = originalUrl;
                        return;
                    }
                    image.hidden = true;
                };
                image.dataset.previewFallback = '';
                image.src = displayUrl;
                image.hidden = false;
            } else {
                image.removeAttribute('src');
                image.removeAttribute('data-original-src');
                image.dataset.previewFallback = '';
                image.hidden = true;
                image.onerror = null;
            }
        }
        if(empty) empty.toggleAttribute('hidden', Boolean(item?.url));
        if(stage) stage.classList.toggle('has-source', Boolean(item?.url));
        if(overlay){
            overlay.hidden = !source?.url || Boolean(output?.url);
            const temperature = Number(node.relightTemperature || 0);
            const color = temperature < -10 ? '104,166,255' : temperature > 10 ? '255,178,92' : '255,244,222';
            overlay.style.setProperty('--relight-color', color);
            overlay.style.setProperty('--relight-opacity', String(0.12 + clamp(node.relightIntensity, 10, 100) / 220));
            overlay.dataset.direction = node.relightDirection;
        }
        if(badge) badge.textContent = output?.url ? 'API 结果' : (source?.url ? '连接预览' : '等待输入');
        if(status) status.textContent = relightPreviewStatusText(source, output);
        if(sourceLabel) sourceLabel.textContent = source?.url ? `源图 · ${source.name || '已连接'}` : '未连接图片';
        if(outputLabel) outputLabel.textContent = output?.url ? `结果 · ${output.name || 'relight.png'}` : '等待结果';
        const temp = root.querySelector('[data-relight-temperature]'), intensity = root.querySelector('[data-relight-intensity]');
        if(temp) temp.textContent = relightTemperatureText(node.relightTemperature);
        if(intensity) intensity.textContent = `${Math.round(node.relightIntensity)}%`;
    }
    function markRelightChanged(root, node, options, source){
        if(outputItem(node)?.url) clearOutputItem(node, options);
        const status = root.querySelector('[data-relight-status]');
        if(status) status.textContent = source?.url ? '参数已更新，点击生成新的灯光结果' : '请先连接或导入图片';
        updateRelightPreview(root, node, options, source);
        notify(options, node, false);
    }
    function relightBodyHtml(node){
        normalizeRelight(node);
        normalizeEditGeneration(node);
        const output = outputItem(node), preview = output?.url || node.relightSourceUrl || '';
        const directions = [['top','上'],['left','左'],['front','正'],['right','右'],['bottom','下'],['rim','轮廓'],['back','逆光']];
        return `<div class="special-node edit-special relight-special" data-special-node="relight">
            <input class="special-file-input" type="file" accept="image/*" data-special-file="relight" hidden>
            <div class="relight-preview-panel">
                <div class="special-edit-stage relight-preview-shell ${preview ? 'has-source' : ''}" data-edit-stage data-relight-stage>
                    <img class="relight-preview-image" data-edit-preview data-relight-preview src="${esc(preview)}" alt="灯光重塑预览" draggable="false" ${preview ? '' : 'hidden'}>
                    <div class="special-empty relight-preview-empty" data-edit-empty data-relight-empty ${preview ? 'hidden' : ''}><i data-lucide="sun-medium"></i><strong>连接或导入一张图片</strong><span>预览会直接显示在节点内</span></div>
                    <div class="relight-preview-overlay" data-relight-overlay ${preview && !output?.url ? '' : 'hidden'}></div>
                    <div class="special-edit-badge relight-preview-chip" data-edit-badge data-relight-chip>${output?.url ? 'API 结果' : '连接预览'}</div>
                </div>
                <div class="relight-preview-meta">
                    <span data-relight-source-label>${preview ? `源图 · ${esc(node.relightSourceName || '已连接')}` : '未连接图片'}</span>
                    <span data-relight-output-label>${output?.url ? `结果 · ${esc(output.name || 'relight.png')}` : '等待结果'}</span>
                </div>
            </div>
            <div class="special-toolbar">
                <button type="button" data-special-action="upload-relight"><i data-lucide="upload"></i><span>导入图片</span></button>
                <span class="special-model-hint"><i data-lucide="cloud-cog"></i>画布默认图片模型</span>
            </div>
            ${editGenerationControlsHtml(node)}
            <div class="relight-direction-pad" aria-label="主光方向">
                ${directions.map(([value,label]) => `<button type="button" data-relight-direction="${value}" class="${node.relightDirection === value ? 'active' : ''}">${label}</button>`).join('')}
            </div>
            <div class="special-settings-grid edit-settings-grid">
                <label><span>氛围</span><select data-edit-field="relightMood">${Object.entries(RELIGHT_MOODS).map(([value,label]) => `<option value="${value}" ${node.relightMood === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>
                <label><span>光质</span><select data-edit-field="relightSoftness"><option value="soft" ${node.relightSoftness === 'soft' ? 'selected' : ''}>柔光</option><option value="balanced" ${node.relightSoftness === 'balanced' ? 'selected' : ''}>平衡</option><option value="hard" ${node.relightSoftness === 'hard' ? 'selected' : ''}>硬光</option></select></label>
                <label class="special-range"><span>色温</span><input type="range" min="-100" max="100" step="1" value="${node.relightTemperature}" data-edit-field="relightTemperature"><b data-relight-temperature>${esc(relightTemperatureText(node.relightTemperature))}</b></label>
                <label class="special-range"><span>强度</span><input type="range" min="10" max="100" step="1" value="${node.relightIntensity}" data-edit-field="relightIntensity"><b data-relight-intensity>${Math.round(node.relightIntensity)}%</b></label>
            </div>
            <label class="special-check"><input type="checkbox" data-edit-field="relightPreserve" ${node.relightPreserve ? 'checked' : ''}><span>严格保持人物/产品与构图不变</span></label>
            <textarea class="special-prompt" data-edit-field="relightNotes" rows="2" placeholder="可选：补充灯光颜色、窗影、舞台光等要求">${esc(node.relightNotes)}</textarea>
            <div class="special-output-row"><span data-relight-status>${output?.url ? `灯光重塑结果已就绪 · ${esc(output.name || 'relight.png')}` : '调整参数后点击生成，不会自动产生 API 费用'}</span><button type="button" class="special-primary" data-special-action="run-relight" ${node.specialRunning ? 'disabled' : ''}><i data-lucide="${node.specialRunning ? 'loader-2' : 'wand-sparkles'}"></i><span>${node.specialRunning ? '重塑中' : '生成重塑图'}</span></button></div>
        </div>`;
    }

    const ANGLE_AZIMUTHS = [
        [0,'正面','front view'],[45,'右前 45°','front-right quarter view'],[90,'右侧 90°','right side view'],[135,'右后 135°','back-right quarter view'],
        [180,'背面 180°','back view'],[225,'左后 225°','back-left quarter view'],[270,'左侧 270°','left side view'],[315,'左前 315°','front-left quarter view']
    ];
    function normalizeAngle(node){
        node.angleAzimuth = ((Number.isFinite(Number(node.angleAzimuth)) ? Number(node.angleAzimuth) : 45) % 360 + 360) % 360;
        // NBP 语义模式使用有符号水平角：左侧为负，右侧为正；保留 angleAzimuth 兼容旧画布。
        node.angleYaw = clamp(Number.isFinite(Number(node.angleYaw)) ? Number(node.angleYaw) : signedAngleAzimuth(node.angleAzimuth), -180, 180);
        node.angleAzimuth = (node.angleYaw + 360) % 360;
        node.angleElevation = clamp(Number.isFinite(Number(node.angleElevation)) ? node.angleElevation : 0, -30, 60);
        node.angleDistance = ['close','medium','wide'].includes(node.angleDistance) ? node.angleDistance : 'medium';
        node.angleLens = ['24','35','50','85'].includes(String(node.angleLens)) ? String(node.angleLens) : '50';
        node.angleSubject = ['person','product','scene'].includes(node.angleSubject) ? node.angleSubject : 'person';
        node.anglePreserve = node.anglePreserve !== false;
        node.angleGeometryMode = ['none','depth','director3d'].includes(node.angleGeometryMode) ? node.angleGeometryMode : 'none';
        node.angleDepthUrl = String(node.angleDepthUrl || '');
        node.angleDepthName = String(node.angleDepthName || '');
        node.angleDirectorCaptureUrl = String(node.angleDirectorCaptureUrl || '');
        node.angleDirectorCaptureName = String(node.angleDirectorCaptureName || '');
        node.angleNotes = String(node.angleNotes || '');
        return node;
    }
    function nearestAzimuth(value){
        const normalized = ((Number(value) || 0) % 360 + 360) % 360;
        return ANGLE_AZIMUTHS.reduce((best, item) => {
            const delta = Math.min(Math.abs(item[0] - normalized), 360 - Math.abs(item[0] - normalized));
            return !best || delta < best.delta ? {item, delta} : best;
        }, null).item;
    }
    function angleElevationText(value){
        const number = Number(value) || 0;
        if(number <= -15) return ['低机位','low-angle shot'];
        if(number <= 15) return ['平视','eye-level shot'];
        if(number <= 45) return ['俯视','elevated shot'];
        return ['高俯视','high-angle shot'];
    }
    function angleControlSignature(node){
        return [Math.round(Number(node.angleYaw)||0),Math.round(Number(node.angleElevation)||0),node.angleDistance,node.angleLens,node.angleSubject,node.anglePreserve,node.angleNotes,node.angleGeometryMode,node.angleDepthUrl,node.angleDirectorCaptureUrl,node.editResolution,node.editQuality,node.editRatio,node.editModel].join('|');
    }
    function signedAngleAzimuth(value){
        const normalized = ((Number(value) || 0) % 360 + 360) % 360;
        return normalized > 180 ? normalized - 360 : normalized;
    }
    function angleOrbitInstruction(value){
        const offset = signedAngleAzimuth(value), magnitude = Math.abs(offset);
        if(magnitude < 0.5) return 'Keep the camera at Image 1 azimuth 0°. This is the original camera ray.';
        if(magnitude === 180) return 'Relocate the camera on a same-radius half-orbit to the physically opposite side of the subject. Do not rotate the subject or world.';
        const axis = offset > 0
            ? 'toward +X, Image 1’s camera-right basis'
            : 'toward -X, Image 1’s camera-left basis';
        return `Physically relocate the camera on a same-radius horizontal arc ${magnitude}° ${axis}. Aim at the same 3D target. Signed azimuth: ${offset > 0 ? '+' : ''}${offset}°. Move the camera, not the subject.`;
    }
    function angleParallaxInstruction(value){
        const offset = signedAngleAzimuth(value), magnitude = Math.abs(offset);
        if(magnitude < 0.5) return 'REQUIRED PROJECTION: Preserve Image 1 projection because the requested orbit is 0°.';
        if(magnitude === 180) return 'REQUIRED NEW PROJECTION: Show true reverse-side surfaces, reverse-camera occlusion and half-orbit depth ordering. A source-matching view is invalid.';
        const side = offset > 0 ? '+X-facing' : '-X-facing';
        const hiddenSide = offset > 0 ? '-X-facing' : '+X-facing';
        const parallax = offset > 0 ? 'screen-left' : 'screen-right';
        const viewClass = magnitude <= 45 ? 'quarter-orbit' : magnitude <= 90 ? 'side-orbit' : 'rear-quarter orbit';
        return `REQUIRED NEW PROJECTION: The ${viewClass} must be unmistakable. Reveal ${side} surfaces, hide more ${hiddenSide} surfaces, rebuild occlusions, and shift near layers toward ${parallax} relative to far layers. A source-matching or near-copy view is invalid.`;
    }
    function angleSubjectLock(subject){
        if(subject === 'product') return 'OBJECT CHIRALITY LOCK: Keep asymmetric parts on their physical side. Preserve controls, fasteners, labels, logos and readable non-reversed text.';
        if(subject === 'scene') return 'SCENE TOPOLOGY LOCK: Keep walls, windows, doors, mirrors, furniture and props at fixed world coordinates. Preserve adjacency; complete newly visible architecture conservatively.';
        return 'ANATOMICAL CHIRALITY LOCK: Preserve anatomical left/right, head/body/gaze direction, hair part, jewelry side, hand-to-prop assignment, grip and crossed-leg order. Keep the person motionless; let the new camera change facial and body occlusion.';
    }
    function angleDirectionText(value){
        const yaw = Number(value) || 0;
        if(Math.abs(yaw) < 0.5) return '正面';
        return yaw < 0 ? `左侧 ${Math.abs(Math.round(yaw))}°` : `右侧 ${Math.abs(Math.round(yaw))}°`;
    }
    function buildAnglePrompt(node){
        normalizeAngle(node);
        const yaw = Math.round(Number(node.angleYaw) || 0);
        const azimuth = nearestAzimuth(node.angleAzimuth), elevation = angleElevationText(node.angleElevation);
        const distance = node.angleDistance === 'close' ? ['近景','close-up'] : node.angleDistance === 'wide' ? ['远景','wide shot'] : ['中景','medium shot'];
        const subject = node.angleSubject === 'product' ? 'the product and its asymmetric details' : node.angleSubject === 'scene' ? 'the same physical room and world layout' : 'the same person, identity and pose';
        const side = yaw < 0 ? 'camera-left' : yaw > 0 ? 'camera-right' : 'straight-on';
        const observerSide = yaw < 0 ? 'the subject’s anatomical LEFT side, looking diagonally across her body toward her RIGHT' : yaw > 0 ? 'the subject’s anatomical RIGHT side, looking diagonally across her body toward her LEFT' : 'straight in front of the subject';
        const screenOcclusion = yaw < 0
            ? 'her RIGHT shoulder is the near shoulder and must appear larger on image-left, while her LEFT shoulder recedes toward image-right'
            : yaw > 0
                ? 'her LEFT shoulder is the near shoulder and must appear larger on image-right, while her RIGHT shoulder recedes toward image-left'
                : 'both shoulders remain symmetric';
        const view = yaw === 0 ? 'front view' : `${Math.abs(yaw)}-degree ${side} three-quarter view`;
        const preserve = node.anglePreserve ? 'Keep identity, proportions, pose, clothing, materials, lighting and background consistent.' : 'Keep the design and world layout consistent while changing the viewpoint.';
        return [
            'CAMERA COORDINATE SYSTEM: Image 1 is the original reference; camera-right +X, left is camera-left and right is camera-right.',
            `Recreate ${subject} from a new camera position: ${view}. Place the camera at the same height and distance, ${elevation[1]}, ${distance[1]}, ${node.angleLens}mm perspective.`,
            angleOrbitInstruction(yaw),
            `OBSERVATION-SIDE ANCHOR: Place the camera on ${observerSide}; this is an observer/world coordinate, not a request to turn the subject. ${screenOcclusion}.`,
            `Show the target ${azimuth[2]} clearly; reveal the correct near-side surfaces and natural occlusion created by the camera move. Keep the horizon and perspective physically plausible.`,
            angleParallaxInstruction(yaw),
            angleSubjectLock(node.angleSubject),
            'RIGID SUBJECT LOCK: Keep the head, neck, shoulders, spine, hips, arms, hands and torso in the exact orientation and pose of Image 1. Keep the head yaw and gaze direction unchanged relative to the torso; a side view must come from camera relocation and occlusion, never from turning or twisting the person.',
            preserve,
            'CAMERA-ONLY CHANGE: Move the camera around a motionless subject and fixed world. Do not rotate, turn, twist, lean or re-pose the subject.',
            'WORLD COORDINATE LOCK: Preserve physical content, not Image 1 pixel positions. Each signed orbit is a new camera ray.',
            'MIRROR LOCK: Never flip, mirror or rotate Image 1; a source-matching or near-copy view is invalid.',
            'STYLE CONSISTENCY LOCK: Keep Image 1 color, lighting and material response consistent. COLOR MATCH CHECK: correct only global tone, never the camera viewpoint.',
            node.angleGeometryMode === 'depth' && node.angleDepthUrl ? 'GEOMETRY REFERENCE: Image 2 is a grayscale MiDaS relative-depth map. Use it only for near/far ordering, silhouette, occlusion and parallax; ignore its colors and do not reproduce it.' : '',
            node.angleGeometryMode === 'director3d' && node.angleDirectorCaptureUrl ? 'GEOMETRY REFERENCE: Image 2 is a 3D director render from the same character/scene. Use it for camera projection, proportions and occlusion; preserve Image 1 identity, clothing and materials.' : '',
            'If a previous accepted angle is provided after the geometry reference, use it only as continuity reference.',
            node.angleNotes ? `Additional requirements: ${node.angleNotes.trim()}` : ''
        ].filter(Boolean).join('\n');
    }
    function angleBodyHtml(node){
        normalizeAngle(node);
        normalizeEditGeneration(node);
        const output = outputItem(node), preview = output?.url || node.angleSourceUrl || '', azimuth = nearestAzimuth(node.angleAzimuth), elevation = angleElevationText(node.angleElevation);
        return `<div class="special-node edit-special angle-special" data-special-node="angle">
            <input class="special-file-input" type="file" accept="image/*" data-special-file="angle" hidden>
            <div class="angle-control-shell">
                <div class="angle-orbit angle-viewport-3d" data-angle-orbit aria-label="三维机位视图">
                    <div class="angle-grid-3d"><i class="angle-grid-line grid-x"></i><i class="angle-grid-line grid-y"></i><i class="angle-grid-line grid-z"></i></div>
                    <div class="angle-axis horizontal"></div><div class="angle-axis vertical"></div>
                    <svg class="angle-camera-trajectory" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                        <ellipse data-angle-trajectory cx="50" cy="50" rx="42" ry="24"></ellipse>
                        <line data-angle-sightline x1="50" y1="50" x2="50" y2="26"></line>
                    </svg>
                    <div class="angle-world-3d" data-angle-world>
                        <div class="angle-subject-preview angle-subject-3d"><img data-edit-preview src="${esc(preview)}" alt="角度调整参考" draggable="false" ${preview ? '' : 'hidden'}><i data-lucide="box" data-angle-empty ${preview ? 'hidden' : ''}></i></div>
                        <div class="angle-ground-3d"></div>
                    </div>
                    <div class="angle-camera-marker" data-angle-marker><i data-lucide="camera"></i><span class="angle-camera-depth" data-angle-depth>前</span></div>
                    <span class="angle-front-label">正面 0°</span><span class="angle-back-label">背面 180°</span><span class="angle-left-label">左侧 270°</span><span class="angle-right-label">右侧 90°</span>
                </div>
                <div class="angle-readout"><strong data-angle-azimuth>水平 ${esc(angleDirectionText(node.angleYaw))} · ${azimuth[1]}</strong><span data-angle-elevation>俯仰 ${Math.round(node.angleElevation)}° · ${elevation[0]}</span><em>左侧为负角度，右侧为正角度；拖拽视图可微调机位</em></div>
            </div>
            ${editGenerationControlsHtml(node)}
            <div class="special-toolbar"><button type="button" data-special-action="upload-angle"><i data-lucide="upload"></i><span>导入图片</span></button><span class="special-model-hint"><i data-lucide="cloud-cog"></i>Nano Banana Pro 语义机位模式</span></div>
            <div class="angle-preset-row">${ANGLE_AZIMUTHS.map(item => `<button type="button" data-angle-preset="${item[0]}" class="${nearestAzimuth(node.angleAzimuth)[0] === item[0] ? 'active' : ''}">${item[0]}°</button>`).join('')}</div>
            <div class="special-settings-grid edit-settings-grid">
                <label><span>几何参考</span><select data-edit-field="angleGeometryMode"><option value="none" ${node.angleGeometryMode === 'none' ? 'selected' : ''}>无（语义模式）</option><option value="depth" ${node.angleGeometryMode === 'depth' ? 'selected' : ''}>自动深度图</option><option value="director3d" ${node.angleGeometryMode === 'director3d' ? 'selected' : ''}>3D导演台截图</option></select></label>
                <label class="special-range wide"><span>水平角（左负右正）</span><input type="range" min="-180" max="180" step="1" value="${Math.round(node.angleYaw)}" data-edit-field="angleYaw"></label>
                <label class="special-range wide"><span>俯仰角</span><input type="range" min="-30" max="60" step="1" value="${node.angleElevation}" data-edit-field="angleElevation"></label>
                <label><span>景别</span><select data-edit-field="angleDistance"><option value="close" ${node.angleDistance === 'close' ? 'selected' : ''}>近景</option><option value="medium" ${node.angleDistance === 'medium' ? 'selected' : ''}>中景</option><option value="wide" ${node.angleDistance === 'wide' ? 'selected' : ''}>远景</option></select></label>
                <label><span>镜头</span><select data-edit-field="angleLens"><option value="24" ${node.angleLens === '24' ? 'selected' : ''}>24mm 广角</option><option value="35" ${node.angleLens === '35' ? 'selected' : ''}>35mm</option><option value="50" ${node.angleLens === '50' ? 'selected' : ''}>50mm 标准</option><option value="85" ${node.angleLens === '85' ? 'selected' : ''}>85mm 人像</option></select></label>
                <label><span>对象</span><select data-edit-field="angleSubject"><option value="person" ${node.angleSubject === 'person' ? 'selected' : ''}>人物</option><option value="product" ${node.angleSubject === 'product' ? 'selected' : ''}>产品/物体</option><option value="scene" ${node.angleSubject === 'scene' ? 'selected' : ''}>场景空间</option></select></label>
            </div>
            <label class="special-check"><input type="checkbox" data-edit-field="anglePreserve" ${node.anglePreserve ? 'checked' : ''}><span>严格锁定主体身份、造型与环境连续性</span></label>
            <textarea class="special-prompt" data-edit-field="angleNotes" rows="2" placeholder="可选：补充动作、视线或构图要求">${esc(node.angleNotes)}</textarea>
            <div class="angle-geometry-row"><span>${node.angleGeometryMode === 'depth' && node.angleDepthUrl ? `深度图已就绪 · ${esc(node.angleDepthName || 'depth.png')}` : node.angleGeometryMode === 'director3d' && node.angleDirectorCaptureUrl ? `导演台参考已就绪 · ${esc(node.angleDirectorCaptureName || 'director.png')}` : '可选：为更稳定的遮挡和透视生成几何参考'}</span><button type="button" data-special-action="generate-angle-depth" ${node.angleDepthGenerating ? 'disabled' : ''}><i data-lucide="${node.angleDepthGenerating ? 'loader-2' : 'layers-2'}"></i><span>${node.angleDepthGenerating ? '生成深度中' : '生成深度图'}</span></button></div>
            <div class="special-output-row"><span data-edit-status>${output?.url ? `新视角结果已就绪 · ${esc(output.name || 'angle.png')}` : '拖动圆环选机位，点击后才会调用 API'}</span><button type="button" class="special-primary" data-special-action="run-angle" ${node.specialRunning ? 'disabled' : ''}><i data-lucide="${node.specialRunning ? 'loader-2' : 'camera'}"></i><span>${node.specialRunning ? '生成中' : '生成新视角'}</span></button></div>
        </div>`;
    }

    function compile(gl, type, source){
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        if(!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) || 'WebGL shader failed');
        return shader;
    }
    function panoramaGl(canvas){
        const gl = canvas.getContext('webgl', {alpha:false, antialias:true, preserveDrawingBuffer:true});
        if(!gl) throw new Error('当前显卡或浏览器不支持全景取景');
        const vertex = compile(gl, gl.VERTEX_SHADER, `attribute vec2 p;varying vec2 v;void main(){v=p;gl_Position=vec4(p,0.,1.);}`);
        const fragment = compile(gl, gl.FRAGMENT_SHADER, `precision highp float;varying vec2 v;uniform sampler2D tex;uniform float aspect;uniform float tanHalf;uniform float yaw;uniform float pitch;const float PI=3.141592653589793;void main(){vec3 d=normalize(vec3(v.x*aspect*tanHalf,v.y*tanHalf,-1.));float cp=cos(pitch),sp=sin(pitch);d=vec3(d.x,cp*d.y-sp*d.z,sp*d.y+cp*d.z);float cy=cos(yaw),sy=sin(yaw);d=vec3(cy*d.x+sy*d.z,d.y,-sy*d.x+cy*d.z);float u=atan(d.x,-d.z)/(2.0*PI)+0.5;float vv=0.5-asin(clamp(d.y,-1.0,1.0))/PI;gl_FragColor=texture2D(tex,vec2(fract(u),clamp(vv,0.001,0.999)));}`);
        const program = gl.createProgram();
        gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program);
        if(!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) || 'WebGL program failed');
        gl.useProgram(program);
        const buffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW);
        const pos = gl.getAttribLocation(program, 'p');
        gl.enableVertexAttribArray(pos); gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);
        const texture = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.uniform1i(gl.getUniformLocation(program, 'tex'), 0);
        return {canvas, gl, program, buffer, texture, image:null, signature:'', loading:'', drag:null, contextLost:false, disposed:false};
    }
    function disposePanoramaCanvas(canvas){
        const state = canvas ? panoramaStates.get(canvas) : null;
        if(!state || state.disposed) return false;
        state.disposed = true;
        state.drag = null;
        try {
            const {gl} = state;
            if(gl && !gl.isContextLost()){
                if(state.texture) gl.deleteTexture(state.texture);
                if(state.buffer) gl.deleteBuffer(state.buffer);
                if(state.program) gl.deleteProgram(state.program);
                gl.getExtension('WEBGL_lose_context')?.loseContext();
            }
        } catch(_) {}
        panoramaStates.delete(canvas);
        return true;
    }
    function disposePanoramasIn(root){
        if(!root) return 0;
        const canvases = [];
        if(root.matches?.('.special-panorama-canvas')) canvases.push(root);
        root.querySelectorAll?.('.special-panorama-canvas').forEach(canvas => canvases.push(canvas));
        return canvases.reduce((count, canvas) => count + (disposePanoramaCanvas(canvas) ? 1 : 0), 0);
    }
    async function loadImage(url, resolveUrl){
        const src = resolveUrl?.(url) || url;
        const image = new Image();
        image.crossOrigin = 'anonymous';
        await new Promise((resolve, reject) => {
            image.onload = resolve;
            image.onerror = () => reject(new Error('全景图片加载失败'));
            image.src = src;
        });
        return image;
    }
    function setPanoramaTexture(state, image){
        const {gl, texture} = state;
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
        state.image = image;
    }
    function aspectNumber(value){
        const [w,h] = String(value || '16:9').split(':').map(Number);
        return w > 0 && h > 0 ? w / h : 16 / 9;
    }
    function fitCanvas(canvas, overlay, node){
        const stage = canvas.closest('[data-panorama-stage]');
        const width = Math.max(240, Math.round(stage?.clientWidth || 480));
        const height = Math.max(150, Math.round(width / aspectNumber(node.panoramaAspect)));
        stage.style.aspectRatio = String(aspectNumber(node.panoramaAspect));
        if(canvas.width !== width) canvas.width = width;
        if(canvas.height !== height) canvas.height = height;
        if(overlay){ overlay.width = width; overlay.height = height; }
    }
    function drawMannequin(ctx, width, height, node){
        ctx.clearRect(0, 0, width, height);
        if(!node.mannequinEnabled) return;
        const scale = clamp(node.mannequinScale, 0.12, 0.7) * height;
        const x = clamp(node.mannequinX, 0.04, 0.96) * width;
        const groundY = clamp(node.mannequinY, 0.12, 0.96) * height;
        const headR = scale * 0.09;
        const shoulderY = groundY - scale * 0.72;
        const hipY = groundY - scale * 0.35;
        ctx.save();
        ctx.lineCap = 'round'; ctx.lineJoin = 'round';
        ctx.shadowColor = 'rgba(0,0,0,.48)'; ctx.shadowBlur = Math.max(3, scale * 0.025);
        ctx.fillStyle = 'rgba(248,248,248,.88)';
        ctx.strokeStyle = 'rgba(35,35,35,.82)';
        ctx.lineWidth = Math.max(2, scale * 0.025);
        ctx.beginPath(); ctx.arc(x, groundY - scale * 0.86, headR, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x - scale*.13, shoulderY); ctx.lineTo(x + scale*.13, shoulderY); ctx.lineTo(x + scale*.1, hipY); ctx.lineTo(x - scale*.1, hipY); ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.lineWidth = Math.max(5, scale * 0.065);
        ctx.beginPath(); ctx.moveTo(x - scale*.11, shoulderY + scale*.04); ctx.lineTo(x - scale*.23, groundY - scale*.43); ctx.lineTo(x - scale*.18, groundY - scale*.25); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x + scale*.11, shoulderY + scale*.04); ctx.lineTo(x + scale*.23, groundY - scale*.43); ctx.lineTo(x + scale*.18, groundY - scale*.25); ctx.stroke();
        ctx.lineWidth = Math.max(6, scale * 0.075);
        ctx.beginPath(); ctx.moveTo(x - scale*.055, hipY); ctx.lineTo(x - scale*.075, groundY - scale*.16); ctx.lineTo(x - scale*.1, groundY); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x + scale*.055, hipY); ctx.lineTo(x + scale*.075, groundY - scale*.16); ctx.lineTo(x + scale*.1, groundY); ctx.stroke();
        ctx.shadowBlur = 0; ctx.fillStyle = 'rgba(24,24,24,.76)'; ctx.font = `700 ${Math.max(10, scale*.07)}px system-ui`; ctx.textAlign = 'center';
        ctx.fillText('位置参考', x, Math.min(height - 5, groundY + Math.max(13, scale*.1))); ctx.restore();
    }
    function renderPanorama(state, canvas, overlay, node){
        if(!state.image || state.disposed || state.contextLost || state.gl?.isContextLost?.()) return;
        fitCanvas(canvas, overlay, node);
        const {gl, program} = state;
        gl.viewport(0, 0, canvas.width, canvas.height); gl.useProgram(program);
        gl.uniform1f(gl.getUniformLocation(program, 'aspect'), canvas.width / Math.max(1, canvas.height));
        gl.uniform1f(gl.getUniformLocation(program, 'tanHalf'), Math.tan(clamp(node.panoramaFov, 35, 100) * Math.PI / 360));
        gl.uniform1f(gl.getUniformLocation(program, 'yaw'), Number(node.panoramaYaw || 0) * Math.PI / 180);
        gl.uniform1f(gl.getUniformLocation(program, 'pitch'), Number(node.panoramaPitch || 0) * Math.PI / 180);
        gl.drawArrays(gl.TRIANGLES, 0, 6); drawMannequin(overlay.getContext('2d'), overlay.width, overlay.height, node);
    }
    function updateAngleLabels(root, node){
        const yaw = root.querySelector('[data-yaw-label]'), pitch = root.querySelector('[data-pitch-label]'), fov = root.querySelector('[data-fov-label]');
        if(yaw) yaw.textContent = `${Math.round(node.panoramaYaw)}°`; if(pitch) pitch.textContent = `${Math.round(node.panoramaPitch)}°`; if(fov) fov.textContent = `${Math.round(node.panoramaFov)}°`;
    }
    async function ensurePanoramaSource(root, state, node, options){
        const source = panoramaSource(node, options), signature = sourceSignature(source), empty = root.querySelector('[data-panorama-empty]');
        empty?.classList.toggle('hidden', Boolean(signature));
        if(!signature || state.signature === signature || state.loading === signature) return;
        state.loading = signature;
        try {
            const image = await loadImage(source.url, options.resolveUrl);
            if(state.loading !== signature) return;
            setPanoramaTexture(state, image); state.signature = signature;
            renderPanorama(state, root.querySelector('.special-panorama-canvas'), root.querySelector('.special-overlay-canvas'), node);
        } catch(error) { options.toast?.(error.message || '全景图片加载失败'); }
        finally { if(state.loading === signature) state.loading = ''; }
    }
    async function exportReference(root, state, node){
        if(!state.image || state.disposed || state.contextLost || state.gl?.isContextLost?.()) throw new Error('全景取景器正在恢复，请稍后重试');
        const [width,height] = String(node.panoramaResolution || '1280x720').split('x').map(Number);
        const canvas = root.querySelector('.special-panorama-canvas'), overlay = root.querySelector('.special-overlay-canvas');
        const old = {w:canvas.width,h:canvas.height,ow:overlay.width,oh:overlay.height};
        try {
            canvas.width = Math.max(320, width || 1280); canvas.height = Math.max(320, height || 720); overlay.width = canvas.width; overlay.height = canvas.height;
            const {gl, program} = state;
            gl.viewport(0, 0, canvas.width, canvas.height); gl.useProgram(program);
            gl.uniform1f(gl.getUniformLocation(program, 'aspect'), canvas.width / canvas.height);
            gl.uniform1f(gl.getUniformLocation(program, 'tanHalf'), Math.tan(clamp(node.panoramaFov, 35, 100) * Math.PI / 360));
            gl.uniform1f(gl.getUniformLocation(program, 'yaw'), Number(node.panoramaYaw || 0) * Math.PI / 180);
            gl.uniform1f(gl.getUniformLocation(program, 'pitch'), Number(node.panoramaPitch || 0) * Math.PI / 180);
            gl.drawArrays(gl.TRIANGLES, 0, 6); drawMannequin(overlay.getContext('2d'), overlay.width, overlay.height, node);
            const merged = document.createElement('canvas'); merged.width = canvas.width; merged.height = canvas.height;
            const ctx = merged.getContext('2d'); ctx.drawImage(canvas, 0, 0); ctx.drawImage(overlay, 0, 0);
            const blob = await new Promise(resolve => merged.toBlob(resolve, 'image/png'));
            if(!blob) throw new Error('参考图合成失败');
            const file = await uploadBlob(blob, `panorama-reference-${Date.now()}.png`); file.natural_w = merged.width; file.natural_h = merged.height;
            return file;
        } finally {
            if(!state.disposed){
                canvas.width = old.w; canvas.height = old.h; overlay.width = old.ow; overlay.height = old.oh;
                renderPanorama(state, canvas, overlay, node);
            }
        }
    }
    function notify(options, node, render=false){ options.onChange?.(node, {render}); }
    function bindPanorama(root, node, options={}){
        if(!root || !node) return;
        normalizePanorama(node);
        const canvas = root.querySelector('.special-panorama-canvas'), overlay = root.querySelector('.special-overlay-canvas');
        if(!canvas || !overlay) return;
        let state;
        try { state = panoramaStates.get(canvas) || panoramaGl(canvas); } catch(error){ options.toast?.(error.message); return; }
        panoramaStates.set(canvas, state); ensurePanoramaSource(root, state, node, options);
        const renderNow = () => { renderPanorama(state, canvas, overlay, node); updateAngleLabels(root, node); };
        canvas.addEventListener('webglcontextlost', event => {
            if(state.disposed) return;
            event.preventDefault();
            state.contextLost = true;
        });
        canvas.addEventListener('webglcontextrestored', () => {
            if(state.disposed || !canvas.isConnected) return;
            const image = state.image, signature = state.signature;
            try {
                const restored = panoramaGl(canvas);
                Object.assign(state, restored, {image:null, signature, loading:''});
                if(image) setPanoramaTexture(state, image);
                renderNow();
            } catch(error){ options.toast?.(error.message || '全景取景器恢复失败'); }
        });
        const panoramaFileInput = root.querySelector('[data-special-file="panorama"]');
        if(panoramaFileInput) panoramaFileInput.onchange = async () => {
            try {
                const file = await uploadFile(panoramaFileInput.files?.[0]);
                node.panoramaSourceUrl = file.url; node.panoramaSourceName = file.name || 'panorama.png';
                node.panoramaSourceWidth = file.natural_w || 0; node.panoramaSourceHeight = file.natural_h || 0;
                state.signature = ''; await ensurePanoramaSource(root, state, node, options); notify(options, node, true);
            } catch(error){ options.toast?.(error.message); }
            finally { panoramaFileInput.value = ''; }
        };
        root.querySelectorAll('[data-special-field]').forEach(control => {
            control.addEventListener('pointerdown', e => e.stopPropagation());
            control.addEventListener(control.matches('textarea,input[type="range"]') ? 'input' : 'change', e => {
                e.stopPropagation(); const key = control.dataset.specialField; let value = control.value;
                if(key === 'panoramaFov') value = clamp(value, 35, 100); if(key === 'mannequinScale') value = clamp(value, 12, 70) / 100;
                node[key] = value; renderNow(); notify(options, node, false);
            });
        });
        root.querySelectorAll('[data-special-action]').forEach(button => {
            button.addEventListener('pointerdown', e => e.stopPropagation());
            button.addEventListener('click', async e => {
                e.preventDefault(); e.stopPropagation(); const action = button.dataset.specialAction;
                try {
                    if(action === 'upload-panorama'){
                        panoramaFileInput?.click(); return;
                    }
                    if(action === 'generate-panorama'){
                        if(!options.generatePanorama) throw new Error('当前画布未配置全景生成模型');
                        node.panoramaGenerating = true; notify(options, node, true);
                        const file = await options.generatePanorama(node, node.panoramaPrompt || DEFAULT_PANORAMA_PROMPT);
                        if(!file?.url) throw new Error('全景生成没有返回图片');
                        node.panoramaSourceUrl = file.url; node.panoramaSourceName = file.name || 'generated-panorama.png'; node.panoramaSourceWidth = file.natural_w || 0; node.panoramaSourceHeight = file.natural_h || 0; node.panoramaGenerating = false; notify(options, node, true); return;
                    }
                    if(action === 'toggle-mannequin'){ node.mannequinEnabled = !node.mannequinEnabled; renderNow(); notify(options, node, true); return; }
                    if(action === 'reset-view'){ node.panoramaYaw = 0; node.panoramaPitch = 0; node.panoramaFov = 72; renderNow(); notify(options, node, true); return; }
                    if(action === 'export-reference'){
                        node.panoramaExporting = true; button.disabled = true; const file = await exportReference(root, state, node);
                        node.panoramaExporting = false; setOutputItem(node, file, options); notify(options, node, true); options.toast?.('位置参考图已生成，可连接到下游节点');
                    }
                } catch(error){ node.panoramaGenerating = false; node.panoramaExporting = false; notify(options, node, true); options.toast?.(error.message || '操作失败'); }
            });
        });
        canvas.addEventListener('pointerdown', e => {
            if(e.button !== 0 || !state.image) return; e.preventDefault(); e.stopPropagation(); canvas.setPointerCapture?.(e.pointerId);
            const rect = canvas.getBoundingClientRect(), nx = (e.clientX - rect.left) / Math.max(1, rect.width), ny = (e.clientY - rect.top) / Math.max(1, rect.height);
            const mannequinHit = node.mannequinEnabled && Math.abs(nx - node.mannequinX) < node.mannequinScale * .28 && Math.abs(ny - node.mannequinY + node.mannequinScale * .42) < node.mannequinScale * .55;
            state.drag = {x:e.clientX,y:e.clientY,yaw:Number(node.panoramaYaw)||0,pitch:Number(node.panoramaPitch)||0,mannequin:mannequinHit,pointerId:e.pointerId,moved:false};
        });
        canvas.addEventListener('pointermove', e => {
            if(!state.drag || state.drag.pointerId !== e.pointerId) return; e.preventDefault(); e.stopPropagation(); const rect = canvas.getBoundingClientRect();
            state.drag.moved = state.drag.moved || Math.abs(e.clientX - state.drag.x) + Math.abs(e.clientY - state.drag.y) > 3;
            if(state.drag.mannequin){ node.mannequinX = clamp((e.clientX - rect.left) / Math.max(1, rect.width), .04, .96); node.mannequinY = clamp((e.clientY - rect.top) / Math.max(1, rect.height), .12, .96); }
            else { node.panoramaYaw = state.drag.yaw - (e.clientX - state.drag.x) * .2; node.panoramaPitch = clamp(state.drag.pitch + (e.clientY - state.drag.y) * .18, -85, 85); }
            renderNow();
        });
        const finish = e => { if(!state.drag) return; canvas.releasePointerCapture?.(state.drag.pointerId); state.lastDragMoved = Boolean(state.drag.moved); state.drag = null; notify(options, node, false); e?.stopPropagation?.(); };
        canvas.addEventListener('pointerup', finish); canvas.addEventListener('pointercancel', finish);
        canvas.addEventListener('click', e => { if(state.lastDragMoved){ state.lastDragMoved = false; return; } if(!node.mannequinEnabled) return; const rect = canvas.getBoundingClientRect(); node.mannequinX = clamp((e.clientX - rect.left) / Math.max(1, rect.width), .04, .96); node.mannequinY = clamp((e.clientY - rect.top) / Math.max(1, rect.height), .12, .96); renderNow(); notify(options, node, false); e.stopPropagation(); });
        canvas.addEventListener('wheel', e => { if(!state.image) return; e.preventDefault(); e.stopPropagation(); node.panoramaFov = clamp(Number(node.panoramaFov || 72) + Math.sign(e.deltaY) * 3, 35, 100); const slider = root.querySelector('[data-special-field="panoramaFov"]'); if(slider) slider.value = node.panoramaFov; renderNow(); notify(options, node, false); }, {passive:false});
        window.requestAnimationFrame(renderNow);
    }

    function sleep(milliseconds){ return new Promise(resolve => setTimeout(resolve, milliseconds)); }
    async function waitForPoseModel(node, options){
        const startedAt = Date.now();
        while(Date.now() - startedAt < DWPOSE_MODEL_WAIT_TIMEOUT_MS){
            const response = await fetch('/api/dwpose/status', {cache:'no-store'});
            if(!response.ok) throw new Error(await responseError(response, 'DWPose 模型状态读取失败'));
            const status = await response.json();
            if(status?.ready) return;
            if(status?.state === 'failed') throw new Error(status.message || 'DWPose 模型下载失败，请重新提取');
            const progress = Math.max(0, Math.min(1, Number(status?.progress) || 0));
            const progressText = progress > 0 ? ` ${Math.round(progress * 100)}%` : '';
            const message = String(status?.message || '正在准备 DWPose 模型');
            const nextLabel = `${message}${progressText}，完成后将自动提取骨架`;
            if(node.posePreparing !== nextLabel){ node.posePreparing = nextLabel; notify(options, node, true); }
            await sleep(1500);
        }
        throw new Error('DWPose 模型准备超时，请检查网络后重新提取');
    }
    async function runPose(node, options, force=false){
        const source = poseSource(node, options, options.poseInputRole || ''), signature = sourceSignature(source);
        const currentOutput = options.getPoseOutput?.(node) || outputItem(node);
        if(!signature) return; if(!force && node.poseSourceSignature === signature && currentOutput?.url) return currentOutput;
        const taskKey = `${options.canvasKey || 'canvas'}:${node.id}`; if(poseTasks.has(taskKey)) return poseTasks.get(taskKey);
        const task = (async () => {
            node.poseStatus = 'running'; node.poseError = ''; node.posePreparing = ''; notify(options, node, true);
            try {
                const sourceUrl = options.resolveUrl?.(source.url) || source.url, imageResponse = await fetch(sourceUrl);
                if(!imageResponse.ok) throw new Error('人物图片读取失败');
                const imageBlob = await imageResponse.blob(), form = new FormData(); form.append('file', imageBlob, source.name || 'pose-source.png');
                let response = await fetch('/api/dwpose/detect', {method:'POST', body:form});
                if(response.status === 503){
                    await waitForPoseModel(node, options);
                    node.posePreparing = ''; notify(options, node, true);
                    const retryForm = new FormData(); retryForm.append('file', imageBlob, source.name || 'pose-source.png');
                    response = await fetch('/api/dwpose/detect', {method:'POST', body:retryForm});
                }
                if(!response.ok) throw new Error(await responseError(response, 'DWPose 动作提取失败'));
                const people = Number(response.headers.get('X-DWPose-People') || 0), outputWidth = Number(response.headers.get('X-DWPose-Width') || 0), outputHeight = Number(response.headers.get('X-DWPose-Height') || 0), blob = await response.blob(), file = await uploadBlob(blob, `dwpose-${Date.now()}.png`);
                file.natural_w = outputWidth || file.width || source.natural_w || 0; file.natural_h = outputHeight || file.height || source.natural_h || 0; node.poseSourceSignature = signature; delete node.poseFailedSignature; node.posePeople = people; node.poseStatus = 'done'; node.poseError = ''; node.posePreparing = '';
                if(options.setPoseOutput) options.setPoseOutput(node, file);
                else setOutputItem(node, file, options);
                notify(options, node, true); options.toast?.(people > 0 ? `已提取 ${people} 人骨架` : '未检测到人物，已输出空骨架图'); return file;
            } catch(error) { node.poseStatus = 'failed'; node.poseFailedSignature = signature; node.poseError = error.message || '动作提取失败'; node.posePreparing = ''; notify(options, node, true); throw error; }
            finally { poseTasks.delete(taskKey); }
        })();
        poseTasks.set(taskKey, task); return task;
    }
    function bindPose(root, node, options={}){
        if(!root || !node) return;
        const poseFileInput = root.querySelector('[data-special-file="dwpose"]');
        if(poseFileInput) poseFileInput.onchange = async () => {
            try {
                const file = await uploadFile(poseFileInput.files?.[0]);
                node.poseSourceUrl = file.url; node.poseSourceName = file.name || 'pose-source.png';
                node.poseSourceWidth = file.natural_w || 0; node.poseSourceHeight = file.natural_h || 0;
                node.poseStatus = 'idle'; node.poseError = ''; delete node.poseSourceSignature; delete node.poseFailedSignature; notify(options, node, true);
                runPose(node, options, true).catch(error => options.toast?.(error.message));
            } catch(error){ options.toast?.(error.message); }
            finally { poseFileInput.value = ''; }
        };
        root.querySelectorAll('[data-special-action]').forEach(button => {
            button.addEventListener('pointerdown', e => e.stopPropagation());
            button.addEventListener('click', async e => {
                e.preventDefault(); e.stopPropagation(); const action = button.dataset.specialAction;
                if(action === 'upload-pose'){
                    poseFileInput?.click(); return;
                }
                if(action === 'retry-pose'){ delete node.poseSourceSignature; runPose(node, options, true).catch(error => options.toast?.(error.message)); }
                if(action === 'export-pose'){
                    const item = outputItem(node);
                    if(!item?.url){ options.toast?.('请先完成骨架提取'); return; }
                    if(!options.createOutputNode){ options.toast?.('当前画布不支持创建输出节点'); return; }
                    try {
                        const outputNode = await options.createOutputNode(node, item);
                        if(!outputNode) throw new Error('输出节点创建失败');
                        node.poseOutputNodeId = outputNode.id || '';
                        notify(options, node, false);
                        options.toast?.('骨架参考图已导出到输出节点，可继续连接下一个节点');
                    } catch(error){ options.toast?.(error.message || '骨架图导出失败'); }
                }
            });
        });
        const currentSignature = sourceSignature(poseSource(node, options));
        if(node.poseStatus !== 'failed' || node.poseFailedSignature !== currentSignature) runPose(node, options, false).catch(() => {});
    }

    function poseReplicateInput(node, options, role){
        return options.getInputImage?.(node, role) || null;
    }
    function assignPoseReplicateInput(node, role, item){
        const prefix = role === 'pose-reference' ? 'poseReference' : 'targetImage';
        const previous = node[`${prefix}Signature`] || '';
        const next = sourceSignature(item);
        node[`${prefix}Signature`] = next;
        node[`${prefix}Url`] = item?.url || '';
        node[`${prefix}Name`] = item?.name || '';
        node[`${prefix}Width`] = item?.natural_w || item?.width || 0;
        node[`${prefix}Height`] = item?.natural_h || item?.height || 0;
        return previous !== next;
    }
    function clearPoseReplicateSkeleton(node){
        node.poseSkeletonUrl = '';
        node.poseSkeletonName = '';
        node.poseSkeletonWidth = 0;
        node.poseSkeletonHeight = 0;
        delete node.poseSourceSignature;
        delete node.poseFailedSignature;
        node.poseStatus = 'idle';
        node.poseError = '';
        node.posePreparing = '';
    }
    function poseReplicatePoseOptions(options){
        return {
            ...options,
            poseInputRole:'pose-reference',
            getPoseOutput:node => node.poseSkeletonUrl ? {
                url:node.poseSkeletonUrl,
                name:node.poseSkeletonName || 'pose-skeleton.png',
                natural_w:node.poseSkeletonWidth || 0,
                natural_h:node.poseSkeletonHeight || 0,
                kind:'image'
            } : null,
            setPoseOutput:(node, file) => {
                node.poseSkeletonUrl = file.url || '';
                node.poseSkeletonName = file.name || 'pose-skeleton.png';
                node.poseSkeletonWidth = file.natural_w || file.width || 0;
                node.poseSkeletonHeight = file.natural_h || file.height || 0;
            }
        };
    }
    function bindPoseReplicate(root, node, options={}){
        if(!root || !node) return;
        const action = poseReplicateInput(node, options, 'pose-reference');
        const target = poseReplicateInput(node, options, 'target-image');
        const actionChanged = assignPoseReplicateInput(node, 'pose-reference', action);
        const targetChanged = assignPoseReplicateInput(node, 'target-image', target);
        if(actionChanged) clearPoseReplicateSkeleton(node);
        if(actionChanged || targetChanged) notify(options, node, true);

        root.querySelectorAll('[data-pose-replicate-field]').forEach(control => {
            control.addEventListener('pointerdown', event => event.stopPropagation());
            control.addEventListener(control.matches('textarea') ? 'input' : 'change', event => {
                event.stopPropagation();
                node[control.dataset.poseReplicateField] = control.value;
                notify(options, node, false);
            });
        });
        root.querySelector('[data-special-action="run-pose-replicate"]')?.addEventListener('click', event => {
            event.preventDefault(); event.stopPropagation();
            const currentAction = poseReplicateInput(node, options, 'pose-reference');
            const currentTarget = poseReplicateInput(node, options, 'target-image');
            const skeleton = node.poseSkeletonUrl ? {
                url:node.poseSkeletonUrl,
                name:node.poseSkeletonName || 'pose-skeleton.png',
                natural_w:node.poseSkeletonWidth || 0,
                natural_h:node.poseSkeletonHeight || 0,
                kind:'image'
            } : null;
            if(!currentAction?.url || !currentTarget?.url || !skeleton?.url){ options.toast?.('请等待动作参考骨架提取完成，并确认目标图已连接'); return; }
            if(!options.generatePoseReplicate){ options.toast?.('当前画布尚未配置一键复刻生成能力'); return; }
            const prompt = String(node.poseReplicatePrompt || DEFAULT_POSE_REPLICATE_PROMPT).trim() || DEFAULT_POSE_REPLICATE_PROMPT;
            node.poseReplicateActiveRuns = Math.max(0, Number(node.poseReplicateActiveRuns) || 0) + 1;
            notify(options, node, true);
            Promise.resolve(options.generatePoseReplicate(node, {action:currentAction, skeleton, target:currentTarget}, prompt))
                .catch(error => options.toast?.(error?.message || '一键复刻任务创建失败'))
                .finally(() => {
                    node.poseReplicateActiveRuns = Math.max(0, Number(node.poseReplicateActiveRuns) || 0) - 1;
                    notify(options, node, true);
                });
        });

        if(action?.url){
            const poseOptions = poseReplicatePoseOptions(options);
            const currentSignature = sourceSignature(action);
            if(node.poseStatus !== 'failed' || node.poseFailedSignature !== currentSignature) runPose(node, poseOptions, false).catch(() => {});
        } else if(node.poseSkeletonUrl || node.poseStatus !== 'idle'){
            clearPoseReplicateSkeleton(node);
            notify(options, node, true);
        }
    }

    function relightControlSignature(node){
        return [node.relightDirection,node.relightTemperature,node.relightIntensity,node.relightSoftness,node.relightMood,node.relightPreserve,node.relightNotes,node.editResolution,node.editQuality,node.editRatio,node.editModel].join('|');
    }
    function editControlSignature(node, prefix){
        return prefix === 'relight' ? relightControlSignature(normalizeRelight(node)) : angleControlSignature(normalizeAngle(node));
    }
    function editPrompt(node, prefix){ return prefix === 'relight' ? buildRelightPrompt(node) : buildAnglePrompt(node); }
    function updateRelightControls(root, node){
        const overlay = root.querySelector('[data-relight-overlay]');
        if(!overlay) return;
        const temperature = Number(node.relightTemperature || 0);
        const color = temperature < -10 ? '104,166,255' : temperature > 10 ? '255,178,92' : '255,244,222';
        overlay.style.setProperty('--relight-color', color);
        overlay.style.setProperty('--relight-opacity', String(0.12 + clamp(node.relightIntensity, 10, 100) / 220));
        overlay.dataset.direction = node.relightDirection;
        const temp = root.querySelector('[data-relight-temperature]'), intensity = root.querySelector('[data-relight-intensity]');
        if(temp) temp.textContent = relightTemperatureText(node.relightTemperature);
        if(intensity) intensity.textContent = `${Math.round(node.relightIntensity)}%`;
    }
    function updateAnglePreview(root, node){
        const viewport = root.querySelector('[data-angle-orbit]');
        const world = root.querySelector('[data-angle-world]');
        const signedYaw = signedAngleAzimuth(node.angleAzimuth);
        if(viewport){
            viewport.style.setProperty('--angle-yaw', `${signedYaw}deg`);
            viewport.style.setProperty('--angle-pitch', `${Math.round(node.angleElevation)}deg`);
        }
        // 参考图代表冻结的世界主体，不能随摄影机参数旋转或漂移；只更新下方的摄影机标记与轨迹。
        if(world) world.style.transform = 'none';
        const marker = root.querySelector('[data-angle-marker]');
        const sightline = root.querySelector('[data-angle-sightline]');
        if(marker){
            const radians = Number(node.angleAzimuth || 0) * Math.PI / 180;
            const depth = Math.cos(radians);
            const pitchPct = clamp(Number(node.angleElevation || 0), -30, 60) / 90 * 16;
            const markerX = 50 + Math.sin(radians) * 42;
            const markerY = 50 - Math.max(depth, 0) * 24 - pitchPct;
            marker.style.left = `${markerX}%`;
            marker.style.top = `${markerY}%`;
            marker.style.transform = `translate(-50%,-50%) rotate(${Math.round(node.angleAzimuth)}deg)`;
            const behind = depth < -0.08;
            marker.classList.toggle('is-behind', behind);
            marker.dataset.depth = behind ? 'back' : 'front';
            const depthLabel = marker.querySelector('[data-angle-depth]');
            if(depthLabel) depthLabel.textContent = behind ? '后' : '前';
            if(sightline){ sightline.setAttribute('x2', markerX.toFixed(2)); sightline.setAttribute('y2', markerY.toFixed(2)); }
        }
        const azimuth = nearestAzimuth(node.angleAzimuth), elevation = angleElevationText(node.angleElevation);
        const azimuthEl = root.querySelector('[data-angle-azimuth]'), elevationEl = root.querySelector('[data-angle-elevation]');
        if(azimuthEl) azimuthEl.textContent = `水平 ${angleDirectionText(node.angleYaw)} · ${azimuth[1]}`;
        if(elevationEl) elevationEl.textContent = `俯仰 ${Math.round(node.angleElevation)}° · ${elevation[0]}`;
        root.querySelectorAll('[data-angle-preset]').forEach(button => button.classList.toggle('active', Number(button.dataset.anglePreset) === azimuth[0]));
    }
    function updateEditPreview(root, node, options, prefix, source){
        const output = outputItem(node), item = output || source, image = root.querySelector('[data-edit-preview]');
        if(image){
            if(item?.url){
                const originalUrl = String(item.url);
                let displayUrl = originalUrl;
                try { displayUrl = options.resolveUrl?.(originalUrl) || originalUrl; } catch(_) {}
                image.dataset.originalSrc = originalUrl;
                image.onerror = () => {
                    // 代理地址不可用时回退原始地址，避免节点永久停留在空占位状态。
                    if(image.src && image.src !== originalUrl && image.dataset.previewFallback !== originalUrl){
                        image.dataset.previewFallback = originalUrl;
                        image.src = originalUrl;
                        return;
                    }
                    image.hidden = true;
                };
                image.dataset.previewFallback = '';
                image.src = displayUrl;
                image.hidden = false;
            } else { image.removeAttribute('src'); image.hidden = true; image.onerror = null; }
        }
        root.querySelector('[data-edit-empty]')?.toggleAttribute('hidden', Boolean(item?.url));
        root.querySelector('[data-angle-empty]')?.toggleAttribute('hidden', Boolean(item?.url));
        root.querySelector('[data-edit-stage]')?.classList.toggle('has-source', Boolean(item?.url));
        const relightOverlay = root.querySelector('[data-relight-overlay]');
        if(relightOverlay) relightOverlay.hidden = !source?.url || Boolean(output?.url);
        const badge = root.querySelector('[data-edit-badge]');
        if(badge) badge.textContent = output?.url ? 'API 结果' : '实时灯光示意';
        if(prefix === 'relight') updateRelightControls(root, node); else updateAnglePreview(root, node);
    }
    function markEditChanged(root, node, options, prefix, source){
        if(outputItem(node)?.url) clearOutputItem(node, options);
        const status = root.querySelector('[data-edit-status]');
        if(status) status.textContent = source?.url ? '参数已更新，点击生成后输出新结果' : '请先连接或导入图片';
        updateEditPreview(root, node, options, prefix, source);
        notify(options, node, false);
    }
    function persistEditSource(node, prefix, source){
        if(!node || !prefix || !source?.url) return false;
        const values = {
            [`${prefix}SourceUrl`]:source.url,
            [`${prefix}SourceName`]:source.name || nameFromUrl(source.url, `${prefix}-source.png`),
            [`${prefix}SourceWidth`]:Number(source.natural_w || source.width || 0),
            [`${prefix}SourceHeight`]:Number(source.natural_h || source.height || 0)
        };
        let changed = false;
        Object.entries(values).forEach(([key, value]) => {
            if(node[key] !== value){ node[key] = value; changed = true; }
        });
        return changed;
    }
    async function generateAngleDepth(node, options, source){
        if(!source?.url) throw new Error('请先连接或导入原图');
        const form = new FormData();
        const response = await fetch(source.url, {credentials:'include'});
        if(!response.ok) throw new Error('原图读取失败，无法生成深度图');
        form.append('file', await response.blob(), source.name || 'angle-source.png');
        const result = await fetch('/api/depth/estimate', {method:'POST', body:form});
        if(!result.ok) throw new Error(await responseError(result, '深度模型尚未就绪，请稍后重试'));
        const width = Number(result.headers.get('X-Depth-Width') || source.natural_w || 0);
        const height = Number(result.headers.get('X-Depth-Height') || source.natural_h || 0);
        const file = await uploadBlob(await result.blob(), `depth-${Date.now()}.png`);
        file.natural_w = width || file.natural_w || 0; file.natural_h = height || file.natural_h || 0;
        node.angleDepthUrl = file.url; node.angleDepthName = file.name || 'depth.png';
        node.angleDepthWidth = file.natural_w; node.angleDepthHeight = file.natural_h;
        node.angleGeometryMode = 'depth'; node.angleDepthGenerating = false; node.angleDepthError = '';
        options.onChange?.(node, {render:true});
        return file;
    }
    function syncDirectorReference(node, options){
        if(node.angleGeometryMode !== 'director3d') return null;
        const ref = options.getAngleGeometryReference?.(node);
        if(ref?.url){
            node.angleDirectorCaptureUrl = ref.url; node.angleDirectorCaptureName = ref.name || 'director-3d.png';
            node.angleDirectorCaptureWidth = Number(ref.natural_w || ref.width || 0); node.angleDirectorCaptureHeight = Number(ref.natural_h || ref.height || 0);
            return ref;
        }
        return node.angleDirectorCaptureUrl ? {url:node.angleDirectorCaptureUrl,name:node.angleDirectorCaptureName || 'director-3d.png',kind:'image',natural_w:node.angleDirectorCaptureWidth || 0,natural_h:node.angleDirectorCaptureHeight || 0} : null;
    }

    function bindEditNode(root, node, options, prefix){
        if(!root || !node) return;
        if(prefix === 'relight') normalizeRelight(node); else normalizeAngle(node);
        normalizeEditGeneration(node);
        if(prefix === 'angle') syncDirectorReference(node, options);
        let source = editSource(node, options, prefix);
        // 上游端口是输入真相；同时把解析到的图片快照写回节点，避免刷新/重绘时只剩空占位。
        if(persistEditSource(node, prefix, source)) notify(options, node, false);
        const sourceSig = sourceSignature(source), controlSig = editControlSignature(node, prefix), output = outputItem(node);
        if(output?.url && ((node.specialGeneratedSourceSignature && node.specialGeneratedSourceSignature !== sourceSig) || (node.specialGeneratedControlSignature && node.specialGeneratedControlSignature !== controlSig))){
            clearOutputItem(node, options);
            notify(options, node, true);
        }
        updateEditPreview(root, node, options, prefix, source);
        const fileInput = root.querySelector(`[data-special-file="${prefix}"]`);
        if(fileInput) fileInput.onchange = async () => {
            try {
                const file = await uploadFile(fileInput.files?.[0]);
                node[`${prefix}SourceUrl`] = file.url; node[`${prefix}SourceName`] = file.name || `${prefix}-source.png`;
                node[`${prefix}SourceWidth`] = file.natural_w || 0; node[`${prefix}SourceHeight`] = file.natural_h || 0;
                clearOutputItem(node, options); source = editSource(node, options, prefix); persistEditSource(node, prefix, source); notify(options, node, true);
            } catch(error){ options.toast?.(error.message); }
            finally { fileInput.value = ''; }
        };
        root.querySelectorAll('[data-edit-field]').forEach(control => {
            control.addEventListener('pointerdown', event => event.stopPropagation());
            const eventName = control.matches('textarea,input[type="range"]') ? 'input' : 'change';
            control.addEventListener(eventName, event => {
                event.stopPropagation(); const key = control.dataset.editField;
                let value = control.type === 'checkbox' ? control.checked : control.value;
                if(['relightTemperature','relightIntensity','angleAzimuth','angleYaw','angleElevation'].includes(key)) value = Number(value);
                if(key === 'angleYaw'){
                    value = clamp(value, -180, 180);
                    node.angleYaw = value;
                    node.angleAzimuth = (value + 360) % 360;
                }
                node[key] = value; source = editSource(node, options, prefix); persistEditSource(node, prefix, source); markEditChanged(root, node, options, prefix, source);
            });
        });
        root.querySelectorAll('[data-relight-direction]').forEach(button => {
            button.addEventListener('pointerdown', event => event.stopPropagation());
            button.addEventListener('click', event => {
                event.preventDefault(); event.stopPropagation(); node.relightDirection = button.dataset.relightDirection;
                root.querySelectorAll('[data-relight-direction]').forEach(item => item.classList.toggle('active', item === button));
                source = editSource(node, options, prefix); persistEditSource(node, prefix, source); markEditChanged(root, node, options, prefix, source);
            });
        });
        root.querySelectorAll('[data-angle-preset]').forEach(button => {
            button.addEventListener('pointerdown', event => event.stopPropagation());
            button.addEventListener('click', event => {
                event.preventDefault(); event.stopPropagation(); node.angleAzimuth = Number(button.dataset.anglePreset || 0); node.angleYaw = signedAngleAzimuth(node.angleAzimuth);
                const slider = root.querySelector('[data-edit-field="angleYaw"]'); if(slider) slider.value = node.angleYaw;
                source = editSource(node, options, prefix); persistEditSource(node, prefix, source); markEditChanged(root, node, options, prefix, source);
            });
        });
        const orbit = root.querySelector('[data-angle-orbit]');
        if(orbit){
            const updateOrbit = (event, initial=false) => {
                if(initial){ orbit.dataset.lastX = String(event.clientX); orbit.dataset.lastY = String(event.clientY); }
                const lastX = Number(orbit.dataset.lastX || event.clientX), lastY = Number(orbit.dataset.lastY || event.clientY);
                const deltaX = event.clientX - lastX, deltaY = event.clientY - lastY;
                if(!initial){
                    node.angleAzimuth = ((Number(node.angleAzimuth || 0) + deltaX * 0.85) % 360 + 360) % 360;
                    node.angleYaw = signedAngleAzimuth(node.angleAzimuth);
                    node.angleElevation = clamp(Number(node.angleElevation || 0) - deltaY * 0.55, -30, 60);
                    orbit.dataset.lastX = String(event.clientX); orbit.dataset.lastY = String(event.clientY);
                }
                const slider = root.querySelector('[data-edit-field="angleYaw"]'); if(slider) slider.value = Math.round(node.angleYaw);
                const pitch = root.querySelector('[data-edit-field="angleElevation"]'); if(pitch) pitch.value = Math.round(node.angleElevation);
                source = editSource(node, options, prefix); persistEditSource(node, prefix, source); markEditChanged(root, node, options, prefix, source);
            };
            orbit.addEventListener('pointerdown', event => { if(event.button !== 0) return; event.preventDefault(); event.stopPropagation(); orbit.setPointerCapture?.(event.pointerId); orbit.dataset.dragging = String(event.pointerId); updateOrbit(event, true); });
            orbit.addEventListener('pointermove', event => { if(orbit.dataset.dragging !== String(event.pointerId)) return; event.preventDefault(); event.stopPropagation(); updateOrbit(event); });
            const finish = event => { if(orbit.dataset.dragging !== String(event.pointerId)) return; orbit.releasePointerCapture?.(event.pointerId); delete orbit.dataset.dragging; delete orbit.dataset.lastX; delete orbit.dataset.lastY; event.stopPropagation(); };
            orbit.addEventListener('pointerup', finish); orbit.addEventListener('pointercancel', finish);
        }
        root.querySelectorAll('[data-special-action]').forEach(button => {
            button.addEventListener('pointerdown', event => event.stopPropagation());
            button.addEventListener('click', async event => {
                event.preventDefault(); event.stopPropagation(); const action = button.dataset.specialAction;
                if(action === `upload-${prefix}`){ fileInput?.click(); return; }
                if(action === 'generate-angle-depth' && prefix === 'angle'){
                    try {
                        source = editSource(node, options, prefix); persistEditSource(node, prefix, source);
                        if(!source?.url) throw new Error('请先连接或导入原图');
                        node.angleDepthGenerating = true; node.angleDepthError = ''; notify(options, node, true);
                        await generateAngleDepth(node, options, source);
                        notify(options, node, true); options.toast?.('深度参考图已生成，下一次角度请求会自动携带');
                    } catch(error){ node.angleDepthGenerating = false; node.angleDepthError = error.message || '深度图生成失败'; notify(options, node, true); options.toast?.(node.angleDepthError); }
                    return;
                }
                if(action !== `run-${prefix}`) return;
                try {
                    source = editSource(node, options, prefix);
                    persistEditSource(node, prefix, source);
                    if(prefix === 'angle') syncDirectorReference(node, options);
                    if(!source?.url) throw new Error('请先连接或导入一张图片');
                    if(!options.generateImageEdit) throw new Error('当前画布未配置图片 API 生成能力');
                    node.specialRunning = true;
                    // 先创建可恢复的下游占位节点，再等待远端任务；长任务期间用户仍能看到并继续连接输出。
                    if(options.createEditPendingOutputNode){
                        try {
                            const pendingNode = await options.createEditPendingOutputNode(node, prefix);
                            if(pendingNode?.id) node.specialOutputNodeId = pendingNode.id;
                        } catch(error){
                            // 占位节点失败不应阻断 API 生成；生成完成后仍会尝试创建正式输出节点。
                            console.warn('[canvas-special] 创建灯光/角度占位输出失败：', error);
                        }
                    }
                    notify(options, node, true);
                    const generatedSourceSignature = sourceSignature(source), generatedControlSignature = editControlSignature(node, prefix);
                    const file = await options.generateImageEdit(node, editPrompt(node, prefix), source, prefix);
                    if(!file?.url) throw new Error('图片 API 没有返回生成结果');
                    node.specialRunning = false; node.specialGeneratedSourceSignature = generatedSourceSignature; node.specialGeneratedControlSignature = generatedControlSignature;
                    setOutputItem(node, file, options);
                    if(options.createEditOutputNode){
                        const outputNode = await options.createEditOutputNode(node, file, prefix);
                        if(!outputNode) throw new Error('输出节点创建失败');
                        node.specialOutputNodeId = outputNode.id || node.specialOutputNodeId || '';
                    }
                    notify(options, node, true); options.toast?.(prefix === 'relight' ? '灯光重塑已完成，可连接到下游节点' : '新视角已生成，可连接到下游节点');
                } catch(error){ node.specialRunning = false; notify(options, node, true); options.toast?.(error.message || '图片生成失败'); }
            });
        });
    }
    function bindRelight(root, node, options={}){
        if(!root || !node) return;
        normalizeRelight(node);
        normalizeEditGeneration(node);
        let source = editSource(node, options, 'relight');
        if(persistEditSource(node, 'relight', source)) notify(options, node, false);
        const sourceSig = sourceSignature(source), controlSig = relightControlSignature(node), output = outputItem(node);
        if(output?.url && ((node.specialGeneratedSourceSignature && node.specialGeneratedSourceSignature !== sourceSig) || (node.specialGeneratedControlSignature && node.specialGeneratedControlSignature !== controlSig))){
            clearOutputItem(node, options);
            notify(options, node, true);
        }
        updateRelightPreview(root, node, options, source);
        const fileInput = root.querySelector('[data-special-file="relight"]');
        if(fileInput) fileInput.onchange = async () => {
            try {
                const file = await uploadFile(fileInput.files?.[0]);
                node.relightSourceUrl = file.url;
                node.relightSourceName = file.name || 'relight-source.png';
                node.relightSourceWidth = file.natural_w || 0;
                node.relightSourceHeight = file.natural_h || 0;
                clearOutputItem(node, options);
                source = editSource(node, options, 'relight');
                persistEditSource(node, 'relight', source);
                updateRelightPreview(root, node, options, source);
                notify(options, node, true);
            } catch(error){ options.toast?.(error.message); }
            finally { fileInput.value = ''; }
        };
        root.querySelectorAll('[data-edit-field]').forEach(control => {
            control.addEventListener('pointerdown', event => event.stopPropagation());
            const eventName = control.matches('textarea,input[type="range"]') ? 'input' : 'change';
            control.addEventListener(eventName, event => {
                event.stopPropagation();
                const key = control.dataset.editField;
                let value = control.type === 'checkbox' ? control.checked : control.value;
                if(['relightTemperature','relightIntensity'].includes(key)) value = Number(value);
                node[key] = value;
                source = editSource(node, options, 'relight');
                persistEditSource(node, 'relight', source);
                markRelightChanged(root, node, options, source);
            });
        });
        root.querySelectorAll('[data-relight-direction]').forEach(button => {
            button.addEventListener('pointerdown', event => event.stopPropagation());
            button.addEventListener('click', event => {
                event.preventDefault(); event.stopPropagation();
                node.relightDirection = button.dataset.relightDirection;
                root.querySelectorAll('[data-relight-direction]').forEach(item => item.classList.toggle('active', item === button));
                source = editSource(node, options, 'relight');
                persistEditSource(node, 'relight', source);
                markRelightChanged(root, node, options, source);
            });
        });
        root.querySelectorAll('[data-special-action]').forEach(button => {
            button.addEventListener('pointerdown', event => event.stopPropagation());
            button.addEventListener('click', async event => {
                event.preventDefault();
                event.stopPropagation();
                const action = button.dataset.specialAction;
                if(action === 'upload-relight'){ fileInput?.click(); return; }
                if(action !== 'run-relight') return;
                try {
                    source = editSource(node, options, 'relight');
                    persistEditSource(node, 'relight', source);
                    if(!source?.url) throw new Error('请先连接或导入一张图片');
                    if(!options.generateImageEdit) throw new Error('当前画布未配置图片 API 生成能力');
                    node.specialRunning = true;
                    if(options.createEditPendingOutputNode){
                        try {
                            const pendingNode = await options.createEditPendingOutputNode(node, 'relight');
                            if(pendingNode?.id) node.specialOutputNodeId = pendingNode.id;
                        } catch(error){
                            console.warn('[canvas-special] 创建灯光调整占位输出失败：', error);
                        }
                    }
                    notify(options, node, true);
                    const generatedSourceSignature = sourceSignature(source), generatedControlSignature = relightControlSignature(node);
                    const file = await options.generateImageEdit(node, buildRelightPrompt(node), source, 'relight');
                    if(!file?.url) throw new Error('图片 API 没有返回生成结果');
                    node.specialRunning = false;
                    node.specialGeneratedSourceSignature = generatedSourceSignature;
                    node.specialGeneratedControlSignature = generatedControlSignature;
                    setOutputItem(node, file, options);
                    if(options.createEditOutputNode){
                        const outputNode = await options.createEditOutputNode(node, file, 'relight');
                        if(!outputNode) throw new Error('输出节点创建失败');
                        node.specialOutputNodeId = outputNode.id || node.specialOutputNodeId || '';
                    }
                    updateRelightPreview(root, node, options, source);
                    notify(options, node, true);
                    options.toast?.('灯光重塑已完成，可连接到下游节点');
                } catch(error){
                    node.specialRunning = false;
                    notify(options, node, true);
                    options.toast?.(error.message || '图片生成失败');
                }
            });
        });
    }
    function bindAngle(root, node, options={}){ bindEditNode(root, node, options, 'angle'); }

    window.CanvasSpecialNodes = {
        DEFAULT_PANORAMA_PROMPT, DEFAULT_ANGLE_PROMPT,
        panoramaBodyHtml, poseBodyHtml, director3dBodyHtml, poseReplicateBodyHtml, angleBodyHtml,
        bindPanorama, bindPose, bindDirector3d, bindPoseReplicate, bindAngle,
        buildAnglePrompt, outputItem, sourceSignature, uploadBlob, normalizePanorama, normalizeAngle,
        disposePanoramaCanvas, disposePanoramasIn, normalizeEditGeneration
    };
})();
