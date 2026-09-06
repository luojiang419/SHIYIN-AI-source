(function(global){
    'use strict';

    const ACTIVE_STATUSES = new Set(['queued','running','jimeng_pending','recovery_pending']);
    const INPUTS = [
        {role:'pose_reference', label:'目标图', required:true, hint:'人物、姿势与画幅基准'},
        {role:'target_image', label:'服装参考', required:true, hint:'当前款式或色号'},
        {role:'model_subject', label:'模特主体', required:false, hint:'可选 · 替换人物身份'},
        {role:'scene', label:'场景', required:false, hint:'可选 · 指定生成环境'},
    ];
    const state = {
        groups:[],
        selectedGroupId:'',
        selectedImageIndex:0,
        uploadTarget:null,
        pollers:new Map(),
        initialized:false,
    };
    const el = {};

    const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));
    const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
    const api = () => global.EcommerceStudio;
    const isActive = () => api()?.state?.operation === 'batch_outfit';
    const groupById = id => state.groups.find(group => group.id === id) || null;
    const selectedGroup = () => groupById(state.selectedGroupId) || state.groups[0] || null;
    const uniqueId = () => `outfit_${global.crypto?.randomUUID?.().replaceAll('-','') || `${Date.now()}_${Math.random().toString(36).slice(2)}`}`;

    function cleanImage(value){
        if(!value || typeof value !== 'object' || !String(value.url || '').trim()) return null;
        return {
            url:String(value.url || ''),
            name:String(value.name || ''),
            mime:String(value.mime || ''),
            width:Number(value.width || value.natural_w || 0),
            height:Number(value.height || value.natural_h || 0),
            kind:'image',
        };
    }

    function cleanWork(value){
        if(!value || typeof value !== 'object' || !String(value.url || '').trim()) return null;
        return {
            url:String(value.url || ''),
            name:String(value.name || ''),
            workId:String(value.workId || value.work_id || ''),
            archivePath:String(value.archivePath || value.archive_path || ''),
            archivedPath:String(value.archivedPath || value.archived_path || ''),
            createdAt:Number(value.createdAt || value.created_at || Date.now()),
        };
    }

    function cleanGroup(value){
        if(!value || typeof value !== 'object') return null;
        const id = /^[A-Za-z0-9_-]{1,96}$/.test(String(value.id || '')) ? String(value.id) : uniqueId();
        const styleName = String(value.styleName || value.style_name || '').trim().slice(0,80);
        if(!styleName) return null;
        const inputs = {};
        INPUTS.forEach(item => {
            const image = cleanImage(value.inputs?.[item.role]);
            if(image) inputs[item.role] = image;
        });
        const controlMap = cleanImage(value.controlMap || value.control_map);
        const works = (Array.isArray(value.works) ? value.works : []).map(cleanWork).filter(Boolean);
        const taskIds = (Array.isArray(value.taskIds) ? value.taskIds : value.task_ids || []).map(item => String(item || '')).filter(Boolean).slice(-40);
        return {
            id,
            styleName,
            inputs,
            controlMap,
            controlSourceUrl:String(value.controlSourceUrl || value.control_source_url || ''),
            taskIds,
            currentTaskId:String(value.currentTaskId || value.current_task_id || taskIds[taskIds.length - 1] || ''),
            status:String(value.status || 'draft'),
            error:String(value.error || ''),
            works,
            updatedAt:Number(value.updatedAt || value.updated_at || Date.now()),
        };
    }

    function snapshot(){
        return {
            schema_version:1,
            groups:state.groups.map(group => ({
                id:group.id,
                style_name:group.styleName,
                inputs:group.inputs,
                control_map:group.controlMap,
                control_source_url:group.controlSourceUrl,
                task_ids:group.taskIds,
                current_task_id:group.currentTaskId,
                status:group.status,
                error:group.error,
                works:group.works,
                updated_at:group.updatedAt,
            })),
            selected_group_id:state.selectedGroupId,
            selected_image_index:state.selectedImageIndex,
        };
    }

    function hydrate(value){
        const groups = (Array.isArray(value?.groups) ? value.groups : []).map(cleanGroup).filter(Boolean);
        state.groups = groups;
        state.selectedGroupId = groups.some(group => group.id === value?.selected_group_id)
            ? String(value.selected_group_id)
            : (groups[0]?.id || '');
        state.selectedImageIndex = Math.max(0, Number(value?.selected_image_index || 0));
        if(api()?.state) api().state.batchOutfit = snapshot();
        render();
        resumePendingTasks();
    }

    function persist(){
        if(api()?.state) api().state.batchOutfit = snapshot();
        api()?.persistSettings?.();
    }

    function showError(message=''){
        if(!el.error) return;
        el.error.textContent = String(message || '');
        el.error.classList.toggle('hidden', !message);
    }

    function showToast(message, isError=false){
        if(api()?.showToast) api().showToast(message, isError);
        else if(isError) console.error(message);
    }

    async function fetchJson(url, init={}){
        const response = await fetch(url, init);
        const data = await response.json().catch(() => ({}));
        if(!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : (data.detail?.message || `HTTP ${response.status}`));
        return data;
    }

    function validateStyleName(value){
        const name = String(value || '').trim().replace(/\s+/g, ' ');
        if(!name) throw new Error('请输入款号名称');
        if(name.length > 80) throw new Error('款号名称不能超过 80 个字符');
        if(/[<>:"/\\|?*\x00-\x1F]/.test(name) || name === '.' || name === '..' || /[. ]$/.test(name)) throw new Error('款号名称包含文件夹非法字符');
        if(/^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)/i.test(name)) throw new Error('款号名称不能使用 Windows 保留名');
        if(state.groups.some(group => group.styleName.toLocaleLowerCase() === name.toLocaleLowerCase())) throw new Error('该款号名称已存在');
        return name;
    }

    function openAddDialog(){
        showError('');
        if(!el.dialog) return;
        el.dialogError?.classList.add('hidden');
        if(el.dialogError) el.dialogError.textContent = '';
        el.styleName.value = '';
        el.dialog.showModal();
        requestAnimationFrame(() => el.styleName.focus());
    }

    function addGroup(styleName){
        const group = cleanGroup({id:uniqueId(), styleName, status:'draft', inputs:{}, works:[], taskIds:[]});
        state.groups.push(group);
        state.selectedGroupId = group.id;
        state.selectedImageIndex = 0;
        persist();
        render();
        requestAnimationFrame(() => el.groups?.querySelector(`[data-batch-group="${CSS.escape(group.id)}"]`)?.scrollIntoView({behavior:'smooth', block:'nearest'}));
    }

    function submitAddDialog(event){
        event.preventDefault();
        try {
            addGroup(validateStyleName(el.styleName.value));
            el.dialog.close();
        } catch(error) {
            el.dialogError.textContent = error.message;
            el.dialogError.classList.remove('hidden');
        }
    }

    function statusText(group){
        if(group.status === 'uploading') return '正在上传';
        if(group.status === 'preparing') return '正在提取骨架';
        if(group.status === 'queued') return '已排队';
        if(group.status === 'running' || group.status === 'jimeng_pending' || group.status === 'recovery_pending') return '正在生成';
        if(group.status === 'succeeded') return group.works.length ? `已生成 ${group.works.length} 张` : '生成完成';
        if(group.status === 'failed' || group.status === 'interrupted') return '生成失败';
        return group.inputs.pose_reference || group.inputs.target_image ? '待完善' : '待添加素材';
    }

    function inputCardHtml(group, item){
        const image = group.inputs[item.role];
        return `<button type="button" class="ec-batch-input-card ${image ? 'has-image' : ''}" data-batch-upload="${item.role}" aria-label="${escapeHtml(item.label)}">
            <span class="ec-batch-input-label">${escapeHtml(item.label)}${item.required ? '<em>*</em>' : ''}</span>
            ${image ? `<img src="${escapeHtml(image.url)}" alt="${escapeHtml(item.label)}"><small>${escapeHtml(image.name || item.hint)}</small><span class="ec-batch-input-replace">点击替换</span>` : `<span class="ec-batch-input-plus">+</span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.hint)}</small>`}
            ${image ? `<span class="ec-batch-input-remove" data-batch-remove-input="${item.role}" role="button" aria-label="移除${escapeHtml(item.label)}">×</span>` : ''}
        </button>`;
    }

    function groupHtml(group, index){
        const selected = group.id === state.selectedGroupId;
        const running = ACTIVE_STATUSES.has(group.status) || ['uploading','preparing'].includes(group.status);
        const canGenerate = Boolean(group.inputs.pose_reference?.url && group.inputs.target_image?.url) && !running;
        const preview = group.works[group.works.length - 1];
        return `<article class="ec-batch-group ${selected ? 'is-selected' : ''}" data-batch-group="${escapeHtml(group.id)}" tabindex="0">
            <header class="ec-batch-group-head">
                <span class="ec-batch-group-number">${String(index + 1).padStart(2,'0')}</span>
                <div><strong>${escapeHtml(group.styleName)}</strong><small class="status-${escapeHtml(group.status)}">${escapeHtml(statusText(group))}</small></div>
                <button type="button" data-batch-run="${escapeHtml(group.id)}" ${canGenerate ? '' : 'disabled'}>${running ? '处理中' : '生成'}</button>
                <button type="button" class="danger" data-batch-remove-group="${escapeHtml(group.id)}" ${running ? 'disabled' : ''} aria-label="删除换款任务">×</button>
            </header>
            <div class="ec-batch-group-slots">
                ${INPUTS.map(item => inputCardHtml(group, item)).join('')}
                <button type="button" class="ec-batch-view-card ${preview ? 'has-image' : ''}" data-batch-view="${escapeHtml(group.id)}">
                    <span class="ec-batch-input-label">查看</span>
                    ${preview ? `<img src="${escapeHtml(preview.url)}" alt="${escapeHtml(group.styleName)}作品"><strong>${group.works.length} 张作品</strong>` : '<span class="ec-batch-view-icon">↗</span><strong>查看作品</strong><small>生成结果将在右侧显示</small>'}
                </button>
            </div>
            ${group.error ? `<p class="ec-batch-group-error">${escapeHtml(group.error)}</p>` : ''}
        </article>`;
    }

    function renderGroups(){
        if(!el.groups) return;
        el.groups.classList.toggle('is-single', state.groups.length === 1);
        el.groups.innerHTML = state.groups.length
            ? state.groups.map(groupHtml).join('')
            : `<div class="ec-batch-empty"><span>＋</span><h3>添加第一个换款任务</h3><p>每组固定包含目标图、服装参考、模特主体、场景和查看。</p><button type="button" data-batch-empty-add>添加换款</button></div>`;
        if(el.runAll) {
            const runnable = state.groups.filter(group => group.inputs.pose_reference?.url && group.inputs.target_image?.url && !ACTIVE_STATUSES.has(group.status));
            el.runAll.disabled = !runnable.length;
            el.runAll.textContent = runnable.length > 1 ? `一键生成全部 · ${runnable.length}` : '一键生成全部';
        }
    }

    function currentWork(group){
        if(!group?.works.length) return null;
        state.selectedImageIndex = Math.max(0, Math.min(group.works.length - 1, state.selectedImageIndex));
        return group.works[state.selectedImageIndex];
    }

    function renderWorks(){
        if(!el.works) return;
        const group = selectedGroup();
        if(!group) {
            el.works.innerHTML = `<div class="ec-batch-works-empty"><span>WORKS</span><h3>查看作品</h3><p>选择或新建换款任务后，生成图片会按款号集中显示。</p></div>`;
            return;
        }
        const work = currentWork(group);
        if(!work) {
            el.works.innerHTML = `<div class="ec-batch-works-shell"><header><div><span>SELECTED STYLE</span><h2>${escapeHtml(group.styleName)}</h2></div><strong>${escapeHtml(statusText(group))}</strong></header><div class="ec-batch-works-empty"><span>${ACTIVE_STATUSES.has(group.status) ? 'GENERATING' : 'NO WORKS'}</span><h3>${ACTIVE_STATUSES.has(group.status) ? '正在生成作品' : '本组尚无作品'}</h3><p>${escapeHtml(group.error || '补齐目标图与服装参考后即可开始生成。')}</p></div></div>`;
            return;
        }
        el.works.innerHTML = `<div class="ec-batch-works-shell">
            <header><div><span>SELECTED STYLE</span><h2>${escapeHtml(group.styleName)}</h2></div><strong>${state.selectedImageIndex + 1} / ${group.works.length}</strong></header>
            <div class="ec-batch-work-stage"><img src="${escapeHtml(work.url)}" alt="${escapeHtml(group.styleName)} 生成作品"></div>
            <div class="ec-batch-work-toolbar">
                <button type="button" data-batch-download-selected>下载当前</button>
                <button type="button" data-batch-download-all>下载本组</button>
                <button type="button" class="danger" data-batch-delete-selected>删除当前</button>
                <button type="button" class="danger" data-batch-delete-all>删除本组全部</button>
            </div>
            <div class="ec-batch-work-thumbs">${group.works.map((item,index) => `<button type="button" class="${index === state.selectedImageIndex ? 'active' : ''}" data-batch-work-index="${index}"><img src="${escapeHtml(item.url)}" alt="作品 ${index + 1}"><span>${index + 1}</span></button>`).join('')}</div>
            ${work.archivedPath ? `<p class="ec-batch-archive-path" title="${escapeHtml(work.archivedPath)}">已归档：${escapeHtml(work.archivedPath)}</p>` : ''}
        </div>`;
    }

    function renderPromptStatus(){
        if(!el.promptStatus) return;
        const count = Object.keys(global.PoseReplicateSettings?.sharedOverrides?.() || {}).length;
        el.promptStatus.textContent = count ? `已同步 ${count} 个自定义组合` : '使用一键复刻内置提示词';
    }

    function render(){
        if(!state.initialized || !isActive()) return;
        renderGroups();
        renderWorks();
        renderPromptStatus();
    }

    function selectGroup(id){
        if(!groupById(id)) return;
        state.selectedGroupId = id;
        state.selectedImageIndex = 0;
        persist();
        render();
    }

    function removeGroup(id){
        const group = groupById(id);
        if(!group || ACTIVE_STATUSES.has(group.status)) return;
        const copy = group.works.length ? `任务内仍有 ${group.works.length} 张作品，移除任务不会删除图片。` : '';
        if(!confirm(`确认移除款号“${group.styleName}”的任务卡？${copy}`)) return;
        state.groups = state.groups.filter(item => item.id !== id);
        if(state.selectedGroupId === id) state.selectedGroupId = state.groups[0]?.id || '';
        state.selectedImageIndex = 0;
        persist();
        render();
    }

    function chooseUpload(groupId, role){
        if(!groupById(groupId) || !INPUTS.some(item => item.role === role)) return;
        state.uploadTarget = {groupId, role};
        el.fileInput.click();
    }

    async function uploadFile(file){
        if(!file || !file.type.startsWith('image/')) throw new Error('请选择 PNG、JPG 或 WEBP 图片');
        if(file.size > 50 * 1024 * 1024) throw new Error('单张图片不能超过 50MB');
        const form = new FormData();
        form.append('files', file, file.name || 'batch-outfit.png');
        const result = await fetchJson('/api/ai/upload', {method:'POST', body:form});
        const uploaded = result.files?.[0];
        if(!uploaded?.url) throw new Error('图片上传没有返回可用地址');
        return cleanImage({...uploaded, name:uploaded.name || file.name});
    }

    async function handleFileSelection(file){
        const target = state.uploadTarget;
        state.uploadTarget = null;
        const group = groupById(target?.groupId);
        if(!group || !target?.role || !file) return;
        group.status = 'uploading';
        group.error = '';
        render();
        try {
            const image = await uploadFile(file);
            group.inputs[target.role] = image;
            if(target.role === 'pose_reference') {
                group.controlMap = null;
                group.controlSourceUrl = '';
            }
            group.status = 'draft';
            group.updatedAt = Date.now();
            persist();
            render();
        } catch(error) {
            group.status = 'failed';
            group.error = error.message || '图片上传失败';
            persist();
            render();
        }
    }

    function removeInput(groupId, role){
        const group = groupById(groupId);
        if(!group || !group.inputs[role]) return;
        delete group.inputs[role];
        if(role === 'pose_reference') {
            group.controlMap = null;
            group.controlSourceUrl = '';
        }
        group.status = 'draft';
        group.error = '';
        persist();
        render();
    }

    async function waitForDwpose(){
        const deadline = Date.now() + 15 * 60 * 1000;
        while(Date.now() < deadline) {
            const status = await fetchJson('/api/dwpose/status', {cache:'no-store'});
            if(status.ready) return;
            if(status.state === 'failed') throw new Error(status.message || 'DWPose 模型准备失败');
            await sleep(1500);
        }
        throw new Error('DWPose 模型准备超时');
    }

    async function uploadBlob(blob, name){
        const file = new File([blob], name, {type:blob.type || 'image/png'});
        return uploadFile(file);
    }

    async function ensureControlMap(group){
        const source = group.inputs.pose_reference;
        if(!source?.url) throw new Error('请先添加目标图');
        if(group.controlMap?.url && group.controlSourceUrl === source.url) return group.controlMap;
        group.status = 'preparing';
        group.error = '';
        render();
        const sourceResponse = await fetch(source.url);
        if(!sourceResponse.ok) throw new Error('目标图读取失败');
        const sourceBlob = await sourceResponse.blob();
        const request = () => {
            const form = new FormData();
            form.append('file', sourceBlob, source.name || 'target.png');
            return fetch('/api/dwpose/detect', {method:'POST', body:form});
        };
        let response = await request();
        if(response.status === 503) {
            await waitForDwpose();
            response = await request();
        }
        if(!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.detail || '目标图骨架提取失败');
        }
        group.controlMap = await uploadBlob(await response.blob(), `batch-outfit-pose-${Date.now()}.png`);
        group.controlSourceUrl = source.url;
        persist();
        return group.controlMap;
    }

    function resolveGenerationRoute(group){
        const studio = api();
        const models = studio?.state?.capabilities?.models || [];
        const referenceCount = 3 + (group.inputs.model_subject?.url ? 1 : 0) + (group.inputs.scene?.url ? 1 : 0);
        const supports = item => Number(item.max_reference_images || 0) >= referenceCount;
        let route = studio.state.model
            ? models.find(item => item.provider_id === studio.state.providerId && item.model === studio.state.model && supports(item))
            : null;
        const preferred = studio.state.capabilities?.routes?.standard;
        if(!route && preferred && (!studio.state.providerId || preferred.provider_id === studio.state.providerId)) {
            route = models.find(item => item.provider_id === preferred.provider_id && item.model === preferred.model && supports(item));
        }
        if(!route && studio.state.providerId) route = models.find(item => item.provider_id === studio.state.providerId && supports(item));
        if(!route) route = models.find(supports);
        if(!route) throw new Error(`当前没有支持 ${referenceCount} 张参考图的已配置模型`);
        return route;
    }

    function appendTaskResult(group, task){
        const result = task?.result || {};
        const images = Array.isArray(result.images) ? result.images : [];
        const workIds = Array.isArray(result.work_ids) ? result.work_ids : [];
        const archives = Array.isArray(result.batch_outfit_archive) ? result.batch_outfit_archive : [];
        const existing = new Set(group.works.map(work => work.url));
        images.forEach((url, index) => {
            if(!url || existing.has(url)) return;
            const archive = archives.find(item => item.source_url === url) || archives[index] || {};
            group.works.push(cleanWork({
                url,
                name:archive.name || `batch-outfit-${group.works.length + 1}.png`,
                workId:workIds[index] || '',
                archivePath:archive.relative_path || '',
                archivedPath:archive.path || '',
                createdAt:Date.now(),
            }));
            existing.add(url);
        });
        if(result.batch_outfit_save_error) group.error = `图片已生成，但按款号归档失败：${result.batch_outfit_save_error}`;
    }

    async function pollTask(group, taskId){
        if(state.pollers.has(taskId)) return state.pollers.get(taskId);
        const promise = (async () => {
            try {
                while(true) {
                    const task = await fetchJson(`/api/canvas-image-tasks/${encodeURIComponent(taskId)}`, {cache:'no-store'});
                    group.status = String(task.status || 'running');
                    group.updatedAt = Date.now();
                    if(!ACTIVE_STATUSES.has(group.status)) {
                        if(group.status === 'succeeded') appendTaskResult(group, task);
                        else group.error = String(task.error || '批量换款生成失败');
                        persist();
                        render();
                        return task;
                    }
                    render();
                    await sleep(1500);
                }
            } catch(error) {
                group.status = 'interrupted';
                group.error = error.message || '任务状态读取失败';
                persist();
                render();
                throw error;
            } finally {
                state.pollers.delete(taskId);
            }
        })();
        state.pollers.set(taskId, promise);
        return promise;
    }

    async function runGroup(groupId){
        const group = groupById(groupId);
        if(!group || ACTIVE_STATUSES.has(group.status) || ['uploading','preparing'].includes(group.status)) return;
        if(!group.inputs.pose_reference?.url || !group.inputs.target_image?.url) {
            group.error = '目标图和服装参考为必填项';
            render();
            return;
        }
        showError('');
        group.error = '';
        try {
            const controlMap = await ensureControlMap(group);
            const route = resolveGenerationRoute(group);
            const studioState = api().state;
            const ratio = ['source','1:1','16:9','9:16','4:3','3:4','4:5'].includes(studioState.aspectRatio) ? studioState.aspectRatio : 'source';
            const resolution = ['1k','2k','4k'].includes(studioState.resolution) ? studioState.resolution : '2k';
            const policyInputs = {mode:'skeleton', modelSubject:group.inputs.model_subject || null, scene:group.inputs.scene || null};
            const payload = {
                mode:'skeleton',
                inputs:{
                    pose_reference:group.inputs.pose_reference,
                    control_map:controlMap,
                    target_image:group.inputs.target_image,
                    model_subject:group.inputs.model_subject || null,
                    scene:group.inputs.scene || null,
                },
                user_instruction:'',
                generation:{provider_id:route.provider_id, model:route.model, resolution, aspect_ratio:ratio, quality:'high', count:1},
                prompt_policy:global.PoseReplicateSettings.sharedPromptPolicy(policyInputs),
                control_signature:`batch-outfit|${group.inputs.pose_reference.url}`,
                batch_outfit:{group_id:group.id, style_name:group.styleName},
            };
            group.status = 'queued';
            group.updatedAt = Date.now();
            persist();
            render();
            const task = await fetchJson('/api/canvas/pose-replicate-tasks', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify(payload),
            });
            const taskId = String(task.task_id || '');
            if(!taskId) throw new Error('一键复刻任务没有返回任务 ID');
            group.currentTaskId = taskId;
            group.taskIds.push(taskId);
            group.taskIds = group.taskIds.slice(-40);
            group.status = String(task.status || 'queued');
            persist();
            render();
            await pollTask(group, taskId);
        } catch(error) {
            group.status = 'failed';
            group.error = error.message || '批量换款生成失败';
            persist();
            render();
        }
    }

    async function runAll(){
        const runnable = state.groups.filter(group => group.inputs.pose_reference?.url && group.inputs.target_image?.url && !ACTIVE_STATUSES.has(group.status) && !['uploading','preparing'].includes(group.status));
        if(!runnable.length) {
            showError('请先为至少一组补齐目标图和服装参考');
            return;
        }
        showError('');
        await Promise.allSettled(runnable.map(group => runGroup(group.id)));
    }

    function resumePendingTasks(){
        state.groups.forEach(group => {
            if(group.currentTaskId && ACTIVE_STATUSES.has(group.status)) pollTask(group, group.currentTaskId).catch(() => {});
        });
    }

    async function downloadWorks(works){
        const items = works.map((work,index) => ({url:work.url, name:work.name || `batch-outfit-${index + 1}.png`}));
        if(!items.length) return;
        try {
            if(items.length === 1) await global.ShiyinQuickSave?.save?.(items[0]);
            else await global.ShiyinQuickSave?.saveAll?.(items);
        } catch(error) {
            showToast(`下载失败：${error.message}`, true);
        }
    }

    async function deleteWorks(group, indexes){
        const selected = indexes.map(index => group.works[index]).filter(Boolean);
        if(!selected.length) return;
        if(!confirm(`确认永久删除“${group.styleName}”选中的 ${selected.length} 张图片？此操作会同时删除作品文件和款号归档副本。`)) return;
        try {
            await fetchJson('/api/ecommerce/batch-outfit/images', {
                method:'DELETE',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({
                    work_ids:selected.map(work => work.workId).filter(Boolean),
                    archive_paths:selected.map(work => work.archivePath).filter(Boolean),
                }),
            });
            const remove = new Set(selected);
            group.works = group.works.filter(work => !remove.has(work));
            state.selectedImageIndex = Math.max(0, Math.min(state.selectedImageIndex, group.works.length - 1));
            group.updatedAt = Date.now();
            persist();
            render();
            showToast(`已删除 ${selected.length} 张批量换款图片`);
        } catch(error) {
            showToast(`删除失败：${error.message}`, true);
        }
    }

    function bindEvents(){
        el.add?.addEventListener('click', openAddDialog);
        el.runAll?.addEventListener('click', runAll);
        el.form?.addEventListener('submit', submitAddDialog);
        el.fileInput?.addEventListener('change', event => {
            const file = event.target.files?.[0];
            event.target.value = '';
            if(file) handleFileSelection(file);
        });
        el.groups?.addEventListener('click', event => {
            if(event.target.closest('[data-batch-empty-add]')) { openAddDialog(); return; }
            const article = event.target.closest('[data-batch-group]');
            if(!article) return;
            const groupId = article.dataset.batchGroup;
            const removeInputButton = event.target.closest('[data-batch-remove-input]');
            if(removeInputButton) { event.preventDefault(); event.stopPropagation(); removeInput(groupId, removeInputButton.dataset.batchRemoveInput); return; }
            const upload = event.target.closest('[data-batch-upload]');
            if(upload) { event.preventDefault(); event.stopPropagation(); chooseUpload(groupId, upload.dataset.batchUpload); return; }
            const run = event.target.closest('[data-batch-run]');
            if(run) { event.preventDefault(); event.stopPropagation(); runGroup(run.dataset.batchRun); return; }
            const remove = event.target.closest('[data-batch-remove-group]');
            if(remove) { event.preventDefault(); event.stopPropagation(); removeGroup(remove.dataset.batchRemoveGroup); return; }
            selectGroup(groupId);
        });
        el.groups?.addEventListener('keydown', event => {
            const article = event.target.closest('[data-batch-group]');
            if(article && event.target === article && (event.key === 'Enter' || event.key === ' ')) {
                event.preventDefault();
                selectGroup(article.dataset.batchGroup);
            }
        });
        el.works?.addEventListener('click', event => {
            const group = selectedGroup();
            if(!group) return;
            const thumb = event.target.closest('[data-batch-work-index]');
            if(thumb) { state.selectedImageIndex = Number(thumb.dataset.batchWorkIndex || 0); persist(); renderWorks(); return; }
            if(event.target.closest('[data-batch-download-selected]')) { const work = currentWork(group); if(work) downloadWorks([work]); return; }
            if(event.target.closest('[data-batch-download-all]')) { downloadWorks(group.works); return; }
            if(event.target.closest('[data-batch-delete-selected]')) { deleteWorks(group, [state.selectedImageIndex]); return; }
            if(event.target.closest('[data-batch-delete-all]')) { deleteWorks(group, group.works.map((_,index) => index)); }
        });
        global.addEventListener('pose-replicate-templates-changed', renderPromptStatus);
    }

    function init(){
        Object.assign(el, {
            control:document.getElementById('batchOutfitControl'),
            groups:document.getElementById('batchOutfitGroups'),
            works:document.getElementById('batchOutfitWorks'),
            error:document.getElementById('batchOutfitError'),
            promptStatus:document.getElementById('batchOutfitPromptStatus'),
            add:document.getElementById('addBatchOutfit'),
            runAll:document.getElementById('runAllBatchOutfit'),
            dialog:document.getElementById('batchOutfitDialog'),
            form:document.getElementById('batchOutfitForm'),
            styleName:document.getElementById('batchOutfitStyleName'),
            dialogError:document.getElementById('batchOutfitDialogError'),
            fileInput:document.getElementById('batchOutfitFileInput'),
        });
        state.initialized = true;
        bindEvents();
        hydrate(api()?.state?.batchOutfit || {});
        render();
    }

    global.EcommerceBatchOutfit = {init, activate:render, render, hydrate, snapshot, runGroup};
    document.addEventListener('DOMContentLoaded', init, {once:true});
})(window);
