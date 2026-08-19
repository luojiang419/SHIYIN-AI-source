const TOPAZ_NODE_ADVANCED_DEFAULTS = Object.freeze({
    preblur:0, noise:0, details:0, halo:0, blur:0, compression:0, pre_noise:0,
    estimate:0, blend:0, grain:0, grain_size:0, device:'-2', vram:1,
    instances:0, download_models:true, color_correction:true,
    encoder:'h264_nvenc', audio_mode:'aac', audio_bitrate_kbps:320
});
let topazVideoCapabilitiesCache = null;
let topazVideoCapabilitiesPromise = null;
const activeTopazVideoTaskPolls = new Map();

function topazText(zh, en){ return langIsEn() ? en : zh; }
function normalizeTopazVideoNode(node){
    if(!node) return node;
    node.model = String(node.model || topazVideoCapabilitiesCache?.default_model || 'prob-4');
    node.target = ['2x','4x','1080p','1440p','2160p'].includes(node.target) ? node.target : '2x';
    node.quality = ['high','balanced','compact'].includes(node.quality) ? node.quality : 'balanced';
    node.topazAdvanced = {...TOPAZ_NODE_ADVANCED_DEFAULTS, ...(node.topazAdvanced || {})};
    node.inputs = Array.isArray(node.inputs) ? node.inputs : [];
    node.generatedOutputs = Array.isArray(node.generatedOutputs) ? node.generatedOutputs : [];
    node.topazProgress = Math.max(0, Math.min(1, Number(node.topazProgress || 0)));
    return node;
}

async function ensureTopazVideoCapabilities(force=false){
    if(topazVideoCapabilitiesCache && !force) return topazVideoCapabilitiesCache;
    if(topazVideoCapabilitiesPromise && !force) return topazVideoCapabilitiesPromise;
    topazVideoCapabilitiesPromise = fetch('/api/topaz-video/capabilities')
        .then(async response => {
            if(!response.ok) throw new Error(await responseErrorMessage(response, topazText('无法检测 Topaz','Unable to detect Topaz')));
            return response.json();
        })
        .then(data => {
            topazVideoCapabilitiesCache = data || {};
            return topazVideoCapabilitiesCache;
        })
        .catch(error => {
            topazVideoCapabilitiesCache = {ready:false, models:[], error:error.message || String(error)};
            return topazVideoCapabilitiesCache;
        })
        .finally(() => { topazVideoCapabilitiesPromise = null; });
    return topazVideoCapabilitiesPromise;
}

function addTopazVideoNode(point){
    const p = point || defaultPoint(180, 0);
    const node = normalizeTopazVideoNode({
        id:uid('topaz'), type:'topazVideo', x:p.x, y:p.y,
        model:topazVideoCapabilitiesCache?.default_model || 'prob-4',
        target:'2x', quality:'balanced', topazAdvanced:{...TOPAZ_NODE_ADVANCED_DEFAULTS},
        topazAdvancedOpen:false, topazTaskId:'', inputs:[], generatedOutputs:[], running:false
    });
    ensureTopazVideoCapabilities().then(capabilities => {
        const current = nodes.find(item => item.id === node.id);
        if(!current) return;
        const ids = (capabilities.models || []).map(item => item.id);
        if(ids.length && !ids.includes(current.model)) current.model = capabilities.default_model || ids[0];
        refreshNodes([current.id]);
        scheduleSave();
    });
    return addNode(node);
}

function topazVideoSources(node){
    return orderedSources(node, generatorSources(node));
}

function topazVideoRefs(node){
    return videoRefsOnly(topazVideoSources(node).flatMap(source => source.refs || []));
}

function topazModelOptions(node){
    const models = topazVideoCapabilitiesCache?.models || [];
    const values = models.length ? models : [{id:node.model || 'prob-4', name:node.model || 'Proteus'}];
    return values.map(item => `<option value="${escapeAttr(item.id)}" ${item.id === node.model ? 'selected' : ''}>${escapeHtml(item.name || item.id)}</option>`).join('');
}

function topazRangeField(key, label, value, min, max, step){
    return `<label class="topaz-advanced-field"><span>${escapeHtml(label)} <b data-topaz-value="${escapeAttr(key)}">${Number(value).toFixed(step < 0.1 ? 2 : 1)}</b></span><input type="range" min="${min}" max="${max}" step="${step}" value="${Number(value)}" data-topaz-advanced="${escapeAttr(key)}"></label>`;
}

