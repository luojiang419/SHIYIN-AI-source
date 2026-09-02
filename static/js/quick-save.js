(function(){
    'use strict';

    const CHANNEL_NAME = 'shiyin-quick-save-settings';
    const API_URL = '/api/app-settings/quick-save';
    let state = {mode:'manual', directory:'', loaded:false};
    let toastTimer = 0;

    function applySettings(value){
        state = {
            mode:value?.mode === 'silent' ? 'silent' : 'manual',
            directory:String(value?.directory || ''),
            loaded:true,
        };
        window.dispatchEvent(new CustomEvent('quick-save-settings-changed', {detail:{...state}}));
        return state;
    }

    async function loadSettings(){
        try {
            const response = await fetch(API_URL, {cache:'no-store'});
            if(!response.ok) return applySettings({mode:'manual', directory:''});
            return applySettings(await response.json());
        } catch(error) {
            return applySettings({mode:'manual', directory:''});
        }
    }

    const ready = loadSettings();

    function isSilent(){
        return state.mode === 'silent' && Boolean(state.directory);
    }

    function filenameFromUrl(url, fallback='download.bin'){
        try {
            const parsed = new URL(String(url || ''), location.href);
            if(parsed.pathname === '/api/download-output'){
                const requested = parsed.searchParams.get('name');
                if(requested) return requested;
                const nested = parsed.searchParams.get('url');
                if(nested) return filenameFromUrl(nested, fallback);
            }
            return decodeURIComponent(parsed.pathname.split('/').filter(Boolean).pop() || fallback);
        } catch(error) {
            return fallback;
        }
    }

    function safeName(name, url=''){
        return String(name || filenameFromUrl(url) || 'download.bin')
            .replace(/[\\/:*?"<>|\u0000-\u001f]+/g, '_')
            .trim() || 'download.bin';
    }

    function showToast(message, error=false){
        let element = document.getElementById('shiyinQuickSaveToast');
        if(!element){
            element = document.createElement('div');
            element.id = 'shiyinQuickSaveToast';
            element.setAttribute('role', 'status');
            Object.assign(element.style, {
                position:'fixed', right:'18px', bottom:'18px', zIndex:'2147483647',
                maxWidth:'min(360px,calc(100vw - 36px))', padding:'11px 14px',
                border:'1px solid rgba(127,127,127,.24)', borderRadius:'8px',
                background:'rgba(28,28,27,.94)', color:'#fff', boxShadow:'0 10px 28px rgba(0,0,0,.2)',
                font:'600 12px/1.5 Inter,"Microsoft YaHei",system-ui,sans-serif',
                wordBreak:'break-word', opacity:'0', transform:'translateY(6px)',
                transition:'opacity .16s ease,transform .16s ease', pointerEvents:'none',
            });
            document.body.appendChild(element);
        }
        clearTimeout(toastTimer);
        element.textContent = message;
        element.style.background = error ? 'rgba(145,38,31,.96)' : 'rgba(28,28,27,.94)';
        element.style.opacity = '1';
        element.style.transform = 'translateY(0)';
        toastTimer = setTimeout(() => {
            element.style.opacity = '0';
            element.style.transform = 'translateY(6px)';
        }, error ? 4600 : 2800);
    }

    async function responseError(response){
        const data = await response.json().catch(() => ({}));
        return data.detail || `HTTP ${response.status}`;
    }

    async function saveItem(item, options={}){
        await ready;
        if(!isSilent()) return {handled:false};
        const url = String(item?.url || '');
        const name = safeName(item?.name, url);
        const form = new FormData();
        form.append('name', name);
        if(item?.blob instanceof Blob){
            form.append('file', item.blob, name);
        } else if(url.startsWith('blob:') || url.startsWith('data:')){
            const response = await fetch(url);
            if(!response.ok) throw new Error(`读取临时下载文件失败（HTTP ${response.status}）`);
            form.append('file', await response.blob(), name);
        } else {
            form.append('url', url);
        }
        if(!options.quiet) showToast(`正在静默保存 ${name}`);
        const response = await fetch(API_URL, {method:'POST', body:form});
        if(!response.ok) throw new Error(await responseError(response));
        const result = await response.json();
        window.dispatchEvent(new CustomEvent('quick-save-complete', {detail:result}));
        if(!options.quiet) showToast(`已保存到快捷目录：${result.name || name}`);
        return {handled:true, ...result};
    }

    function downloadResourceUrl(item){
        const url = String(item?.url || '');
        const name = safeName(item?.name, url);
        if(!url || url.startsWith('blob:') || url.startsWith('data:') || url.startsWith('/api/download-output')) return url;
        return `/api/download-output?url=${encodeURIComponent(url)}&name=${encodeURIComponent(name)}`;
    }

    function uniqueListName(name, used){
        const initial = safeName(name);
        const dot = initial.lastIndexOf('.');
        const stem = dot > 0 ? initial.slice(0, dot) : initial;
        const extension = dot > 0 ? initial.slice(dot) : '';
        let candidate = initial;
        let sequence = 2;
        while(used.has(candidate.toLowerCase())) candidate = `${stem} (${sequence++})${extension}`;
        used.add(candidate.toLowerCase());
        return candidate;
    }

    async function uniqueDirectoryName(directory, name, used){
        const initial = uniqueListName(name, used);
        const dot = initial.lastIndexOf('.');
        const stem = dot > 0 ? initial.slice(0, dot) : initial;
        const extension = dot > 0 ? initial.slice(dot) : '';
        let candidate = initial;
        let sequence = 2;
        while(true){
            try {
                await directory.getFileHandle(candidate);
                candidate = `${stem} (${sequence++})${extension}`;
            } catch(error) {
                if(error?.name === 'NotFoundError'){
                    used.add(candidate.toLowerCase());
                    return candidate;
                }
                throw error;
            }
        }
    }

    async function saveAllWithDirectoryPicker(list){
        let directory;
        try {
            directory = await window.showDirectoryPicker({mode:'readwrite'});
        } catch(error) {
            if(error?.name === 'AbortError') return {handled:true, cancelled:true, count:0, mode:'manual'};
            throw error;
        }
        const used = new Set();
        let count = 0;
        for(const item of list){
            const name = await uniqueDirectoryName(directory, item.name, used);
            let content = item?.blob instanceof Blob ? item.blob : null;
            if(!content){
                const response = await fetch(downloadResourceUrl(item));
                if(!response.ok) throw new Error(`下载 ${name} 失败（HTTP ${response.status}）`);
                content = await response.blob();
            }
            const handle = await directory.getFileHandle(name, {create:true});
            const writable = await handle.createWritable();
            try {
                await writable.write(content);
                await writable.close();
            } catch(error) {
                try { await writable.abort(); } catch(abortError) {}
                throw error;
            }
            count += 1;
        }
        return {handled:true, cancelled:false, count, mode:'manual'};
    }

    function requestDesktopBatchSave(list){
        if(window.parent === window || !window.parent?.postMessage) return null;
        const requestId = `quick-save-batch-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                window.removeEventListener('message', receive);
                reject(new Error('桌面文件保存服务未响应，请重启软件后重试'));
            }, 120000);
            function receive(event){
                if(event.origin && event.origin !== location.origin) return;
                const data = event.data || {};
                if(data.type !== 'desktop-canvas-download:response' || data.requestId !== requestId) return;
                clearTimeout(timeout);
                window.removeEventListener('message', receive);
                if(data.error) reject(new Error(data.error));
                else resolve({handled:true, mode:'manual', ...data});
            }
            window.addEventListener('message', receive);
            window.parent.postMessage({
                type:'desktop-canvas-download:save',
                requestId,
                items:list.map(item => ({url:downloadResourceUrl(item), name:item.name})),
            }, location.origin);
        });
    }

    function fallbackIndividualDownloads(list){
        list.forEach((item, index) => {
            setTimeout(() => {
                const link = document.createElement('a');
                link.href = downloadResourceUrl(item);
                link.download = item.name;
                link.dataset.quickSaveBypass = '1';
                document.body.appendChild(link);
                link.click();
                link.remove();
            }, index * 120);
        });
        return {handled:true, cancelled:false, count:list.length, mode:'manual'};
    }

    async function saveAll(items){
        if(!state.loaded) await ready;
        const list = (Array.isArray(items) ? items : [])
            .filter(item => item?.url || item?.blob instanceof Blob)
            .map(item => ({...item, name:safeName(item?.name || filenameFromUrl(item?.url), item?.url)}));
        if(!list.length) return {handled:true, count:0};
        if(isSilent()){
            showToast(`正在静默保存 ${list.length} 个文件`);
            let count = 0;
            for(const item of list){
                await saveItem(item, {quiet:true});
                count += 1;
            }
            showToast(`已静默保存 ${count} 个文件`);
            return {handled:true, cancelled:false, count, directory:state.directory, mode:'silent'};
        }
        showToast(`请选择文件夹保存 ${list.length} 个文件`);
        let result;
        if(typeof window.showDirectoryPicker === 'function') result = await saveAllWithDirectoryPicker(list);
        else result = await requestDesktopBatchSave(list);
        if(!result) result = fallbackIndividualDownloads(list);
        if(!result.cancelled) showToast(`已保存 ${result.count || 0} 个文件`);
        return result;
    }

    function isDownloadLink(anchor){
        if(!anchor || anchor.dataset.quickSaveBypass === '1') return false;
        if(anchor.hasAttribute('download')) return true;
        const href = String(anchor.getAttribute('href') || '');
        return /^\/api\/(?:download-output|works\/download-all|blender\/addon)(?:\?|$)/i.test(href);
    }

    function replayManualDownload(anchor){
        anchor.dataset.quickSaveBypass = '1';
        try { anchor.click(); }
        finally { delete anchor.dataset.quickSaveBypass; }
    }

    document.addEventListener('click', event => {
        const anchor = event.target?.closest?.('a');
        if(!isDownloadLink(anchor)) return;
        if(state.loaded && !isSilent()) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        const url = String(anchor.href || anchor.getAttribute('href') || '');
        const name = safeName(anchor.getAttribute('download'), url);
        const earlyBlob = url.startsWith('blob:') || url.startsWith('data:')
            ? fetch(url).then(response => response.blob())
            : null;
        void (async () => {
            try {
                await ready;
                if(!isSilent()){
                    replayManualDownload(anchor);
                    return;
                }
                await saveItem({url, name, blob:earlyBlob ? await earlyBlob : null});
            } catch(error) {
                showToast(`静默保存失败：${error.message || error}`, true);
                window.dispatchEvent(new CustomEvent('quick-save-error', {detail:{error}}));
            }
        })();
    }, true);

    try {
        const channel = new BroadcastChannel(CHANNEL_NAME);
        channel.addEventListener('message', event => applySettings(event.data));
    } catch(error) {}
    window.addEventListener('message', event => {
        if(event.origin && event.origin !== location.origin) return;
        if(event.data?.type === 'quick-save-settings:changed') applySettings(event.data);
    });

    window.ShiyinQuickSave = {
        ready,
        isSilent,
        getState:async () => ({...(await ready), ...state}),
        refresh:loadSettings,
        save:saveItem,
        saveAll,
    };
})();
