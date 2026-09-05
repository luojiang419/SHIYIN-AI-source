(function(root, factory){
    if(typeof module === 'object' && module.exports){
        module.exports = factory;
        return;
    }
    root.CanvasStartup = factory(root);
    const id = new URLSearchParams(root.location.search).get('id');
    if(id) root.CanvasStartup.prefetch(id);
})(typeof window !== 'undefined' ? window : null, function(host){
    'use strict';

    // 单个页面只拥有一个启动会话：必需数据 -> 挂载 -> 首帧 -> 后续任务。
    // 请求不跨页面持久化；更换会话会取消请求和尚未执行的后续任务。
    const REQUEST_TIMEOUT_MS = 15000;
    let active = null;
    let prefetched = null;
    let visible = !host.document?.hidden;
    let sequence = 0;
    const configRequests = new Set();

    async function readJson(url, signal, resource){
        const response = await host.fetch(url, {signal, cache:'no-store'});
        if(!response.ok){
            const error = new Error(`${resource} request failed (${response.status})`);
            error.resource = resource;
            error.status = response.status;
            throw error;
        }
        const value = await response.json();
        if(resource === 'config' && (!value || !Array.isArray(value.api_providers))){
            throw new Error('Invalid canvas runtime config');
        }
        return value;
    }
    function requestController(){
        const controller = new AbortController();
        const timer = host.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
        return {controller, finish:() => host.clearTimeout(timer)};
    }
    function createSession(id){
        active?.cancel();
        const {controller, finish} = requestController();
        let frame = null;
        let idle = null;
        let work = null;
        let started = false;
        const timings = {requestStartedAt:host.performance.now(), dataReadyAt:null, configReadyAt:null};
        const session = {
            id, sequence:++sequence, phase:'loading', timings,
            isCurrent:() => active === session && session.phase !== 'cancelled',
            cancel(){
                session.phase = 'cancelled';
                controller.abort();
                finish();
                clearScheduled();
                work = null;
            },
            afterPaint(task){
                if(!session.isCurrent() || started || work) return;
                work = task;
                session.phase = 'mounted';
                schedule();
            },
            resume:schedule
        };
        function clearScheduled(){
            if(frame !== null) host.cancelAnimationFrame(frame);
            if(idle !== null){
                if(host.requestIdleCallback) host.cancelIdleCallback(idle);
                else host.clearTimeout(idle);
            }
            frame = idle = null;
        }
        function schedule(){
            if(!visible){ clearScheduled(); return; }
            if(!session.isCurrent() || !work || started || frame !== null || idle !== null) return;
            // 两次 rAF 跨过一次绘制机会；idle 只决定何时运行后续任务，不决定数据依赖。
            frame = host.requestAnimationFrame(() => {
                frame = host.requestAnimationFrame(() => {
                    frame = null;
                    const run = () => {
                        idle = null;
                        if(!visible || !session.isCurrent() || started) return;
                        started = true;
                        const task = work;
                        work = null;
                        session.phase = 'background';
                        Promise.resolve().then(() => {
                            if(session.isCurrent()) return task(session);
                        }).then(() => {
                            if(session.isCurrent()) session.phase = 'complete';
                        }).catch(error => {
                            if(session.isCurrent()) session.phase = 'complete';
                            host.console.warn('Canvas background startup failed', error);
                        });
                    };
                    idle = host.requestIdleCallback
                        ? host.requestIdleCallback(run, {timeout:1500}) : host.setTimeout(run, 0);
                });
            });
        }
        active = session;
        session.ready = Promise.all([
            readJson(`/api/canvases/${encodeURIComponent(id)}`, controller.signal, 'canvas').then(data => {
                if(!data?.canvas || data.canvas.id !== id || !Array.isArray(data.canvas.nodes)){
                    throw new Error('Invalid canvas project');
                }
                timings.dataReadyAt = host.performance.now();
                return data;
            }),
            readJson('/api/runtime/config', controller.signal, 'config').then(config => {
                timings.configReadyAt = host.performance.now();
                return config;
            })
        ]).then(([data, config]) => {
            if(session.isCurrent()) session.phase = 'ready';
            return {data, config};
        }).catch(error => {
            controller.abort();
            if(session.isCurrent()) session.phase = 'error';
            // 脚本仍在下载时也不会产生未处理 rejection；错误由界面统一呈现。
            return {error};
        }).finally(finish);
        return session;
    }
    return {
        prefetch(id){
            if(id) prefetched = createSession(id);
        },
        open(id){
            if(prefetched?.id === id && prefetched.isCurrent()){
                const session = prefetched;
                prefetched = null;
                return session;
            }
            prefetched = null;
            return createSession(id);
        },
        async readConfig(){
            const request = requestController();
            configRequests.add(request);
            try { return await readJson('/api/runtime/config', request.controller.signal, 'config'); }
            finally { request.finish(); configRequests.delete(request); }
        },
        setVisible(value){
            visible = Boolean(value);
            active?.resume();
        },
        cancel(){
            active?.cancel();
            prefetched = null;
            for(const request of configRequests){ request.controller.abort(); request.finish(); }
            configRequests.clear();
        }
    };
});