function topazAdvancedSettingsHtml(node){
    const advanced = node.topazAdvanced;
    return `<details class="topaz-advanced-settings" ${node.topazAdvancedOpen ? 'open' : ''}>
        <summary><i data-lucide="sliders-horizontal"></i><span>${topazText('高级设置','Advanced')}</span></summary>
        <div class="topaz-advanced-panel">
            <div class="topaz-advanced-title">${topazText('画面修复','Image refinement')}</div>
            ${topazRangeField('preblur',topazText('反锯齿 / 去模糊','Anti-alias / Deblur'),advanced.preblur,-1,1,0.05)}
            ${topazRangeField('noise',topazText('降噪','Reduce noise'),advanced.noise,-1,1,0.05)}
            ${topazRangeField('details',topazText('细节恢复','Recover details'),advanced.details,-1,1,0.05)}
            ${topazRangeField('halo',topazText('去光晕','Dehalo'),advanced.halo,-1,1,0.05)}
            ${topazRangeField('blur',topazText('锐化','Sharpen'),advanced.blur,-1,1,0.05)}
            ${topazRangeField('compression',topazText('压缩修复','Revert compression'),advanced.compression,-1,1,0.05)}
            ${topazRangeField('pre_noise',topazText('预加噪','Pre-noise'),advanced.pre_noise,0,0.1,0.005)}
            ${topazRangeField('blend',topazText('保留原始细节','Recover original detail'),advanced.blend,0,1,0.05)}
            ${topazRangeField('grain',topazText('胶片颗粒','Grain amount'),advanced.grain,0,0.1,0.005)}
            ${topazRangeField('grain_size',topazText('颗粒尺寸','Grain size'),advanced.grain_size,0,5,0.1)}
            <div class="topaz-advanced-title">${topazText('性能与模型','Performance and model')}</div>
            <div class="topaz-advanced-grid">
                <label><span>${topazText('自动分析帧','Estimate frames')}</span><input type="number" min="0" max="100" step="1" value="${Number(advanced.estimate)}" data-topaz-advanced="estimate"></label>
                <label><span>${topazText('计算设备','Compute device')}</span><select data-topaz-advanced="device"><option value="-2">Auto</option><option value="0">GPU 0</option><option value="-1">CPU</option></select></label>
                <label><span>${topazText('显存比例','VRAM ratio')}</span><input type="number" min="0.1" max="1" step="0.05" value="${Number(advanced.vram)}" data-topaz-advanced="vram"></label>
                <label><span>${topazText('并行实例','Instances')}</span><input type="number" min="0" max="3" step="1" value="${Number(advanced.instances)}" data-topaz-advanced="instances"></label>
            </div>
            <label class="topaz-check"><input type="checkbox" data-topaz-advanced="color_correction" ${advanced.color_correction ? 'checked' : ''}><span>${topazText('启用模型颜色校正','Model color correction')}</span></label>
            <label class="topaz-check"><input type="checkbox" data-topaz-advanced="download_models" ${advanced.download_models ? 'checked' : ''}><span>${topazText('允许自动下载缺失模型','Download missing models')}</span></label>
            <div class="topaz-advanced-title">${topazText('输出与音频','Output and audio')}</div>
            <div class="topaz-advanced-grid">
                <label><span>${topazText('视频编码','Video codec')}</span><select data-topaz-advanced="encoder"><option value="h264_nvenc">H.264 NVIDIA</option><option value="hevc_nvenc">H.265 NVIDIA</option></select></label>
                <label><span>${topazText('音频处理','Audio')}</span><select data-topaz-advanced="audio_mode"><option value="aac">AAC ${topazText('保留','Preserve')}</option><option value="copy">${topazText('原流复制','Stream copy')}</option><option value="none">${topazText('移除音频','Remove')}</option></select></label>
                <label><span>${topazText('音频码率','Audio bitrate')}</span><input type="number" min="64" max="512" step="32" value="${Number(advanced.audio_bitrate_kbps)}" data-topaz-advanced="audio_bitrate_kbps"></label>
            </div>
        </div>
    </details>`;
}

