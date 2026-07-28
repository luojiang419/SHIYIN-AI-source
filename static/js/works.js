(function(){
    'use strict';
    const state = {works:[],tab:'all',search:'',kind:'',compareWork:null,compareViewer:null,localBaseUrl:'',localTargetUrl:''};
    const el = {};
    const byId = id => document.getElementById(id);
    const t = key => window.StudioI18n?.t?.(key) || key;
    const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g,ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));

    function cache(){
        ['worksCount','worksTabs','worksSearch','worksKind','worksRefresh','worksQuickCompare','worksClearAll','worksDownloadAll','worksGrid','worksEmpty','worksCompareDialog','compareWorkName','compareFavorite','closeWorksCompare','compareTargetSelect','compareTargetFileButton','compareTargetFile','compareBaseSelect','compareBaseFileButton','compareBaseFile','compareHint','worksCompareStage','worksBeforeImage','worksAfterImage','worksAfterClip','worksCompareHandle','worksZoomOut','worksZoomReset','worksZoomIn','worksFullscreen','compareMeta','compareDownload','worksToast'].forEach(id => el[id]=byId(id));
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
    function visibleWorks(){
        const search=state.search.trim().toLowerCase();
        return state.works.filter(item => {
            if(state.tab==='trash') return item.trashed && (!search || `${item.name} ${item.prompt} ${item.model} ${item.operation}`.toLowerCase().includes(search)) && (!state.kind || item.kind===state.kind);
            if(item.trashed) return false;
            if(state.tab==='favorite' && !item.favorite) return false;
            if(state.kind && item.kind!==state.kind) return false;
            if(search && !`${item.name} ${item.prompt} ${item.model} ${item.operation}`.toLowerCase().includes(search)) return false;
            return true;
        });
    }
    function kindLabel(item){
        const operations={try_on:'works.tryOn',pose_transfer:'works.poseTransfer',prop_replace:'works.propReplace',angle_change:'works.angleChange',background_change:'works.backgroundChange',universal:'works.universal'};
        if(item.kind==='ecommerce') return operations[item.operation] ? t(operations[item.operation]) : t('works.ecommerce');
        if(item.kind==='online') return t('works.online');
        return item.kind || t('works.image');
    }
    function dateText(timestamp){
        const value=Number(timestamp || 0);
        return value ? new Date(value*1000).toLocaleString() : '—';
    }
    function renderKinds(){
        const current=state.kind;
        const kinds=[...new Set(state.works.filter(item=>state.tab==='trash'?item.trashed:!item.trashed).map(item=>item.kind).filter(Boolean))].sort();
        el.worksKind.innerHTML=`<option value="">${escapeHtml(t('works.allTypes'))}</option>`+kinds.map(kind=>`<option value="${escapeHtml(kind)}">${escapeHtml(kind==='ecommerce'?t('works.ecommerce'):kind==='online'?t('works.online'):kind)}</option>`).join('');
        state.kind=kinds.includes(current)?current:'';
        el.worksKind.value=state.kind;
    }
    function render(){
        const works=visibleWorks();
        el.worksCount.textContent=String(works.length);
        el.worksGrid.classList.toggle('hidden',works.length===0);
        el.worksEmpty.classList.toggle('hidden',works.length!==0);
        if(el.worksDownloadAll) el.worksDownloadAll.disabled = !downloadableWorks().length;
        if(el.worksClearAll) el.worksClearAll.disabled = !state.works.length;
        el.worksTabs.querySelectorAll('[data-tab]').forEach(button=>button.classList.toggle('active',button.dataset.tab===state.tab));
        el.worksGrid.innerHTML=works.map(item=>`<article class="works-card ${item.trashed?'trashed':''}" data-work-id="${escapeHtml(item.id)}">
            <button class="works-card-media" type="button" data-compare-work="${escapeHtml(item.id)}"><img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.name)}" loading="lazy"><span class="works-kind">${escapeHtml(kindLabel(item))}</span></button>
            ${item.trashed?'':`<button class="works-favorite ${item.favorite?'active':''}" type="button" data-favorite-work="${escapeHtml(item.id)}" aria-label="${escapeHtml(t('works.favorite'))}">${item.favorite?'★':'☆'}</button>`}
            <div class="works-card-body"><h2 title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</h2><p>${escapeHtml(item.prompt || t('works.noPrompt'))}</p>
                <div class="works-card-meta"><span>${escapeHtml(item.model || '—')}</span><span>${escapeHtml(dateText(item.created_at))}</span></div>
                <div class="works-card-actions"><button class="primary" type="button" data-compare-work="${escapeHtml(item.id)}">${escapeHtml(t('works.compare'))}</button><button type="button" data-download-work="${escapeHtml(item.id)}">${escapeHtml(t('works.download'))}</button><button type="button" data-reveal-work="${escapeHtml(item.id)}">${escapeHtml(t('works.openDirectory'))}</button><button type="button" data-trash-work="${escapeHtml(item.id)}" data-trash-value="${item.trashed?'false':'true'}">${escapeHtml(t(item.trashed?'works.restore':'works.moveToTrash'))}</button></div>
            </div></article>`).join('');
        el.worksGrid.querySelectorAll('[data-compare-work]').forEach(button=>button.addEventListener('click',()=>openCompare(button.dataset.compareWork)));
        el.worksGrid.querySelectorAll('[data-favorite-work]').forEach(button=>button.addEventListener('click',()=>toggleFavorite(button.dataset.favoriteWork)));
        el.worksGrid.querySelectorAll('[data-download-work]').forEach(button=>button.addEventListener('click',()=>downloadWork(state.works.find(item=>item.id===button.dataset.downloadWork))));
        el.worksGrid.querySelectorAll('[data-reveal-work]').forEach(button=>button.addEventListener('click',()=>revealWork(button.dataset.revealWork)));
        el.worksGrid.querySelectorAll('[data-trash-work]').forEach(button=>button.addEventListener('click',()=>setTrashed(button.dataset.trashWork,button.dataset.trashValue==='true')));
    }
    async function loadWorks(){
        el.worksRefresh.disabled=true;
        try {
            const data=await fetchJson('/api/works?limit=1000&include_trashed=true',{cache:'no-store'});
            state.works=data.works || [];
            renderKinds();
            render();
        } catch(error){ toast(error.message); }
        finally { el.worksRefresh.disabled=false; }
    }
    async function toggleFavorite(workId){
        const work=state.works.find(item=>item.id===workId);
        if(!work) return;
        try {
            const data=await fetchJson(`/api/works/${encodeURIComponent(work.id)}/favorite`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({favorite:!work.favorite})});
            Object.assign(work,data.work || {favorite:!work.favorite});
            if(state.compareWork?.id===work.id) state.compareWork=work;
            render();
            syncCompareFavorite();
        } catch(error){ toast(error.message); }
    }

    async function updateMetadata(workId,changes){
        const data=await fetchJson(`/api/works/${encodeURIComponent(workId)}/metadata`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(changes)});
        const index=state.works.findIndex(item=>item.id===workId);
        if(index>=0) state.works[index]=data.work;
        if(state.compareWork?.id===workId) state.compareWork=data.work;
        renderKinds();render();syncCompareFavorite();
        return data.work;
    }

    async function setTrashed(workId,trashed){
        if(trashed && !window.confirm(t('works.trashConfirm'))) return;
        try {
            await updateMetadata(workId,{trashed});
            if(state.compareWork?.id===workId && trashed) closeCompare();
            toast(t(trashed?'works.trashedDone':'works.restoredDone'));
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
        const values=work?[work.model,work.width&&work.height?`${work.width}×${work.height}`:'',dateText(work.created_at)].filter(Boolean):[];
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

    function openCompare(workId=''){
        const preferred=state.works.some(item=>item.id===workId)?workId:(availableWorks()[0]?.id || (state.localTargetUrl?'local':''));
        renderTargetOptions(preferred);
        if(preferred) el.compareTargetSelect.value=preferred;
        syncCompareTarget();
        el.worksCompareDialog.showModal();
        requestAnimationFrame(()=>state.compareViewer.refresh());
    }
    function padSequence(value){
        return String(Math.max(1, Number(value) || 1)).padStart(6,'0');
    }
    function workDatePart(work){
        const date = Number(work?.created_at || 0) ? new Date(Number(work.created_at) * 1000) : new Date();
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2,'0');
        const day = String(date.getDate()).padStart(2,'0');
        return `${year}${month}${day}`;
    }
    function extensionFromWork(work){
        const source=String(work?.original_name || work?.url || '').split(/[?#]/)[0];
        const slash=Math.max(source.lastIndexOf('/'),source.lastIndexOf('\\'));
        const dot=source.lastIndexOf('.');
        return dot>slash ? source.slice(dot).toLowerCase() : '.png';
    }
    function workDownloadName(work){
        if(work?.download_name) return String(work.download_name);
        const sequence = work?.download_sequence || (Number(work?.output_index || 0) + 1);
        return `SHIYIN-${padSequence(sequence)}-${workDatePart(work)}${extensionFromWork(work)}`;
    }
    function downloadWork(work){
        if(!work?.url) return;
        const name=workDownloadName(work);
        const direct=/^(blob:|data:)/i.test(work.url);
        const link=document.createElement('a');
        link.href=direct?work.url:`/api/download-output?url=${encodeURIComponent(work.url)}&name=${encodeURIComponent(name)}`;
        link.download=name;
        document.body.appendChild(link);
        link.click();
        link.remove();
    }
    async function downloadAllWorks(){
        const works=downloadableWorks();
        if(!works.length){toast(t('works.noDownloadableWorks'));return;}
        const date = workDatePart({});
        const name = `SHIYIN-全部作品-${date}.zip`;
        const url=`/api/works/download-all?name=${encodeURIComponent(name)}`;
        if(window.showSaveFilePicker){
            try{
                const handle=await window.showSaveFilePicker({
                    suggestedName:name,
                    types:[{description:'ZIP',accept:{'application/zip':['.zip']}}],
                });
                const response=await fetch(url);
                if(!response.ok) throw new Error(await response.text() || t('works.downloadFailed'));
                const writable=await handle.createWritable();
                await writable.write(await response.blob());
                await writable.close();
                toast(t('works.downloadSaved'));
            }catch(error){
                if(error?.name === 'AbortError') return;
                toast(error.message || t('works.downloadFailed'));
            }
            return;
        }
        const link=document.createElement('a');
        link.href=url;
        link.download=name;
        document.body.appendChild(link);
        link.click();
        link.remove();
    }
    async function clearAllWorks(){
        const count = state.works.length;
        if(!count){toast(t('works.noWorksToClear'));return;}
        if(!window.confirm(t('works.clearAllConfirm').replace('{count}', String(count)))) return;
        el.worksClearAll.disabled=true;
        try{
            const result=await fetchJson('/api/works',{method:'DELETE'});
            state.works=[];
            state.kind='';
            if(el.worksCompareDialog.open) closeCompare();
            renderKinds();
            render();
            toast(t('works.clearAllDone').replace('{count}', String(result.deleted_files ?? 0)));
        }catch(error){
            toast(error.message || t('works.clearAllFailed'));
        }finally{
            el.worksClearAll.disabled=!state.works.length;
        }
    }
    function closeCompare(){
        if(state.localBaseUrl){ URL.revokeObjectURL(state.localBaseUrl); state.localBaseUrl=''; }
        if(state.localTargetUrl){ URL.revokeObjectURL(state.localTargetUrl); state.localTargetUrl=''; }
        state.compareWork=null;
        state.compareViewer.exitFullscreen();
        el.worksCompareDialog.close();
    }
    function validImageFile(file){return !!file && (String(file.type||'').startsWith('image/') || /\.(png|jpe?g|webp)$/i.test(file.name||''));}
    function bind(){
        el.worksTabs.addEventListener('click',event=>{const button=event.target.closest('[data-tab]');if(button){state.tab=button.dataset.tab;renderKinds();render();}});
        el.worksSearch.addEventListener('input',()=>{state.search=el.worksSearch.value;render();});
        el.worksKind.addEventListener('change',()=>{state.kind=el.worksKind.value;render();});
        el.worksRefresh.addEventListener('click',loadWorks);
        el.worksQuickCompare.addEventListener('click',()=>openCompare());
        el.worksDownloadAll?.addEventListener('click',downloadAllWorks);
        el.worksClearAll?.addEventListener('click',clearAllWorks);
        el.closeWorksCompare.addEventListener('click',closeCompare);
        el.worksCompareDialog.addEventListener('cancel',event=>{event.preventDefault();closeCompare();});
        el.compareTargetSelect.addEventListener('change',syncCompareTarget);
        el.compareBaseSelect.addEventListener('change',()=>applyComparison());
        el.compareFavorite.addEventListener('click',()=>state.compareWork&&toggleFavorite(state.compareWork.id));
        el.compareTargetFileButton.addEventListener('click',()=>el.compareTargetFile.click());
        el.compareTargetFile.addEventListener('change',event=>{
            const file=event.target.files?.[0];if(!validImageFile(file))return;
            if(state.localTargetUrl)URL.revokeObjectURL(state.localTargetUrl);
            state.localTargetUrl=URL.createObjectURL(file);renderTargetOptions('local');el.compareTargetSelect.value='local';syncCompareTarget();event.target.value='';
        });
        el.compareBaseFileButton.addEventListener('click',()=>el.compareBaseFile.click());
        el.compareBaseFile.addEventListener('change',event=>{
            const file=event.target.files?.[0]; if(!validImageFile(file)) return;
            if(state.localBaseUrl) URL.revokeObjectURL(state.localBaseUrl);
            state.localBaseUrl=URL.createObjectURL(file);
            renderBaseOptions(selectedTarget());el.compareBaseSelect.value='local';applyComparison();event.target.value='';
        });
        window.addEventListener('message',event=>{
            if(event.data?.type==='entity.changed'&&event.data.topic==='history')loadWorks();
            if(event.data?.type==='desktop.download.finished'){
                const path=String(event.data.path || '').trim();
                toast(event.data.success?`${t('works.downloadSaved')}${path?`：${path}`:''}`:t('works.downloadFailed'));
            }
        });
        window.addEventListener('studio-lang-change',()=>{renderKinds();render();if(el.worksCompareDialog.open){renderTargetOptions(state.compareWork?.id || (state.localTargetUrl?'local':''));syncCompareTarget();}});
    }
    async function init(){
        cache();
        state.compareViewer=new window.CompareViewer({root:el.worksCompareStage,before:el.worksBeforeImage,after:el.worksAfterImage,afterClip:el.worksAfterClip,handle:el.worksCompareHandle,zoomLabel:el.worksZoomReset,zoomInButton:el.worksZoomIn,zoomOutButton:el.worksZoomOut,fullscreenButton:el.worksFullscreen});
        bind();
        await loadWorks();
    }
    window.WorksManager={state,loadWorks,openCompare};
    document.addEventListener('DOMContentLoaded',init,{once:true});
})();
