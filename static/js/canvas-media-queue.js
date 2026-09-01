(function(factory){
    const api = factory();
    if(typeof module !== 'undefined' && module.exports) module.exports = api;
    if(typeof window !== 'undefined') window.CanvasMediaQueue = api;
})(function(){
    function createMediaQueue(options={}){
        const name = String(options.name || 'canvas-media');
        const maxActive = Math.max(1, Number(options.maxActive || 6));
        const maxImageActive = Math.max(1, Number(options.maxImageActive || maxActive));
        const maxVideoActive = Math.max(1, Number(options.maxVideoActive || Math.min(2, maxActive)));
        const imageTimeoutMs = Math.max(1, Number(options.imageTimeoutMs || 20000));
        const videoTimeoutMs = Math.max(1, Number(options.videoTimeoutMs || 45000));
        const maxAttempts = Math.max(1, Number(options.maxAttempts || 2));
        const retryDelayMs = Math.max(0, Number(options.retryDelayMs || 1200));
        const now = typeof options.now === 'function' ? options.now : () => Date.now();
        const setTimer = typeof options.setTimer === 'function' ? options.setTimer : (fn, delay) => setTimeout(fn, delay);
        const clearTimer = typeof options.clearTimer === 'function' ? options.clearTimer : handle => clearTimeout(handle);
        const scheduleFrame = typeof options.scheduleFrame === 'function'
            ? options.scheduleFrame
            : fn => typeof requestAnimationFrame === 'function' ? requestAnimationFrame(fn) : setTimeout(fn, 0);
        const cancelFrame = typeof options.cancelFrame === 'function'
            ? options.cancelFrame
            : handle => typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame(handle) : clearTimeout(handle);
        const active = new Map();
        let frameHandle = 0;
        let sequence = 0;
        let destroyed = false;

        function mediaKind(img){ return img?.dataset?.previewKind === 'video' ? 'video' : 'image'; }
        function activeCounts(){
            let image = 0, video = 0;
            active.forEach(task => { if(task.kind === 'video') video += 1; else image += 1; });
            return {image, video, total:image + video};
        }
        function snapshot(){
            const counts = activeCounts();
            return {
                name,
                activeTotal:counts.total,
                activeImage:counts.image,
                activeVideo:counts.video,
                maxActive,
                maxImageActive,
                maxVideoActive
            };
        }
        function hasCapacity(kind){
            const counts = activeCounts();
            if(counts.total >= maxActive) return false;
            return kind === 'video' ? counts.video < maxVideoActive : counts.image < maxImageActive;
        }
        function isCurrent(task){
            return active.get(task.img) === task && task.img?.dataset?.previewTaskId === task.id;
        }
        function eligible(img){
            if(!img?.isConnected) return false;
            if(typeof options.isEligible !== 'function') return true;
            try { return Boolean(options.isEligible(img)); }
            catch(error) { return false; }
        }
        function removeSource(img){
            try { img?.removeAttribute?.('src'); }
            catch(error) {}
        }
        function cleanupTask(task){
            if(task.timer) clearTimer(task.timer);
            task.timer = 0;
            task.img?.removeEventListener?.('load', task.onLoad);
            task.img?.removeEventListener?.('error', task.onError);
        }
        function record(task, outcome, reason=''){
            if(typeof options.onRecord !== 'function') return;
            try {
                options.onRecord({
                    name,
                    kind:task.kind,
                    outcome,
                    reason,
                    attempt:task.attempt,
                    duration:Math.max(0, now() - task.startedAt),
                    ...snapshot()
                });
            } catch(error) {}
        }
        function notifyStart(task){
            if(typeof options.onStart !== 'function') return;
            try {
                options.onStart({
                    name,
                    kind:task.kind,
                    attempt:task.attempt,
                    ...snapshot()
                });
            } catch(error) {}
        }
        function scheduleRetry(img, delay){
            if(destroyed || !img?.isConnected) return;
            setTimer(() => {
                if(destroyed || !img?.isConnected || img.dataset.previewState !== 'queued') return;
                delete img.dataset.previewRetryAt;
                schedule();
            }, delay);
        }
        function settle(task, outcome, reason=''){
            if(task.settled) return false;
            task.settled = true;
            cleanupTask(task);
            active.delete(task.img);
            const current = task.img?.dataset?.previewTaskId === task.id;
            if(current) delete task.img.dataset.previewTaskId;
            if(current && task.img.isConnected){
                if(outcome === 'loaded'){
                    task.img.dataset.previewState = 'loaded';
                    delete task.img.dataset.previewAttempt;
                    delete task.img.dataset.previewRetryAt;
                    delete task.img.dataset.previewPhase;
                } else if(outcome === 'canceled'){
                    removeSource(task.img);
                    task.img.dataset.previewState = 'queued';
                    delete task.img.dataset.previewAttempt;
                    delete task.img.dataset.previewRetryAt;
                    delete task.img.dataset.previewPhase;
                } else if(outcome === 'timeout' && task.attempt < maxAttempts && eligible(task.img)){
                    removeSource(task.img);
                    const delay = retryDelayMs * Math.pow(2, Math.max(0, task.attempt - 1));
                    task.img.dataset.previewState = 'queued';
                    task.img.dataset.previewRetryAt = String(now() + delay);
                    delete task.img.dataset.previewPhase;
                    scheduleRetry(task.img, delay);
                } else {
                    removeSource(task.img);
                    task.img.dataset.previewState = 'failed';
                    delete task.img.dataset.previewRetryAt;
                    delete task.img.dataset.previewPhase;
                }
            }
            record(task, outcome, reason);
            if(!destroyed) schedule();
            return true;
        }
        function armTimeout(task){
            if(task.timer) clearTimer(task.timer);
            const timeout = task.kind === 'video' ? videoTimeoutMs : imageTimeoutMs;
            task.timer = setTimer(() => settle(task, 'timeout', task.phase), timeout);
        }
        function switchToFallback(task){
            if(task.phase !== 'preview' || !isCurrent(task)) return false;
            if(task.kind === 'video' && typeof options.replaceVideoFallback === 'function'){
                let replaced = false;
                try { replaced = Boolean(options.replaceVideoFallback(task.img)); }
                catch(error) {}
                if(replaced) settle(task, 'failed', 'video-fallback');
                return replaced;
            }
            let source = '';
            if(typeof options.fallbackSource === 'function'){
                try { source = String(options.fallbackSource(task.img) || ''); }
                catch(error) {}
            }
            if(!source || task.img.getAttribute?.('src') === source) return false;
            task.phase = 'fallback';
            task.img.dataset.previewPhase = 'fallback';
            armTimeout(task);
            task.img.src = source;
            return true;
        }
        function start(img){
            if(destroyed || !img?.isConnected || active.has(img)) return false;
            const preview = String(img.dataset?.previewSrc || '');
            if(!preview || img.dataset.previewState === 'loaded' || img.dataset.previewState === 'loading' || img.dataset.previewState === 'failed') return false;
            const retryAt = Number(img.dataset.previewRetryAt || 0);
            if(retryAt > now()) return false;
            const kind = mediaKind(img);
            if(!hasCapacity(kind)) return false;
            const attempt = Math.max(0, Number(img.dataset.previewAttempt || 0)) + 1;
            const task = {
                id:`${name}-${++sequence}`,
                img,
                kind,
                attempt,
                phase:'preview',
                startedAt:now(),
                settled:false,
                timer:0,
                onLoad:null,
                onError:null
            };
            task.onLoad = () => { if(isCurrent(task)) settle(task, 'loaded', task.phase); };
            task.onError = () => {
                if(!isCurrent(task)) return;
                if(switchToFallback(task)) return;
                settle(task, 'failed', task.phase);
            };
            active.set(img, task);
            img.dataset.previewTaskId = task.id;
            img.dataset.previewAttempt = String(attempt);
            img.dataset.previewPhase = 'preview';
            img.dataset.previewState = 'loading';
            img.addEventListener?.('load', task.onLoad);
            img.addEventListener?.('error', task.onError);
            armTimeout(task);
            notifyStart(task);
            try { img.src = preview; }
            catch(error) {
                settle(task, 'failed', 'source-assignment');
                return false;
            }
            return true;
        }
        function cancelTask(task, reason='ineligible'){
            if(!task || task.settled) return false;
            return settle(task, 'canceled', reason);
        }
        function cancelIneligible(){
            [...active.values()].forEach(task => {
                if(!eligible(task.img)) cancelTask(task, task.img?.isConnected ? 'offscreen' : 'detached');
            });
            return snapshot();
        }
        function drainNow(){
            if(destroyed) return snapshot();
            cancelIneligible();
            let candidates = [];
            if(typeof options.collectCandidates === 'function'){
                try { candidates = options.collectCandidates() || []; }
                catch(error) { candidates = []; }
            }
            let candidateList = [];
            try { candidateList = [...candidates]; }
            catch(error) {}
            candidateList
                .filter(candidate => candidate?.img && eligible(candidate.img))
                .sort((left, right) => Number(left.priority || 0) - Number(right.priority || 0) || Number(left.distance || 0) - Number(right.distance || 0))
                .forEach(candidate => { start(candidate.img); });
            return snapshot();
        }
        function schedule(){
            if(destroyed || frameHandle) return;
            frameHandle = scheduleFrame(() => {
                frameHandle = 0;
                drainNow();
            });
        }
        function destroy(){
            if(destroyed) return;
            destroyed = true;
            if(frameHandle) cancelFrame(frameHandle);
            frameHandle = 0;
            [...active.values()].forEach(task => cancelTask(task, 'destroyed'));
            active.clear();
        }
        return Object.freeze({start, schedule, drainNow, cancelIneligible, snapshot, destroy});
    }

    return Object.freeze({createMediaQueue});
});
