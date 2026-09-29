(function(global){
    'use strict';

    const MAX_REGIONS = 4;
    const MIN_SIZE = .01;
    const ALIGNMENT_STORAGE_KEY = 'studio_pose_calibration_alignments_v1';
    const ui = {};
    let mode = 'draw';
    let selectedId = '';
    let nextId = 1;
    let boxesVisible = true;
    let gesture = null;
    let tab = 'source';
    let viewer = null;
    let nativeCrop = null;
    let reviewContext = null;
    let lastReviewRegionId = '';
    let customResultUrl = '';
    let alignmentValues = loadAlignments();

    const studio = () => global.EcommerceStudio;
    const state = () => studio()?.state;
    const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const taskId = task => String(task?.id || task?.task_id || 'task');

    function loadAlignments(){
        try {
            const value = JSON.parse(localStorage.getItem(ALIGNMENT_STORAGE_KEY) || '{}');
            return value && typeof value === 'object' ? value : {};
        } catch(error) { return {}; }
    }

    function saveAlignments(){
        try {
            const entries = Object.entries(alignmentValues);
            if(entries.length > 400) alignmentValues = Object.fromEntries(entries.slice(-400));
            localStorage.setItem(ALIGNMENT_STORAGE_KEY, JSON.stringify(alignmentValues));
        } catch(error) {}
    }

    function poseOptions(){
        const current = state();
        if(!current) return {};
        current.options.pose_transfer = current.options.pose_transfer || {};
        return current.options.pose_transfer;
    }

    function sourceInput(){ return state()?.workspaces?.pose_transfer?.inputs?.source || state()?.inputs?.source || null; }

    function cleanRegions(values){
        if(!Array.isArray(values)) return [];
        return values.slice(0, MAX_REGIONS).map((item,index) => ({
            id:String(item?.id || index + 1),
            name:String(item?.name || `重点区域 ${index + 1}`).slice(0,32),
            x:clamp(Number(item?.x) || 0,0,1), y:clamp(Number(item?.y) || 0,0,1),
            w:clamp(Number(item?.w) || MIN_SIZE,MIN_SIZE,1), h:clamp(Number(item?.h) || MIN_SIZE,MIN_SIZE,1),
        })).map(item => ({...item,w:Math.min(item.w,1-item.x),h:Math.min(item.h,1-item.y)}));
    }

    function currentCalibration(){
        const source = sourceInput();
        const saved = poseOptions().calibration;
        if(!source?.url || !saved || saved.source_url !== source.url) return {source_url:source?.url || '',regions:[]};
        return {source_url:source.url,regions:cleanRegions(saved.regions)};
    }

    function reconcileSource(asset, notify=false){
        const options = poseOptions();
        const saved = options.calibration;
        const nextUrl = String(asset?.url || '');
        if(!saved || saved.source_url === nextUrl) return;
        const hadRegions = Array.isArray(saved.regions) && saved.regions.length > 0;
        delete options.calibration;
        studio()?.persistSettings?.();
        if(notify && hadRegions) studio()?.showToast?.('已更换保留款原图，旧图标定框已清除。');
    }

    function commitRegions(message=''){
        const source = sourceInput();
        if(!source?.url) return;
        const regions = activeSourceRegions();
        if(regions.length) poseOptions().calibration = {version:1,source_url:source.url,regions:regions.map(item => ({...item}))};
        else delete poseOptions().calibration;
        studio()?.persistSettings?.();
        if(message && ui.status) ui.status.textContent = message;
    }

    function activeSourceRegions(){
        if(!reviewContext || tab === 'source') return cleanRegions(poseOptions().calibration?.regions);
        return cleanRegions(reviewContext.regions);
    }

    function regionById(id, values=activeSourceRegions()){ return values.find(item => item.id === String(id)); }

    function setSourceRegions(regions){
        const source = sourceInput();
        if(!source?.url) return;
        poseOptions().calibration = {version:1,source_url:source.url,regions:cleanRegions(regions)};
    }

    function cardHtml(asset){
        reconcileSource(asset, false);
        const calibration = asset?.url && poseOptions().calibration?.source_url === asset.url ? poseOptions().calibration : null;
        const count = Array.isArray(calibration?.regions) ? calibration.regions.length : 0;
        return `<div class="ec-pose-calibration-card"><span>${count ? `已标定 ${count} 处` : '未标定重点区域'}</span><button type="button" data-pose-calibrate>${count ? '调整标定' : '标定'}</button></div>`;
    }

    function bindSlot(slot, role){
        if(role !== 'source') return;
        slot.querySelector('[data-pose-calibrate]')?.addEventListener('click', event => {
            event.preventDefault(); event.stopPropagation(); openSource();
        });
    }

    function removeSource(){
        const options = poseOptions();
        if(options.calibration) {
            delete options.calibration;
            studio()?.persistSettings?.();
        }
    }

    function point(event){
        const rect = ui.sourceImage.getBoundingClientRect();
        return {x:clamp((event.clientX-rect.left)/Math.max(1,rect.width),0,1),y:clamp((event.clientY-rect.top)/Math.max(1,rect.height),0,1)};
    }

    function setMode(next){
        mode = next === 'select' ? 'select' : 'draw';
        document.querySelectorAll('[data-pose-calibration-mode]').forEach(button => button.classList.toggle('active',button.dataset.poseCalibrationMode === mode));
        if(ui.status) ui.status.textContent = mode === 'draw' ? '在原图上连续拖动绘制选区；完成一个后可继续绘制。' : '拖动框移动，拖动右下角调整大小；点击标题可改名。';
    }

    function renderBoxes(){
        if(!ui.boxes) return;
        const regions = activeSourceRegions();
        ui.boxes.innerHTML = tab === 'source' ? regions.map((item,index) => `<div class="ec-pose-calibration-box ${selectedId === item.id ? 'selected':''}" data-region-id="${escapeHtml(item.id)}" style="left:${item.x*100}%;top:${item.y*100}%;width:${item.w*100}%;height:${item.h*100}%;display:${boxesVisible?'block':'none'}"><span class="badge" role="button" tabindex="0" title="点击修改名称">${String(index+1).padStart(2,'0')}　${escapeHtml(item.name)}</span><i class="handle"></i></div>`).join('') : '';
    }

    function renderList(){
        if(!ui.list) return;
        const regions = activeSourceRegions();
        ui.count.textContent = String(regions.length);
        ui.list.innerHTML = regions.length ? regions.map((item,index) => `<div class="ec-pose-calibration-item ${selectedId === item.id ? 'active':''}" data-region-item="${escapeHtml(item.id)}"><div><small>区域 ${String(index+1).padStart(2,'0')}</small><button type="button" data-region-delete="${escapeHtml(item.id)}">删除</button></div><input maxlength="32" value="${escapeHtml(item.name)}" aria-label="区域名称"><small>${Math.round(item.w*100)}% × ${Math.round(item.h*100)}% · 原图区域</small></div>`).join('') : '<div class="ec-pose-calibration-empty">还没有标定框。<br>在原图上拖动，圈出要重点保持的细节。</div>';
        ui.list.querySelectorAll('[data-region-item]').forEach(item => {
            item.addEventListener('click', event => {
                if(event.target.matches('button,input')) return;
                selectedId = item.dataset.regionItem; renderAll();
            });
            const input = item.querySelector('input');
            input?.addEventListener('input', () => {
                const regions = activeSourceRegions(); const target = regionById(item.dataset.regionItem,regions);
                if(!target || tab !== 'source') return;
                target.name = input.value.slice(0,32) || target.name;
                setSourceRegions(regions); studio()?.persistSettings?.();
            });
            input?.addEventListener('change', () => {
                const regions = activeSourceRegions(); const target = regionById(item.dataset.regionItem,regions);
                if(!target || tab !== 'source') return;
                target.name = input.value.trim() || target.name;
                setSourceRegions(regions); commitRegions('标定名称已更新。'); renderAll();
            });
        });
        ui.list.querySelectorAll('[data-region-delete]').forEach(button => button.addEventListener('click', event => {
            event.stopPropagation();
            if(tab !== 'source') return;
            const regions = activeSourceRegions().filter(item => item.id !== button.dataset.regionDelete);
            if(selectedId === button.dataset.regionDelete) selectedId = regions[0]?.id || '';
            setSourceRegions(regions); commitRegions('已删除标定区域。'); renderAll();
        }));
        document.querySelectorAll('[data-pose-review-step]').forEach(button => { button.disabled = regions.length < 2; });
    }

    function renderAll(){ renderBoxes(); renderList(); if(tab === 'review') updateReviewRegion(); }

    function editName(id){
        if(tab !== 'source') return;
        const regions = activeSourceRegions(); const target = regionById(id,regions); if(!target) return;
        selectedId = target.id; renderBoxes();
        const badge = ui.boxes.querySelector(`[data-region-id="${CSS.escape(target.id)}"] .badge`); if(!badge) return;
        const original = target.name; badge.textContent = '';
        const input = document.createElement('input'); input.value = original; input.maxLength = 32; badge.appendChild(input);
        let finished = false;
        const finish = save => {
            if(finished) return; finished = true;
            if(save) target.name = input.value.trim() || original;
            setSourceRegions(regions); commitRegions(save ? '标定名称已更新。' : '已取消修改名称。'); renderAll();
        };
        input.addEventListener('keydown', event => { if(event.key === 'Enter'){event.preventDefault();finish(true);} else if(event.key === 'Escape'){event.preventDefault();finish(false);} event.stopPropagation(); });
        input.addEventListener('blur',()=>finish(true)); input.focus(); input.select();
    }

    function beginGesture(event){
        if(gesture || tab !== 'source' || !boxesVisible || event.target.matches('.badge input')) return;
        const badge = event.target.closest('.badge');
        if(badge){ event.preventDefault(); editName(badge.closest('.ec-pose-calibration-box').dataset.regionId); return; }
        const p = point(event); const box = event.target.closest('.ec-pose-calibration-box'); const regions = activeSourceRegions();
        if(box){
            const target = regionById(box.dataset.regionId,regions); if(!target) return;
            selectedId = target.id; gesture = {type:event.target.closest('.handle')?'resize':'move',id:target.id,start:p,initial:{...target},regions};
        } else if(mode === 'draw') {
            if(regions.length >= MAX_REGIONS){ studio()?.showToast?.(`最多标定 ${MAX_REGIONS} 个区域`,true); return; }
            const id = `region-${Date.now().toString(36)}-${nextId++}`;
            const target = {id,name:`重点区域 ${regions.length+1}`,x:p.x,y:p.y,w:.001,h:.001};
            regions.push(target); selectedId = id; gesture = {type:'draw',id,start:p,regions}; setSourceRegions(regions);
        } else { selectedId=''; renderAll(); return; }
        ui.art.setPointerCapture(event.pointerId); renderAll();
    }

    function moveGesture(event){
        if(!gesture) return;
        const p=point(event), target=regionById(gesture.id,gesture.regions); if(!target) return;
        if(gesture.type === 'draw'){
            target.x=Math.min(p.x,gesture.start.x); target.y=Math.min(p.y,gesture.start.y);
            target.w=Math.max(.001,Math.abs(p.x-gesture.start.x)); target.h=Math.max(.001,Math.abs(p.y-gesture.start.y));
        } else if(gesture.type === 'move'){
            target.x=clamp(gesture.initial.x+p.x-gesture.start.x,0,1-target.w); target.y=clamp(gesture.initial.y+p.y-gesture.start.y,0,1-target.h);
        } else {
            target.w=clamp(gesture.initial.w+p.x-gesture.start.x,MIN_SIZE,1-target.x); target.h=clamp(gesture.initial.h+p.y-gesture.start.y,MIN_SIZE,1-target.y);
        }
        setSourceRegions(gesture.regions); renderBoxes();
    }

    function endGesture(){
        if(!gesture) return;
        const regions = gesture.regions; const target = regionById(gesture.id,regions);
        if(gesture.type === 'draw' && target && (target.w < MIN_SIZE || target.h < MIN_SIZE)){
            const index=regions.indexOf(target); if(index>=0)regions.splice(index,1); selectedId=regions[0]?.id||'';
            ui.status.textContent='选区过小，未保存；请拖出至少占原图 1% 的区域。';
        } else ui.status.textContent='标定已保存；可继续新增或调整。';
        gesture=null; setSourceRegions(regions); commitRegions(); renderAll();
    }

    function taskCalibration(task){
        const value = task?.options?.calibration || task?.request?.options?.calibration || task?.result?.params?.options?.calibration;
        if(!value || !Array.isArray(value.regions)) return null;
        return {source_url:String(value.source_url||''),regions:cleanRegions(value.regions)};
    }

    function taskSource(task){
        const refs=task?.inputs || task?.request?.inputs || task?.result?.inputs || [];
        return refs.find(item => item?.url && (item.role === 'source' || item.reference_type === 'source'))?.url || taskCalibration(task)?.source_url || '';
    }

    function taskResult(task,index){ return task?.result?.images?.[index] || task?.result?.images?.[0] || ''; }

    function alignmentKey(region){ return `${reviewContext?.key || 'review'}:${region.id}`; }
    function alignmentFor(region){
        const fallback={x:(region.x+region.w/2)*100,y:(region.y+region.h/2)*100};
        const saved=alignmentValues[alignmentKey(region)];
        return saved && Number.isFinite(Number(saved.x)) && Number.isFinite(Number(saved.y)) ? {x:Number(saved.x),y:Number(saved.y)} : fallback;
    }

    function positionNativeCrop(){
        if(!nativeCrop || !ui.compare.clientWidth) return;
        const left=Math.round((ui.compare.clientWidth-nativeCrop.w)/2),top=Math.round((ui.compare.clientHeight-nativeCrop.h)/2);
        [ui.before,ui.after].forEach(crop=>{crop.style.width=`${nativeCrop.w}px`;crop.style.height=`${nativeCrop.h}px`;crop.style.left=`${left}px`;crop.style.top=`${top}px`;});
        [[ui.beforeImage,nativeCrop.sx,nativeCrop.sy],[ui.afterImage,nativeCrop.rx,nativeCrop.ry]].forEach(([image,x,y])=>{
            image.style.width=`${image.naturalWidth}px`;image.style.height=`${image.naturalHeight}px`;image.style.left=`-${x}px`;image.style.top=`-${y}px`;
        });
    }

    function updateReviewRegion(){
        if(tab !== 'review') return;
        const regions=activeSourceRegions();
        if(!reviewContext?.sourceUrl || !reviewContext?.resultUrl || !regions.length){
            nativeCrop=null;ui.compare.classList.add('hidden');ui.reviewEmpty.classList.remove('hidden');
            ui.reviewEmpty.textContent=!regions.length?'当前任务没有标定区域':!reviewContext?.resultUrl?'当前任务还没有可核对的成品':'缺少原图，无法核对';ui.alignment.classList.add('hidden');return;
        }
        if(!ui.beforeImage.naturalWidth || !ui.afterImage.naturalWidth){ui.compare.classList.add('hidden');ui.reviewEmpty.classList.remove('hidden');ui.reviewEmpty.textContent='正在读取原图与成品的原始像素…';return;}
        if(!regionById(selectedId,regions)) selectedId=regions[0].id;
        const region=regionById(selectedId,regions),sw=ui.beforeImage.naturalWidth,sh=ui.beforeImage.naturalHeight,rw=ui.afterImage.naturalWidth,rh=ui.afterImage.naturalHeight;
        const width=Math.max(1,Math.min(Math.round(region.w*sw),rw)),height=Math.max(1,Math.min(Math.round(region.h*sh),rh));
        const sx=clamp(Math.round((region.x+region.w/2)*sw-width/2),0,sw-width),sy=clamp(Math.round((region.y+region.h/2)*sh-height/2),0,sh-height);
        const center=alignmentFor(region),rx=clamp(Math.round(center.x/100*rw-width/2),0,rw-width),ry=clamp(Math.round(center.y/100*rh-height/2),0,rh-height);
        nativeCrop={w:width,h:height,sx,sy,rx,ry};
        ui.reviewTitle.textContent=`${region.name}`;ui.reviewPixels.textContent=`原始像素 100% · ${width} × ${height} px`;
        ui.resultX.value=String(Math.round(center.x));ui.resultY.value=String(Math.round(center.y));ui.resultX.nextElementSibling.textContent=`${Math.round(center.x)}%`;ui.resultY.nextElementSibling.textContent=`${Math.round(center.y)}%`;
        ui.alignment.classList.remove('hidden');ui.compare.classList.remove('hidden');ui.reviewEmpty.classList.add('hidden');
        if(lastReviewRegionId !== region.id){viewer?.reset();lastReviewRegionId=region.id;}
        positionNativeCrop();viewer?.refresh();
    }

    function setTab(next){
        tab=next==='review'?'review':'source';
        document.querySelectorAll('[data-pose-calibration-tab]').forEach(button=>{
            const active=button.dataset.poseCalibrationTab===tab;
            button.classList.toggle('active',active);button.setAttribute('aria-selected',active?'true':'false');
        });
        ui.art.classList.toggle('hidden',tab==='review');ui.reviewStage.classList.toggle('hidden',tab!=='review');
        document.querySelectorAll('[data-pose-calibration-mode],[data-pose-calibration-toggle]').forEach(button=>button.classList.toggle('hidden',tab==='review'));
        ui.stageTitle.textContent=tab==='review'?'标定细节 · 成品像素核对':'保留款原图 · 重点区域';
        if(tab==='review'){
            if(!reviewContext) setReviewFromTask(state()?.currentTask,state()?.selectedOutput||0);
            if(!reviewContext){
                const calibration=currentCalibration();
                if(calibration.regions.length){
                    reviewContext={task:null,index:0,key:`custom:${Date.now()}`,regions:calibration.regions,sourceUrl:calibration.source_url,resultUrl:''};
                    ui.beforeImage.src=reviewContext.sourceUrl;
                }
            }
            selectedId=reviewContext?.regions?.[0]?.id||selectedId; requestAnimationFrame(()=>{renderAll();updateReviewRegion();});
        } else {
            reviewContext=null; const calibration=currentCalibration();selectedId=calibration.regions[0]?.id||'';renderAll();
        }
    }

    function setReviewFromTask(task,index){
        const calibration=taskCalibration(task); const resultUrl=taskResult(task,index);
        reviewContext=calibration?{task,index,key:`${taskId(task)}:${index}`,regions:calibration.regions,sourceUrl:taskSource(task),resultUrl}:null;
        if(reviewContext){ui.beforeImage.src=reviewContext.sourceUrl;ui.afterImage.src=reviewContext.resultUrl;}
        lastReviewRegionId='';nativeCrop=null;
    }

    function openDialog(){ if(!ui.dialog.open) ui.dialog.showModal(); }
    function openSource(){
        const source=sourceInput();if(!source?.url){studio()?.showToast?.('请先上传保留款原图',true);return;}
        reconcileSource(source,true);reviewContext=null;ui.sourceImage.src=source.url;selectedId=currentCalibration().regions[0]?.id||'';boxesVisible=true;openDialog();setTab('source');setMode(currentCalibration().regions.length?'select':'draw');
    }
    function openReview(task=state()?.currentTask,index=state()?.selectedOutput||0){
        const calibration=taskCalibration(task);if(!calibration?.regions?.length){studio()?.showToast?.('当前成品没有可核对的标定区域',true);return;}
        setReviewFromTask(task,index);selectedId=calibration.regions[0].id;openDialog();setTab('review');
    }

    function syncResult(task){
        if(!ui.reviewButton) return;
        const visible=task?.operation==='pose_transfer' && Boolean(taskCalibration(task)?.regions?.length) && Boolean(task?.result?.images?.length);
        ui.reviewButton.classList.toggle('hidden',!visible);
    }

    function init(){
        const ids={dialog:'poseCalibrationDialog',close:'poseCalibrationClose',sourceImage:'poseCalibrationSourceImage',boxes:'poseCalibrationBoxes',art:'poseCalibrationArt',stageTitle:'poseCalibrationStageTitle',status:'poseCalibrationStatus',size:'poseCalibrationSize',count:'poseCalibrationCount',list:'poseCalibrationList',reviewStage:'poseCalibrationReviewStage',compare:'poseCalibrationCompare',before:'poseCalibrationBefore',after:'poseCalibrationAfter',afterClip:'poseCalibrationAfterClip',beforeImage:'poseCalibrationBeforeImage',afterImage:'poseCalibrationAfterImage',handle:'poseCalibrationHandle',reviewEmpty:'poseCalibrationReviewEmpty',reviewTitle:'poseCalibrationReviewTitle',reviewPixels:'poseCalibrationReviewPixels',alignment:'poseCalibrationAlignment',resultX:'poseCalibrationResultX',resultY:'poseCalibrationResultY',reviewReset:'poseCalibrationReviewReset',customResult:'poseCalibrationCustomResult',resultFile:'poseCalibrationResultFile',reviewButton:'poseCalibrationReview'};
        Object.entries(ids).forEach(([key,id])=>ui[key]=document.getElementById(id));
        if(!ui.dialog) return;
        ui.close.addEventListener('click',()=>{ui.dialog.close();studio()?.renderInputs?.();});
        ui.dialog.addEventListener('cancel',()=>studio()?.renderInputs?.());
        document.querySelectorAll('[data-pose-calibration-tab]').forEach(button=>button.addEventListener('click',()=>setTab(button.dataset.poseCalibrationTab)));
        document.querySelectorAll('[data-pose-calibration-mode]').forEach(button=>button.addEventListener('click',()=>setMode(button.dataset.poseCalibrationMode)));
        document.querySelector('[data-pose-calibration-toggle]')?.addEventListener('click',event=>{boxesVisible=!boxesVisible;event.currentTarget.textContent=boxesVisible?'◉ 隐藏框':'◉ 显示框';renderBoxes();});
        document.querySelector('[data-pose-calibration-add]')?.addEventListener('click',()=>{setTab('source');setMode('draw');boxesVisible=true;ui.status.textContent='在原图上拖动，新增标定区域。';});
        document.querySelector('[data-pose-calibration-clear]')?.addEventListener('click',()=>{if(tab!=='source')return;setSourceRegions([]);selectedId='';commitRegions('已清空当前原图的全部标定区域。');renderAll();});
        ui.art.addEventListener('pointerdown',beginGesture);ui.art.addEventListener('pointermove',moveGesture);ui.art.addEventListener('pointerup',endGesture);ui.art.addEventListener('pointercancel',endGesture);
        ui.art.addEventListener('keydown',event=>{const badge=event.target.closest('.badge');if(badge&&(event.key==='Enter'||event.key===' ')){event.preventDefault();editName(badge.closest('.ec-pose-calibration-box').dataset.regionId);}});
        ui.sourceImage.addEventListener('load',()=>{ui.size.textContent=`原图 ${ui.sourceImage.naturalWidth} × ${ui.sourceImage.naturalHeight} px`;});
        ui.beforeImage.addEventListener('load',updateReviewRegion);ui.afterImage.addEventListener('load',updateReviewRegion);
        const updateAlignment=()=>{const region=regionById(selectedId,activeSourceRegions());if(!region)return;alignmentValues[alignmentKey(region)]={x:Number(ui.resultX.value),y:Number(ui.resultY.value)};saveAlignments();updateReviewRegion();};
        ui.resultX.addEventListener('input',updateAlignment);ui.resultY.addEventListener('input',updateAlignment);
        document.querySelectorAll('[data-pose-review-step]').forEach(button=>button.addEventListener('click',()=>{const regions=activeSourceRegions();if(!regions.length)return;const current=Math.max(0,regions.findIndex(item=>item.id===selectedId));selectedId=regions[(current+Number(button.dataset.poseReviewStep)+regions.length)%regions.length].id;renderAll();}));
        ui.reviewReset.addEventListener('click',()=>{viewer?.reset();positionNativeCrop();});
        ui.customResult.addEventListener('click',()=>ui.resultFile.click());
        ui.resultFile.addEventListener('change',event=>{const file=event.target.files?.[0];if(!file)return;if(customResultUrl)URL.revokeObjectURL(customResultUrl);customResultUrl=URL.createObjectURL(file);if(reviewContext){reviewContext={...reviewContext,key:`custom:${Date.now()}`,resultUrl:customResultUrl};ui.afterImage.src=customResultUrl;lastReviewRegionId='';}});
        ui.reviewButton?.addEventListener('click',()=>openReview());
        if(global.CompareViewer){viewer=new global.CompareViewer({root:ui.compare,before:ui.before,after:ui.after,afterClip:ui.afterClip,handle:ui.handle,divider:50});const refresh=viewer.refresh.bind(viewer);viewer.refresh=()=>{refresh();positionNativeCrop();};}
        global.addEventListener('resize',()=>viewer?.refresh());
    }

    global.PoseTransferCalibration={cardHtml,bindSlot,removeSource,reconcileSource,openSource,openReview,syncResult,taskCalibration};
    document.addEventListener('DOMContentLoaded',init,{once:true});
})(window);
