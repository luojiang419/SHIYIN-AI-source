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

    function createMediaResidency(options={}){
        const name = String(options.name || 'canvas-media-residency');
        const graceMs = Math.max(0, Number(options.graceMs ?? 3000));
        const maxResident = Math.max(1, Number(options.maxResident || 72));
        const maxResidentPixels = Math.max(1, Number(options.maxResidentPixels || 32 * 1024 * 1024));
        const defaultPixels = Math.max(1, Number(options.defaultPixels || 512 * 512));
        const now = typeof options.now === 'function' ? options.now : () => Date.now();
        const setTimer = typeof options.setTimer === 'function' ? options.setTimer : (fn, delay) => setTimeout(fn, delay);
        const clearTimer = typeof options.clearTimer === 'function' ? options.clearTimer : handle => clearTimeout(handle);
        const scheduleFrame = typeof options.scheduleFrame === 'function'
            ? options.scheduleFrame
            : fn => typeof requestAnimationFrame === 'function' ? requestAnimationFrame(fn) : setTimeout(fn, 0);
        const cancelFrame = typeof options.cancelFrame === 'function'
            ? options.cancelFrame
            : handle => typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame(handle) : clearTimeout(handle);
        const outsideSince = new WeakMap();
        let frameHandle = 0;
        let timerHandle = 0;
        let destroyed = false;
        let cumulativeEvictions = 0;
        const detachedRecords = new WeakMap();
        let lastSnapshot = {
            name,
            residentTotal:0,
            residentPixels:0,
            evictedTotal:0,
            maxResident,
            maxResidentPixels,
            budgetExceeded:false,
            cumulativeEvictions:0
        };

        function tagName(element){ return String(element?.tagName || '').toLowerCase(); }
        function sourceOf(element){
            try { return String(element?.getAttribute?.('src') || element?.dataset?.mediaResidentSrc || ''); }
            catch(error) { return ''; }
        }
        function isEvicted(element){
            return element?.dataset?.mediaResidentState === 'evicted'
                || element?.dataset?.mediaResidentPlaceholder === '1'
                || (tagName(element) === 'img' && element?.dataset?.previewState === 'evicted');
        }
        function isPlaying(element){
            const tag = tagName(element);
            return (tag === 'video' || tag === 'audio') && element?.paused === false;
        }
        function isPinned(entry){ return Boolean(entry.pinned || isPlaying(entry.element)); }
        function pixelCost(entry){
            const explicit = Number(entry.pixels || 0);
            if(explicit > 0) return Math.round(explicit);
            const element = entry.element;
            const width = Number(element?.naturalWidth || element?.videoWidth || 0);
            const height = Number(element?.naturalHeight || element?.videoHeight || 0);
            if(width > 0 && height > 0) return Math.round(width * height);
            return tagName(element) === 'audio' ? 1 : defaultPixels;
        }
        function normalizeEntries(){
            let raw = [];
            if(typeof options.collectEntries === 'function'){
                try { raw = options.collectEntries() || []; }
                catch(error) { raw = []; }
            }
            let list = [];
            try { list = [...raw]; }
            catch(error) {}
            const seen = new Set();
            return list.map(value => {
                const entry = value?.element ? value : {element:value};
                return {
                    ...entry,
                    element:entry.element,
                    eligible:Boolean(entry.eligible),
                    visible:Boolean(entry.visible),
                    pinned:Boolean(entry.pinned),
                    distance:Number(entry.distance || 0)
                };
            }).filter(entry => {
                const element = entry.element;
                if(!element?.isConnected || seen.has(element)) return false;
                seen.add(element);
                return ['img', 'video', 'audio'].includes(tagName(element)) || element?.dataset?.mediaResidentPlaceholder === '1';
            });
        }
        function notify(entry, action, reason, pixels){
            const payload = {name, action, reason, kind:tagName(entry.element), pixels, ...lastSnapshot};
            if(typeof options.onRecord === 'function'){
                try { options.onRecord(payload); }
                catch(error) {}
            }
            if(typeof options.onChange === 'function'){
                try { options.onChange(payload); }
                catch(error) {}
            }
        }
        function queueNotification(events, entry, action, reason, pixels){
            if(events) events.push({entry, action, reason, pixels});
            else notify(entry, action, reason, pixels);
        }
        function evict(entry, reason, events=null){
            const element = entry.element;
            const tag = tagName(element);
            const source = sourceOf(element);
            if(!source || isPinned(entry)) return false;
            if(tag === 'img'){
                if(!element.dataset?.previewSrc || element.dataset.previewState === 'loading' || element.dataset.previewTaskId) return false;
                const original = element;
                try { element.removeAttribute('src'); }
                catch(error) { return false; }
                element.dataset.previewState = 'evicted';
                delete element.dataset.selectedHighResTarget;
                if(typeof options.detachImage === 'function'){
                    let placeholder = null;
                    try { placeholder = options.detachImage(original, entry); }
                    catch(error) {}
                    if(placeholder?.isConnected){
                        placeholder.dataset.mediaResidentPlaceholder = '1';
                        placeholder.dataset.mediaResidentState = 'evicted';
                        placeholder.dataset.mediaResidentSrc = source;
                        placeholder.dataset.mediaResidentReason = reason;
                        detachedRecords.set(placeholder, {original, placeholder, source, entry});
                    }
                }
            } else {
                element.dataset.mediaResidentSrc = source;
                try { element.pause?.(); } catch(error) {}
                try { element.removeAttribute('src'); }
                catch(error) { return false; }
                try { element.load?.(); } catch(error) {}
                element.dataset.mediaResidentState = 'evicted';
            }
            element.dataset.mediaResidentReason = reason;
            outsideSince.delete(element);
            cumulativeEvictions += 1;
            queueNotification(events, entry, 'evicted', reason, pixelCost(entry));
            return true;
        }
        function restore(entry, events=null){
            const element = entry.element;
            const tag = tagName(element);
            if(!isEvicted(element)) return false;
            if(element?.dataset?.mediaResidentPlaceholder === '1'){
                const record = detachedRecords.get(element);
                if(!record?.original) return false;
                let restored = false;
                try {
                    restored = typeof options.restoreImage === 'function'
                        ? Boolean(options.restoreImage(element, record.original, entry))
                        : Boolean(element.replaceWith?.(record.original));
                } catch(error) {}
                if(!restored && !record.original.isConnected) return false;
                record.original.dataset.previewState = 'queued';
                delete record.original.dataset.mediaResidentReason;
                detachedRecords.delete(element);
                const reason = element.dataset.mediaResidentReason || 'offscreen';
                outsideSince.delete(element);
                queueNotification(events, entry, 'restored', reason, pixelCost(entry));
                return true;
            }
            if(tag === 'img'){
                element.dataset.previewState = 'queued';
                delete element.dataset.previewAttempt;
                delete element.dataset.previewRetryAt;
                delete element.dataset.previewPhase;
                delete element.dataset.previewTaskId;
            } else {
                const source = String(element.dataset?.mediaResidentSrc || element.dataset?.url || '');
                if(!source) return false;
                try { element.src = source; }
                catch(error) { return false; }
                try { element.load?.(); } catch(error) {}
                delete element.dataset.mediaResidentSrc;
                delete element.dataset.mediaResidentState;
            }
            const reason = element.dataset.mediaResidentReason || 'offscreen';
            delete element.dataset.mediaResidentReason;
            outsideSince.delete(element);
            queueNotification(events, entry, 'restored', reason, pixelCost(entry));
            return true;
        }
        function residentStats(entries){
            let residentTotal = 0;
            let residentPixels = 0;
            let evictedTotal = 0;
            entries.forEach(entry => {
                if(isEvicted(entry.element)){
                    evictedTotal += 1;
                    return;
                }
                if(!sourceOf(entry.element)) return;
                residentTotal += 1;
                residentPixels += pixelCost(entry);
            });
            return {residentTotal, residentPixels, evictedTotal};
        }
        function updateSnapshot(entries){
            const stats = residentStats(entries);
            lastSnapshot = {
                name,
                ...stats,
                maxResident,
                maxResidentPixels,
                budgetExceeded:stats.residentTotal > maxResident || stats.residentPixels > maxResidentPixels,
                cumulativeEvictions
            };
            return lastSnapshot;
        }
        function scheduleDeadline(delay){
            if(destroyed || timerHandle) return;
            timerHandle = setTimer(() => {
                timerHandle = 0;
                schedule();
            }, Math.max(1, delay));
        }
        function reconcileNow(){
            if(destroyed) return lastSnapshot;
            if(timerHandle) clearTimer(timerHandle);
            timerHandle = 0;
            const entries = normalizeEntries();
            const timestamp = now();
            const events = [];
            let nextDelay = Number.POSITIVE_INFINITY;
            entries.forEach(entry => {
                const pinned = isPinned(entry);
                if(isEvicted(entry.element)){
                    const reason = entry.element.dataset?.mediaResidentReason || 'offscreen';
                    if(pinned || entry.visible || (entry.eligible && reason !== 'budget')) restore(entry, events);
                    return;
                }
                if(!sourceOf(entry.element)) return;
                if(pinned || entry.eligible){
                    outsideSince.delete(entry.element);
                    return;
                }
                const since = outsideSince.get(entry.element) ?? timestamp;
                outsideSince.set(entry.element, since);
                const remaining = graceMs - (timestamp - since);
                if(remaining <= 0) evict(entry, 'offscreen', events);
                else nextDelay = Math.min(nextDelay, remaining);
            });

            let stats = residentStats(entries);
            if(stats.residentTotal > maxResident || stats.residentPixels > maxResidentPixels){
                const budgetCandidates = entries
                    .filter(entry => sourceOf(entry.element) && !isEvicted(entry.element) && !entry.visible && !isPinned(entry))
                    .sort((left, right) => Number(right.distance || 0) - Number(left.distance || 0));
                for(const entry of budgetCandidates){
                    if(stats.residentTotal <= maxResident && stats.residentPixels <= maxResidentPixels) break;
                    if(evict(entry, 'budget', events)) stats = residentStats(entries);
                }
            }
            const result = updateSnapshot(entries);
            events.forEach(event => notify(event.entry, event.action, event.reason, event.pixels));
            if(Number.isFinite(nextDelay)) scheduleDeadline(nextDelay);
            return result;
        }
        function schedule(){
            if(destroyed || frameHandle) return;
            frameHandle = scheduleFrame(() => {
                frameHandle = 0;
                reconcileNow();
            });
        }
        function snapshot(){ return {...lastSnapshot}; }
        function destroy(){
            if(destroyed) return;
            destroyed = true;
            if(frameHandle) cancelFrame(frameHandle);
            if(timerHandle) clearTimer(timerHandle);
            frameHandle = 0;
            timerHandle = 0;
        }

        return Object.freeze({schedule, reconcileNow, snapshot, destroy});
    }

    function createSpatialGridIndex(options={}){
        const cellSize = Math.max(32, Number(options.cellSize || 640));
        const cells = new Map();
        const entries = new Map();
        const key = (x, y) => `${x}:${y}`;
        const cellsFor = rect => {
            const minX = Math.floor(Number(rect?.x || 0) / cellSize);
            const minY = Math.floor(Number(rect?.y || 0) / cellSize);
            const maxX = Math.floor((Number(rect?.x || 0) + Math.max(1, Number(rect?.w ?? rect?.width ?? 1)) - 1) / cellSize);
            const maxY = Math.floor((Number(rect?.y || 0) + Math.max(1, Number(rect?.h ?? rect?.height ?? 1)) - 1) / cellSize);
            const result = [];
            for(let x=minX; x<=maxX; x++) for(let y=minY; y<=maxY; y++) result.push(key(x,y));
            return result;
        };
        function remove(id){
            const old = entries.get(id);
            if(!old) return false;
            old.keys.forEach(cell => cells.get(cell)?.delete(id));
            entries.delete(id);
            return true;
        }
        function upsert(id, rect, value=id){
            if(id == null || !rect) return false;
            remove(id);
            const record = {id, rect:{...rect}, value, keys:cellsFor(rect)};
            entries.set(id, record);
            record.keys.forEach(cell => {
                if(!cells.has(cell)) cells.set(cell, new Set());
                cells.get(cell).add(id);
            });
            return true;
        }
        function clear(){ cells.clear(); entries.clear(); }
        function search(rect){
            const ids = new Set();
            cellsFor(rect).forEach(cell => cells.get(cell)?.forEach(id => ids.add(id)));
            const minX = Number(rect?.x || 0), minY = Number(rect?.y || 0);
            const maxX = minX + Math.max(0, Number(rect?.w ?? rect?.width ?? 0));
            const maxY = minY + Math.max(0, Number(rect?.h ?? rect?.height ?? 0));
            return [...ids].map(id => entries.get(id)).filter(record => {
                if(!record) return false;
                const value = record.rect;
                const x = Number(value.x || 0), y = Number(value.y || 0);
                const w = Math.max(0, Number(value.w ?? value.width ?? 0));
                const h = Math.max(0, Number(value.h ?? value.height ?? 0));
                return x < maxX && x + w > minX && y < maxY && y + h > minY;
            }).map(record => record.value);
        }
        function size(){ return entries.size; }
        return Object.freeze({upsert, remove, clear, search, size});
    }

    return Object.freeze({createMediaQueue, createMediaResidency, createSpatialGridIndex});
});
