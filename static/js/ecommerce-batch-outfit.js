(function(global){
    'use strict';

    const ACTIVE_STATUSES = new Set(['queued','running','jimeng_pending','recovery_pending']);
    const PERSON_DEPTH_ACTIVE_STATES = new Set(['checking','downloading','verifying','installing','smoke']);
    const TARGET_IMAGE_MAX = 20;
    const GRID_RATIOS = ['16:9','4:5','1:1','3:4','9:16','4:3','3:2','2:3'];
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
        controlPromises:new Map(),
        gridRatio:'16:9',
        workStageHovered:false,
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
    const inputImages = (group, role) => {
        const value = group?.inputs?.[role];
        return (Array.isArray(value) ? value : value?.url ? [value] : []).filter(item => item?.url);
    };
    const hasRequiredInputs = group => Boolean(group?.inputs?.pose_reference?.url && inputImages(group, 'target_image').length);

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
            if(item.role === 'target_image') {
                const images = (Array.isArray(value.inputs?.[item.role]) ? value.inputs[item.role] : [value.inputs?.[item.role]])
                    .map(cleanImage).filter(Boolean).slice(0, TARGET_IMAGE_MAX);
                if(images.length) inputs[item.role] = images;
                return;
            }
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
            runTaskIds:(Array.isArray(value.runTaskIds) ? value.runTaskIds : value.run_task_ids || []).map(item => String(item || '')).filter(Boolean).slice(-TARGET_IMAGE_MAX),
            taskStatuses:(value.taskStatuses && typeof value.taskStatuses === 'object')
                ? {...value.taskStatuses}
                : (value.task_statuses && typeof value.task_statuses === 'object') ? {...value.task_statuses} : {},
            targetImageIndex:Number.isFinite(Number(value.targetImageIndex ?? value.target_image_index))
                ? Math.max(0, Number(value.targetImageIndex ?? value.target_image_index))
                : 0,
            status:String(value.status || 'draft'),
            error:String(value.error || ''),
            works,
            updatedAt:Number(value.updatedAt || value.updated_at || Date.now()),
        };
    }

    function snapshot(){
        return {
            schema_version:2,
            grid_ratio:state.gridRatio,
            groups:state.groups.map(group => ({
                id:group.id,
                style_name:group.styleName,
                inputs:group.inputs,
                control_map:group.controlMap,
                control_source_url:group.controlSourceUrl,
                task_ids:group.taskIds,
                current_task_id:group.currentTaskId,
                run_task_ids:group.runTaskIds,
                task_statuses:group.taskStatuses,
                target_image_index:group.targetImageIndex,
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
        state.gridRatio = GRID_RATIOS.includes(String(value?.grid_ratio || '')) ? String(value.grid_ratio) : '16:9';
        state.groups = groups;
        state.selectedGroupId = groups.some(group => group.id === value?.selected_group_id)
            ? String(value.selected_group_id)
            : (groups[0]?.id || '');
        state.selectedImageIndex = Math.max(0, Number(value?.selected_image_index || 0));
        if(api()?.state) api().state.batchOutfit = snapshot();
        applyGridRatio();
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
        if(group.status === 'preparing') return '正在提取深度图';
        if(group.status === 'queued') return '已排队';
        if(group.status === 'running' || group.status === 'jimeng_pending' || group.status === 'recovery_pending') return '正在生成';
        if(group.status === 'succeeded') return group.works.length ? `已生成 ${group.works.length} 张` : '生成完成';
        if(group.status === 'failed' || group.status === 'interrupted') return '生成失败';
        return group.inputs.pose_reference || inputImages(group, 'target_image').length ? '待完善' : '待添加素材';
    }

    function applyGridRatio(){
        const ratio = GRID_RATIOS.includes(state.gridRatio) ? state.gridRatio : '16:9';
        const [width,height] = ratio.split(':').map(Number);
        el.control?.style.setProperty('--ec-batch-card-aspect', `${width} / ${height}`);
        if(el.gridRatio) el.gridRatio.value = ratio;
    }

    function inputCardHtml(group, item){
        const images = inputImages(group, item.role);
        if(item.role === 'target_image') group.targetImageIndex = Math.max(0, Math.min(images.length - 1, Number(group.targetImageIndex || 0)));
        const selectedIndex = item.role === 'target_image' ? group.targetImageIndex : 0;
        const image = images[selectedIndex] || null;
        const hasStack = images.length > 1;
        const stack = hasStack ? `<span class="ec-batch-card-shadow one" aria-hidden="true"></span><span class="ec-batch-card-shadow two" aria-hidden="true"></span>` : '';
        const controls = hasStack ? `<span class="ec-batch-stack-controls">
            <span data-batch-input-step="-1" data-batch-input-role="${item.role}" role="button" aria-label="上一张服装参考">‹</span>
            <b>${selectedIndex + 1}/${images.length}</b>
            <span data-batch-input-step="1" data-batch-input-role="${item.role}" role="button" aria-label="下一张服装参考">›</span>
        </span>` : '';
        const depthStatus = item.role === 'pose_reference' && image
            ? group.controlMap?.url && group.controlSourceUrl === image.url
                ? `<span class="ec-batch-depth-chip is-ready"><img src="${escapeHtml(group.controlMap.url)}" alt="">深度图 ✓</span>`
                : `<span class="ec-batch-depth-chip ${group.status === 'preparing' ? 'is-loading' : ''}">${group.status === 'preparing' ? '深度提取中' : '等待深度图'}</span>`
            : '';
        const actionText = item.role === 'target_image' && image ? `继续添加 · ${images.length}/${TARGET_IMAGE_MAX}` : '点击替换';
        return `<button type="button" class="ec-batch-input-card ${image ? 'has-image' : ''} ${hasStack ? 'has-stack' : ''}" data-batch-upload="${item.role}" aria-label="${escapeHtml(item.label)}">
            <span class="ec-batch-input-label">${escapeHtml(item.label)}${item.required ? '<em>*</em>' : ''}</span>
            ${image ? `<span class="ec-batch-card-stack">${stack}<img src="${escapeHtml(image.url)}" alt="${escapeHtml(item.label)}">${controls}</span><small title="${escapeHtml(image.name || item.hint)}">${escapeHtml(image.name || item.hint)}</small><span class="ec-batch-input-replace">${actionText}</span>${depthStatus}` : `<span class="ec-batch-input-plus">+</span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.hint)}</small>`}
            ${image ? `<span class="ec-batch-input-remove" data-batch-remove-input="${item.role}" data-batch-remove-index="${selectedIndex}" role="button" aria-label="移除${escapeHtml(item.label)}">×</span>` : ''}
        </button>`;
    }

    function groupHtml(group, index){
        const selected = group.id === state.selectedGroupId;
        const running = ACTIVE_STATUSES.has(group.status) || ['uploading','preparing'].includes(group.status);
        const canGenerate = hasRequiredInputs(group) && !running;
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
            const runnable = state.groups.filter(group => hasRequiredInputs(group) && !ACTIVE_STATUSES.has(group.status));
            el.runAll.disabled = !runnable.length;
            el.runAll.textContent = runnable.length > 1 ? `一键生成全部 · ${runnable.length}` : '一键生成全部';
        }
    }

    function currentWork(group){
        if(!group?.works.length) return null;
        state.selectedImageIndex = Math.max(0, Math.min(group.works.length - 1, state.selectedImageIndex));
        return group.works[state.selectedImageIndex];
    }

    function previewIsOpen(){
        return Boolean(el.preview?.open);
    }

    function renderWorkPreview(){
        if(!el.preview) return;
        const group = selectedGroup();
        const work = currentWork(group);
        if(!group || !work) {
            if(el.preview.open) el.preview.close();
            return;
        }
        el.previewTitle.textContent = group.styleName;
        el.previewCount.textContent = `${state.selectedImageIndex + 1} / ${group.works.length}`;
        el.previewImage.src = work.url;
        el.previewImage.alt = `${group.styleName} 生成作品 ${state.selectedImageIndex + 1}`;
        el.preview.querySelector('[data-batch-preview-step="-1"]').disabled = state.selectedImageIndex <= 0;
        el.preview.querySelector('[data-batch-preview-step="1"]').disabled = state.selectedImageIndex >= group.works.length - 1;
    }

    function selectWorkIndex(index){
        const group = selectedGroup();
        if(!group?.works.length) return false;
        const nextIndex = Math.max(0, Math.min(group.works.length - 1, Number(index || 0)));
        state.selectedImageIndex = nextIndex;
        persist();
        if(previewIsOpen()) renderWorkPreview();
        else renderWorks();
        return true;
    }

    function stepWork(delta){
        return selectWorkIndex(state.selectedImageIndex + Number(delta || 0));
    }

    function openWorkPreview(){
        const group = selectedGroup();
        if(!currentWork(group) || !el.preview) return;
        renderWorkPreview();
        if(!el.preview.open) el.preview.showModal();
        requestAnimationFrame(() => el.previewStage?.focus());
    }

    function closeWorkPreview(){
        if(el.preview?.open) el.preview.close();
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
            <div class="ec-batch-work-stage" data-batch-work-stage tabindex="0">
                <button class="ec-batch-work-nav previous" type="button" data-batch-work-step="-1" aria-label="上一张作品" ${state.selectedImageIndex <= 0 ? 'disabled' : ''}>‹</button>
                <button class="ec-batch-work-preview" type="button" data-batch-work-preview aria-label="全屏查看作品 ${state.selectedImageIndex + 1}"><img src="${escapeHtml(work.url)}" alt="${escapeHtml(group.styleName)} 生成作品" draggable="false"></button>
                <button class="ec-batch-work-nav next" type="button" data-batch-work-step="1" aria-label="下一张作品" ${state.selectedImageIndex >= group.works.length - 1 ? 'disabled' : ''}>›</button>
            </div>
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
        if(!group || ACTIVE_STATUSES.has(group.status) || ['uploading','preparing'].includes(group.status)) return;
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
        el.fileInput.multiple = role === 'target_image';
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

    async function handleFileSelection(files){
        const target = state.uploadTarget;
        state.uploadTarget = null;
        const group = groupById(target?.groupId);
        const selected = Array.from(files || []).filter(Boolean);
        if(!group || !target?.role || !selected.length) return;
        const currentTargets = inputImages(group, 'target_image');
        const accepted = target.role === 'target_image'
            ? selected.slice(0, Math.max(0, TARGET_IMAGE_MAX - currentTargets.length))
            : selected.slice(0, 1);
        if(!accepted.length) {
            showToast(`服装参考最多添加 ${TARGET_IMAGE_MAX} 张`, true);
            return;
        }
        group.status = 'uploading';
        group.error = '';
        render();
        try {
            const images = await Promise.all(accepted.map(uploadFile));
            if(target.role === 'target_image') {
                group.inputs.target_image = [...currentTargets, ...images].slice(0, TARGET_IMAGE_MAX);
                group.targetImageIndex = currentTargets.length;
                if(accepted.length < selected.length) showToast(`已达到 ${TARGET_IMAGE_MAX} 张服装参考上限`, true);
            } else group.inputs[target.role] = images[0];
            if(target.role === 'pose_reference') {
                group.controlMap = null;
                group.controlSourceUrl = '';
            }
            group.status = 'draft';
            group.updatedAt = Date.now();
            persist();
            render();
            if(target.role === 'pose_reference') await ensureControlMap(group);
        } catch(error) {
            group.status = 'failed';
            group.error = error.message || '图片上传失败';
            persist();
            render();
        }
    }

    function removeInput(groupId, role, index=-1){
        const group = groupById(groupId);
        if(!group || !group.inputs[role]) return;
        if(role === 'target_image') {
            const images = inputImages(group, role);
            const removeIndex = Math.max(0, Math.min(images.length - 1, Number(index >= 0 ? index : group.targetImageIndex || 0)));
            images.splice(removeIndex, 1);
            if(images.length) group.inputs[role] = images;
            else delete group.inputs[role];
            group.targetImageIndex = Math.max(0, Math.min(removeIndex, images.length - 1));
        } else delete group.inputs[role];
        if(role === 'pose_reference') {
            group.controlMap = null;
            group.controlSourceUrl = '';
        }
        group.status = 'draft';
        group.error = '';
        persist();
        render();
    }

    function stepInput(groupId, role, step){
        const group = groupById(groupId);
        const images = inputImages(group, role);
        if(!group || images.length < 2 || role !== 'target_image') return;
        group.targetImageIndex = (Number(group.targetImageIndex || 0) + Number(step || 0) + images.length) % images.length;
        persist();
        renderGroups();
    }

    async function waitForPersonDepth(){
        const deadline = Date.now() + 15 * 60 * 1000;
        while(Date.now() < deadline) {
            const status = await fetchJson('/api/person-depth/component/status', {cache:'no-store'});
            if(status.ready) return;
            if(status.state === 'failed') throw new Error(status.message || '高精度人物深度组件准备失败');
            await sleep(1500);
        }
        throw new Error('高精度人物深度组件准备超时');
    }

    async function ensurePersonDepthReady(){
        const status = await fetchJson('/api/person-depth/component/status', {cache:'no-store'});
        if(status.ready) return;
        if(['idle','missing'].includes(String(status.state || '')) && status.install_available) {
            await fetchJson('/api/person-depth/component/install', {method:'POST'});
        } else if(!PERSON_DEPTH_ACTIVE_STATES.has(String(status.state || ''))) {
            throw new Error(status.message || '高精度人物深度组件尚未就绪');
        }
        await waitForPersonDepth();
    }

    async function uploadBlob(blob, name){
        const file = new File([blob], name, {type:blob.type || 'image/png'});
        return uploadFile(file);
    }

    async function ensureControlMap(group){
        const source = group.inputs.pose_reference;
        if(!source?.url) throw new Error('请先添加目标图');
        if(group.controlMap?.url && group.controlSourceUrl === source.url) return group.controlMap;
        const existing = state.controlPromises.get(group.id);
        if(existing?.sourceUrl === source.url) return existing.promise;
        const promise = (async () => {
            group.status = 'preparing';
            group.error = '';
            persist();
            render();
            await ensurePersonDepthReady();
            const sourceResponse = await fetch(source.url);
            if(!sourceResponse.ok) throw new Error('目标图读取失败');
            const form = new FormData();
            form.append('file', await sourceResponse.blob(), source.name || 'target.png');
            form.append('bit_depth', '8');
            const response = await fetch('/api/person-depth/estimate', {method:'POST', body:form});
            if(!response.ok) {
                const data = await response.json().catch(() => ({}));
                throw new Error(data.detail || '高精度人物深度图生成失败');
            }
            const controlMap = await uploadBlob(await response.blob(), `batch-outfit-depth-${Date.now()}.png`);
            if(group.inputs.pose_reference?.url !== source.url) return null;
            group.controlMap = controlMap;
            group.controlSourceUrl = source.url;
            group.status = 'draft';
            group.error = '';
            group.updatedAt = Date.now();
            persist();
            render();
            return controlMap;
        })().catch(error => {
            if(group.inputs.pose_reference?.url === source.url) {
                group.status = 'failed';
                group.error = error.message || '高精度人物深度图生成失败';
                persist();
                render();
            }
            throw error;
        }).finally(() => {
            if(state.controlPromises.get(group.id)?.promise === promise) state.controlPromises.delete(group.id);
        });
        state.controlPromises.set(group.id, {sourceUrl:source.url, promise});
        return promise;
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

    function refreshRunStatus(group){
        const ids = Array.isArray(group.runTaskIds) ? group.runTaskIds : [];
        const statuses = ids.map(id => String(group.taskStatuses?.[id] || 'queued'));
        if(!statuses.length) return;
        if(statuses.some(status => ACTIVE_STATUSES.has(status))) group.status = 'running';
        else if(statuses.some(status => status === 'succeeded')) group.status = 'succeeded';
        else if(statuses.every(status => ['failed','interrupted','cancelled'].includes(status))) group.status = 'failed';
        else group.status = statuses[statuses.length - 1] || group.status;
    }

    async function pollTask(group, taskId){
        if(state.pollers.has(taskId)) return state.pollers.get(taskId);
        const promise = (async () => {
            try {
                while(true) {
                    const task = await fetchJson(`/api/canvas-image-tasks/${encodeURIComponent(taskId)}`, {cache:'no-store'});
                    const taskStatus = String(task.status || 'running');
                    group.taskStatuses[taskId] = taskStatus;
                    refreshRunStatus(group);
                    group.updatedAt = Date.now();
                    if(!ACTIVE_STATUSES.has(taskStatus)) {
                        if(taskStatus === 'succeeded') appendTaskResult(group, task);
                        else group.error = [group.error, String(task.error || '批量换款生成失败')].filter(Boolean).join('；');
                        refreshRunStatus(group);
                        persist();
                        render();
                        return task;
                    }
                    render();
                    await sleep(1500);
                }
            } catch(error) {
                group.taskStatuses[taskId] = 'interrupted';
                group.error = [group.error, error.message || '任务状态读取失败'].filter(Boolean).join('；');
                refreshRunStatus(group);
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
        const targetImages = inputImages(group, 'target_image');
        if(!group.inputs.pose_reference?.url || !targetImages.length) {
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
            const quality = ['low','medium','high'].includes(studioState.quality) ? studioState.quality : 'high';
            const policyInputs = {mode:'depth', modelSubject:group.inputs.model_subject || null, scene:group.inputs.scene || null};
            group.status = 'queued';
            group.runTaskIds = [];
            group.taskStatuses = {};
            group.updatedAt = Date.now();
            persist();
            render();
            const submissions = targetImages.map(async (targetImage, index) => {
                const payload = {
                    mode:'depth',
                    inputs:{
                        pose_reference:group.inputs.pose_reference,
                        control_map:controlMap,
                        target_image:targetImage,
                        model_subject:group.inputs.model_subject || null,
                        scene:group.inputs.scene || null,
                    },
                    user_instruction:'',
                    generation:{provider_id:route.provider_id, model:route.model, resolution, aspect_ratio:ratio, quality, count:1},
                    prompt_policy:global.PoseReplicateSettings.sharedPromptPolicy(policyInputs),
                    control_signature:`batch-outfit-depth|${group.inputs.pose_reference.url}`,
                    batch_outfit:{group_id:group.id, style_name:group.styleName},
                };
                try {
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
                    group.runTaskIds.push(taskId);
                    group.taskStatuses[taskId] = String(task.status || 'queued');
                    refreshRunStatus(group);
                    persist();
                    render();
                    return pollTask(group, taskId);
                } catch(error) {
                    group.error = [group.error, `服装参考 ${index + 1}：${error.message || '任务创建失败'}`].filter(Boolean).join('；');
                    throw error;
                }
            });
            const results = await Promise.allSettled(submissions);
            refreshRunStatus(group);
            if(!group.runTaskIds.length) group.status = 'failed';
            else if(results.some(result => result.status === 'rejected') && group.status === 'succeeded') {
                group.error = group.error || '部分服装参考生成失败';
            }
            persist();
            render();
        } catch(error) {
            group.status = 'failed';
            group.error = error.message || '批量换款生成失败';
            persist();
            render();
        }
    }

    async function runAll(){
        const runnable = state.groups.filter(group => hasRequiredInputs(group) && !ACTIVE_STATUSES.has(group.status) && !['uploading','preparing'].includes(group.status));
        if(!runnable.length) {
            showError('请先为至少一组补齐目标图和服装参考');
            return;
        }
        showError('');
        await Promise.allSettled(runnable.map(group => runGroup(group.id)));
    }

    function resumePendingTasks(){
        state.groups.forEach(group => {
            const ids = group.runTaskIds?.length ? group.runTaskIds : [group.currentTaskId].filter(Boolean);
            ids.filter(id => ACTIVE_STATUSES.has(String(group.taskStatuses?.[id] || group.status))).forEach(id => pollTask(group, id).catch(() => {}));
        });
    }

    function resumeDepthMaps(){
        if(!isActive()) return;
        state.groups.filter(group => group.inputs.pose_reference?.url && (!group.controlMap?.url || group.controlSourceUrl !== group.inputs.pose_reference.url))
            .forEach(group => ensureControlMap(group).catch(() => {}));
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
            const files = Array.from(event.target.files || []);
            event.target.value = '';
            if(files.length) handleFileSelection(files);
        });
        el.gridRatio?.addEventListener('change', () => {
            state.gridRatio = GRID_RATIOS.includes(el.gridRatio.value) ? el.gridRatio.value : '16:9';
            applyGridRatio();
            persist();
        });
        el.groups?.addEventListener('click', event => {
            if(event.target.closest('[data-batch-empty-add]')) { openAddDialog(); return; }
            const article = event.target.closest('[data-batch-group]');
            if(!article) return;
            const groupId = article.dataset.batchGroup;
            const removeInputButton = event.target.closest('[data-batch-remove-input]');
            if(removeInputButton) { event.preventDefault(); event.stopPropagation(); removeInput(groupId, removeInputButton.dataset.batchRemoveInput, Number(removeInputButton.dataset.batchRemoveIndex || 0)); return; }
            const stepButton = event.target.closest('[data-batch-input-step]');
            if(stepButton) { event.preventDefault(); event.stopPropagation(); stepInput(groupId, stepButton.dataset.batchInputRole, Number(stepButton.dataset.batchInputStep || 0)); return; }
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
            if(thumb) { selectWorkIndex(Number(thumb.dataset.batchWorkIndex || 0)); return; }
            const step = event.target.closest('[data-batch-work-step]');
            if(step) { stepWork(Number(step.dataset.batchWorkStep || 0)); return; }
            if(event.target.closest('[data-batch-work-preview]')) { openWorkPreview(); return; }
            if(event.target.closest('[data-batch-download-selected]')) { const work = currentWork(group); if(work) downloadWorks([work]); return; }
            if(event.target.closest('[data-batch-download-all]')) { downloadWorks(group.works); return; }
            if(event.target.closest('[data-batch-delete-selected]')) { deleteWorks(group, [state.selectedImageIndex]); return; }
            if(event.target.closest('[data-batch-delete-all]')) { deleteWorks(group, group.works.map((_,index) => index)); }
        });
        el.works?.addEventListener('pointerover', event => {
            if(event.target.closest('[data-batch-work-stage]')) state.workStageHovered = true;
        });
        el.works?.addEventListener('pointerout', event => {
            const stage = event.target.closest('[data-batch-work-stage]');
            if(stage && !stage.contains(event.relatedTarget)) state.workStageHovered = false;
        });
        el.preview?.addEventListener('click', event => {
            if(event.target === el.preview) { closeWorkPreview(); return; }
            const step = event.target.closest('[data-batch-preview-step]');
            if(step) stepWork(Number(step.dataset.batchPreviewStep || 0));
        });
        el.preview?.addEventListener('close', () => {
            if(state.initialized && isActive()) renderWorks();
        });
        el.closePreview?.addEventListener('click', closeWorkPreview);
        document.addEventListener('keydown', event => {
            if(!isActive()) return;
            if(event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
            if(!['ArrowLeft','ArrowRight'].includes(event.key)) return;
            if(event.target?.matches?.('input,textarea,select,[contenteditable="true"]')) return;
            const workStage = el.works?.querySelector('[data-batch-work-stage]');
            if(!previewIsOpen() && !state.workStageHovered && !workStage?.matches?.(':hover') && document.activeElement !== workStage) return;
            const group = selectedGroup();
            if(!group?.works.length) return;
            event.preventDefault();
            stepWork(event.key === 'ArrowLeft' ? -1 : 1);
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
            gridRatio:document.getElementById('batchOutfitGridRatio'),
            preview:document.getElementById('batchOutfitPreview'),
            previewStage:document.getElementById('batchOutfitPreviewStage'),
            previewImage:document.getElementById('batchOutfitPreviewImage'),
            previewTitle:document.getElementById('batchOutfitPreviewTitle'),
            previewCount:document.getElementById('batchOutfitPreviewCount'),
            closePreview:document.getElementById('closeBatchOutfitPreview'),
        });
        state.initialized = true;
        bindEvents();
        hydrate(api()?.state?.batchOutfit || {});
        render();
        resumeDepthMaps();
    }

    function activate(){
        applyGridRatio();
        render();
        resumeDepthMaps();
    }

    global.EcommerceBatchOutfit = {init, activate, render, hydrate, snapshot, runGroup};
    document.addEventListener('DOMContentLoaded', init, {once:true});
})(window);