function renderTopazVideoInputPreview(container, node){
    if(!container) return;
    const refs = topazVideoRefs(node);
    const first = refs[0];
    container.innerHTML = first
        ? `<div class="topaz-input-card">${canvasVideoPreviewHtml(first.url, 256, 'alt="Topaz input"')}<div><strong>${escapeHtml(first.name || outputImageName(first.url) || 'Video')}</strong><span>${refs.length > 1 ? topazText(`已连接 ${refs.length} 个视频，仅处理第一个`,`Connected ${refs.length}; only the first is used`) : topazText('本地视频输入','Local video input')}</span></div></div>`
        : `<div class="topaz-input-empty"><i data-lucide="film"></i><span>${topazText('连接一个视频作为输入','Connect one video input')}</span></div>`;
    bindCanvasPreviewImageFallbacks(container);
}

function renderTopazVideoBody(node){
    normalizeTopazVideoNode(node);
    const wrap = document.createElement('div');
    wrap.className = 'topaz-video-body';
    const capabilities = topazVideoCapabilitiesCache;
    const ready = Boolean(capabilities?.ready);
    const progress = Math.round(Number(node.topazProgress || 0) * 100);
    const statusText = node.running
        ? `${node.topazMessage || topazText('Topaz 正在处理','Topaz is processing')} · ${progress}%${node.topazSpeed ? ` · ${escapeHtml(node.topazSpeed)}` : ''}`
        : node.runStatus === 'failed'
            ? node.runError || topazText('处理失败','Processing failed')
            : capabilities && !ready
                ? capabilities.error || topazText('Topaz 尚未就绪','Topaz is not ready')
                : topazText('本地 Topaz Video AI','Local Topaz Video AI');
    wrap.innerHTML = `<div class="topaz-input-list"></div>
        <div class="topaz-common-settings">
            <label><span>${topazText('AI 模型','AI model')}</span><select data-topaz-common="model">${topazModelOptions(node)}</select></label>
            <label><span>${topazText('输出尺寸','Output size')}</span><select data-topaz-common="target"><option value="2x">2×</option><option value="4x">4×</option><option value="1080p">1080p</option><option value="1440p">2K / 1440p</option><option value="2160p">4K / 2160p</option></select></label>
            <label><span>${topazText('质量预设','Quality')}</span><select data-topaz-common="quality"><option value="high">${topazText('高质量','High')}</option><option value="balanced">${topazText('均衡','Balanced')}</option><option value="compact">${topazText('小体积','Compact')}</option></select></label>
        </div>
        ${node.running ? `<div class="topaz-progress"><span style="width:${progress}%"></span></div>` : ''}
        <div class="topaz-status ${node.runStatus === 'failed' ? 'failed' : ''}">${escapeHtml(statusText)}</div>
        <div class="topaz-node-actions">
            <button type="button" class="gen-btn ${node.running ? 'running' : ''}" data-topaz-run ${node.running || !ready ? 'disabled' : ''}><i data-lucide="sparkles"></i><span>${node.running ? topazText('处理中','Processing') : topazText('高清放大','Upscale')}</span></button>
            ${node.running ? `<button type="button" class="tool-btn topaz-cancel" data-topaz-cancel><i data-lucide="square"></i><span>${topazText('取消','Cancel')}</span></button>` : ''}
            ${topazAdvancedSettingsHtml(node)}
        </div>`;
    wrap.querySelector('[data-topaz-common="target"]').value = node.target;
    wrap.querySelector('[data-topaz-common="quality"]').value = node.quality;
    ['device','encoder','audio_mode'].forEach(key => {
        const select = wrap.querySelector(`[data-topaz-advanced="${key}"]`);
        if(select) select.value = String(node.topazAdvanced[key]);
    });
    renderTopazVideoInputPreview(wrap.querySelector('.topaz-input-list'), node);
    wrap.querySelectorAll('[data-topaz-common]').forEach(control => {
        control.onmousedown = event => event.stopPropagation();
        control.onchange = () => {
            node[control.dataset.topazCommon] = control.value;
            scheduleSave();
        };
    });
    wrap.querySelectorAll('[data-topaz-advanced]').forEach(control => {
        control.onmousedown = event => event.stopPropagation();
        const update = () => {
            const key = control.dataset.topazAdvanced;
            const numeric = new Set(['preblur','noise','details','halo','blur','compression','pre_noise','estimate','blend','grain','grain_size','vram','instances','audio_bitrate_kbps']);
            node.topazAdvanced[key] = control.type === 'checkbox' ? control.checked : numeric.has(key) ? Number(control.value) : control.value;
            const value = wrap.querySelector(`[data-topaz-value="${CSS.escape(key)}"]`);
            if(value) value.textContent = Number(control.value).toFixed(Number(control.step) < 0.1 ? 2 : 1);
            scheduleSave();
        };
        control.oninput = update;
        control.onchange = update;
    });
    const details = wrap.querySelector('.topaz-advanced-settings');
    if(details) details.ontoggle = () => { node.topazAdvancedOpen = details.open; scheduleSave(); };
    wrap.querySelector('[data-topaz-run]')?.addEventListener('click', event => {
        event.stopPropagation();
        runTopazVideoNode(node.id);
    });
    wrap.querySelector('[data-topaz-cancel]')?.addEventListener('click', event => {
        event.stopPropagation();
        cancelTopazVideoTask(node.id);
    });
    if(!topazVideoCapabilitiesCache && !topazVideoCapabilitiesPromise){
        ensureTopazVideoCapabilities().then(() => {
            if(nodes.some(item => item.id === node.id)) refreshNodes([node.id]);
        });
    }
    return wrap;
}

