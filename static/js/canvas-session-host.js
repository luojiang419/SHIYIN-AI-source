// 保留完整编辑器文档；不能移除/重新挂载 iframe，否则浏览器会重新导航。
(() => {
    'use strict';
    const MAX_RESIDENT_EDITORS = 3;
    const editors = [];
    let sequence = 0;
    let current = null;
    let manager = null;
    let entryWait = null;
    let warmEditor = null;
    function frameRuntimeReady(frame){
        try {
            const url = new URL(frame.src, location.href);
            if(url.pathname === '/static/canvas-list.html') return typeof frame.contentWindow?.loadAll === 'function';
            if(url.pathname === '/static/canvas.html') return typeof frame.contentWindow?.CanvasSessionLifecycle?.state === 'function';
        } catch(e) {}
        return false;
    }
    function waitForEntry(frame){
        if(entryWait){
            clearTimeout(entryWait.timer);
            entryWait.frame.removeEventListener('load', entryWait.onLoad);
            entryWait.overlay?.remove();
        }
        entryWait = null;
        if(!frame || (frame.dataset.frameReady === '1' && frameRuntimeReady(frame))) return;
        // 立即切换编辑器文档；正常导航不显示加载层，仅在文档确实无法挂载时提示错误。
        const timer = setTimeout(() => {
            if(entryWait?.frame !== frame) return;
            const overlay = window.CanvasEntryProgress.create(frame.parentElement);
            overlay.error('画布页面未能打开，请检查连接或重试。', () => {
                overlay.remove();
                frame.src = frame.src;
                waitForEntry(frame);
            });
            entryWait.overlay = overlay;
        }, 20000);
        const onLoad = () => finishEntryWait(frame);
        entryWait = {frame, timer, overlay:null, onLoad};
        frame.addEventListener('load', onLoad);
    }
    function finishEntryWait(frame){
        if(entryWait?.frame !== frame || !frameRuntimeReady(frame)) return;
        entryWait.overlay?.remove();
        clearTimeout(entryWait.timer);
        frame.removeEventListener('load', entryWait.onLoad);
        entryWait = null;
    }
    window.addEventListener('message', event => {
        if(event.origin === location.origin && event.data?.type === 'canvas-entry-mounted' && entryWait?.frame.contentWindow === event.source) finishEntryWait(entryWait.frame);
    });
    const studio = () => Boolean(document.getElementById('frame-canvas'));

    function editorState(entry){
        try { return entry.frame.contentWindow?.CanvasSessionLifecycle?.state(); }
        catch(e){ return null; }
    }
    function setActive(frame, active){
        frame.classList.toggle('active', active);
        frame.dataset.routeActive = active ? '1' : '0';
        frame.setAttribute('aria-hidden', String(!active));
        frame.inert = !active;
        try {
            const lifecycle = frame.contentWindow?.CanvasSessionLifecycle;
            if(lifecycle) lifecycle.setActive(active);
            else frame.contentWindow?.postMessage({type:'studio-route-active', active}, location.origin);
        } catch(e) {}
    }
    function prune(){
        for(const entry of [...editors].sort((a,b) => a.used - b.used)){
            if(editors.length <= MAX_RESIDENT_EDITORS) break;
            if(entry === current || editorState(entry)?.evictable !== true) continue;
            entry.frame.remove();
            editors.splice(editors.indexOf(entry), 1);
        }
    }
    function activate(frame){
        if(studio()){
            const previous = document.getElementById('frame-canvas');
            const active = previous.classList.contains('active');
            if(previous !== frame){
                setActive(previous, false);
                previous.id = previous.dataset.canvasSessionSlot;
                frame.id = 'frame-canvas';
            }
            setActive(frame, active);
        } else {
            for(const entry of editors) setActive(entry.frame, entry.frame === frame);
        }
        if(frame.classList.contains('active')){
            try { frame.contentWindow.focus(); } catch(e) {}
        }
    }
    function editorUrl(rawUrl){
        const url = new URL(rawUrl || '/static/canvas.html', location.href);
        return url.origin === location.origin && url.pathname === '/static/canvas.html' ? url : null;
    }
    function appendEditorFrame(frame){
        if(!manager && !document.getElementById('canvas-session-style')){
            const style = document.createElement('style');
            style.id = 'canvas-session-style';
            style.textContent = '[data-canvas-session-resident]:not(.active){visibility:hidden;pointer-events:none}';
            document.head.appendChild(style);
        }
        (manager?.parentElement || document.body).appendChild(frame);
    }
    function createEditorFrame(url, entry){
        const frame = document.createElement('iframe');
        frame.dataset.canvasSessionSlot = `frame-canvas-session-${++sequence}`;
        frame.dataset.canvasSessionResident = '1';
        frame.id = frame.dataset.canvasSessionSlot;
        frame.title = '无限画布';
        if(!manager) frame.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;border:0;z-index:10000;background:var(--bg,#f5f5f5)';
        frame.addEventListener('load', () => {
            const ready = frameRuntimeReady(frame);
            frame.dataset.frameReady = ready ? '1' : '0';
            setActive(frame, frame.classList.contains('active'));
            window.syncThemeToFrame?.(frame);
            window.syncLanguageToFrame?.(frame);
            if(entry.pendingUrl){
                if(ready) void openInWarmEditor(entry, entry.pendingUrl);
                else {
                    const pending = entry.pendingUrl;
                    entry.pendingUrl = null;
                    frame.src = pending.href;
                }
            }
        });
        frame.src = url.href;
        appendEditorFrame(frame);
        return frame;
    }
    async function openInWarmEditor(entry, url){
        if(!entry?.frame?.isConnected || !url || entry.opening) return;
        const lifecycle = entry.frame.contentWindow?.CanvasSessionLifecycle;
        if(typeof lifecycle?.openProject !== 'function'){
            entry.pendingUrl = null;
            entry.frame.src = url.href;
            return;
        }
        entry.opening = true;
        try {
            const opened = await lifecycle.openProject(url.searchParams.get('id'), url.href);
            if(!opened) throw new Error('warm canvas runtime rejected project');
            entry.pendingUrl = null;
            entry.frame.dataset.frameReady = '1';
            finishEntryWait(entry.frame);
        } catch(error) {
            console.warn('warm canvas runtime failed, falling back to navigation', error);
            entry.pendingUrl = null;
            entry.frame.dataset.frameReady = '0';
            entry.frame.src = url.href;
        } finally {
            entry.opening = false;
        }
    }
    function prewarm(){
        if(warmEditor?.frame?.isConnected) return warmEditor.frame;
        if(editors.length >= MAX_RESIDENT_EDITORS) return null;
        if(!manager && studio()){
            manager = document.getElementById('frame-canvas');
            manager.dataset.canvasSessionSlot = 'frame-canvas-manager';
            manager.dataset.canvasSessionResident = '1';
        }
        const url = editorUrl('/static/canvas.html?warm=1');
        if(!url) return null;
        const entry = {frame:null, id:'', used:0, pendingUrl:null, opening:false};
        entry.frame = createEditorFrame(url, entry);
        warmEditor = entry;
        return entry.frame;
    }
    function schedulePrewarm(){
        const run = () => prewarm();
        if(window.requestIdleCallback) window.requestIdleCallback(run, {timeout:800});
        else window.setTimeout(run, 0);
    }
    function open(rawUrl){
        const url = editorUrl(rawUrl);
        if(!url) return false;
        const id = url.searchParams.get('id');
        if(!id) return false;
        if(!manager && studio()){
            manager = document.getElementById('frame-canvas');
            manager.dataset.canvasSessionSlot = 'frame-canvas-manager';
            manager.dataset.canvasSessionResident = '1';
        }
        let entry = editors.find(item => (editorState(item)?.id || item.id) === id);
        if(!entry){
            entry = warmEditor?.frame?.isConnected ? warmEditor : null;
            if(entry){
                warmEditor = null;
                entry.id = id;
                entry.pendingUrl = url;
                entry.frame.dataset.frameReady = '0';
            } else {
                entry = {frame:null, id, used:0, pendingUrl:null, opening:false};
                entry.frame = createEditorFrame(url, entry);
            }
            editors.push(entry);
        }
        current = entry;
        entry.used = ++sequence;
        activate(entry.frame);
        waitForEntry(entry.frame);
        if(entry.pendingUrl && entry.frame.dataset.frameReady === '0') void openInWarmEditor(entry, entry.pendingUrl);
        window.StudioPageState?.session('shell').checkpoint();
        prune();
        return true;
    }
    function back(source, project){
        if(!current || current.frame.contentWindow !== source) return false;
        waitForEntry(null);
        current.used = ++sequence;
        if(manager) activate(manager);
        else setActive(current.frame, false);
        current = null;
        window.StudioPageState?.session('shell').checkpoint();
        const target = manager?.contentWindow || window;
        target.postMessage({type:'canvas-session-manager', project}, location.origin);
        prune();
        if(manager || !studio()) schedulePrewarm();
        return true;
    }
    function clear(){
        waitForEntry(null);
        if(current && manager) activate(manager);
        current = null;
        warmEditor?.frame?.remove();
        warmEditor = null;
        for(const entry of editors) entry.frame.remove();
        editors.length = 0;
    }
    // 仅在删除已成功或服务器明确报告不存在时调用，防止恢复后复用已删除实例。
    function invalidate(id){
        void window.StudioPageState?.session(`canvas:${id}`).remove();
        for(const entry of [...editors]){
            if((editorState(entry)?.id || entry.id) !== id) continue;
            entry.frame.contentWindow?.CanvasSessionLifecycle?.forgetCheckpoint?.();
            if(entry === current) back(entry.frame.contentWindow);
            entry.frame.remove();
            const index = editors.indexOf(entry);
            if(index >= 0) editors.splice(index, 1);
        }
    }
    window.addEventListener('message', event => {
        if(event.origin !== location.origin || event.data?.type !== 'canvas-manager-ready') return;
        const sourceFrame = manager || document.getElementById('frame-canvas');
        if((sourceFrame?.contentWindow === event.source && sourceFrame.classList.contains('active')) || window === event.source) prewarm();
    });
    window.CanvasSessionHost = {open, back, prune, clear, invalidate, waitForEntry, prewarm};
    // 未保存/运行中会话暂时越过上限，完成后自动收敛。
    window.setInterval(prune, 30000);
})();
