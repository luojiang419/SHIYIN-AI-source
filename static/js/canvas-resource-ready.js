// 检查当前 DOM 的真实像素/媒体状态，不把已被重绘移除的旧元素当成完成。
(function(root, factory){
    if(typeof module === 'object' && module.exports) module.exports = factory;
    else root.CanvasResourceReady = factory(root);
})(typeof window === 'undefined' ? null : window, function(host){
    async function wait({root, isCurrent, drain, progress, active=()=>true, include=()=>true, timeoutMs=90000}){
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
            if(done===elements.length){
                if(!stableSince) stableSince=Date.now();
                if(Date.now()-stableSince>=300) return {failed:[]};
            } else stableSince=0;
            await new Promise(resolve=>host.setTimeout(resolve,80));
        }
        return {cancelled:true,failed:[]};
    }
    return {wait};
});
