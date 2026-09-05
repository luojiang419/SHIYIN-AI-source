(() => {
    'use strict';

    // 在 CSS 和编辑器脚本之前发起详情请求，冷启动时与静态资源并行。
    // 只在本页面内消费一次，不把项目内容放进跨账号/跨页面缓存。
    const id = new URLSearchParams(window.location.search).get('id');
    const timings = {requestStartedAt:performance.now(), dataReadyAt:null};
    let initialTask = id ? (async () => {
        try {
            const response = await fetch(`/api/canvases/${encodeURIComponent(id)}`);
            if(!response.ok) throw new Error(`Canvas request failed (${response.status})`);
            const data = await response.json();
            timings.dataReadyAt = performance.now();
            return {data};
        } catch(error) {
            // 编辑器脚本可能还没下载完，先收拢错误，交给 openCanvas 的失败路径处理。
            return {error};
        }
    })() : null;

    window.CanvasStartup = {
        timings,
        takeCanvas(requestedId){
            if(requestedId !== id || !initialTask) return null;
            const task = initialTask;
            initialTask = null;
            return task;
        }
    };
})();
