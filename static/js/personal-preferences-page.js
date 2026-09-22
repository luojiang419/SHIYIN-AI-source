(async function(){
    'use strict';
    const $ = id => document.getElementById(id);
    const api = window.PersonalPreferences;
    let draft = {}, providers = [], selected = {};
    const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const status = (message,error=false) => { $('preferenceStatus').textContent=message; $('preferenceStatus').classList.toggle('error',error); };
    const list = kind => providers.filter(p => p.enabled !== false && (kind !== 'image' || p.image_generation_ready !== false) && p[`${kind}_models`]?.length);
    function options(items,value){ return items.map(item => { const [id,label]=Array.isArray(item)?item:[item,item]; return `<option value="${escape(id)}" ${String(id)===String(value)?'selected':''}>${escape(label)}</option>`; }).join(''); }
    function select(label,key,items,value){ return `<label>${label}<select data-field="${key}">${options(items,value)}</select></label>`; }
    function render(kind){
        const choices=list(kind), root=$(`${kind}Settings`);
        if(!choices.length){ root.innerHTML='<p class="app-settings-note">暂无可用平台，请先配置对应的 API 平台。</p>'; return; }
        const defaultKey=kind==='image'?'defaultImageProvider':'defaultVideoProvider';
        const provider=choices.find(p=>p.id===selected[kind]) || choices.find(p=>p.id===draft[defaultKey]) || choices[0];
        selected[kind]=provider.id;
        draft[kind] ||= {};
        const h3=provider.id==='minimax-h3', youyun=provider.id==='youyun-h3', kling=provider.id.includes('kling');
        const baseline=kind==='image'?{ratio:'wide',resolution:'2k',quality:'auto'}:{duration:5,aspectRatio:'16:9',resolution:h3?'0.2MP 16:9 - 608x352':youyun?'768P':kling?'1080p':'',generateAudio:false};
        const value={...baseline,model:provider[`${kind}_models`][0],...draft[kind][provider.id]};
        if(!provider[`${kind}_models`].includes(value.model)) value.model=provider[`${kind}_models`][0];
        let fields=select('生成模型','model',provider[`${kind}_models`],value.model);
        if(kind==='image'){
            fields+=select('画幅比例','ratio',[['wide','16:9 横屏'],['story','9:16 竖屏'],['square','1:1 方形'],['landscape43','4:3'],['portrait43','3:4'],['portrait45','4:5'],['landscape','3:2'],['portrait','2:3'],['ultrawide','21:9'],['source','跟随参考图']],value.ratio);
            fields+=select('分辨率','resolution',[['auto','自动'],'1k','2k','4k'],value.resolution);
            fields+=select('生成质量','quality',['auto','low','medium','high'],value.quality);
        } else {
            fields+=`<label>视频时长（秒）<input data-field="duration" type="number" min="${youyun?4:kling?3:1}" max="${youyun?30:h3||kling?15:60}" step="1" value="${escape(value.duration)}" required></label>`;
            fields+=select('画幅比例','aspectRatio',h3?['21:9','16:9','4:3','1:1','3:4','9:16']:youyun?['16:9','9:16','1:1','4:3','3:4','21:9','adaptive']:kling?['16:9','9:16','1:1','auto']:['16:9','9:16','1:1','4:3','3:4','21:9','9:21','keep_ratio','adaptive'],value.aspectRatio);
            const resolutions=h3?['0.2MP 21:9 - 672x288','0.3MP 21:9 - 896x384','0.5MP 21:9 - 1120x480','0.2MP 16:9 - 608x352','0.3MP 16:9 - 736x416','0.4MP 16:9 - 864x480','0.5MP 16:9 - 960x544','0.6MP 16:9 - 1056x608','0.2MP 4:3 - 512x384','0.3MP 4:3 - 640x480','0.4MP 4:3 - 768x576','Square 512x512','0.2MP 3:4 - 384x512','0.3MP 3:4 - 480x640','0.4MP 3:4 - 576x768','0.2MP 9:16 - 352x608','0.3MP 9:16 - 416x736','0.4MP 9:16 - 480x864']:youyun?['768P','1080P','2K']:[['','平台默认'],'720p','1080p'];
            fields+=select('分辨率','resolution',kling?['720p','1080p','4K']:!h3&&!youyun?[['','平台默认'],'480p','720p','1080p','780P']:resolutions,value.resolution);
            if(h3) fields+=`<label>采样步数<input data-field="steps" type="number" step="1" value="${escape(value.steps ?? 12)}" required></label>`;
            const toggles=h3||youyun?[['multimodal','全能参考'],['useFrameRoles','首尾帧模式'],...(youyun?[['muteAudio','移除音轨'],['watermark','添加水印']]:[])]:[['generateAudio','生成音频'],...(!kling?[['enhancePrompt','增强提示词'],['enableUpsample','高清增强'],['cameraFixed','固定镜头'],['watermark','添加水印'],['useFrameRoles','首尾帧模式']]:[])];
            for(const [key,label] of toggles) fields+=`<label class="preferences-check"><input type="checkbox" data-field="${key}" ${value[key]?'checked':''}>${label}</label>`;
        }
        root.innerHTML=`<div class="preferences-grid"><label>编辑平台<select data-provider>${options(choices.map(p=>[p.id,p.name||p.id]),provider.id)}</select></label><label>新建节点默认平台<select data-default>${options(choices.map(p=>[p.id,p.name||p.id]),draft[defaultKey]||choices[0].id)}</select></label></div><div class="preferences-grid">${fields}</div><p class="app-settings-note">切换平台可分别设置；保存后，新建节点自动使用对应平台参数。</p>`;
        const collect=()=>{
            const next={};
            root.querySelectorAll('[data-field]').forEach(input=>next[input.dataset.field]=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value);
            draft[kind][provider.id]=next;
            draft[defaultKey]=root.querySelector('[data-default]').value;
        };
        root.querySelector('[data-provider]').onchange=event=>{collect();selected[kind]=event.target.value;render(kind);};
        root.onchange=event=>{
            if(event.target.matches('[data-provider]'))return;
            if((h3||youyun) && event.target.checked && ['multimodal','useFrameRoles'].includes(event.target.dataset.field)) root.querySelector(`[data-field="${event.target.dataset.field==='multimodal'?'useFrameRoles':'multimodal'}"]`).checked=false;
            if(h3 && event.target.dataset.field==='resolution') root.querySelector('[data-field="aspectRatio"]').value=event.target.value.match(/\d+:\d+/)?.[0]||'1:1';
            if(h3 && event.target.dataset.field==='aspectRatio'){
                const ratio=event.target.value;
                const res=root.querySelector('[data-field="resolution"]');
                res.value=Array.from(res.options).find(o=>ratio==='1:1'?o.value.startsWith('Square'):o.value.includes(` ${ratio} `))?.value||res.value;
            }
            collect();status('有未保存的更改');
        };
    }
    try{
        const response=await fetch('/api/runtime/config');
        if(!response.ok)throw new Error('无法加载平台目录，请刷新重试');
        providers=(await response.json()).api_providers||[];
        draft=structuredClone(await api.read());
        render('image');render('video');
        const quickResponse=await api.requestSaveSettings();
        if(!quickResponse.ok)throw new Error('无法读取保存设置');
        const quick=await quickResponse.json();
        $('saveMode').value=quick.mode||'manual';$('saveDirectory').value=quick.directory||'';
        $('preferencesFields').disabled=false;$('preferencesForm').setAttribute('aria-busy','false');status('偏好已加载');
        if(api.legacyBackend) document.querySelector('.preferences-notice').textContent='生成偏好按当前账号保存在本机，应用于整个工作区。保存目录沿用本机软件设置。';
        if(!window.ShiyinQuickSave?.isDesktop()) $('saveHint').textContent='目录设置供桌面客户端使用；浏览器下载位置由浏览器管理。';
    }catch(error){status(error.message,true);return;}
    $('chooseDirectory').onclick=async()=>{
        const button=$('chooseDirectory');button.disabled=true;
        try{
            const response=await api.requestSaveSettings('select-directory',{method:'POST'});
            const data=await response.json();if(!response.ok)throw new Error(data.detail||'目录选择失败');
            if(data.selected && data.path){$('saveDirectory').value=data.path;$('saveMode').value='silent';status('目录已选择，保存后生效');}
        }catch(error){status(error.message,true);}finally{button.disabled=false;}
    };
    $('preferencesForm').onsubmit=async event=>{
        event.preventDefault();const button=$('savePreferences');button.disabled=true;status('正在保存…');
        try{
            for(const kind of ['image','video']) $(`${kind}Settings`).querySelector('[data-default]')?.dispatchEvent(new Event('change',{bubbles:true}));
            draft.quickSave={mode:$('saveMode').value,directory:$('saveDirectory').value.trim()};
            await api.save(draft);status('已保存，新建节点将使用你的偏好');
            const channel=new BroadcastChannel('shiyin-quick-save-settings');channel.postMessage(draft.quickSave);channel.close();
        }catch(error){status(error.message,true);}finally{button.disabled=false;}
    };
})();
