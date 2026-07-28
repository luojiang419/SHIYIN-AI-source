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
    let currentBehavior = 'ask_on_close';
    let currentOutputDirectory = '';
    let statusTimer = null;
    let updateRequestSequence = 0;

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

    async function loadSettings(){
        options.disabled = true;
        setOutputBusy(true);
        try {
            const data = await requestSettings('/api/app-settings', {cache:'no-store'});
            currentBehavior = closeBehaviorFromServer(data.close_behavior);
            selectBehavior(currentBehavior);
            updateCloseBehaviorNote();
            applyOutputSettings(data);
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
    chooseOutput.addEventListener('click', chooseOutputDirectory);
    resetOutput.addEventListener('click', resetOutputDirectory);
    window.addEventListener('message', event => {
        if(event.origin && event.origin !== location.origin) return;
        if(event.data?.type === 'studio-language') window.StudioI18n?.set?.(event.data.lang,{sync:false});
    });
    document.addEventListener('DOMContentLoaded', () => { loadSettings(); loadUpdateSettings(); }, {once:true});
})();
