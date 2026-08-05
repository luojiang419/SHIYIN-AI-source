(function(){
    'use strict';
    const PAGE_LIMIT = 120;
    const OVERSCAN_ROWS = 3;
    const CARD_MIN_WIDTH = 210;
    const CARD_HEIGHT = 334;
    const GRID_GAP = 13;
    const state = {
        works:[],
        total:0,
        nextCursor:'',
        loading:false,
        tab:'all',
        search:'',
        kind:'',
        compareWork:null,
        compareViewer:null,
        previewController:null,
        localBaseUrl:'',
        localTargetUrl:'',
        renderStart:-1,
        renderEnd:-1,
    };
    const el = {};
    const byId = id => document.getElementById(id);
    const t = key => window.StudioI18n?.t?.(key) || key;
    const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g,ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));

    function cache(){
        ['worksCount','worksTabs','worksSearch','worksKind','worksRefresh','worksQuickCompare','worksClearAll','worksDownloadAll','worksGrid','worksEmpty','worksCompareDialog','compareWorkName','compareFavorite','closeWorksCompare','compareTargetSelect','compareTargetFileButton','compareTargetFile','compareBaseSelect','compareBaseFileButton','compareBaseFile','compareHint','worksCompareStage','worksBeforeImage','worksAfterImage','worksAfterClip','worksCompareHandle','worksZoomOut','worksZoomReset','worksZoomIn','worksFullscreen','compareMeta','compareDownload','worksPreviewDialog','closeWorksPreview','worksPreviewFrame','worksPreviewImage','worksPreviewName','worksPreviewMeta','worksPreviewDownload','worksPreviewFullscreen','worksToast'].forEach(id => el[id]=byId(id));
    }
    async function fetchJson(url,options={}){
        const response = await fetch(url,options);
        const data = await response.json().catch(() => ({}));
        if(!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
        return data;
    }
    function toast(message){
        el.worksToast.textContent = message;
        el.worksToast.classList.add('show');
        clearTimeout(toast.timer);
        toast.timer=setTimeout(()=>el.worksToast.classList.remove('show'),2200);
    }
    function kindLabel(item){
        const operations={try_on:'works.tryOn',pose_transfer:'works.poseTransfer',prop_replace:'works.propReplace',angle_change:'works.angleChange',background_change:'works.backgroundChange',universal:'works.universal'};
        if(item.kind==='ecommerce') return operations[item.operation] ? t(operations[item.operation]) : t('works.ecommerce');
        if(item.kind==='online') return t('works.online');
        return item.kind || t('works.image');
    }
    function dateText(timestamp){
        const value=Number(timestamp || 0);
        return value ? new Date(value*1000).toLocaleString() : '-';
    }
    function queryParams(cursor=''){
        const params = new URLSearchParams({limit:String(PAGE_LIMIT),include_trashed:'true'});
        if(cursor) params.set('cursor', cursor);
        if(state.tab === 'favorite') params.set('favorite','true');
        if(state.tab === 'trash') params.set('include_trashed','true');
        if(state.kind) params.set('kind', state.kind);
        if(state.search.trim()) params.set('search', state.search.trim());
        return params;
    }
    function serverVisible(item){
        if(state.tab === 'trash') return item.trashed;
        if(item.trashed) return false;
        if(state.tab === 'favorite' && !item.favorite) return false;
        return true;
    }
    function renderKinds(){
        const current=state.kind;
        const kinds=[...new Set(state.works.filter(serverVisible).map(item=>item.kind).filter(Boolean))].sort();
        el.worksKind.innerHTML=`<option value="">${escapeHtml(t('works.allTypes'))}</option>`+kinds.map(kind=>`<option value="${escapeHtml(kind)}">${escapeHtml(kind==='ecommerce'?t('works.ecommerce'):kind==='online'?t('works.online'):kind)}</option>`).join('');
        state.kind=kinds.includes(current)?current:'';
        el.worksKind.value=state.kind;
    }
    function gridMetrics(){
        const width = Math.max(1, el.worksGrid.clientWidth || 1);
        const columns = Math.max(1, Math.floor((width + GRID_GAP) / (CARD_MIN_WIDTH + GRID_GAP)));
        const cardWidth = Math.floor((width - GRID_GAP * (columns - 1)) / columns);
        return {columns,cardWidth,rowHeight:CARD_HEIGHT + GRID_GAP};
    }
    function renderCard(item,index,metrics){
        const col = index % metrics.columns;
        const row = Math.floor(index / metrics.columns);
        const left = col * (metrics.cardWidth + GRID_GAP);
        const top = row * metrics.rowHeight;
        return `<article class="works-card ${item.trashed?'trashed':''}" data-work-id="${escapeHtml(item.id)}" style="position:absolute;width:${metrics.cardWidth}px;left:${left}px;top:${top}px">
            <button class="works-card-media" type="button" data-preview-work="${escapeHtml(item.id)}"><img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.name)}" loading="lazy"><span class="works-kind">${escapeHtml(kindLabel(item))}</span></button>
            ${item.trashed?'':`<button class="works-favorite ${item.favorite?'active':''}" type="button" data-favorite-work="${escapeHtml(item.id)}" aria-label="${escapeHtml(t('works.favorite'))}">${item.favorite?'★':'☆'}</button>`}
            <div class="works-card-body"><h2 title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</h2><p>${escapeHtml(item.prompt || t('works.noPrompt'))}</p>
                <div class="works-card-meta"><span>${escapeHtml(item.model || '-')}</span><span>${escapeHtml(dateText(item.created_at))}</span></div>
                <div class="works-card-actions"><button class="primary" type="button" data-compare-work="${escapeHtml(item.id)}">${escapeHtml(t('works.compare'))}</button><button type="button" data-download-work="${escapeHtml(item.id)}">${escapeHtml(t('works.download'))}</button><button type="button" data-reveal-work="${escapeHtml(item.id)}">${escapeHtml(t('works.openDirectory'))}</button><button type="button" data-trash-work="${escapeHtml(item.id)}" data-trash-value="${item.trashed?'false':'true'}">${escapeHtml(t(item.trashed?'works.restore':'works.moveToTrash'))}</button></div>
            </div></article>`;
    }
    function bindGridActions(){
        el.worksGrid.querySelectorAll('[data-preview-work]').forEach(button=>button.addEventListener('click',()=>openPreview(button.dataset.previewWork)));
        el.worksGrid.querySelectorAll('[data-compare-work]').forEach(button=>button.addEventListener('click',()=>openCompare(button.dataset.compareWork)));
        el.worksGrid.querySelectorAll('[data-favorite-work]').forEach(button=>button.addEventListener('click',()=>toggleFavorite(button.dataset.favoriteWork)));
        el.worksGrid.querySelectorAll('[data-download-work]').forEach(button=>button.addEventListener('click',()=>downloadWork(state.works.find(item=>item.id===button.dataset.downloadWork))));
        el.worksGrid.querySelectorAll('[data-reveal-work]').forEach(button=>button.addEventListener('click',()=>revealWork(button.dataset.revealWork)));
        el.worksGrid.querySelectorAll('[data-trash-work]').forEach(button=>button.addEventListener('click',()=>setTrashed(button.dataset.trashWork,button.dataset.trashValue==='true')));
    }
    function renderVirtual(force=false){
        const metrics = gridMetrics();
        const totalRows = Math.ceil(Math.max(state.total,state.works.length) / metrics.columns);
        const scrollTop = el.worksGrid.scrollTop || 0;
        const visibleRows = Math.ceil((el.worksGrid.clientHeight || 600) / metrics.rowHeight);
        const startRow = Math.max(0, Math.floor(scrollTop / metrics.rowHeight) - OVERSCAN_ROWS);
        const endRow = Math.min(totalRows, startRow + visibleRows + OVERSCAN_ROWS * 2);
        const start = startRow * metrics.columns;
        const end = Math.min(state.works.length, endRow * metrics.columns);
        el.worksCount.textContent=String(state.total || state.works.length);
        el.worksGrid.classList.toggle('hidden',state.total===0 && !state.loading);
        el.worksEmpty.classList.toggle('hidden',state.total!==0 || state.loading);
        if(el.worksDownloadAll) el.worksDownloadAll.disabled = !(state.total || state.works.length);
        if(el.worksClearAll) el.worksClearAll.disabled = !(state.total || state.works.length);
        el.worksTabs.querySelectorAll('[data-tab]').forEach(button=>button.classList.toggle('active',button.dataset.tab===state.tab));
        if(!force && state.renderStart === start && state.renderEnd === end) return;
        state.renderStart = start;
        state.renderEnd = end;
        const spacerHeight = Math.max(0, totalRows * metrics.rowHeight - GRID_GAP);
        const cards = state.works.slice(start,end).map((item,i)=>renderCard(item,start+i,metrics)).join('');
        const loading = state.loading ? '<div class="works-loading">加载中...</div>' : '';
        el.worksGrid.innerHTML = `<div class="works-virtual-spacer" style="position:relative;height:${spacerHeight}px">${cards}${loading}</div>`;
        bindGridActions();
    }
    async function loadWorks({reset=false}={}){
        if(state.loading) return;
        if(!reset && !state.nextCursor) return;
        state.loading = true;
        el.worksRefresh.disabled=true;
        try {
            if(reset){
                state.works=[];
                state.total=0;
                state.nextCursor='';
                state.renderStart=-1;
                state.renderEnd=-1;
                el.worksGrid.scrollTop=0;
            }
            renderVirtual(true);
            const data=await fetchJson(`/api/works?${queryParams(reset?'':state.nextCursor)}`,{cache:'no-store'});
            state.works = reset ? (data.works || []) : [...state.works, ...(data.works || [])];
            state.total = Number(data.total || state.works.length);
            state.nextCursor = data.next_cursor || '';
            renderKinds();
        } catch(error){ toast(error.message); }
        finally {
            state.loading=false;
            el.worksRefresh.disabled=false;
            renderVirtual(true);
        }
    }
    function scheduleReload(){
        clearTimeout(scheduleReload.timer);
        scheduleReload.timer=setTimeout(()=>loadWorks({reset:true}),220);
    }
    async function toggleFavorite(workId){
        const work=state.works.find(item=>item.id===workId);
        if(!work) return;
        try {
            const data=await fetchJson(`/api/works/${encodeURIComponent(work.id)}/favorite`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({favorite:!work.favorite})});
            Object.assign(work,data.work || {favorite:!work.favorite});
            if(state.compareWork?.id===work.id) state.compareWork=work;
            renderVirtual(true);
            syncCompareFavorite();
        } catch(error){ toast(error.message); }
    }
    async function updateMetadata(workId,changes){
        const data=await fetchJson(`/api/works/${encodeURIComponent(workId)}/metadata`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(changes)});
        const index=state.works.findIndex(item=>item.id===workId);
        if(index>=0) state.works[index]=data.work;
        if(state.compareWork?.id===workId) state.compareWork=data.work;
        renderKinds();renderVirtual(true);syncCompareFavorite();
        return data.work;
    }
    async function setTrashed(workId,trashed){
        if(trashed && !window.confirm(t('works.trashConfirm'))) return;
        try {
            await updateMetadata(workId,{trashed});
            if(state.compareWork?.id===workId && trashed) closeCompare();
            toast(t(trashed?'works.trashedDone':'works.restoredDone'));
            if(state.tab !== 'trash') scheduleReload();
        } catch(error){ toast(error.message); }
    }
    async function revealWork(workId){
        const work=state.works.find(item=>item.id===workId);if(!work)return;
        try {
            await fetchJson(`/api/works/${encodeURIComponent(work.id)}/reveal`,{method:'POST'});
            toast(t('works.openDirectoryDone'));
        } catch(error){ toast(error.message || t('works.openDirectoryFailed')); }
    }
    function availableWorks(){return state.works.filter(item=>!item.trashed);}
    function downloadableWorks(){return state.works.filter(item=>!item.trashed && item.url);}
    function comparisonOptions(work){
        const options=[];
        if(work?.source_url) options.push({value:'source',label:t('works.originalReference'),url:work.source_url});
        availableWorks().filter(item=>item.id!==work?.id).slice(0,200).forEach(item=>options.push({value:item.id,label:item.name,url:item.url}));
        return options;
    }
    function renderCompareMeta(work){
        const values=work?[work.model,work.width&&work.height?`${work.width}x${work.height}`:'',dateText(work.created_at)].filter(Boolean):[];
        el.compareMeta.innerHTML=values.map(value=>`<span>${escapeHtml(value)}</span>`).join('');
    }
    function syncCompareFavorite(){
        el.compareFavorite.disabled=!state.compareWork;
        el.compareFavorite.textContent=state.compareWork?.favorite?'★':'☆';
        el.compareFavorite.title=state.compareWork?t(state.compareWork.favorite?'works.unfavorite':'works.favorite'):t('works.localWork');
    }
    function renderTargetOptions(preferred=''){
        const targets=availableWorks().slice(0,500);
        const selectedTrash=state.works.find(item=>item.id===preferred && item.trashed);
        if(selectedTrash) targets.unshift(selectedTrash);
        const options=targets.map(item=>`<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`);
        if(state.localTargetUrl) options.unshift(`<option value="local">${escapeHtml(t('works.localWork'))}</option>`);
        if(!options.length) options.push(`<option value="">${escapeHtml(t('works.chooseTargetPrompt'))}</option>`);
        el.compareTargetSelect.innerHTML=options.join('');
        if(preferred && [...el.compareTargetSelect.options].some(item=>item.value===preferred)) el.compareTargetSelect.value=preferred;
    }
    function selectedTarget(){
        if(el.compareTargetSelect.value==='local' && state.localTargetUrl) return {id:'',name:t('works.localWork'),url:state.localTargetUrl,local:true};
        return state.works.find(item=>item.id===el.compareTargetSelect.value) || null;
    }
    function renderBaseOptions(work){
        const previous=el.compareBaseSelect.value;
        const options=comparisonOptions(work);
        if(state.localBaseUrl) options.unshift({value:'local',label:t('works.localBase'),url:state.localBaseUrl});
        el.compareBaseSelect.innerHTML=options.length?options.map(item=>`<option value="${escapeHtml(item.value)}" data-url="${escapeHtml(item.url)}">${escapeHtml(item.label)}</option>`).join(''):`<option value="">${escapeHtml(t('works.chooseBasePrompt'))}</option>`;
        if(previous && [...el.compareBaseSelect.options].some(item=>item.value===previous)) el.compareBaseSelect.value=previous;
    }
    function applyComparison(reset=true){
        const target=selectedTarget();
        state.compareWork=target && !target.local ? target : null;
        const baseUrl=el.compareBaseSelect.selectedOptions[0]?.dataset?.url || '';
        const targetUrl=target?.url || '';
        state.compareViewer.setImages(baseUrl,targetUrl);
        if(reset) state.compareViewer.reset();
        el.compareWorkName.textContent=target?.name || t('works.freeCompare');
        el.compareHint.textContent=baseUrl&&targetUrl?t('works.compareHint'):t('works.chooseTwoImages');
        renderCompareMeta(state.compareWork);
        syncCompareFavorite();
        el.compareDownload.disabled=!targetUrl;
        el.compareDownload.onclick=()=>target&&downloadWork(target);
    }
    function syncCompareTarget(){
        const target=selectedTarget();
        renderBaseOptions(target);
        applyComparison();
    }
    function openPreview(workId=''){
        const work=state.works.find(item=>item.id===workId && item.url);
        if(!work) return;
        el.worksPreviewImage.src=work.url;
        el.worksPreviewImage.alt=work.name || t('works.work');
        el.worksPreviewName.textContent=work.name || t('works.work');
        el.worksPreviewMeta.innerHTML=[kindLabel(work),work.model || '',work.width&&work.height?`${work.width}x${work.height}`:'',dateText(work.created_at)].filter(Boolean).map(value=>`<span>${escapeHtml(value)}</span>`).join('');
        el.worksPreviewDownload.onclick=()=>downloadWork(work);
        el.worksPreviewDialog.showModal();
        if(!state.previewController && window.StudioImagePreview?.attach){
            state.previewController=window.StudioImagePreview.attach(el.worksPreviewFrame,{img:el.worksPreviewImage,maxZoom:8});
        }
        state.previewController?.reset?.();
    }
    function closePreview(){
        if(document.fullscreenElement === el.worksPreviewFrame) document.exitFullscreen?.().catch?.(()=>{});
        el.worksPreviewDialog.close();
        el.worksPreviewImage.removeAttribute('src');
        state.previewController?.reset?.();
    }
    async function togglePreviewFullscreen(){
        if(document.fullscreenElement === el.worksPreviewFrame){
            await document.exitFullscreen?.();
            return;
        }
        try { await el.worksPreviewFrame.requestFullscreen?.({navigationUI:'hide'}); }
        catch(error) { toast(error.message || t('works.preview')); }
    }
    function openCompare(workId=''){
        const work=state.works.find(item=>item.id===workId) || state.works.find(item=>!item.trashed);
        if(!state.compareViewer) state.compareViewer=new window.CompareViewer({root:el.worksCompareStage,before:el.worksBeforeImage,after:el.worksAfterImage,afterClip:el.worksAfterClip,handle:el.worksCompareHandle,zoomOutButton:el.worksZoomOut,zoomLabel:el.worksZoomReset,zoomInButton:el.worksZoomIn,fullscreenButton:el.worksFullscreen});
        renderTargetOptions(work?.id || '');
        if(work) el.compareTargetSelect.value=work.id;
        syncCompareTarget();
        el.worksCompareDialog.showModal();
    }
    function closeCompare(){el.worksCompareDialog.close();}
    function extensionFromWork(work){
        const source=String(work?.original_name || work?.url || '').split('?')[0].split('#')[0];
        const match=source.match(/\.[a-z0-9]{1,8}$/i);
        return match?match[0].toLowerCase():'.png';
    }
    function workDatePart(work){
        const value=Number(work?.created_at || 0);
        const date=value?new Date(value*1000):new Date();
        const pad=n=>String(n).padStart(2,'0');
        return `${date.getFullYear()}${pad(date.getMonth()+1)}${pad(date.getDate())}`;
    }
    function padSequence(value){return String(Math.max(1,Number(value)||1)).padStart(6,'0');}
    function workDownloadName(work){
        return work?.download_name || `SHIYIN-${padSequence(work?.download_sequence || 1)}-${workDatePart(work)}${extensionFromWork(work)}`;
    }
    function downloadWork(work){
        if(!work?.url)return;
        const name=workDownloadName(work);
        const link=document.createElement('a');
        link.href=`/api/download-output?url=${encodeURIComponent(work.url)}&name=${encodeURIComponent(name)}`;
        link.download=name;
        document.body.appendChild(link);
        link.click();
        link.remove();
        toast(t('desktop.download.finished'));
    }
    async function downloadAll(){
        const name=`SHIYIN-全部作品-${workDatePart({created_at:Date.now()/1000})}.zip`;
        const url=`/api/works/download-all?name=${encodeURIComponent(name)}`;
        if(window.showSaveFilePicker){
            try {
                const handle=await window.showSaveFilePicker({suggestedName:name,types:[{description:'ZIP',accept:{'application/zip':['.zip']}}]});
                const response=await fetch(url);
                if(!response.ok) throw new Error(`HTTP ${response.status}`);
                const writable=await handle.createWritable();
                await writable.write(await response.blob());
                await writable.close();
                toast(t('desktop.download.finished'));
                return;
            } catch(error){ if(error?.name==='AbortError') return; toast(error.message || t('desktop.download.failed')); return; }
        }
        window.location.href=url;
    }
    async function clearAllWorks(){
        if(!window.confirm(t('works.clearAllConfirm'))) return;
        try {
            const result=await fetchJson('/api/works',{method:'DELETE'});
            state.works=[]; state.total=0; state.nextCursor='';
            renderKinds(); renderVirtual(true);
            toast(`${t('works.clearAllDone')} ${result.deleted_files || 0}`);
        } catch(error){ toast(error.message || t('works.clearAllFailed')); }
    }
    function handleScroll(){
        renderVirtual();
        const remaining = el.worksGrid.scrollHeight - el.worksGrid.scrollTop - el.worksGrid.clientHeight;
        if(remaining < 1200 && state.nextCursor && !state.loading) loadWorks();
    }
    function bind(){
        el.worksRefresh.addEventListener('click',()=>loadWorks({reset:true}));
        el.worksTabs.addEventListener('click',event=>{const btn=event.target.closest('[data-tab]');if(!btn)return;state.tab=btn.dataset.tab;loadWorks({reset:true});});
        el.worksSearch.addEventListener('input',event=>{state.search=event.target.value;scheduleReload();});
        el.worksKind.addEventListener('change',event=>{state.kind=event.target.value;loadWorks({reset:true});});
        el.worksQuickCompare.addEventListener('click',()=>openCompare());
        el.closeWorksCompare.addEventListener('click',closeCompare);
        el.compareTargetSelect.addEventListener('change',syncCompareTarget);
        el.compareBaseSelect.addEventListener('change',()=>applyComparison());
        el.compareFavorite.addEventListener('click',()=>state.compareWork&&toggleFavorite(state.compareWork.id));
        el.compareBaseFileButton.addEventListener('click',()=>el.compareBaseFile.click());
        el.compareTargetFileButton.addEventListener('click',()=>el.compareTargetFile.click());
        el.compareBaseFile.addEventListener('change',event=>{const file=event.target.files?.[0];if(!file)return;state.localBaseUrl=URL.createObjectURL(file);renderBaseOptions(selectedTarget());applyComparison();});
        el.compareTargetFile.addEventListener('change',event=>{const file=event.target.files?.[0];if(!file)return;state.localTargetUrl=URL.createObjectURL(file);renderTargetOptions('local');syncCompareTarget();});
        el.closeWorksPreview.addEventListener('click',closePreview);
        el.worksPreviewDialog.addEventListener('click',event=>{if(event.target===el.worksPreviewDialog)closePreview();});
        el.worksPreviewFullscreen.addEventListener('click',togglePreviewFullscreen);
        el.worksGrid.addEventListener('scroll',handleScroll,{passive:true});
        window.addEventListener('resize',()=>renderVirtual(true));
        el.worksDownloadAll.addEventListener('click',downloadAll);
        el.worksClearAll.addEventListener('click',clearAllWorks);
    }
    document.addEventListener('DOMContentLoaded',()=>{cache();bind();loadWorks({reset:true});});
})();
