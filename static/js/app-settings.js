(function(){
    'use strict';

    const options = document.getElementById('closeBehaviorOptions');
    const status = document.getElementById('saveStatus');
    const outputInput = document.getElementById('generatedOutputDir');
    const outputHint = document.getElementById('generatedOutputHint');
    const closeBehaviorNote = document.getElementById('closeBehaviorNote');
    const chooseOutput = document.getElementById('chooseGeneratedOutput');
    const resetOutput = document.getElementById('resetGeneratedOutput');
    const updatePolicy = document.getElementById('updatePolicy');
    const updateNetworkMode = document.getElementById('updateNetworkMode');
    const updateManualProxy = document.getElementById('updateManualProxy');
    const updateSaveStatus = document.getElementById('updateSaveStatus');
    const checkDesktopUpdate = document.getElementById('checkDesktopUpdate');
    const storageStatus = document.getElementById('storageStatus');
    const storageMediaTotal = document.getElementById('storageMediaTotal');
    const storageMediaDetail = document.getElementById('storageMediaDetail');
    const storageOrphanTotal = document.getElementById('storageOrphanTotal');
    const storageOrphanDetail = document.getElementById('storageOrphanDetail');
    const refreshStorageSummary = document.getElementById('refreshStorageSummary');
    const reconcileMediaStorage = document.getElementById('reconcileMediaStorage');
    const previewOrphanMedia = document.getElementById('previewOrphanMedia');
    const cleanupOrphanMedia = document.getElementById('cleanupOrphanMedia');
    const storageOrphanList = document.getElementById('storageOrphanList');
    const topazStatus = document.getElementById('topazStatus');
    const topazInstallDir = document.getElementById('topazInstallDir');
    const chooseTopazInstall = document.getElementById('chooseTopazInstall');
    const resetTopazInstall = document.getElementById('resetTopazInstall');
    const checkTopazInstall = document.getElementById('checkTopazInstall');
    const topazReadyState = document.getElementById('topazReadyState');
    const topazModelCount = document.getElementById('topazModelCount');
    const topazVersion = document.getElementById('topazVersion');
    const topazSignature = document.getElementById('topazSignature');
    const topazInstallHint = document.getElementById('topazInstallHint');
    const shortcutSaveStatus = document.getElementById('shortcutSaveStatus');
    const shortcutSearch = document.getElementById('shortcutSearch');
    const shortcutCategory = document.getElementById('shortcutCategory');
    const resetAllShortcuts = document.getElementById('resetAllShortcuts');
    const shortcutSummary = document.getElementById('shortcutSummary');
    const shortcutConflict = document.getElementById('shortcutConflict');
    const shortcutList = document.getElementById('shortcutList');
    let currentBehavior = 'ask_on_close';
    let currentOutputDirectory = '';
    let statusTimer = null;
    let updateRequestSequence = 0;
    let lastOrphanPreview = [];
    let currentTopazDirectory = '';
    let shortcutOverrides = {};
    let shortcutRecordingId = '';
    let shortcutSaveSequence = 0;
    let shortcutStatusTimer = null;

    const t = key => window.StudioI18n?.t?.(key) || key;

    function showStatus(message, isError=false){
        clearTimeout(statusTimer);
        status.textContent = message;
        status.classList.toggle('error', isError);
        if(message) statusTimer = setTimeout(() => { status.textContent=''; status.classList.remove('error'); }, 2600);
    }

    function showUpdateStatus(message, isError=false){
        if(!updateSaveStatus) return;
        updateSaveStatus.textContent = message;
        updateSaveStatus.classList.toggle('error', isError);
    }

    function showStorageStatus(message, isError=false){
        if(!storageStatus) return;
        storageStatus.textContent = message;
        storageStatus.classList.toggle('error', isError);
    }

    function showTopazStatus(message, isError=false){
        if(!topazStatus) return;
        topazStatus.textContent = message;
        topazStatus.classList.toggle('error', isError);
    }

    function showShortcutStatus(message, isError=false){
        if(!shortcutSaveStatus) return;
        clearTimeout(shortcutStatusTimer);
        shortcutSaveStatus.textContent = message;
        shortcutSaveStatus.classList.toggle('error', isError);
        if(message && !isError) shortcutStatusTimer = setTimeout(() => { shortcutSaveStatus.textContent = ''; }, 2400);
    }

    function showShortcutConflict(message=''){
        if(!shortcutConflict) return;
        shortcutConflict.hidden = !message;
        shortcutConflict.textContent = message;
    }

    function shortcutBindingParts(binding){
        return String(binding || '').split('+').filter(Boolean);
    }

    function renderShortcutBinding(button, binding, recording){
        button.replaceChildren();
        button.classList.toggle('recording', recording);
        button.setAttribute('aria-pressed', recording ? 'true' : 'false');
        button.title = recording ? '正在录制，点击可取消' : '点击后录入新的快捷键';
        if(recording){
            const label = document.createElement('span');
            label.className = 'unassigned';
            label.textContent = '请按下新的组合键…';
            button.appendChild(label);
            return;
        }
        const parts = shortcutBindingParts(binding);
        if(!parts.length){
            const label = document.createElement('span');
            label.className = 'unassigned';
            label.textContent = '未设置';
            button.appendChild(label);
            return;
        }
        parts.forEach(part => {
            const key = document.createElement('kbd');
            key.textContent = part;
            button.appendChild(key);
        });
    }

    function populateShortcutCategories(){
        if(!shortcutCategory || shortcutCategory.options.length > 1 || !window.ShortcutActions) return;
        [...new Set(window.ShortcutActions.actions.map(action => action.category))].forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category;
            shortcutCategory.appendChild(option);
        });
    }

    function renderShortcutSettings(){
        if(!shortcutList || !window.ShortcutActions) return;
        populateShortcutCategories();
        const query = String(shortcutSearch?.value || '').trim().toLowerCase();
        const category = shortcutCategory?.value || '';
        const resolved = window.ShortcutActions.resolvedBindings(shortcutOverrides);
        const visible = window.ShortcutActions.actions.filter(action => {
            if(category && action.category !== category) return false;
            if(!query) return true;
            return `${action.name} ${action.id} ${action.category}`.toLowerCase().includes(query);
        });
        const customized = Object.keys(shortcutOverrides).length;
        const disabled = Object.values(resolved).filter(binding => !binding).length;
        if(shortcutSummary) shortcutSummary.textContent = `${window.ShortcutActions.actions.length} 项功能 · ${customized} 项自定义 · ${disabled} 项未分配`;
        shortcutList.replaceChildren();
        if(!visible.length){
            const empty = document.createElement('div');
            empty.className = 'app-settings-shortcut-empty';
            empty.textContent = '没有符合条件的快捷键';
            shortcutList.appendChild(empty);
            return;
        }
        const categories = [...new Set(visible.map(action => action.category))];
        categories.forEach(groupName => {
            const group = document.createElement('section');
            group.className = 'app-settings-shortcut-group';
            const heading = document.createElement('h3');
            heading.textContent = `${groupName} · ${visible.filter(action => action.category === groupName).length}`;
            group.appendChild(heading);
            visible.filter(action => action.category === groupName).forEach(action => {
                const row = document.createElement('div');
                row.className = 'app-settings-shortcut-row';
                row.dataset.actionId = action.id;
                const copy = document.createElement('div');
                copy.className = 'app-settings-shortcut-copy';
                const name = document.createElement('b');
                name.textContent = action.name;
                const id = document.createElement('small');
                id.textContent = action.id;
                copy.append(name, id);
                const binding = document.createElement('button');
                binding.type = 'button';
                binding.className = 'app-settings-shortcut-binding';
                binding.dataset.shortcutRecord = action.id;
                renderShortcutBinding(binding, resolved[action.id], shortcutRecordingId === action.id);
                const clear = document.createElement('button');
                clear.type = 'button';
                clear.className = 'app-settings-shortcut-icon-btn';
                clear.dataset.shortcutClear = action.id;
                clear.title = '清空快捷键';
                clear.setAttribute('aria-label', `清空${action.name}快捷键`);
                clear.textContent = '×';
                clear.disabled = !resolved[action.id];
                const reset = document.createElement('button');
                reset.type = 'button';
                reset.className = 'app-settings-shortcut-icon-btn';
                reset.dataset.shortcutReset = action.id;
                reset.title = '恢复默认快捷键';
                reset.setAttribute('aria-label', `恢复${action.name}默认快捷键`);
                reset.textContent = '↺';
                reset.disabled = !Object.prototype.hasOwnProperty.call(shortcutOverrides, action.id);
                row.append(copy, binding, clear, reset);
                group.appendChild(row);
            });
            shortcutList.appendChild(group);
        });
    }

    function broadcastShortcutSettings(){
        if(!window.ShortcutActions) return;
        const payload = JSON.stringify(shortcutOverrides);
        try { localStorage.setItem(window.ShortcutActions.storageKey, payload); } catch(e) {}
        try {
            const channel = new BroadcastChannel(window.ShortcutActions.channelName);
            channel.postMessage({type:'shortcut-bindings:changed', bindings:shortcutOverrides});
            channel.close();
        } catch(e) {}
        try { window.parent?.postMessage({type:'shortcut-bindings:changed', bindings:shortcutOverrides}, location.origin); } catch(e) {}
    }

    function applyShortcutSettings(data){
        shortcutOverrides = window.ShortcutActions?.sanitizeOverrides(data?.shortcut_bindings) || {};
        shortcutRecordingId = '';
        showShortcutConflict('');
        renderShortcutSettings();
        broadcastShortcutSettings();
    }

    async function saveShortcutSettings(nextOverrides, successMessage='已保存'){
        const previous = shortcutOverrides;
        const sequence = ++shortcutSaveSequence;
        shortcutOverrides = window.ShortcutActions.sanitizeOverrides(nextOverrides);
        shortcutRecordingId = '';
        showShortcutConflict('');
        renderShortcutSettings();
        showShortcutStatus('保存中…');
        try {
            const data = await saveSettings({shortcut_bindings:shortcutOverrides});
            if(sequence !== shortcutSaveSequence) return;
            shortcutOverrides = window.ShortcutActions.sanitizeOverrides(data.shortcut_bindings);
            renderShortcutSettings();
            broadcastShortcutSettings();
            showShortcutStatus(successMessage);
        } catch(error) {
            if(sequence !== shortcutSaveSequence) return;
            shortcutOverrides = previous;
            renderShortcutSettings();
            showShortcutStatus(`保存失败：${error.message}`, true);
        }
    }

    function setShortcutBinding(actionId, binding){
        const action = window.ShortcutActions?.get(actionId);
        if(!action) return;
        const validation = window.ShortcutActions.validate(binding, {allowModifierOnly:Boolean(action.hold)});
        if(!validation.ok){
            showShortcutConflict(validation.error);
            showShortcutStatus('快捷键不可用', true);
            return;
        }
        const conflictActions = window.ShortcutActions.conflicts(shortcutOverrides, actionId, validation.binding);
        if(conflictActions.length){
            const names = conflictActions.map(item => `“${item.name}”`).join('、');
            showShortcutConflict(`${validation.binding} 已用于${names}，请先修改冲突项。`);
            showShortcutStatus('存在快捷键冲突', true);
            return;
        }
        const next = {...shortcutOverrides};
        if(validation.binding === window.ShortcutActions.canonicalize(action.defaultBinding)) delete next[actionId];
        else next[actionId] = validation.binding;
        saveShortcutSettings(next);
    }

    function setTopazBusy(busy){
        [chooseTopazInstall, resetTopazInstall, checkTopazInstall].forEach(button => {
            if(button) button.disabled = busy || (button === resetTopazInstall && !currentTopazDirectory);
        });
    }

    function applyTopazSettings(data){
        currentTopazDirectory = String(data.topaz_video_install_dir || '');
        if(topazInstallDir) topazInstallDir.value = currentTopazDirectory;
        if(resetTopazInstall) resetTopazInstall.disabled = !currentTopazDirectory;
    }

    function renderTopazCapabilities(data){
        const ready = Boolean(data?.ready);
        const detected = String(data?.install_dir || '');
        if(topazInstallDir) topazInstallDir.value = currentTopazDirectory || detected;
        if(topazReadyState) topazReadyState.textContent = ready ? '可用' : data?.installed ? '不可用' : '未安装';
        if(topazModelCount) topazModelCount.textContent = String((data?.models || []).length);
        if(topazVersion) topazVersion.textContent = String(data?.version || '--');
        if(topazSignature) topazSignature.textContent = data?.signature_valid ? 'Topaz 签名有效' : String(data?.signature_status || '--');
        if(topazInstallHint) topazInstallHint.textContent = ready
            ? `${currentTopazDirectory ? '使用指定目录' : '已自动检测'} · tvai_up 可用 · 模型目录正常`
            : String(data?.error || 'Topaz Video AI 尚未就绪');
        showTopazStatus(ready ? '检测通过' : '检测未通过', !ready);
    }

    async function checkTopazCapabilities(){
        setTopazBusy(true);
        showTopazStatus('检测中…');
        try {
            renderTopazCapabilities(await requestSettings('/api/topaz-video/capabilities', {cache:'no-store'}));
        } catch(error) {
            showTopazStatus(`检测失败：${error.message}`, true);
            if(topazInstallHint) topazInstallHint.textContent = error.message;
        } finally {
            setTopazBusy(false);
        }
    }

    function desktopRequest(type, payload={}){
        if(window.parent === window) return Promise.reject(new Error('请在 Windows 桌面版中使用更新设置。'));
        const requestId = `update-${Date.now()}-${++updateRequestSequence}`;
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => { window.removeEventListener('message', receive); reject(new Error('桌面更新服务未响应。')); }, 8000);
            function receive(event){
                if(event.origin && event.origin !== location.origin) return;
                const data = event.data || {};
                if(data.type !== 'desktop-update-settings:response' || data.requestId !== requestId) return;
                clearTimeout(timeout);
                window.removeEventListener('message', receive);
                if(data.error) reject(new Error(data.error)); else resolve(data);
            }
            window.addEventListener('message', receive);
            window.parent.postMessage({type, requestId, ...payload}, location.origin);
        });
    }

    function applyUpdateSettings(settings){
        if(!settings) return;
        updatePolicy.value = settings.updatePolicy || 'automatic';
        updateNetworkMode.value = settings.networkMode || 'automaticProxy';
        updateManualProxy.value = settings.manualProxyUrl || 'http://127.0.0.1:7890';
        updateManualProxy.disabled = updateNetworkMode.value !== 'manualProxy';
        checkDesktopUpdate.disabled = updatePolicy.value === 'disabled';
    }

    async function loadUpdateSettings(){
        try { applyUpdateSettings((await desktopRequest('desktop-update-settings:get')).settings); }
        catch(error) { showUpdateStatus(error.message, true); [updatePolicy, updateNetworkMode, updateManualProxy, checkDesktopUpdate].forEach(item => { if(item) item.disabled = true; }); }
    }

    async function saveUpdateSettings(){
        try {
            showUpdateStatus('保存中…');
            const response = await desktopRequest('desktop-update-settings:save', {settings:{updatePolicy:updatePolicy.value, networkMode:updateNetworkMode.value, manualProxyUrl:updateManualProxy.value}});
            applyUpdateSettings(response.settings);
            showUpdateStatus('已保存');
        } catch(error) { showUpdateStatus(error.message, true); }
    }

    function selectBehavior(value){
        options.querySelectorAll('input[name="closeBehavior"]').forEach(input => {
            input.checked = input.value === value;
        });
    }

    function closeBehaviorFromServer(value){
        const behavior = String(value || '').trim();
        return ['ask_on_close', 'minimize_to_tray', 'exit'].includes(behavior) ? behavior : 'ask_on_close';
    }

    function updateCloseBehaviorNote(){
        if(!closeBehaviorNote) return;
        closeBehaviorNote.textContent = t(currentBehavior === 'ask_on_close' ? 'appSettings.askOnClosePending' : 'appSettings.appliesImmediately');
    }

    function setOutputBusy(busy){
        chooseOutput.disabled = busy;
        resetOutput.disabled = busy || !currentOutputDirectory;
    }

    function applyOutputSettings(data){
        currentOutputDirectory = String(data.generated_output_dir || '');
        outputInput.value = String(data.generated_output_effective_dir || currentOutputDirectory);
        outputHint.textContent = t(currentOutputDirectory ? 'appSettings.customDirectoryActive' : 'appSettings.defaultDirectoryActive');
        resetOutput.disabled = !currentOutputDirectory;
    }

    async function requestSettings(url, init={}){
        const response = await fetch(url, init);
        const data = await response.json().catch(() => ({}));
        if(!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
        return data;
    }

    function formatBytes(value){
        const bytes = Number(value || 0);
        if(bytes < 1024) return `${bytes} B`;
        const units = ['KB','MB','GB','TB'];
        let current = bytes / 1024;
        for(const unit of units){
            if(current < 1024 || unit === 'TB') return `${current.toFixed(current >= 10 ? 1 : 2)} ${unit}`;
            current /= 1024;
        }
        return `${bytes} B`;
    }

    function mediaCategoryDetail(summary){
        const categories = summary?.media?.categories || summary?.categories || {};
        return Object.entries(categories).map(([key,item]) => `${key} ${item.count || 0}`).join(' · ') || '暂无媒体索引';
    }

    function orphanSummary(summary){
        const orphaned = summary?.media?.orphaned || summary?.orphaned || {};
        return Object.values(orphaned).reduce((total,item) => total + Number(item.count || 0), 0);
    }

    function renderStorageSummary(data){
        const media = data?.media || data?.summary?.media || (data?.categories || data?.total_count !== undefined ? data : data?.summary) || {};
        storageMediaTotal.textContent = String(media.total_count ?? data?.tracked ?? 0);
        storageMediaDetail.textContent = `${formatBytes(media.total_bytes || 0)} · ${mediaCategoryDetail(media)}`;
        storageOrphanTotal.textContent = String(orphanSummary(media));
        storageOrphanDetail.textContent = lastOrphanPreview.length ? `本次预览 ${lastOrphanPreview.length} 个候选` : '先预览再清理';
    }

    function setStorageBusy(busy){
        [refreshStorageSummary, reconcileMediaStorage, previewOrphanMedia, cleanupOrphanMedia].forEach(button => {
            if(button) button.disabled = busy || (button === cleanupOrphanMedia && !lastOrphanPreview.length);
        });
    }

    function renderOrphanPreview(items){
        lastOrphanPreview = Array.isArray(items) ? items : [];
        cleanupOrphanMedia.disabled = !lastOrphanPreview.length;
        if(!storageOrphanList) return;
        storageOrphanList.hidden = !lastOrphanPreview.length;
        storageOrphanList.innerHTML = lastOrphanPreview.slice(0, 8).map(item => `
            <div class="app-settings-storage-row">
                <span>${String(item.url || '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}</span>
                <small>${formatBytes(item.size || 0)}</small>
            </div>
        `).join('');
    }

    async function loadStorageSummary(){
        setStorageBusy(true);
        try {
            const data = await requestSettings('/api/storage/summary', {cache:'no-store'});
            renderStorageSummary(data);
            showStorageStatus('已刷新');
        } catch(error) {
            showStorageStatus(`加载失败：${error.message}`, true);
        } finally {
            setStorageBusy(false);
        }
    }

    async function reconcileStorage(){
        setStorageBusy(true);
        try {
            const data = await requestSettings('/api/storage/media/reconcile', {method:'POST'});
            renderStorageSummary(data);
            showStorageStatus(`已扫描 ${data.tracked || 0} 个媒体文件`);
        } catch(error) {
            showStorageStatus(`扫描失败：${error.message}`, true);
        } finally {
            setStorageBusy(false);
        }
    }

    async function previewOrphans(){
        setStorageBusy(true);
        try {
            const data = await requestSettings('/api/storage/media/cleanup-orphans', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({dry_run:true, grace_seconds:7 * 24 * 60 * 60, limit:200}),
            });
            renderOrphanPreview(data.candidates || []);
            renderStorageSummary(data.summary || {});
            showStorageStatus(lastOrphanPreview.length ? `发现 ${lastOrphanPreview.length} 个候选` : '暂无可清理候选');
        } catch(error) {
            showStorageStatus(`预览失败：${error.message}`, true);
        } finally {
            setStorageBusy(false);
        }
    }

    async function cleanupOrphans(){
        if(!lastOrphanPreview.length) return;
        if(!confirm(`确认清理 ${lastOrphanPreview.length} 个孤立内部文件？`)) return;
        setStorageBusy(true);
        try {
            const data = await requestSettings('/api/storage/media/cleanup-orphans', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({dry_run:false, grace_seconds:7 * 24 * 60 * 60, limit:200}),
            });
            renderOrphanPreview([]);
            renderStorageSummary(data.summary || {});
            showStorageStatus(`已清理 ${data.deleted_files || 0} 个文件`);
        } catch(error) {
            showStorageStatus(`清理失败：${error.message}`, true);
        } finally {
            setStorageBusy(false);
        }
    }

    async function loadSettings(){
        options.disabled = true;
        setOutputBusy(true);
        applyShortcutSettings({shortcut_bindings:{}});
        try {
            const data = await requestSettings('/api/app-settings', {cache:'no-store'});
            currentBehavior = closeBehaviorFromServer(data.close_behavior);
            selectBehavior(currentBehavior);
            updateCloseBehaviorNote();
            applyOutputSettings(data);
            applyTopazSettings(data);
            applyShortcutSettings(data);
        } catch(error) {
            showStatus(`${t('appSettings.loadFailed')}：${error.message}`, true);
        } finally {
            options.disabled = false;
            setOutputBusy(false);
        }
    }

    async function saveSettings(values){
        return requestSettings('/api/app-settings', {
            method:'PUT',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify(values),
        });
    }

    async function saveBehavior(value){
        const previous = currentBehavior;
        options.disabled = true;
        try {
            const data = await saveSettings({close_behavior:value});
            currentBehavior = closeBehaviorFromServer(data.close_behavior);
            selectBehavior(currentBehavior);
            updateCloseBehaviorNote();
            showStatus(t('appSettings.saved'));
        } catch(error) {
            selectBehavior(previous);
            showStatus(`${t('appSettings.saveFailed')}：${error.message}`, true);
        } finally {
            options.disabled = false;
        }
    }

    async function chooseOutputDirectory(){
        setOutputBusy(true);
        try {
            const selection = await requestSettings('/api/app-settings/select-generated-output-directory', {method:'POST'});
            if(!selection.selected || !selection.path) return;
            const data = await saveSettings({generated_output_dir:selection.path});
            applyOutputSettings(data);
            showStatus(t('appSettings.saved'));
        } catch(error) {
            showStatus(`${t('appSettings.saveFailed')}：${error.message}`, true);
        } finally {
            setOutputBusy(false);
        }
    }

    async function resetOutputDirectory(){
        setOutputBusy(true);
        try {
            const data = await saveSettings({generated_output_dir:''});
            applyOutputSettings(data);
            showStatus(t('appSettings.saved'));
        } catch(error) {
            showStatus(`${t('appSettings.saveFailed')}：${error.message}`, true);
        } finally {
            setOutputBusy(false);
        }
    }

    async function chooseTopazDirectory(){
        setTopazBusy(true);
        try {
            const selection = await requestSettings('/api/app-settings/select-topaz-video-directory', {method:'POST'});
            if(!selection.selected || !selection.path) return;
            const data = await saveSettings({topaz_video_install_dir:selection.path});
            applyTopazSettings(data);
            await checkTopazCapabilities();
        } catch(error) {
            showTopazStatus(`保存失败：${error.message}`, true);
        } finally {
            setTopazBusy(false);
        }
    }

    async function resetTopazDirectory(){
        setTopazBusy(true);
        try {
            const data = await saveSettings({topaz_video_install_dir:''});
            applyTopazSettings(data);
            await checkTopazCapabilities();
        } catch(error) {
            showTopazStatus(`恢复自动检测失败：${error.message}`, true);
        } finally {
            setTopazBusy(false);
        }
    }

    options.addEventListener('change', event => {
        const input = event.target.closest('input[name="closeBehavior"]');
        if(input && input.value !== currentBehavior) saveBehavior(input.value);
    });
    updatePolicy?.addEventListener('change', saveUpdateSettings);
    updateNetworkMode?.addEventListener('change', () => { updateManualProxy.disabled = updateNetworkMode.value !== 'manualProxy'; saveUpdateSettings(); });
    updateManualProxy?.addEventListener('change', saveUpdateSettings);
    checkDesktopUpdate?.addEventListener('click', async () => {
        checkDesktopUpdate.disabled = true;
        try { await desktopRequest('desktop-update:check'); } catch(error) { showUpdateStatus(error.message, true); } finally { checkDesktopUpdate.disabled = false; }
    });
    refreshStorageSummary?.addEventListener('click', loadStorageSummary);
    reconcileMediaStorage?.addEventListener('click', reconcileStorage);
    previewOrphanMedia?.addEventListener('click', previewOrphans);
    cleanupOrphanMedia?.addEventListener('click', cleanupOrphans);
    chooseOutput.addEventListener('click', chooseOutputDirectory);
    resetOutput.addEventListener('click', resetOutputDirectory);
    chooseTopazInstall?.addEventListener('click', chooseTopazDirectory);
    resetTopazInstall?.addEventListener('click', resetTopazDirectory);
    checkTopazInstall?.addEventListener('click', checkTopazCapabilities);
    shortcutSearch?.addEventListener('input', renderShortcutSettings);
    shortcutCategory?.addEventListener('change', renderShortcutSettings);
    shortcutList?.addEventListener('click', event => {
        const record = event.target.closest('[data-shortcut-record]');
        if(record){
            const actionId = record.dataset.shortcutRecord || '';
            shortcutRecordingId = shortcutRecordingId === actionId ? '' : actionId;
            showShortcutConflict('');
            showShortcutStatus(shortcutRecordingId ? '等待按键…' : '已取消录制');
            renderShortcutSettings();
            return;
        }
        const clear = event.target.closest('[data-shortcut-clear]');
        if(clear){
            const actionId = clear.dataset.shortcutClear || '';
            saveShortcutSettings({...shortcutOverrides, [actionId]:''}, '已清空');
            return;
        }
        const reset = event.target.closest('[data-shortcut-reset]');
        if(reset){
            const next = {...shortcutOverrides};
            delete next[reset.dataset.shortcutReset || ''];
            saveShortcutSettings(next, '已恢复默认');
        }
    });
    resetAllShortcuts?.addEventListener('click', () => {
        if(!Object.keys(shortcutOverrides).length){ showShortcutStatus('当前已是默认设置'); return; }
        if(confirm('确认将所有快捷键恢复为默认设置？')) saveShortcutSettings({}, '已全部恢复默认');
    });
    window.addEventListener('keydown', event => {
        if(!shortcutRecordingId || !window.ShortcutActions || event.repeat) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const action = window.ShortcutActions.get(shortcutRecordingId);
        const binding = window.ShortcutActions.fromEvent(event, {allowModifierOnly:Boolean(action?.hold)});
        if(!binding){ showShortcutConflict('请同时或依次按下修饰键与一个普通按键。'); return; }
        setShortcutBinding(shortcutRecordingId, binding);
    }, true);
    window.addEventListener('message', event => {
        if(event.origin && event.origin !== location.origin) return;
        if(event.data?.type === 'studio-language') window.StudioI18n?.set?.(event.data.lang,{sync:false});
    });
    document.addEventListener('DOMContentLoaded', async () => { await loadSettings(); checkTopazCapabilities(); loadUpdateSettings(); loadStorageSummary(); }, {once:true});
})();