async function createTopazVideoTask(payload, options={}){
    const response = await cascadeFetch('/api/topaz-video/tasks', {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)
    }, options);
    if(!response.ok) throw new Error(await responseErrorMessage(response, topazText('Topaz 任务创建失败','Unable to create Topaz task')));
    return response.json();
}

function topazResultItems(task){
    const raw = task?.result?.videos || (task?.result?.url ? [{url:task.result.url, kind:'video'}] : []);
    return raw.map(item => typeof item === 'string' ? {url:item,kind:'video'} : {...item,kind:'video'}).filter(item => item.url);
}

async function pollTopazVideoTask(nodeId, taskId, options={}){
    if(activeTopazVideoTaskPolls.has(taskId)) return activeTopazVideoTaskPolls.get(taskId);
    const promise = (async () => {
        while(true){
            const node = nodes.find(item => item.id === nodeId);
            if(!node || node.topazTaskId !== taskId) return 'missing';
            const cascadeTargetId = String(options.cascadeTargetId || '');
            if(cascadeTargetId) ensureCascadeActive(cascadeTargetId);
            const response = await cascadeFetch(`/api/topaz-video/tasks/${encodeURIComponent(taskId)}`, {}, {cascadeTargetId});
            if(!response.ok) throw new Error(await responseErrorMessage(response, topazText('Topaz 任务查询失败','Unable to query Topaz task')));
            const task = await response.json();
            const status = String(task.status || 'running');
            node.topazProgress = Number(task.progress || 0);
            node.topazSpeed = String(task.speed || '');
            node.topazMessage = String(task.message || '');
            node.running = ['queued','probing','running','canceling'].includes(status);
            node.runStatus = node.running ? (status === 'queued' ? 'queued' : 'running') : status === 'succeeded' ? 'done' : status === 'canceled' ? '' : 'failed';
            node.runError = String(task.error || '');
            refreshNodes([node.id]);
            if(status === 'succeeded'){
                const outputs = topazResultItems(task);
                if(!outputs.length) throw new Error(topazText('Topaz 没有返回视频','Topaz returned no video'));
                const out = outputForNode(node, 460);
                const inputRef = topazVideoRefs(node)[0] || null;
                const runMs = Math.max(0, Date.now() - Number(node.topazRunStartedAt || Date.now()));
                if(out) appendOutputImagesWithoutDuplicates(out, outputs, inputRef, [{runMs, kind:'video'}]);
                mergeGeneratedOutputs(node, outputs, Boolean(options.cascade));
                if(node.topazLoggedTaskId !== taskId){
                    const run = node.topazRunSnapshot || runSnapshot(node, 'Topaz Video AI', inputRef ? [inputRef] : []);
                    run.taskLabel = `Topaz ${node.model}`;
                    addGenerationLog({run, outputs, runMs});
                    node.topazLoggedTaskId = taskId;
                }
                node.topazLastTaskId = taskId;
                node.topazTaskId = '';
                node.topazProgress = 1;
                node.running = false;
                node.runStatus = 'done';
                delete node.topazRunSnapshot;
                refreshRunNodes(node, out);
                scheduleSave();
                return 'succeeded';
            }
            if(status === 'canceled'){
                node.topazTaskId = '';
                node.running = false;
                node.topazMessage = '';
                refreshNodes([node.id]);
                scheduleSave();
                return 'canceled';
            }
            if(['failed','interrupted'].includes(status)){
                node.topazTaskId = '';
                node.running = false;
                node.runStatus = 'failed';
                node.runError = task.error || topazText('Topaz 处理失败','Topaz processing failed');
                refreshNodes([node.id]);
                scheduleSave();
                throw new Error(node.runError);
            }
            scheduleSave();
            await sleep(1000);
        }
    })().finally(() => activeTopazVideoTaskPolls.delete(taskId));
    activeTopazVideoTaskPolls.set(taskId, promise);
    return promise;
}

