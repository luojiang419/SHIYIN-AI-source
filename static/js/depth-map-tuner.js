(function(){
    'use strict';
    const pageSession=window.StudioPageState?.session('depth-map-tuner');
    let depthBlob=null;

    const RANGES = Object.freeze({
        farPoint:[0,99], nearPoint:[1,100], midtone:[-100,100],
        contrast:[0,300], brightness:[-100,100], smooth:[0,50]
    });
    const DEFAULTS = Object.freeze({farPoint:0,nearPoint:100,midtone:0,contrast:100,brightness:0,smooth:0,invert:false});
    const PRESETS = Object.freeze({
        neutral:{label:'原始中性',values:DEFAULTS},
        portrait:{label:'人像层次',values:{farPoint:4,nearPoint:96,midtone:16,contrast:122,brightness:0,smooth:2,invert:false}},
        soft:{label:'柔和平滑',values:{farPoint:0,nearPoint:100,midtone:28,contrast:82,brightness:5,smooth:8,invert:false}},
        dramatic:{label:'强烈纵深',values:{farPoint:12,nearPoint:88,midtone:-14,contrast:185,brightness:-4,smooth:1,invert:false}},
        cutout:{label:'硬边分层',values:{farPoint:24,nearPoint:76,midtone:-22,contrast:245,brightness:-10,smooth:0,invert:false}}
    });
    const el = Object.fromEntries([
        'depthTunerBack','depthTunerMode','depthInputMeta','depthInputStage','depthInputImage','depthInputEmpty','depthInputFile',
        'depthOutputMeta','depthOutputCanvas','depthOutputEmpty','depthProcessing','depthPresetStrip','depthTunerStatus',
        'depthResetControls','depthExportImage','depthSaveConfig','depthTunerToast'
    ].map(id => [id,document.getElementById(id)]));
    const state = {mode:'person',controls:{...DEFAULTS},file:null,inputUrl:'',depthUrl:'',depthImage:null,busy:false,renderFrame:0,request:0};

    function clamp(value,min,max){ return Math.max(min,Math.min(max,Number(value) || 0)); }
    function normalizeControls(source={},changed=''){
        const next = {};
        Object.entries(RANGES).forEach(([field,[min,max]]) => { next[field] = Math.round(clamp(source[field] ?? DEFAULTS[field],min,max)); });
        next.invert = Boolean(source.invert);
        if(changed === 'farPoint' && next.farPoint >= next.nearPoint) next.nearPoint = Math.min(100,next.farPoint + 1);
        if(changed === 'nearPoint' && next.nearPoint <= next.farPoint) next.farPoint = Math.max(0,next.nearPoint - 1);
        if(next.nearPoint <= next.farPoint) next.nearPoint = Math.min(100,next.farPoint + 1);
        if(next.nearPoint <= next.farPoint) next.farPoint = Math.max(0,next.nearPoint - 1);
        return next;
    }
    function signature(source){ const value=normalizeControls(source); return [value.farPoint,value.nearPoint,value.midtone,value.contrast,value.brightness,value.smooth,value.invert?1:0].join('|'); }
    function formatValue(field,value){
        if(['farPoint','nearPoint','contrast'].includes(field)) return `${value}%`;
        if(field === 'smooth') return value ? `${value} 级` : '关闭';
        return `${value > 0 ? '+' : ''}${value}`;
    }
    function toast(message,error=false){
        el.depthTunerToast.textContent = message;
        el.depthTunerToast.classList.toggle('error',error);
        el.depthTunerToast.classList.add('show');
        clearTimeout(toast.timer);
        toast.timer = setTimeout(() => el.depthTunerToast.classList.remove('show'),3000);
    }
    async function requestJson(url,init={}){
        const response = await fetch(url,init);
        const data = await response.json().catch(() => ({}));
        if(!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
        return data;
    }
    function syncMode(){
        el.depthTunerMode.textContent = state.mode === 'professional' ? '专业模式 · 完整画面' : '人物模式 · 人物区域';
        el.depthTunerMode.closest('.depth-tuner-mode').dataset.mode = state.mode;
    }
    function syncControls(){
        const active = Object.entries(PRESETS).find(([,preset]) => signature(preset.values) === signature(state.controls))?.[0] || '';
        document.querySelectorAll('[data-depth-field]').forEach(control => {
            const field = control.dataset.depthField;
            if(control.type === 'checkbox'){ control.checked=Boolean(state.controls[field]); return; }
            control.value = String(state.controls[field]);
            control.closest('[data-depth-control]')?.querySelector('output')?.replaceChildren(formatValue(field,state.controls[field]));
        });
        el.depthPresetStrip.querySelectorAll('[data-depth-preset]').forEach(button => button.classList.toggle('active',button.dataset.depthPreset === active));
    }
    function setControls(patch,changed=''){
        state.controls = normalizeControls({...state.controls,...patch},changed);
        syncControls();
        schedulePreview();
    }
    function depthLut(){
        const c=state.controls,lut=new Uint8ClampedArray(256),far=c.farPoint/100,near=c.nearPoint/100,contrast=c.contrast/100,brightness=c.brightness/100,gamma=Math.pow(2,-c.midtone/50);
        for(let index=0;index<256;index++){
            let value=clamp((index/255-far)/Math.max(.01,near-far),0,1);
            value=Math.pow(value,gamma); value=(value-.5)*contrast+.5+brightness; value=clamp(value,0,1);
            if(c.invert) value=1-value; lut[index]=Math.round(value*255);
        }
        return lut;
    }
    function renderDepth(target,maxEdge=0){
        if(!state.depthImage) return null;
        const sourceWidth=state.depthImage.naturalWidth,sourceHeight=state.depthImage.naturalHeight;
        const scale=maxEdge?Math.min(1,maxEdge/Math.max(sourceWidth,sourceHeight)):1;
        const width=Math.max(1,Math.round(sourceWidth*scale)),height=Math.max(1,Math.round(sourceHeight*scale));
        const work=document.createElement('canvas');work.width=width;work.height=height;
        const context=work.getContext('2d',{willReadFrequently:true});context.drawImage(state.depthImage,0,0,width,height);
        const pixels=context.getImageData(0,0,width,height),lut=depthLut();
        for(let index=0;index<pixels.data.length;index+=4){ const gray=Math.round((pixels.data[index]+pixels.data[index+1]+pixels.data[index+2])/3),mapped=lut[gray]; pixels.data[index]=mapped;pixels.data[index+1]=mapped;pixels.data[index+2]=mapped; }
        context.putImageData(pixels,0,0);target.width=width;target.height=height;
        const output=target.getContext('2d');output.fillStyle=state.controls.invert?'#fff':'#000';output.fillRect(0,0,width,height);
        if(state.controls.smooth>0) output.filter=`blur(${Math.max(.2,state.controls.smooth*width/1000).toFixed(2)}px)`;
        output.drawImage(work,0,0);output.filter='none';return target;
    }
    function schedulePreview(){
        if(!state.depthImage) return;
        cancelAnimationFrame(state.renderFrame);
        state.renderFrame=requestAnimationFrame(() => {
            state.renderFrame=0;renderDepth(el.depthOutputCanvas,1400);el.depthOutputCanvas.hidden=false;el.depthOutputEmpty.hidden=true;el.depthExportImage.disabled=false;
            el.depthTunerStatus.textContent='实时预览已更新，点击“保存配置”应用到全部深度图功能。';
        });
    }
    function setBusy(busy){ state.busy=busy;el.depthProcessing.hidden=!busy;el.depthInputStage.disabled=busy;el.depthSaveConfig.disabled=busy;el.depthExportImage.disabled=busy||!state.depthImage; }
    function loadImage(url){ return new Promise((resolve,reject) => { const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('图片解码失败'));image.src=url; }); }
    function clearDepth(){ depthBlob=null; if(state.depthUrl) URL.revokeObjectURL(state.depthUrl);state.depthUrl='';state.depthImage=null;el.depthOutputCanvas.hidden=true;el.depthOutputEmpty.hidden=false;el.depthExportImage.disabled=true;el.depthOutputMeta.textContent='8-BIT PNG'; }
    async function processFile(file){
        if(!file || state.busy) return;
        const request=++state.request;
        if(file.size>25*1024*1024){ toast('输入图片不能超过 25MB',true);return; }
        if(state.inputUrl) URL.revokeObjectURL(state.inputUrl);
        state.file=file;state.inputUrl=URL.createObjectURL(file);el.depthInputImage.src=state.inputUrl;el.depthInputImage.hidden=false;el.depthInputEmpty.hidden=true;el.depthInputMeta.textContent=`${file.name} · ${(file.size/1024/1024).toFixed(1)}MB`;clearDepth();setBusy(true);
        el.depthTunerStatus.textContent=state.mode==='professional'?'正在提取完整画面深度…':'正在提取人物深度…';
        try {
            const form=new FormData();form.append('file',file,file.name);if(state.mode==='person') form.append('bit_depth','8');
            const endpoint=state.mode==='professional'?'/api/depth/estimate':'/api/person-depth/estimate';
            const response=await fetch(endpoint,{method:'POST',body:form});
            if(!response.ok){ const data=await response.json().catch(()=>({}));throw new Error(data.detail||'深度图提取失败'); }
            if(request!==state.request)return;
            const blob=await response.blob();depthBlob=blob;state.depthUrl=URL.createObjectURL(blob);state.depthImage=await loadImage(state.depthUrl);
            const width=Number(response.headers.get(state.mode==='professional'?'X-Depth-Width':'X-Person-Depth-Width'))||state.depthImage.naturalWidth;
            const height=Number(response.headers.get(state.mode==='professional'?'X-Depth-Height':'X-Person-Depth-Height'))||state.depthImage.naturalHeight;
            el.depthOutputMeta.textContent=`${width} × ${height} · 8-BIT PNG`;schedulePreview();toast('深度提取完成，可实时调整参数');
        } catch(error){ if(request===state.request){clearDepth();el.depthTunerStatus.textContent=error.message||'深度图提取失败';toast(el.depthTunerStatus.textContent,true);} }
        finally{ if(request===state.request){setBusy(false);pageSession?.checkpoint();} }
    }
    async function loadSettings(){
        const valid=pageSession?.guard() || (()=>true);
        try {
            const data=await requestJson('/api/app-settings',{cache:'no-store'});
            if(!valid() || pageSession?.restored) return;
            state.mode=data.depth_map_mode==='professional'?'professional':'person';state.controls=normalizeControls(data.depth_map_controls||DEFAULTS);syncMode();syncControls();
            el.depthTunerStatus.textContent=state.mode==='professional'?'专业模式已就绪：输入图片后提取完整画面深度。':'人物模式已就绪：输入图片后仅提取人物深度。';
        } catch(error){ el.depthTunerStatus.textContent=`设置读取失败：${error.message}`;toast(el.depthTunerStatus.textContent,true); }
    }
    async function saveConfig(){
        const valid=pageSession?.guard() || (()=>true);
        if(state.busy)return;el.depthSaveConfig.disabled=true;el.depthTunerStatus.textContent='正在保存共享配置…';
        try {
            const data=await requestJson('/api/app-settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({depth_map_mode:state.mode,depth_map_controls:state.controls})});
            if(valid()){state.controls=normalizeControls(data.depth_map_controls||state.controls);syncControls();}
            pageSession?.checkpoint();
            const message={type:'depth-map-settings:changed',mode:state.mode,controls:{...state.controls},updatedAt:Date.now()};
            try{window.parent?.postMessage(message,location.origin);}catch(error){}
            el.depthTunerStatus.textContent='配置已保存，并已通知所有深度图节点立即生效。';toast('深度图配置已保存');
        } catch(error){el.depthTunerStatus.textContent=`保存失败：${error.message}`;toast(el.depthTunerStatus.textContent,true);}
        finally{el.depthSaveConfig.disabled=false;}
    }
    function exportDepth(){
        if(!state.depthImage)return;const canvas=document.createElement('canvas');renderDepth(canvas);
        canvas.toBlob(blob=>{if(!blob)return;const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`${String(state.file?.name||'depth-map').replace(/\.[^.]+$/,'')}-depth.png`;link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1200);},'image/png');
    }
    function initialize(){
        Object.entries(PRESETS).forEach(([key,preset])=>{const button=document.createElement('button');button.type='button';button.dataset.depthPreset=key;button.textContent=preset.label;button.onclick=()=>setControls(preset.values);el.depthPresetStrip.appendChild(button);});
        document.querySelectorAll('[data-depth-field]').forEach(control=>control.addEventListener(control.type==='checkbox'?'change':'input',()=>setControls({[control.dataset.depthField]:control.type==='checkbox'?control.checked:Number(control.value)},control.dataset.depthField)));
        el.depthInputStage.onclick=()=>el.depthInputFile.click();el.depthInputFile.onchange=()=>{processFile(el.depthInputFile.files?.[0]);el.depthInputFile.value='';};
        el.depthResetControls.onclick=()=>setControls(DEFAULTS);el.depthExportImage.onclick=exportDepth;el.depthSaveConfig.onclick=saveConfig;
        el.depthTunerBack.onclick=()=>{if(window.parent&&window.parent!==window)window.parent.postMessage({type:'studio-depth-map-tuner-back'},location.origin);else location.href='/static/app-settings.html';};
        window.addEventListener('message',event=>{if(event.origin&&event.origin!==location.origin)return;if(event.data?.type==='studio-theme'){document.documentElement.classList.toggle('studio-theme-dark',event.data.theme==='dark');document.documentElement.classList.toggle('studio-theme-pure-white',event.data.theme==='pure-white');}});
        pageSession?.watch(()=>({mode:state.mode,controls:state.controls,file:state.file,depthBlob,outputMeta:el.depthOutputMeta.textContent}));
        syncControls();
        void (async()=>{
            await pageSession?.restore(async saved=>{
                const valid=pageSession.guard();
                const inputUrl=saved.file?URL.createObjectURL(saved.file):'';
                const depthUrl=saved.depthBlob?URL.createObjectURL(saved.depthBlob):'';
                const depthImage=depthUrl?await loadImage(depthUrl):null;
                if(!valid()){if(inputUrl)URL.revokeObjectURL(inputUrl);if(depthUrl)URL.revokeObjectURL(depthUrl);return;}
                Object.assign(state,{mode:saved.mode || 'person',controls:normalizeControls(saved.controls),file:saved.file || null,inputUrl,depthUrl,depthImage});
                depthBlob=saved.depthBlob || null;
                if(inputUrl){el.depthInputImage.src=inputUrl;el.depthInputImage.hidden=false;el.depthInputEmpty.hidden=true;el.depthInputMeta.textContent=saved.file.name;}
                el.depthOutputMeta.textContent=saved.outputMeta || '';
                syncMode();syncControls();schedulePreview();
            });
            void loadSettings();
        })();
    }
    initialize();
})();
