// 检查当前 DOM 的真实像素/媒体状态，不把已被重绘移除的旧元素当成完成。
(function(root, factory){
    if(typeof module === 'object' && module.exports) module.exports = factory;
    else root.CanvasResourceReady = factory(root);
})(typeof window === 'undefined' ? null : window, function(host){
    async function wait({root, isCurrent, drain, progress, active=()=>true, include=()=>true, timeoutMs=90000, budgetMs=Infinity}){
        const states = new WeakMap();
        let stableSince=0, previous=[];
        let elapsed=0,lastTick=Date.now();
        while(isCurrent()){
            const now=Date.now();
            if(!active()){lastTick=now;await new Promise(resolve=>host.setTimeout(resolve,80));continue;}
            elapsed+=now-lastTick;lastTick=now;
            drain();
            const missing=[...root.querySelectorAll('.missing-asset')].filter(include);
            if(missing.length) return {failed:missing};
            const elements=[...root.querySelectorAll('img,video,audio')].filter(include).filter(el =>
                el.dataset.previewSrc || el.getAttribute('src') || el.querySelector?.('source[src]'));
            const changed=elements.length!==previous.length || elements.some((el,i)=>el!==previous[i]);
            if(changed) stableSince=0;
            previous=elements;
            let done=0;
            const failed=[];
            for(const el of elements){
                const source=[el.dataset.previewSrc || '',el.getAttribute('src') || el.querySelector?.('source[src]')?.src || '',el.currentSrc || ''].join('|');
                let state=states.get(el);
                if(!state || state.source!==source){
                    state={source,started:elapsed,decoded:false,decoding:false,error:false};states.set(el,state);
                    if(el.tagName==='IMG') el.loading='eager';
                    else {el.preload='auto';if(el.readyState===0) el.load();}
                }
                if(el.tagName==='IMG'){
                    if(el.dataset.previewSrc && el.dataset.previewState==='queued') state.started=elapsed;
                    if(el.dataset.previewState==='failed') state.error=true;
                    // 队列的 loaded 仅代表 load 事件，仍需完成解码；普通图片同样检查。
                    const queueReady=!el.dataset.previewSrc || ['ready','loaded','evicted'].includes(el.dataset.previewState);
                    if(queueReady && el.complete && el.naturalWidth>0 && !state.decoding && !state.decoded){
                        state.decoding=true;
                        Promise.resolve().then(()=>el.decode?.()).then(()=>{state.decoded=true;},error=>{
                            state.decoding=false;
                            if(error?.name!=='AbortError') state.error=true;
                        });
                    }
                    if(!el.dataset.previewSrc && el.complete && el.naturalWidth===0) state.error=true;
                } else {
                    state.decoded=el.readyState>=3;
                    if(el.error) state.error=true;
                }
                if(state.decoded && !state.error) done++;
                else if(state.error || elapsed-state.started>timeoutMs) failed.push(el);
            }
            progress(done,elements.length);
            if(failed.length) return {failed};
            // 整体预算包含排队和 DOM 替换，不随单个资源重试重置。
            if(elapsed>=budgetMs) return {failed:[],pending:elements.filter(el=>!states.get(el)?.decoded)};
            if(done===elements.length){
                if(!stableSince) stableSince=Date.now();
                if(Date.now()-stableSince>=300) return {failed:[]};
            } else stableSince=0;
            await new Promise(resolve=>host.setTimeout(resolve,80));
        }
        return {cancelled:true,failed:[]};
    }
    function monitor({root,isCurrent,drain,retryMissing}){
        if(!host.MutationObserver) return {stop(){}};
        const notices=new Map();
        let timer=null,stopped=false;
        function status(el){
            if(el.classList.contains('missing-asset')) return 'missing';
            if(el.tagName==='IMG'){
                if(el.dataset.previewState==='failed') return 'failed';
                if(el.complete && el.naturalWidth>0 && (!el.dataset.previewSrc || ['loaded','ready','evicted'].includes(el.dataset.previewState))) return 'ready';
                if(!el.dataset.previewSrc && el.complete && !el.naturalWidth) return 'failed';
            }else{
                if(el.error) return 'failed';
                if(el.readyState>=2 || (el.tagName==='VIDEO' && el.poster)) return 'ready';
            }
            return 'pending';
        }
        async function retry(node){
            if(!isCurrent()) return;
            for(const el of node.querySelectorAll('img,video,audio')){
                if(status(el)!=='failed') continue;
                if(el.dataset.previewSrc){
                    el.dataset.previewState='queued';
                    delete el.dataset.previewAttempt;delete el.dataset.previewRetryAt;
                }else if(el.tagName==='IMG'){
                    const src=el.getAttribute('src');el.removeAttribute('src');if(src) el.src=src;
                }else el.load();
            }
            drain();schedule();
            if(node.querySelector('.missing-asset')){
                try{await retryMissing?.(node);}catch(error){host.console?.warn('canvas resource retry failed',error);}
                schedule();
            }
        }
        function scan(){
            timer=null;
            if(stopped || !isCurrent()){stop();return;}
            const groups=new Map();
            for(const el of root.querySelectorAll('img,video,audio,.missing-asset')){
                if(!el.classList.contains('missing-asset') && !el.dataset.previewSrc && !el.getAttribute('src') && !el.querySelector('source[src]')) continue;
                const node=el.closest('.node');
                if(!node) continue;
                const state=status(el);
                if(state==='ready') continue;
                const counts=groups.get(node) || {pending:0,failed:0,missing:0};
                counts[state]++;groups.set(node,counts);
            }
            for(const [node,notice] of notices){
                if(!groups.has(node) || !root.contains(node)){notice.remove();notices.delete(node);}
            }
            for(const [node,counts] of groups){
                let notice=notices.get(node);
                if(notice && !node.contains(notice)){notices.delete(node);notice=null;}
                if(!notice){
                    notice=host.document.createElement('button');notice.type='button';
                    notice.className='canvas-resource-notice';
                    for(const type of ['pointerdown','mousedown','dblclick']) notice.addEventListener(type,event=>event.stopPropagation());
                    notice.addEventListener('click',event=>{event.stopPropagation();void retry(node);});
                    node.appendChild(notice);notices.set(node,notice);
                }
                const failed=counts.failed+counts.missing;
                const label=failed ? `${failed} 项资源${counts.missing?'缺失':'加载失败'} · 重试` : `${counts.pending} 项资源加载中…`;
                if(notice.textContent!==label) notice.textContent=label;
                notice.disabled=!failed;
            }
        }
        function schedule(){if(!stopped && timer===null) timer=host.setTimeout(scan,120);}
        const observer=new host.MutationObserver(schedule);
        observer.observe(root,{subtree:true,childList:true,attributes:true,attributeFilter:['src','data-preview-state']});
        const events=['load','error','loadeddata','canplay'];
        for(const event of events) root.addEventListener(event,schedule,true);
        function stop(){
            stopped=true;observer.disconnect();host.clearTimeout(timer);timer=null;
            for(const event of events) root.removeEventListener(event,schedule,true);
            for(const notice of notices.values()) notice.remove();
            notices.clear();
        }
        schedule();return {stop};
    }
    return {wait,monitor};
});
