(() => {
    'use strict';

    const query = new URLSearchParams(location.search);
    const enabled = query.get('canvasPerf') === '1' || (() => {
        try { return localStorage.getItem('canvas_perf_overlay') === '1'; }
        catch (_) { return false; }
    })();
    const MAX_SAMPLES = 600;
    const samples = new Map();
    const longTasks = [];
    const eventTimings = [];
    const interactions = new Map();
    const fixtureFactories = new Map();
    let overlay = null;
    let overlayTimer = 0;
    let frameRaf = 0;
    let lastFrameAt = 0;

    function now(){ return performance.now(); }
    function boundedPush(list, value){
        list.push(value);
        if(list.length > MAX_SAMPLES) list.splice(0, list.length - MAX_SAMPLES);
    }
    function record(name, duration, meta={}){
        const value = Number(duration);
        if(!Number.isFinite(value) || value < 0) return;
        let list = samples.get(name);
        if(!list){ list = []; samples.set(name, list); }
        boundedPush(list, {duration:value, at:Date.now(), meta});
    }
    function start(name, meta={}){
        const startedAt = now();
        let ended = false;
        return extra => {
            if(ended) return 0;
            ended = true;
            const duration = now() - startedAt;
            record(name, duration, {...meta, ...(extra || {})});
            return duration;
        };
    }
    function measure(name, fn, meta={}){
        const end = start(name, meta);
        try { return fn(); }
        finally { end(); }
    }
    function beginInteraction(name, meta={}){
        interactions.set(name, {at:now(), meta});
    }
    function endInteraction(name, metric=name, meta={}){
        const item = interactions.get(name);
        if(!item) return 0;
        interactions.delete(name);
        const duration = now() - item.at;
        record(metric, duration, {...item.meta, ...meta});
        return duration;
    }
    function markPaintFrom(name, metric, meta={}){
        requestAnimationFrame(() => requestAnimationFrame(() => endInteraction(name, metric, meta)));
    }
    function percentile(values, ratio){
        if(!values.length) return 0;
        const sorted = values.slice().sort((a,b) => a - b);
        return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * ratio) - 1))];
    }
    function summaryFor(list){
        const values = (list || []).map(item => item.duration).filter(Number.isFinite);
        return {
            count:values.length,
            p50:percentile(values, .50),
            p95:percentile(values, .95),
            p99:percentile(values, .99),
            max:values.length ? Math.max(...values) : 0
        };
    }
    function snapshot(){
        const metrics = {};
        samples.forEach((list, name) => { metrics[name] = summaryFor(list); });
        return {
            enabled,
            metrics,
            longTasks:longTasks.slice(),
            eventTimings:eventTimings.slice(),
            activeInteractions:[...interactions.keys()],
            generatedAt:new Date().toISOString()
        };
    }
    function clear(){
        samples.clear();
        longTasks.length = 0;
        eventTimings.length = 0;
        interactions.clear();
    }
    function formatMs(value){ return `${Number(value || 0).toFixed(1)}ms`; }
    function ensureOverlay(){
        if(!enabled || overlay) return;
        overlay = document.createElement('aside');
        overlay.id = 'canvasPerfOverlay';
        overlay.setAttribute('aria-label', 'Canvas performance monitor');
        overlay.style.cssText = 'position:fixed;right:12px;bottom:12px;z-index:2147483640;width:280px;max-height:42vh;overflow:auto;padding:10px 12px;border:1px solid rgba(148,163,184,.45);border-radius:10px;background:rgba(15,23,42,.88);color:#e2e8f0;font:11px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace;box-shadow:0 12px 30px rgba(15,23,42,.28);backdrop-filter:blur(8px);pointer-events:none';
        document.body.appendChild(overlay);
        renderOverlay();
    }
    function renderOverlay(){
        if(!overlay) return;
        const data = snapshot();
        const rows = Object.entries(data.metrics)
            .filter(([, metric]) => metric.count)
            .sort((a,b) => b[1].p95 - a[1].p95)
            .slice(0, 10)
            .map(([name, metric]) => `<div style="display:grid;grid-template-columns:1fr auto;gap:8px"><span>${name}</span><b style="color:${metric.p95 > 33 ? '#f87171' : metric.p95 > 16.7 ? '#fbbf24' : '#86efac'}">${formatMs(metric.p95)}</b></div>`)
            .join('');
        overlay.innerHTML = `<div style="font-weight:700;margin-bottom:6px">Canvas Perf · p95</div>${rows || '<div>等待交互样本…</div>'}<div style="margin-top:6px;opacity:.7">Long tasks: ${data.longTasks.length}</div>`;
    }
    function frameLoop(timestamp){
        if(lastFrameAt){
            const duration = timestamp - lastFrameAt;
            if(duration < 1000) record('frame.interval', duration);
        }
        lastFrameAt = timestamp;
        frameRaf = requestAnimationFrame(frameLoop);
    }
    function observePerformance(){
        if(!enabled) return;
        if('PerformanceObserver' in window){
            try {
                const observer = new PerformanceObserver(list => {
                    list.getEntries().forEach(entry => boundedPush(longTasks, {duration:entry.duration, startTime:entry.startTime}));
                });
                observer.observe({entryTypes:['longtask']});
            } catch (_) {}
            try {
                const observer = new PerformanceObserver(list => {
                    list.getEntries().forEach(entry => {
                        if(entry.duration < 16) return;
                        boundedPush(eventTimings, {name:entry.name, duration:entry.duration, startTime:entry.startTime});
                    });
                });
                observer.observe({type:'event', buffered:true, durationThreshold:16});
            } catch (_) {}
        }
        frameRaf = requestAnimationFrame(frameLoop);
        overlayTimer = window.setInterval(renderOverlay, 1000);
        if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ensureOverlay, {once:true});
        else ensureOverlay();
    }
    function registerFixtureFactory(kind, factory){
        if(typeof factory === 'function') fixtureFactories.set(String(kind), factory);
    }
    function installFixture(kind, options={}){
        if(!enabled) throw new Error('请先使用 ?canvasPerf=1 打开画布，再安装性能 fixture');
        const factory = fixtureFactories.get(String(kind));
        if(!factory) throw new Error(`未注册 ${kind} 画布 fixture`);
        return factory(options);
    }
    function destroy(){
        if(frameRaf) cancelAnimationFrame(frameRaf);
        if(overlayTimer) clearInterval(overlayTimer);
        overlay?.remove();
        overlay = null;
    }

    window.CanvasPerformance = Object.freeze({
        enabled,
        record,
        start,
        measure,
        beginInteraction,
        endInteraction,
        markPaintFrom,
        snapshot,
        clear,
        registerFixtureFactory,
        installFixture,
        destroy
    });
    observePerformance();
})();