async function runTopazVideoNode(nodeId, options={}){
    const node = nodes.find(item => item.id === nodeId);
    if(!node || node.running) return;
    normalizeTopazVideoNode(node);
    const input = topazVideoRefs(node)[0];
    if(!input?.url){
        if(options.cascade) throw new Error(topazText('Topaz 高清放大需要一个视频输入','Topaz upscaling requires one video input'));
        showErrorModal(topazText('请先连接一个视频节点或视频素材。','Connect a video node or video asset first.'), topazText('缺少视频输入','Missing video input'));
        return;
    }
    const cascadeTargetId = cascadeTargetIdFromOptions(options);
    const run = runSnapshot(node, 'Topaz Video AI', [input]);
    run.taskLabel = `Topaz ${node.model}`;
    node.topazRunSnapshot = run;
    node.topazRunStartedAt = Date.now();
    node.topazProgress = 0;
    node.topazSpeed = '';
    node.running = true;
    node.runStatus = 'queued';
    node.runError = '';
    outputForNode(node, 460);
    refreshNodes([node.id]);
    try {
        const task = await createTopazVideoTask({
            input_url:input.url, model:node.model, target:node.target, quality:node.quality,
            advanced:{...node.topazAdvanced}, canvas_id:canvas?.id || '', node_id:node.id
        }, {cascadeTargetId});
        node.topazTaskId = task.id || task.task_id;
        node.topazMessage = task.message || '';
        scheduleSave();
        await saveCanvas();
        return await pollTopazVideoTask(node.id, node.topazTaskId, {cascade:Boolean(options.cascade), cascadeTargetId});
    } catch(error) {
        node.running = false;
        node.runStatus = 'failed';
        node.runError = error.message || String(error);
        addGenerationLog({run, outputs:[], runMs:Date.now() - node.topazRunStartedAt, error:node.runError});
        refreshNodes([node.id]);
        scheduleSave();
        if(options.cascade) throw error;
        showErrorModal(node.runError, topazText('Topaz 高清放大失败','Topaz upscale failed'));
        return 'failed';
    }
}

async function cancelTopazVideoTask(nodeId){
    const node = nodes.find(item => item.id === nodeId);
    if(!node?.topazTaskId) return;
    node.topazMessage = topazText('正在取消任务','Canceling task');
    refreshNodes([node.id]);
    try {
        const response = await fetch(`/api/topaz-video/tasks/${encodeURIComponent(node.topazTaskId)}/cancel`, {method:'POST'});
        if(!response.ok) throw new Error(await responseErrorMessage(response, topazText('取消失败','Cancel failed')));
    } catch(error) {
        showErrorModal(error.message || String(error), topazText('取消 Topaz 任务失败','Unable to cancel Topaz task'));
    }
}

function resumeTopazVideoTasks(){
    nodes.filter(node => node.type === 'topazVideo' && node.topazTaskId).forEach(node => {
        normalizeTopazVideoNode(node);
        node.running = true;
        node.runStatus = 'running';
        pollTopazVideoTask(node.id, node.topazTaskId, {resume:true}).catch(error => {
            node.running = false;
            node.runStatus = 'failed';
            node.runError = error.message || String(error);
            refreshNodes([node.id]);
        });
    });
}
