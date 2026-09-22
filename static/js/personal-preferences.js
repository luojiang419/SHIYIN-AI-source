(function(){
    'use strict';
    let values = {};
    let legacyBackend = false;
    function localKey(){
        const accountId = window.StudioPageState?.accountId;
        if(!accountId) throw new Error('账号尚未就绪，请重新打开个人偏好');
        return `studio_personal_preferences_v1:account:${accountId}`;
    }
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
        legacyBackend = response.status === 404;
        if(legacyBackend){
            apply(JSON.parse(localStorage.getItem(localKey()) || '{}'));
            return values;
        }
        if(!response.ok) throw new Error('无法读取个人偏好');
        let next = await response.json();
        if(!Object.keys(next).length){
            const local = JSON.parse(localStorage.getItem(localKey()) || '{}');
            const imported = Object.fromEntries(['image','video','defaultImageProvider','defaultVideoProvider'].filter(key=>Object.hasOwn(local,key)).map(key=>[key,local[key]]));
            if(Object.keys(imported).length){
                const migration = await fetch('/api/personal-preferences', {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(imported)});
                if(!migration.ok) throw new Error('本机偏好迁移失败，请重试');
                next = await migration.json();
            }
        }
        apply(next);
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
        get legacyBackend(){ return legacyBackend; },
        async requestSaveSettings(action='', options={}){
            const modern = action === 'select-directory' ? '/api/personal-preferences/select-directory' : '/api/personal-preferences/quick-save';
            const legacy = action === 'select-directory' ? '/api/app-settings/select-quick-save-directory' : '/api/app-settings/quick-save';
            let response = await fetch(legacyBackend ? legacy : modern, options);
            if(response.status === 404 && !legacyBackend) response = await fetch(legacy, options);
            return response;
        },
        get values(){ return values; },
        async save(next){
            if(legacyBackend){
                const key = localKey();
                if(next.quickSave){
                    const current = await this.requestSaveSettings();
                    if(!current.ok) throw new Error('无法读取保存设置');
                    const previous = await current.json();
                    if(previous.mode !== next.quickSave.mode || previous.directory !== next.quickSave.directory){
                        const response = await fetch('/api/app-settings', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({quick_save_mode:next.quickSave.mode,quick_save_dir:next.quickSave.directory})});
                        const data = await response.json();
                        if(!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '保存目录设置失败');
                    }
                }
                localStorage.setItem(key,JSON.stringify(next));
                apply(structuredClone(next));
                channel?.postMessage('changed');
                return values;
            }
            const response = await fetch('/api/personal-preferences', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(next)});
            const data = await response.json();
            if(!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '保存失败，请重试');
            apply(data);
            channel?.postMessage('changed');
            return values;
        }
    };
})();
