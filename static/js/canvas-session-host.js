// 保留完整编辑器文档；不能移除/重新挂载 iframe，否则浏览器会重新导航。
(() => {
    'use strict';
    const MAX_RESIDENT_EDITORS = 3;
    const editors = [];
    let sequence = 0;
    let current = null;
    let manager = null;
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
    function open(rawUrl){
        const url = new URL(rawUrl, location.href);
        if(url.origin !== location.origin || url.pathname !== '/static/canvas.html') return false;
        const id = url.searchParams.get('id');
        if(!id) return false;
        if(!manager && studio()){
            manager = document.getElementById('frame-canvas');
            manager.dataset.canvasSessionSlot = 'frame-canvas-manager';
            manager.dataset.canvasSessionResident = '1';
        }
        let entry = editors.find(item => (editorState(item)?.id || item.id) === id);
        if(!entry){
            const frame = document.createElement('iframe');
            frame.dataset.canvasSessionSlot = `frame-canvas-session-${++sequence}`;
            frame.dataset.canvasSessionResident = '1';
            frame.id = frame.dataset.canvasSessionSlot;
            frame.title = '无限画布';
            // 独立列表也能作为宿主。固定尺寸和 visibility 保留媒体与布局状态。
            if(!manager){
                frame.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;border:0;z-index:10000;background:var(--bg,#f5f5f5)';
                if(!document.getElementById('canvas-session-style')){
                    const style = document.createElement('style');
                    style.id = 'canvas-session-style';
                    style.textContent = '[data-canvas-session-resident]:not(.active){visibility:hidden;pointer-events:none}';
                    document.head.appendChild(style);
                }
            }
            entry = {frame, id, used:0};
            editors.push(entry);
            frame.addEventListener('load', () => {
                frame.dataset.frameReady = '1';
                setActive(frame, frame.classList.contains('active'));
                window.syncThemeToFrame?.(frame);
                window.syncLanguageToFrame?.(frame);
            });
            frame.src = url.href;
            (manager?.parentElement || document.body).appendChild(frame);
        }
        current = entry;
        entry.used = ++sequence;
        activate(entry.frame);
        window.StudioPageState?.session('shell').checkpoint();
        prune();
        return true;
    }
    function back(source, project){
        if(!current || current.frame.contentWindow !== source) return false;
        current.used = ++sequence;
        if(manager) activate(manager);
        else setActive(current.frame, false);
        current = null;
        window.StudioPageState?.session('shell').checkpoint();
        const target = manager?.contentWindow || window;
        target.postMessage({type:'canvas-session-manager', project}, location.origin);
        prune();
        return true;
    }
    function clear(){
        if(current && manager) activate(manager);
        current = null;
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
    window.CanvasSessionHost = {open, back, prune, clear, invalidate};
    // 未保存/运行中会话暂时越过上限，完成后自动收敛。
    window.setInterval(prune, 30000);
})();
