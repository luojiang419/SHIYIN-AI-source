(function(){
    'use strict';
    let values = {};
    const fields = ['model','ratio','resolution','quality','count','duration','aspectRatio','generateAudio','enhancePrompt','enableUpsample','watermark','cameraFixed','multimodal','useFrameRoles','steps','muteAudio'];
    const channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel('studio-personal-preferences') : null;
    function apply(next){
        values = next || {};
        window.dispatchEvent(new CustomEvent('personal-preferences-changed', {detail:values}));
        window.ShiyinQuickSave?.refresh();
    }
    async function read(){
        await window.StudioPageState?.ready();
        const response = await fetch('/api/personal-preferences', {cache:'no-store', signal:AbortSignal.timeout(8000)});
        if(!response.ok) throw new Error('无法读取个人偏好');
        apply(await response.json());
        return values;
    }
    const ready = read().catch(error => { console.warn(error); return values; });
    channel?.addEventListener('message', () => { void read().catch(console.warn); });
    function profile(kind, provider){
        const source = values[kind]?.[provider];
        if(!source || typeof source !== 'object') return {};
        return Object.fromEntries(fields.filter(key => Object.hasOwn(source,key)).map(key => [key, source[key]]));
    }
    window.PersonalPreferences = {
        ready, read, profile,
        get values(){ return values; },
        async save(next){
            const response = await fetch('/api/personal-preferences', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(next)});
            const data = await response.json();
            if(!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '保存失败，请重试');
            apply(data);
            channel?.postMessage('changed');
            return values;
        }
    };
})();
