// 页面业务状态的持久化层。只接受适配器显式提供的数据，不保存 HTML 或拦截 fetch。
(function(){
    'use strict';
    const DATABASE = 'shiyin-page-state-v1';
    const STORAGE_TIMEOUT_MS = 1500;
    const sessions = new Map();
    let account = '', epoch = 0, databasePromise, validationPromise;
    let resolveAccount;
    const accountReady = new Promise(resolve => { resolveAccount = resolve; });
    function configure(value){
        const id = String(value?.account_id || value?.id || value?.user_id || '');
        if(!id){ resolveAccount(''); return; }
        if(account && account !== id){ epoch++;sessions.clear(); }
        account = id;
        resolveAccount(id);
    }
    async function ready(){
        if(account) return account;
        try {
            if(window.parent !== window && window.parent.StudioPageState){
                configure({id:await window.parent.StudioPageState.ready()});
                return account;
            }
        } catch(error) {}
        if(!['/','/static/index.html'].includes(location.pathname) || window.parent!==window) void verifyAccount();
        return accountReady;
    }
    function verifyAccount(){
        if(validationPromise)return validationPromise;
        const controller=new AbortController();
        const timeout=setTimeout(()=>{controller.abort();resolveAccount('');},6000);
        validationPromise=fetch('/api/account/me',{cache:'no-store',signal:controller.signal}).then(response=>response.ok?response.json():null)
            .then(data=>configure(data?.account))
            .catch(()=>resolveAccount(''))
            .finally(()=>clearTimeout(timeout));
        return validationPromise;
    }
    function database(){
        if(databasePromise) return databasePromise;
        databasePromise = new Promise(resolve => {
            let settled=false;
            const finish=value=>{
                if(settled){value?.close();return;}
                settled=true;clearTimeout(timeout);resolve(value);
            };
            const timeout=setTimeout(()=>finish(null),STORAGE_TIMEOUT_MS);
            let request;
            try {
                if(!window.indexedDB){finish(null);return;}
                request = indexedDB.open(DATABASE, 1);
            }
            catch(error){ finish(null); return; }
            request.onupgradeneeded = () => request.result.createObjectStore('pages');
            request.onsuccess = () => {
                request.result.onversionchange = () => request.result.close();
                finish(request.result);
            };
            request.onerror = request.onblocked = () => finish(null);
        });
        return databasePromise;
    }
    async function transact(key, value, writing=false){
        if(!key) return null;
        const db = await database();
        if(!db) return null;
        return new Promise(resolve => {
            let transaction;
            const finish=value=>{clearTimeout(timeout);resolve(value);};
            const timeout=setTimeout(()=>{
                finish(null);
                try{transaction?.abort();}catch(error){}
            },STORAGE_TIMEOUT_MS);
            try {
                transaction = db.transaction('pages', writing ? 'readwrite' : 'readonly');
                const request = writing ? transaction.objectStore('pages').put(value, key) : transaction.objectStore('pages').get(key);
                transaction.oncomplete = () => finish(writing ? true : request.result || null);
                transaction.onerror = transaction.onabort = () => finish(null);
            } catch(error){ finish(null); }
        });
    }
    function session(name){
        if(sessions.has(name)) return sessions.get(name);
        let revision=0, capture=null, pending=null, latest=null, flushing=null, scheduled=0, hydrated=false, discarded=false;
        const ownerEpoch=epoch;
        const keyReady=ready().then(id=>id ? `${id}:${name}` : null);
        const initial=keyReady.then(key=>transact(key));
        function flush(){
            if(flushing) return flushing;
            flushing=(async()=>{
                const key=await keyReady;
                while(pending && !discarded && ownerEpoch===epoch){
                    const record=pending;pending=null;
                    await transact(key,record,true);
                }
            })().finally(()=>{
                flushing=null;
                if(pending && !discarded && ownerEpoch===epoch) return flush();
            });
            return flushing;
        }
        function save(value){
            if(discarded || ownerEpoch!==epoch) return;
            try { pending={schema:1,value:structuredClone(value),view:{x:window.scrollX || 0,y:window.scrollY || 0},savedAt:Date.now()};latest=pending; }
            catch(error){ return; }
            void flush();
        }
        function checkpoint(){
            if(!capture) return;
            if(scheduled){clearTimeout(scheduled);scheduled=0;}
            try { const value=capture();if(value!==undefined)save(value); } catch(error) { console.warn('page state capture failed', name, error); }
        }
        function schedule(){
            if(scheduled) return;
            // 模型与编辑序号同步更新，磁盘快照合并短时输入，避免大列表反复深拷贝。
            scheduled=setTimeout(()=>{scheduled=0;checkpoint();},80);
        }
        const api={
            mark(){revision++;},
            guard(){const ticket=revision;return ()=>!discarded && ownerEpoch===epoch && revision===ticket;},
            async restore(apply){
                const valid=api.guard();
                const record=await initial;
                if(!valid() || !record || record.schema!==1) return false;
                await apply(structuredClone(record.value));
                if(!valid())return false;
                if(record.view)window.scrollTo(record.view.x || 0,record.view.y || 0);
                hydrated=true;
                return true;
            },
            read:()=>initial.then(record=>!discarded && ownerEpoch===epoch && (latest || record)?.schema===1 ? structuredClone((latest || record).value) : null),
            async remove(){
                discarded=true;pending=null;latest=null;revision++;sessions.delete(name);
                const key=await keyReady,db=await database();
                if(!db || !key)return;
                await new Promise(resolve=>{
                    try {const tx=db.transaction('pages','readwrite');tx.objectStore('pages').delete(key);tx.oncomplete=tx.onerror=tx.onabort=resolve;}
                    catch(error){resolve();}
                });
            },
            save,checkpoint,flush,schedule,
            setCapture(callback){capture=callback;},
            get restored(){return hydrated;},
            watch(callback){
                capture=callback;
                ['input','change','click'].forEach(type=>document.addEventListener(type,()=>{api.mark();schedule();},true));
                let scrollTimer;
                document.addEventListener('scroll',()=>{clearTimeout(scrollTimer);scrollTimer=setTimeout(checkpoint,80);},true);
                window.addEventListener('pagehide',checkpoint);
                document.addEventListener('visibilitychange',()=>{if(document.hidden)checkpoint();});
                window.addEventListener('message',event=>{
                    if(event.origin!==location.origin) return;
                    if(event.data?.type==='studio-route-active' && !event.data.active) checkpoint();
                });
            }
        };
        sessions.set(name,api);
        return api;
    }
    function close(){ epoch++; account=''; sessions.clear(); }
    async function flushAll(){
        const writes=[];
        for(const page of sessions.values()){page.checkpoint();writes.push(page.flush());}
        document.querySelectorAll('iframe').forEach(frame=>{
            try {const child=frame.contentWindow?.StudioPageState;if(child)writes.push(child.flushAll());}catch(error){}
        });
        await Promise.allSettled(writes);
    }
    window.StudioPageState={configure,ready,session,close,flushAll,get accountId(){return account;}};
    // 主框架由原有鉴权流程 configure；独立页面自行验证账号后才能读缓存。
    if(window.parent===window && !['/','/static/index.html'].includes(location.pathname)){
        void verifyAccount();
    }
})();
